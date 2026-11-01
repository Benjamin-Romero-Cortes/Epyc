"""
Operaciones del ciclo de una reserva: preparación, despacho, devolución, merma, cierre y cancelación.

Cada operación vuelve a consultar y bloquear el servicio, valida todo en el servidor
y se ejecuta en una sola transacción: si algo falla no queda ningún registro parcial.
"""
from datetime import date, datetime, time, timedelta

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from Inventario.disponibilidad import calcular_disponibilidad, periodo_servicio
from Inventario.models import (
    Articulo,
    Despacho,
    DetalleDespacho,
    DetalleDevolucion,
    Devolucion,
    Merma,
    DetallePreparacion,
    DetalleServicio,
    HistorialServicio,
    MovimientoInventario,
    Preparacion,
    Servicio,
)


class OperacionInvalida(Exception):
    """Regla de negocio no cumplida. `detalles` lista los problemas puntuales (p. ej. por artículo)."""

    def __init__(self, mensaje, detalles=None, por_fila=None):
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.detalles = detalles or []
        # Errores asociados a una fila concreta del formulario (clave: id de artículo o detalle).
        self.por_fila = por_fila or {}


def registrar_historial(servicio, accion, usuario=None, estado_anterior="", observacion=""):
    return HistorialServicio.objects.create(
        servicio=servicio,
        usuario=usuario,
        accion=accion,
        estado_anterior=estado_anterior,
        estado_nuevo=servicio.estado,
        observacion=observacion,
        fecha=timezone.now(),
    )


def _cambiar_estado_servicio(servicio, nuevo_estado):
    anterior = servicio.estado
    servicio.estado = nuevo_estado
    servicio.save(update_fields=["estado", "fecha_actualizacion"])
    return anterior


def _bloquear_preparacion(preparacion_id):
    preparacion = (
        Preparacion.objects
        .select_for_update()
        .select_related("servicio")
        .get(id=preparacion_id)
    )
    servicio = Servicio.objects.select_for_update().get(id=preparacion.servicio_id)
    preparacion.servicio = servicio
    return preparacion, servicio


def _validar_editable(preparacion, servicio):
    if preparacion.estado == Preparacion.Estado.COMPLETA:
        raise OperacionInvalida("La preparación ya está completa y no se puede modificar.")
    if servicio.estado != Servicio.Estado.PREPARACION:
        raise OperacionInvalida(
            f"La reserva está en estado {servicio.get_estado_display()} y no admite cambios en la preparación."
        )


def resumen_unidades(detalles):
    requeridas = sum(d.cantidad_solicitada for d in detalles)
    preparadas = sum(d.cantidad_preparada for d in detalles)
    porcentaje = round(preparadas * 100 / requeridas) if requeridas else 0
    return {"requeridas": requeridas, "preparadas": preparadas, "porcentaje": porcentaje}


def generar_preparacion(servicio_id, usuario):
    with transaction.atomic():
        servicio = Servicio.objects.select_for_update().get(id=servicio_id)

        if servicio.estado != Servicio.Estado.CONFIRMADO:
            raise OperacionInvalida(
                "Solo una reserva confirmada puede generar una preparación "
                f"(estado actual: {servicio.get_estado_display()})."
            )
        if Preparacion.objects.filter(servicio=servicio).exists():
            raise OperacionInvalida("Esta reserva ya tiene una preparación.")

        _, fin = periodo_servicio(servicio)
        if fin is None:
            raise OperacionInvalida("La reserva no tiene fecha de evento.")
        if fin < timezone.localdate():
            raise OperacionInvalida("La fecha del evento ya pasó; revisa la reserva antes de prepararla.")

        cantidades = list(
            DetalleServicio.objects
            .filter(servicio=servicio)
            .values("articulo_id")
            .annotate(total=Sum("cantidad"))
            .order_by("articulo_id")
        )
        if not cantidades:
            raise OperacionInvalida("La reserva no tiene artículos asignados.")

        preparacion = Preparacion.objects.create(
            servicio=servicio,
            usuario=usuario,
            estado=Preparacion.Estado.PENDIENTE,
            fecha_creacion=timezone.now(),
        )
        DetallePreparacion.objects.bulk_create([
            DetallePreparacion(
                preparacion=preparacion,
                articulo_id=fila["articulo_id"],
                cantidad_solicitada=fila["total"],
            )
            for fila in cantidades
        ])

        anterior = _cambiar_estado_servicio(servicio, Servicio.Estado.PREPARACION)
        total = sum(fila["total"] for fila in cantidades)
        registrar_historial(
            servicio, "Generar preparación", usuario, anterior,
            f"{len(cantidades)} artículos, {total} unidades por preparar.",
        )
        return preparacion


def _leer_cantidad(texto):
    """Entero >= 0 escrito como dígitos; cualquier otra cosa (negativos, decimales, texto) es None."""
    texto = (texto or "").strip()
    return int(texto) if texto.isdigit() else None


def guardar_avance(preparacion_id, usuario, filas, observaciones=None):
    """
    `filas` es una lista de (detalle_id, cantidad_texto, observacion).
    Valida todas las filas antes de guardar: si una falla, no se guarda ninguna.
    """
    with transaction.atomic():
        preparacion, servicio = _bloquear_preparacion(preparacion_id)
        _validar_editable(preparacion, servicio)

        detalles = {
            d.id: d
            for d in DetallePreparacion.objects.select_for_update().filter(preparacion=preparacion).select_related("articulo")
        }
        errores = []
        vistos = set()
        cambios = []

        for detalle_id, cantidad_texto, observacion in filas:
            detalle = detalles.get(_leer_cantidad(str(detalle_id)))
            if detalle is None:
                errores.append("Se envió un artículo que no pertenece a esta preparación.")
                continue
            if detalle.id in vistos:
                errores.append(f"{detalle.articulo.nombre}: viene repetido en el formulario.")
                continue
            vistos.add(detalle.id)

            cantidad = _leer_cantidad(cantidad_texto)
            if cantidad is None:
                errores.append(f"{detalle.articulo.nombre}: la cantidad preparada debe ser un número entero igual o mayor que 0.")
            elif cantidad > detalle.cantidad_solicitada:
                errores.append(
                    f"{detalle.articulo.nombre}: preparado {cantidad} supera lo reservado ({detalle.cantidad_solicitada})."
                )
            else:
                cambios.append((detalle, cantidad, None if observacion is None else observacion.strip()[:255]))

        if errores:
            raise OperacionInvalida("No se guardó el avance. Revisa las cantidades marcadas.", errores)

        for detalle, cantidad, observacion in cambios:
            detalle.cantidad_preparada = cantidad
            if observacion is not None:
                detalle.observaciones = observacion
            detalle.save(update_fields=["cantidad_preparada", "observaciones"])

        if observaciones is not None:
            preparacion.observaciones = observaciones.strip()
        if preparacion.estado == Preparacion.Estado.PENDIENTE:
            preparacion.estado = Preparacion.Estado.EN_PREPARACION
            preparacion.fecha_inicio = timezone.now()
        if preparacion.usuario_id is None:
            preparacion.usuario = usuario
        preparacion.save()

        resumen = resumen_unidades(detalles.values())
        registrar_historial(
            servicio, "Guardar avance de preparación", usuario, servicio.estado,
            f"{resumen['preparadas']} de {resumen['requeridas']} unidades preparadas ({resumen['porcentaje']} %).",
        )
        return preparacion


def finalizar_preparacion(preparacion_id, usuario):
    with transaction.atomic():
        preparacion, servicio = _bloquear_preparacion(preparacion_id)
        _validar_editable(preparacion, servicio)

        detalles = list(
            DetallePreparacion.objects.filter(preparacion=preparacion).select_related("articulo")
        )
        if not detalles:
            raise OperacionInvalida("La preparación no tiene artículos.")

        incompletos = [
            f"{d.articulo.nombre}: preparado {d.cantidad_preparada} de {d.cantidad_solicitada} (faltan {d.cantidad_faltante})."
            for d in detalles
            if d.cantidad_preparada != d.cantidad_solicitada
        ]
        if incompletos:
            raise OperacionInvalida("No se puede finalizar: hay artículos incompletos.", incompletos)

        ahora = timezone.now()
        preparacion.estado = Preparacion.Estado.COMPLETA
        preparacion.fecha_inicio = preparacion.fecha_inicio or ahora
        preparacion.fecha_finalizacion = ahora
        preparacion.finalizada_por = usuario
        preparacion.save()

        anterior = _cambiar_estado_servicio(servicio, Servicio.Estado.PREPARADO)
        registrar_historial(
            servicio, "Finalizar preparación", usuario, anterior,
            f"{resumen_unidades(detalles)['requeridas']} unidades preparadas y revisadas.",
        )
        return preparacion


def resumen_despacho(preparacion):
    detalles = list(preparacion.detalles.all())
    return {"articulos": len(detalles), "unidades": sum(d.cantidad_preparada for d in detalles)}


def registrar_despacho(servicio_id, usuario, tipo_entrega, fecha_salida, responsable, receptor="", observaciones="",
                       cantidades=None, fecha_devolucion=None):
    """
    Registra la salida física de una reserva preparada (un despacho por reserva).
    `cantidades`: {articulo_id: texto} con lo realmente enviado; por defecto, todo lo preparado.
    Si sale menos (p. ej. un vaso se quebró), se despacha y se espera de vuelta solo lo enviado.
    `fecha_devolucion`: día en que todo debe volver; pasa a ser el término de la reserva.
    No modifica el stock: las unidades ya quedaron comprometidas al confirmar la reserva
    y siguen retenidas hasta la devolución; aquí solo pasan a estar fuera de bodega.
    """
    with transaction.atomic():
        servicio = Servicio.objects.select_for_update().get(id=servicio_id)

        if servicio.estado != Servicio.Estado.PREPARADO:
            raise OperacionInvalida(
                "Solo una reserva con la preparación finalizada puede despacharse "
                f"(estado actual: {servicio.get_estado_display()})."
            )
        preparacion = Preparacion.objects.filter(servicio=servicio).first()
        if preparacion is None or preparacion.estado != Preparacion.Estado.COMPLETA:
            raise OperacionInvalida("La preparación de esta reserva no está completa.")
        if Despacho.objects.filter(servicio=servicio).exclude(estado=Despacho.Estado.CANCELADO).exists():
            raise OperacionInvalida("Esta reserva ya tiene un despacho registrado.")

        errores = []
        if tipo_entrega not in Despacho.TipoEntrega.values:
            errores.append("Indica si es despacho a domicilio o retiro en bodega.")
        if fecha_salida is None:
            errores.append("Indica la fecha y hora de salida.")
        elif fecha_salida > timezone.now() + timedelta(minutes=5):
            errores.append("La fecha de salida no puede estar en el futuro: registra el despacho cuando los artículos salgan.")
        responsable = (responsable or "").strip()
        if not responsable:
            errores.append("Indica quién entrega o entregó los artículos.")
        detalles_prep = list(preparacion.detalles.select_related("articulo").order_by("articulo__nombre"))
        enviados, por_fila = {}, {}
        for d in detalles_prep:
            texto = d.cantidad_preparada if cantidades is None else cantidades.get(d.articulo_id, d.cantidad_preparada)
            cantidad = _leer_cantidad(str(texto))
            if cantidad is None:
                por_fila[d.articulo_id] = "Usa un número entero igual o mayor que 0."
            elif cantidad > d.cantidad_preparada:
                por_fila[d.articulo_id] = f"No puedes enviar más de lo preparado ({d.cantidad_preparada})."
            else:
                enviados[d.articulo_id] = cantidad
        errores += [f"{d.articulo.nombre}: {por_fila[d.articulo_id]}" for d in detalles_prep if d.articulo_id in por_fila]
        if not por_fila and not any(enviados.values()):
            errores.append("Debe salir al menos una unidad para registrar el despacho.")
        inicio_periodo, fin_actual = periodo_servicio(servicio)
        if fecha_devolucion is not None:
            if fecha_salida and fecha_devolucion < timezone.localtime(fecha_salida).date():
                errores.append("La fecha de devolución no puede ser anterior a la salida.")
            elif inicio_periodo and fecha_devolucion < inicio_periodo:
                errores.append("La fecha de devolución no puede ser anterior al inicio del evento.")
            elif fin_actual and fecha_devolucion > fin_actual:
                # Días extra fuera de bodega: las unidades deben estar libres también en ese tramo.
                faltan = []
                for d in detalles_prep:
                    if not enviados.get(d.articulo_id):
                        continue
                    articulo = Articulo.objects.select_for_update().get(id=d.articulo_id)
                    r = calcular_disponibilidad(articulo, fin_actual + timedelta(days=1), fecha_devolucion,
                                                excluir_servicio=servicio, solicitado=enviados[d.articulo_id])
                    if r["faltante"]:
                        faltan.append(f"{articulo.nombre}: solo hay {r['disponible']} libres hasta el {fecha_devolucion:%d/%m}")
                if faltan:
                    errores.append("Con esa fecha de devolución no alcanza el stock (otras reservas usan esas unidades). "
                                   + "; ".join(faltan) + ".")
        if errores:
            raise OperacionInvalida("No se registró el despacho. Revisa los datos marcados.", errores, por_fila)
        inicio = servicio.fecha_inicio or servicio.fecha_evento
        despacho = Despacho.objects.create(
            servicio=servicio,
            preparacion=preparacion,
            usuario=usuario,
            estado=Despacho.Estado.ENTREGADO,
            tipo_entrega=tipo_entrega,
            fecha_programada=(
                timezone.make_aware(datetime.combine(inicio, servicio.hora_inicio or time(0, 0)))
                if inicio else None
            ),
            fecha_despacho=fecha_salida,
            responsable_entrega=responsable[:150],
            receptor=(receptor or "").strip()[:150],
            observaciones=(observaciones or "").strip(),
            fecha_registro=timezone.now(),
        )
        salen = [(d, enviados[d.articulo_id]) for d in detalles_prep if enviados[d.articulo_id] > 0]
        DetalleDespacho.objects.bulk_create([
            DetalleDespacho(despacho=despacho, articulo=d.articulo, cantidad=cantidad)
            for d, cantidad in salen
        ])
        # Trazabilidad por artículo, sin tocar el stock (stock_anterior/nuevo vacíos).
        MovimientoInventario.objects.bulk_create([
            MovimientoInventario(
                articulo=d.articulo,
                usuario=usuario,
                servicio=servicio,
                tipo="Salida a cliente",
                cantidad=-cantidad,
                motivo=f"Despacho de la reserva {servicio.codigo} (no modifica el stock)",
                fecha=fecha_salida,
            )
            for d, cantidad in salen
        ])

        if fecha_devolucion is not None and fecha_devolucion != fin_actual:
            servicio.fecha_termino = fecha_devolucion
            if not servicio.fecha_inicio:
                servicio.fecha_inicio = inicio_periodo
            servicio.save(update_fields=["fecha_termino", "fecha_inicio", "fecha_actualizacion"])
        anterior = _cambiar_estado_servicio(servicio, Servicio.Estado.DESPACHADO)
        unidades = sum(cantidad for _, cantidad in salen)
        nota = f"{unidades} unidades de {len(salen)} artículos. Entrega: {responsable}."
        menos = [
            f"{d.articulo.nombre}: {enviados[d.articulo_id]} de {d.cantidad_preparada}"
            for d in detalles_prep if enviados[d.articulo_id] < d.cantidad_preparada
        ]
        if menos:
            nota += " Enviado con diferencias: " + "; ".join(menos) + "."
        if despacho.receptor:
            nota += f" Recibe: {despacho.receptor}."
        if servicio.fecha_termino:
            nota += f" Devolución: {servicio.fecha_termino:%d/%m/%Y}."
        registrar_historial(servicio, "Registrar despacho", usuario, anterior, nota)
        return despacho


# ---------------------------------------------------------------------------
# MOVIMIENTOS QUE NO CAMBIAN EL STOCK (trazabilidad de compromiso y salidas)
# ---------------------------------------------------------------------------

def registrar_movimientos_servicio(servicio, tipo, usuario, signo, motivo):
    """Un movimiento por artículo de la reserva, sin cifras de stock (no lo modifica)."""
    filas = (
        DetalleServicio.objects
        .filter(servicio=servicio)
        .values("articulo_id")
        .annotate(total=Sum("cantidad"))
    )
    MovimientoInventario.objects.bulk_create([
        MovimientoInventario(
            articulo_id=fila["articulo_id"],
            usuario=usuario,
            servicio=servicio,
            tipo=tipo,
            cantidad=signo * fila["total"],
            motivo=motivo,
            fecha=timezone.now(),
        )
        for fila in filas
    ])


# ---------------------------------------------------------------------------
# MERMA
# ---------------------------------------------------------------------------

def _aplicar_baja(articulo, tipo, cantidad):
    """Descuenta del stock según el tipo de merma. Devuelve (total_anterior, total_nuevo)."""
    anterior_total, anterior_trabajable = articulo.stock_total, articulo.stock_trabajable
    if tipo == Merma.Tipo.DANADO:
        articulo.stock_trabajable = max(0, articulo.stock_trabajable - cantidad)
    else:
        articulo.stock_total = max(0, articulo.stock_total - cantidad)
        articulo.stock_trabajable = max(0, min(articulo.stock_trabajable - cantidad, articulo.stock_total))
    articulo.save(update_fields=["stock_total", "stock_trabajable"])
    return anterior_total, anterior_trabajable


def _crear_merma(articulo, tipo, cantidad, usuario, motivo="", observaciones="", servicio=None,
                 detalle_devolucion=None, valor_reposicion=None, fecha=None):
    """Registra la merma, descuenta el stock una sola vez y deja el movimiento correspondiente."""
    fecha = fecha or timezone.now()
    if valor_reposicion is None:
        valor_reposicion = cantidad * articulo.valor_unitario_merma
    anterior_total, anterior_trabajable = _aplicar_baja(articulo, tipo, cantidad)
    merma = Merma.objects.create(
        articulo=articulo,
        tipo=tipo,
        cantidad=cantidad,
        usuario=usuario,
        motivo=motivo[:255],
        observaciones=observaciones,
        servicio=servicio,
        detalle_devolucion=detalle_devolucion,
        valor_reposicion=valor_reposicion,
        fecha=fecha,
    )
    afecta = "trabajable" if tipo == Merma.Tipo.DANADO else "total y trabajable"
    MovimientoInventario.objects.create(
        articulo=articulo,
        usuario=usuario,
        servicio=servicio,
        tipo="Merma",
        cantidad=-cantidad,
        stock_anterior=anterior_total,
        stock_nuevo=articulo.stock_total,
        motivo=f"{tipo}: {motivo}".strip(": ")[:255],
        observaciones=(
            f"Baja de stock {afecta}. Trabajable: {anterior_trabajable} → {articulo.stock_trabajable}."
        ),
        fecha=fecha,
    )
    return merma


def _leer_entero(texto, campo, errores):
    valor = _leer_cantidad(str(texto if texto is not None else ""))
    if valor is None:
        errores.append(f"{campo}: debe ser un número entero igual o mayor que 0.")
    return valor


def registrar_merma_manual(articulo_id, usuario, tipo, cantidad_texto, motivo, observaciones="", valor_reposicion_texto=""):
    """Merma fuera de una devolución (bodega, ajuste de inventario). Sin valor: cantidad × costo de reposición."""
    with transaction.atomic():
        articulo = Articulo.objects.select_for_update().get(id=articulo_id)
        errores = []
        if tipo not in Merma.Tipo.values:
            errores.append("Selecciona un tipo de merma válido.")
        cantidad = _leer_entero(cantidad_texto, "Cantidad", errores)
        if cantidad == 0:
            errores.append("Cantidad: debe ser mayor que 0.")
        valor_texto = (valor_reposicion_texto or "").strip()
        valor = _leer_entero(valor_texto, "Valor de reposición", errores) if valor_texto else None
        motivo = (motivo or "").strip()
        if not motivo:
            errores.append("Indica el motivo de la merma.")
        if cantidad and not errores:
            limite = articulo.stock_trabajable if tipo == Merma.Tipo.DANADO else articulo.stock_total
            if cantidad > limite:
                errores.append(
                    f"Cantidad: supera el stock {'trabajable' if tipo == Merma.Tipo.DANADO else 'total'} "
                    f"de {articulo.nombre} ({limite})."
                )
        if errores:
            raise OperacionInvalida("No se registró la merma.", errores)
        return _crear_merma(articulo, tipo, cantidad, usuario, motivo, (observaciones or "").strip(),
                            valor_reposicion=valor)


def reparar_merma(merma_id, usuario, cantidad_texto):
    """Unidades dañadas que se repararon vuelven al stock trabajable."""
    with transaction.atomic():
        merma = Merma.objects.select_for_update().get(id=merma_id)
        articulo = Articulo.objects.select_for_update().get(id=merma.articulo_id)
        errores = []
        if merma.anulada:
            raise OperacionInvalida("La merma está anulada.")
        if merma.tipo != Merma.Tipo.DANADO:
            raise OperacionInvalida("Solo las mermas por daño recuperable se pueden reparar.")
        cantidad = _leer_entero(cantidad_texto, "Cantidad reparada", errores)
        if cantidad == 0:
            errores.append("Cantidad reparada: debe ser mayor que 0.")
        elif cantidad and cantidad > merma.pendiente_reparar:
            errores.append(f"Cantidad reparada: solo quedan {merma.pendiente_reparar} unidades por reparar.")
        elif cantidad and articulo.stock_trabajable + cantidad > articulo.stock_total:
            errores.append("El stock trabajable no puede superar el stock total.")
        if errores:
            raise OperacionInvalida("No se registró la reparación.", errores)

        anterior = articulo.stock_trabajable
        articulo.stock_trabajable += cantidad
        articulo.save(update_fields=["stock_trabajable"])
        merma.cantidad_reparada += cantidad
        merma.save(update_fields=["cantidad_reparada"])
        MovimientoInventario.objects.create(
            articulo=articulo, usuario=usuario, servicio=merma.servicio, tipo="Reparación", cantidad=cantidad,
            stock_anterior=articulo.stock_total, stock_nuevo=articulo.stock_total,
            motivo=f"Reparación de merma #{merma.id}",
            observaciones=f"Trabajable: {anterior} → {articulo.stock_trabajable}.", fecha=timezone.now(),
        )
        return merma


def anular_merma(merma_id, usuario, motivo):
    """Corrige una merma registrada por error devolviendo su efecto en el stock. La merma no se borra."""
    with transaction.atomic():
        merma = Merma.objects.select_for_update().get(id=merma_id)
        articulo = Articulo.objects.select_for_update().get(id=merma.articulo_id)
        motivo = (motivo or "").strip()
        if merma.anulada:
            raise OperacionInvalida("La merma ya estaba anulada.")
        if not motivo:
            raise OperacionInvalida("Indica por qué se anula la merma.")
        if merma.detalle_devolucion_id:
            raise OperacionInvalida(
                "Esta merma viene de una devolución registrada; corrígela con un ajuste de inventario para "
                "no descuadrar las cantidades devueltas."
            )

        anterior_total, anterior_trabajable = articulo.stock_total, articulo.stock_trabajable
        vigente = merma.cantidad - merma.cantidad_reparada
        if merma.afecta_stock_total:
            articulo.stock_total += merma.cantidad
            articulo.stock_trabajable += merma.cantidad
        else:
            articulo.stock_trabajable = min(articulo.stock_total, articulo.stock_trabajable + vigente)
        articulo.save(update_fields=["stock_total", "stock_trabajable"])

        merma.anulada = True
        merma.fecha_anulacion = timezone.now()
        merma.anulada_por = usuario
        merma.motivo_anulacion = motivo[:255]
        merma.save(update_fields=["anulada", "fecha_anulacion", "anulada_por", "motivo_anulacion"])
        MovimientoInventario.objects.create(
            articulo=articulo, usuario=usuario, servicio=merma.servicio, tipo="Anulación de merma",
            cantidad=merma.cantidad if merma.afecta_stock_total else vigente,
            stock_anterior=anterior_total, stock_nuevo=articulo.stock_total,
            motivo=f"Anula merma #{merma.id}: {motivo}"[:255],
            observaciones=f"Trabajable: {anterior_trabajable} → {articulo.stock_trabajable}.", fecha=timezone.now(),
        )
        return merma


# ---------------------------------------------------------------------------
# DEVOLUCIÓN
# ---------------------------------------------------------------------------

def estado_devolucion(servicio):
    """
    Por artículo despachado: cuánto salió, cuánto se resolvió en devoluciones anteriores y cuánto sigue pendiente.
    Cumple siempre: buenas + dañadas + perdidas + pendiente = despachado.
    """
    despacho = Despacho.objects.filter(servicio=servicio).exclude(estado=Despacho.Estado.CANCELADO).first()
    if despacho is None:
        return None, []
    despachados = {
        d.articulo_id: d
        for d in DetalleDespacho.objects.filter(despacho=despacho).select_related("articulo").order_by("articulo__nombre")
    }
    previos = {
        f["articulo_id"]: f
        for f in (
            DetalleDevolucion.objects
            .filter(devolucion__servicio=servicio)
            .values("articulo_id")
            .annotate(buenas=Sum("cantidad_buena"), danadas=Sum("cantidad_danada"), perdidas=Sum("cantidad_perdida"))
        )
    }
    filas = []
    for articulo_id, detalle in despachados.items():
        previo = previos.get(articulo_id, {})
        buenas = previo.get("buenas") or 0
        danadas = previo.get("danadas") or 0
        perdidas = previo.get("perdidas") or 0
        filas.append({
            "articulo": detalle.articulo,
            "articulo_id": articulo_id,
            "despachado": detalle.cantidad,
            "buenas": buenas,
            "danadas": danadas,
            "perdidas": perdidas,
            "resuelto": buenas + danadas + perdidas,
            "pendiente": detalle.cantidad - buenas - danadas - perdidas,
        })
    return despacho, filas


def registrar_devolucion(servicio_id, usuario, fecha, entregado_por, filas, observaciones=""):
    """
    `filas`: lista de (articulo_id, buenas, dañadas, perdidas, observacion), como texto del formulario.
    Libera las buenas, registra como merma las dañadas y perdidas y deja comprometido lo pendiente.
    """
    with transaction.atomic():
        servicio = Servicio.objects.select_for_update().get(id=servicio_id)
        if servicio.estado not in (Servicio.Estado.DESPACHADO, Servicio.Estado.DEVOLUCION_PARCIAL):
            raise OperacionInvalida(
                "Solo se registran devoluciones de reservas despachadas o con devolución parcial "
                f"(estado actual: {servicio.get_estado_display()})."
            )
        despacho, estado = estado_devolucion(servicio)
        if despacho is None or not estado:
            raise OperacionInvalida("La reserva no tiene un despacho con artículos entregados.")
        por_articulo = {fila["articulo_id"]: fila for fila in estado}

        errores, por_fila, vistos, cambios = [], {}, set(), []
        if fecha is None:
            errores.append("Indica la fecha y hora de recepción.")
        elif fecha > timezone.now() + timedelta(minutes=5):
            errores.append("La fecha de recepción no puede estar en el futuro.")
        elif fecha < despacho.fecha_despacho:
            errores.append("La fecha de recepción no puede ser anterior a la salida del despacho.")

        for articulo_texto, buenas_t, danadas_t, perdidas_t, observacion in filas:
            articulo_id = _leer_cantidad(str(articulo_texto))
            fila = por_articulo.get(articulo_id)
            if fila is None:
                errores.append("Se envió un artículo que no pertenece al despacho de esta reserva.")
                continue
            if articulo_id in vistos:
                errores.append(f"{fila['articulo'].nombre}: viene repetido en el formulario.")
                continue
            vistos.add(articulo_id)

            mensajes = []
            valores = [_leer_cantidad(str(v if v is not None else "")) for v in (buenas_t, danadas_t, perdidas_t)]
            if any(v is None for v in valores):
                mensajes.append("Las cantidades deben ser números enteros iguales o mayores que 0.")
            else:
                buenas, danadas, perdidas = valores
                if buenas + danadas + perdidas > fila["pendiente"]:
                    mensajes.append(
                        f"Entre buenas, dañadas y perdidas suman {buenas + danadas + perdidas}, "
                        f"pero solo quedan {fila['pendiente']} pendientes."
                    )
                elif buenas + danadas + perdidas:
                    cambios.append((fila, buenas, danadas, perdidas, (observacion or "").strip()[:255]))
            if mensajes:
                por_fila[articulo_id] = mensajes
                errores.extend(f"{fila['articulo'].nombre}: {m}" for m in mensajes)

        if not errores and not cambios:
            errores.append("Ingresa al menos una cantidad recibida, dañada o perdida.")
        if errores:
            raise OperacionInvalida("No se registró la devolución. Revisa las filas marcadas.", errores, por_fila)

        pendiente_total = sum(f["pendiente"] for f in estado) - sum(b + d + p for _, b, d, p, _ in cambios)
        devolucion = Devolucion.objects.create(
            servicio=servicio,
            despacho=despacho,
            usuario=usuario,
            fecha_devolucion=fecha,
            entregado_por=(entregado_por or "").strip()[:150],
            completa=pendiente_total == 0,
            observaciones=(observaciones or "").strip(),
            fecha_registro=timezone.now(),
        )

        articulos = {a.id: a for a in Articulo.objects.select_for_update().filter(id__in=[f["articulo_id"] for f, *_ in cambios]).order_by("id")}
        totales = {"buenas": 0, "merma": 0}
        for fila, buenas, danadas, perdidas, observacion in cambios:
            articulo = articulos[fila["articulo_id"]]
            detalle = DetalleDevolucion.objects.create(
                devolucion=devolucion,
                articulo=articulo,
                cantidad_devuelta=buenas + danadas,
                cantidad_buena=buenas,
                cantidad_danada=danadas,
                cantidad_perdida=perdidas,
                cantidad_pendiente=fila["pendiente"] - buenas - danadas - perdidas,
                observaciones=observacion,
            )
            if buenas:
                MovimientoInventario.objects.create(
                    articulo=articulo, usuario=usuario, servicio=servicio, tipo="Devolución", cantidad=buenas,
                    motivo=f"Devolución de la reserva {servicio.codigo}: unidades liberadas (no modifica el stock)",
                    fecha=fecha,
                )
            for tipo, cantidad in ((Merma.Tipo.DANADO, danadas), (Merma.Tipo.PERDIDO, perdidas)):
                if cantidad:
                    _crear_merma(
                        articulo, tipo, cantidad, usuario,
                        motivo=f"Devolución de la reserva {servicio.codigo}",
                        observaciones=observacion, servicio=servicio, detalle_devolucion=detalle,
                        fecha=fecha,
                    )
            totales["buenas"] += buenas
            totales["merma"] += danadas + perdidas

        nuevo = Servicio.Estado.FINALIZADO if pendiente_total == 0 else Servicio.Estado.DEVOLUCION_PARCIAL
        anterior = _cambiar_estado_servicio(servicio, nuevo)
        registrar_historial(
            servicio, "Registrar devolución", usuario, anterior,
            f"{totales['buenas']} unidades recibidas en buen estado, {totales['merma']} como merma, "
            f"{pendiente_total} pendientes." + (f" Entregó: {devolucion.entregado_por}." if devolucion.entregado_por else ""),
        )
        return devolucion


# ---------------------------------------------------------------------------
# CIERRE Y CANCELACIÓN
# ---------------------------------------------------------------------------

def cerrar_servicio(servicio_id, usuario):
    with transaction.atomic():
        servicio = Servicio.objects.select_for_update().get(id=servicio_id)
        if servicio.estado != Servicio.Estado.FINALIZADO:
            raise OperacionInvalida(
                f"Solo se cierra una reserva devuelta (estado actual: {servicio.get_estado_display()})."
            )
        _, estado = estado_devolucion(servicio)
        pendientes = [f"{f['articulo'].nombre}: {f['pendiente']} pendientes." for f in estado if f["pendiente"]]
        descuadres = [
            f"{f['articulo'].nombre}: las devoluciones no cuadran con lo despachado."
            for f in estado if f["resuelto"] + f["pendiente"] != f["despachado"] or f["pendiente"] < 0
        ]
        if pendientes or descuadres:
            raise OperacionInvalida("No se puede cerrar la reserva.", pendientes + descuadres)
        anterior = _cambiar_estado_servicio(servicio, Servicio.Estado.CERRADO)
        registrar_historial(servicio, "Cerrar reserva", usuario, anterior, "Todas las unidades quedaron resueltas.")
        return servicio


ESTADOS_CANCELABLES = (
    Servicio.Estado.COTIZACION,
    Servicio.Estado.CONTACTADO,
    Servicio.Estado.CONFIRMADO,
    Servicio.Estado.PREPARACION,
    Servicio.Estado.PREPARADO,
)


def cancelar_servicio(servicio_id, usuario, motivo, accion=None):
    """
    Antes del despacho: libera el stock comprometido (un servicio cancelado no bloquea) y cancela
    la preparación activa. Después del despacho no se cancela: primero se registra la devolución.
    """
    with transaction.atomic():
        servicio = Servicio.objects.select_for_update().get(id=servicio_id)
        motivo = (motivo or "").strip()
        if servicio.estado not in ESTADOS_CANCELABLES:
            raise OperacionInvalida(
                f"Una reserva en estado {servicio.get_estado_display()} no se puede cancelar"
                + (": primero registra la devolución de los artículos." if servicio.estado in (
                    Servicio.Estado.DESPACHADO, Servicio.Estado.DEVOLUCION_PARCIAL) else ".")
            )
        reteniendo = servicio.estado in (Servicio.Estado.CONFIRMADO, Servicio.Estado.PREPARACION, Servicio.Estado.PREPARADO)
        if reteniendo and not motivo:
            raise OperacionInvalida("Indica el motivo de la cancelación.")

        Preparacion.objects.filter(servicio=servicio).exclude(estado=Preparacion.Estado.CANCELADA).update(
            estado=Preparacion.Estado.CANCELADA
        )
        anterior = _cambiar_estado_servicio(servicio, Servicio.Estado.CANCELADO)
        if reteniendo:
            registrar_movimientos_servicio(
                servicio, "Cancelación", usuario, 1,
                f"Reserva {servicio.codigo} cancelada: unidades liberadas (no modifica el stock)",
            )
        registrar_historial(
            servicio, accion or ("Cancelar reserva" if reteniendo else "Cancelar cotización"), usuario, anterior,
            motivo or "Sin motivo indicado.",
        )
        return servicio
