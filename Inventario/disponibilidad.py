from django.db import transaction
from django.db.models import F, Q, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

from Inventario.models import Articulo, DetalleDevolucion, DetalleServicio, Servicio


# Solo estos estados retienen stock: una cotización o un servicio cancelado o devuelto no lo bloquea.
ESTADOS_QUE_BLOQUEAN = [
    Servicio.Estado.CONFIRMADO,
    Servicio.Estado.PREPARACION,
    Servicio.Estado.PREPARADO,
    Servicio.Estado.DESPACHADO,
    Servicio.Estado.DEVOLUCION_PARCIAL,
]


# Con artículos todavía en el cliente: sus unidades pendientes siguen bloqueadas aunque
# la fecha del evento ya haya pasado, hasta que se registre su devolución.
ESTADOS_EN_CLIENTE = [
    Servicio.Estado.DESPACHADO,
    Servicio.Estado.DEVOLUCION_PARCIAL,
]


def unidades_resueltas(detalles_servicio):
    """
    Por (servicio, artículo): unidades ya devueltas en buen estado, dañadas o perdidas.
    Esas dejan de estar comprometidas; las buenas vuelven a estar disponibles y el resto pasa a merma.
    """
    pares = list(detalles_servicio.values_list("servicio_id", "articulo_id").distinct())
    if not pares:
        return {}
    servicio_ids = {s for s, _ in pares}
    articulo_ids = {a for _, a in pares}
    filas = (
        DetalleDevolucion.objects
        .filter(devolucion__servicio_id__in=servicio_ids, articulo_id__in=articulo_ids)
        .values("devolucion__servicio_id", "articulo_id")
        .annotate(total=Sum(F("cantidad_buena") + F("cantidad_danada") + F("cantidad_perdida")))
    )
    return {(f["devolucion__servicio_id"], f["articulo_id"]): f["total"] or 0 for f in filas}


def comprometido_por_articulo(detalles_servicio):
    """Suma por artículo lo reservado menos lo ya resuelto en devoluciones."""
    reservados = {}
    for fila in detalles_servicio.values("servicio_id", "articulo_id").annotate(total=Sum("cantidad")):
        clave = (fila["servicio_id"], fila["articulo_id"])
        reservados[clave] = reservados.get(clave, 0) + (fila["total"] or 0)
    resueltas = unidades_resueltas(detalles_servicio)
    resultado = {}
    for (servicio_id, articulo_id), total in reservados.items():
        pendiente = max(0, total - resueltas.get((servicio_id, articulo_id), 0))
        resultado[articulo_id] = resultado.get(articulo_id, 0) + pendiente
    return resultado


def comprometido_vigente(articulo_ids, hoy=None):
    """Unidades retenidas hoy por artículo: reservas vigentes más lo que sigue en clientes."""
    hoy = hoy or timezone.localdate()
    detalles = (
        DetalleServicio.objects
        .filter(articulo_id__in=articulo_ids, servicio__estado__in=ESTADOS_QUE_BLOQUEAN)
        .annotate(fin=Coalesce("servicio__fecha_termino", "servicio__fecha_evento", "servicio__fecha_inicio"))
        .filter(Q(fin__gte=hoy) | Q(servicio__estado__in=ESTADOS_EN_CLIENTE))
    )
    return comprometido_por_articulo(detalles)


NIVELES_ALERTA = ("sin-stock", "agotado", "bajo")


def porcentaje(parte, total):
    return round(parte * 100 / total) if total else 0


def nivel_stock(disponible, trabajable):
    """Semáforo del stock libre: sin stock cargado, agotado, bajo (≤ 10 o ≤ 25 %) u ok."""
    if trabajable <= 0:
        return "sin-stock"
    if disponible <= 0:
        return "agotado"
    if disponible <= 10 or disponible * 4 <= trabajable:
        return "bajo"
    return "ok"


def estado_stock(articulos, hoy=None):
    """
    Única fuente de las cifras de stock (Resumen, Inventario, alertas y Reportes).
    Anota en cada artículo stock_comprometido, stock_disponible y nivel_stock, y devuelve
    los totales calculados solo con los productos activos (los inactivos no se arriendan).
    Disponible = trabajable − comprometido; los porcentajes son siempre sobre el trabajable.
    """
    articulos = list(articulos)
    comprometido = comprometido_vigente([a.id for a in articulos], hoy)
    for a in articulos:
        a.stock_comprometido = comprometido.get(a.id, 0)
        a.stock_disponible = max(0, a.stock_trabajable - a.stock_comprometido)
        a.nivel_stock = nivel_stock(a.stock_disponible, a.stock_trabajable)

    activos = [a for a in articulos if a.activo]
    alertas = sorted(
        (a for a in activos if a.nivel_stock in NIVELES_ALERTA),
        key=lambda a: (a.stock_disponible, a.nombre.lower()),
    )
    totales = {
        "productos": len(activos),
        "total": sum(a.stock_total for a in activos),
        "trabajable": sum(a.stock_trabajable for a in activos),
        "comprometido": sum(a.stock_comprometido for a in activos),
        "disponible": sum(a.stock_disponible for a in activos),
        "alertas": alertas,
        "alertas_count": len(alertas),
    }
    totales["porcentaje_disponible"] = porcentaje(totales["disponible"], totales["trabajable"])
    return articulos, totales


class StockInsuficiente(Exception):
    """Se lanza al confirmar cuando algún artículo no alcanza; trae el detalle de los faltantes."""

    def __init__(self, faltantes):
        super().__init__("Stock insuficiente")
        self.faltantes = faltantes


def periodo_servicio(servicio):
    """Rango de fechas que ocupa un servicio: inicio/término o, si faltan, la fecha del evento."""
    inicio = servicio.fecha_inicio or servicio.fecha_evento
    fin = servicio.fecha_termino or servicio.fecha_evento or inicio
    return inicio, fin


def cantidad_comprometida(articulo, fecha_inicio, fecha_fin, excluir_servicio=None):
    """Unidades del artículo retenidas por servicios activos cuyo periodo se cruza con el solicitado."""
    detalles = (
        DetalleServicio.objects
        .filter(articulo=articulo, servicio__estado__in=ESTADOS_QUE_BLOQUEAN)
        .annotate(
            ini=Coalesce("servicio__fecha_inicio", "servicio__fecha_evento"),
            fin=Coalesce("servicio__fecha_termino", "servicio__fecha_evento", "servicio__fecha_inicio"),
        )
        .filter(ini__lte=fecha_fin)
        .filter(Q(fin__gte=fecha_inicio) | Q(servicio__estado__in=ESTADOS_EN_CLIENTE))
    )
    if excluir_servicio is not None:
        detalles = detalles.exclude(servicio=excluir_servicio)
    return comprometido_por_articulo(detalles).get(articulo.id, 0)


def calcular_disponibilidad(articulo, fecha_inicio, fecha_fin, excluir_servicio=None, solicitado=0):
    comprometido = cantidad_comprometida(articulo, fecha_inicio, fecha_fin, excluir_servicio)
    disponible = max(0, articulo.stock_trabajable - comprometido)
    return {
        "articulo_id": articulo.id,
        "articulo": articulo,
        "stock_trabajable": articulo.stock_trabajable,
        "comprometido": comprometido,
        "disponible": disponible,
        "solicitado": solicitado,
        "faltante": max(0, solicitado - disponible),
    }


def disponibilidad_servicio(servicio):
    """Disponibilidad de cada artículo del servicio, sin contar al propio servicio."""
    inicio, fin = periodo_servicio(servicio)
    solicitados = (
        DetalleServicio.objects
        .filter(servicio=servicio)
        .values("articulo_id")
        .annotate(total=Sum("cantidad"))
    )
    cantidades = {fila["articulo_id"]: fila["total"] for fila in solicitados}
    articulos = Articulo.objects.filter(id__in=cantidades).order_by("nombre")

    if inicio is None:
        return [
            {"articulo": a, "articulo_id": a.id, "solicitado": cantidades[a.id],
             "disponible": None, "faltante": 0, "stock_trabajable": a.stock_trabajable, "comprometido": 0}
            for a in articulos
        ]
    return [
        calcular_disponibilidad(a, inicio, fin, excluir_servicio=servicio, solicitado=cantidades[a.id])
        for a in articulos
    ]


def confirmar_servicio(servicio_id, nuevo_estado=Servicio.Estado.CONFIRMADO):
    """
    Pasa un servicio a un estado que bloquea stock solo si hay disponibilidad.
    Bloquea las filas de los artículos para que dos confirmaciones simultáneas no sobrevendan.
    """
    with transaction.atomic():
        servicio = Servicio.objects.select_for_update().get(id=servicio_id)
        inicio, _ = periodo_servicio(servicio)
        if inicio is None:
            raise ValueError("El servicio no tiene fecha de evento.")

        articulo_ids = list(
            DetalleServicio.objects.filter(servicio=servicio).values_list("articulo_id", flat=True)
        )
        if not articulo_ids:
            raise ValueError("El servicio no tiene artículos.")

        # Mismo orden siempre (por id) para evitar bloqueos cruzados entre transacciones.
        list(Articulo.objects.select_for_update().filter(id__in=articulo_ids).order_by("id"))

        faltantes = [r for r in disponibilidad_servicio(servicio) if r["faltante"] > 0]
        if faltantes:
            raise StockInsuficiente(faltantes)

        servicio.estado = nuevo_estado
        if not servicio.fecha_confirmacion:
            servicio.fecha_confirmacion = timezone.now()
        servicio.save(update_fields=["estado", "fecha_confirmacion", "fecha_actualizacion"])
        return servicio
