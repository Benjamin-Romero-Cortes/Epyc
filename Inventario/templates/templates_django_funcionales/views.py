from datetime import date, datetime
import json
import re
from urllib.parse import quote
from uuid import uuid4

from django.contrib.auth.hashers import check_password, make_password
from django.db import transaction
from django.db.models import Sum, Avg, Count, F
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_POST

from Inventario.models import (
    Negocio,
    Categoria,
    Articulo,
    Cliente,
    Servicio,
    DetalleServicio,
    Preparacion,
    DetallePreparacion,
    Despacho,
    DetalleDespacho,
    Devolucion,
    DetalleDevolucion,
    Merma,
    MovimientoInventario,
    Rol,
    Usuario,
)


# ============================================================
# UTILIDADES
# ============================================================

def obtener_negocio():
    return Negocio.objects.filter(activo=True).order_by("id").first()


def _separar_nombre(nombre_completo):
    partes = nombre_completo.strip().split()

    if not partes:
        return "", ""

    if len(partes) == 1:
        return partes[0], ""

    return partes[0], " ".join(partes[1:])


def _entero(valor, default=0):
    try:
        return int(valor)
    except (TypeError, ValueError):
        return default


# ============================================================
# SITIO PÚBLICO
# ============================================================

def index(request):
    return render(request, "index.html")


def catalogo(request):
    productos = list(
        Articulo.objects
        .filter(activo=True)
        .select_related("categoria")
        .order_by("nombre")
    )

    categorias = list(
        Categoria.objects
        .filter(activo=True, articulos__activo=True)
        .distinct()
        .order_by("nombre")
    )

    return render(
        request,
        "catalogo.html",
        {
            "productos": productos,
            "categorias": categorias,
        },
    )


def cotizador(request):
    negocio = obtener_negocio()

    if negocio is None:
        return render(
            request,
            "cotizador.html",
            {
                "categorias": [],
                "error": "No existe un negocio activo configurado en el sistema.",
            },
        )

    categorias = list(
        Categoria.objects
        .filter(negocio=negocio, activo=True)
        .order_by("nombre")
    )

    articulo_preseleccionado = None
    articulo_id = request.GET.get("articulo") or request.POST.get("articulo_id")

    if articulo_id:
        articulo_preseleccionado = (
            Articulo.objects
            .filter(id=articulo_id, negocio=negocio, activo=True)
            .select_related("categoria")
            .first()
        )

    if request.method == "POST":
        tipo_evento = request.POST.get("tipoEvento", "").strip()
        fecha_evento = request.POST.get("fecha", "").strip()
        invitados = request.POST.get("invitados", "").strip()
        comuna = request.POST.get("comuna", "").strip()
        despacho = request.POST.get("despacho", "").strip()

        nombre_completo = request.POST.get("nombre", "").strip()
        rut = request.POST.get("rut", "").strip()
        empresa = request.POST.get("empresa", "").strip()
        telefono = request.POST.get("telefono", "").strip()
        correo = request.POST.get("correo", "").strip().lower()
        direccion = request.POST.get("direccion", "").strip()
        medio_contacto = request.POST.get("medioContacto", "").strip()
        comentarios = request.POST.get("comentarios", "").strip()
        categorias_seleccionadas = request.POST.getlist("categorias")

        if not all([
            tipo_evento,
            fecha_evento,
            invitados,
            comuna,
            despacho,
            nombre_completo,
            rut,
            telefono,
            correo,
            direccion,
            medio_contacto,
        ]):
            return render(
                request,
                "cotizador.html",
                {
                    "categorias": categorias,
                    "articulo_preseleccionado": articulo_preseleccionado,
                    "error": "Completa todos los campos obligatorios.",
                },
            )

        cantidad_personas = _entero(invitados)

        if cantidad_personas < 1:
            return render(
                request,
                "cotizador.html",
                {
                    "categorias": categorias,
                    "articulo_preseleccionado": articulo_preseleccionado,
                    "error": "La cantidad de invitados no es válida.",
                },
            )

        nombre, apellido = _separar_nombre(nombre_completo)

        observaciones_partes = [
            f"Despacho: {despacho}",
            f"Medio de contacto preferido: {medio_contacto}",
        ]

        if empresa:
            observaciones_partes.append(f"Empresa: {empresa}")

        if categorias_seleccionadas:
            observaciones_partes.append(
                "Categorías de interés: " + ", ".join(categorias_seleccionadas)
            )

        if articulo_preseleccionado:
            observaciones_partes.append(
                f"Artículo consultado: "
                f"{articulo_preseleccionado.codigo} - "
                f"{articulo_preseleccionado.nombre}"
            )

        if comentarios:
            observaciones_partes.append(f"Comentarios: {comentarios}")

        observaciones = "\n".join(observaciones_partes)

        with transaction.atomic():
            cliente = (
                Cliente.objects
                .filter(negocio=negocio, email__iexact=correo)
                .first()
            )

            if cliente:
                cliente.rut = rut
                cliente.nombre = nombre
                cliente.apellido = apellido
                cliente.telefono = telefono
                cliente.email = correo
                cliente.direccion = direccion
                cliente.comuna = comuna
                cliente.activo = True
                cliente.save()
            else:
                cliente = Cliente.objects.create(
                    negocio=negocio,
                    rut=rut,
                    nombre=nombre,
                    apellido=apellido,
                    telefono=telefono,
                    email=correo,
                    direccion=direccion,
                    comuna=comuna,
                    activo=True,
                )

            codigo = f"COT-{date.today():%Y%m%d}-{uuid4().hex[:6].upper()}"

            servicio = Servicio.objects.create(
                negocio=negocio,
                cliente=cliente,
                codigo=codigo,
                estado="Cotizacion",
                tipo_servicio=tipo_evento,
                fecha_solicitud=date.today(),
                fecha_evento=fecha_evento,
                fecha_inicio=fecha_evento,
                fecha_termino=fecha_evento,
                comuna_evento=comuna,
                cantidad_personas=cantidad_personas,
                observaciones=observaciones,
                subtotal=0,
                descuento=0,
                total=0,
                abono=0,
                garantia=0,
            )

        mensaje = (
            "Hola, envié una solicitud de cotización en la web. "
            f"Mi código es {servicio.codigo}."
        )

        whatsapp_url = (
            "https://wa.me/56942058820?text=" + quote(mensaje)
        )

        return render(
            request,
            "cotizador.html",
            {
                "categorias": categorias,
                "enviado": True,
                "codigo_servicio": servicio.codigo,
                "whatsapp_url": whatsapp_url,
            },
        )

    return render(
        request,
        "cotizador.html",
        {
            "categorias": categorias,
            "articulo_preseleccionado": articulo_preseleccionado,
        },
    )


def nosotros(request):
    return render(request, "nosotros.html")


def contacto(request):
    return render(request, "contacto.html")


def producto(request, id):
    producto = get_object_or_404(
        Articulo.objects.select_related("categoria", "negocio"),
        id=id,
        activo=True,
    )

    relacionados = list(
        Articulo.objects
        .filter(
            activo=True,
            categoria=producto.categoria,
        )
        .exclude(id=producto.id)
        .select_related("categoria")[:4]
    )

    return render(
        request,
        "producto.html",
        {
            "producto": producto,
            "relacionados": relacionados,
        },
    )


# ============================================================
# GESTIÓN - INICIO
# ============================================================

def gestionIndex(request):
    return render(request, "inicio.html")


# ============================================================
# INVENTARIO
# ============================================================

PREFIJOS_CATEGORIA = {
    "Vajilla": "VAJ",
    "Cristalería": "CRIS",
    "Cubiertos y servicio": "CUB",
    "Mesas y sillas": "MOB",
    "Mantelería": "MAN",
    "Carpas y exteriores": "CAR",
    "Equipamiento": "EQU",
    "Decoración": "DEC",
}


def generar_codigo_producto(categoria):
    prefijo = PREFIJOS_CATEGORIA.get(
        categoria.nombre,
        categoria.nombre[:3].upper(),
    )

    productos = (
        Articulo.objects
        .filter(codigo__startswith=f"{prefijo}-")
        .values_list("codigo", flat=True)
    )

    numeros = []

    for codigo in productos:
        coincidencia = re.search(r"-(\d+)$", codigo)

        if coincidencia:
            numeros.append(int(coincidencia.group(1)))

    siguiente = (max(numeros) if numeros else 0) + 1

    return f"{prefijo}-{siguiente:03d}"


def inventario(request):
    negocio = obtener_negocio()

    if request.method == "POST" and request.POST.get("accion") == "crear":
        categoria = get_object_or_404(
            Categoria,
            id=request.POST.get("categoria_id"),
            negocio=negocio,
        )

        codigo = request.POST.get("codigo", "").strip()
        if not codigo:
            codigo = generar_codigo_producto(categoria)

        stock_total = _entero(request.POST.get("stock_total"), 0)
        stock_trabajable = _entero(
            request.POST.get("stock_trabajable"),
            stock_total,
        )

        if stock_total < 0:
            stock_total = 0

        if stock_trabajable < 0:
            stock_trabajable = 0

        if stock_trabajable > stock_total:
            stock_trabajable = stock_total

        Articulo.objects.create(
            negocio=negocio,
            categoria=categoria,
            codigo=codigo,
            nombre=request.POST.get("nombre", "").strip(),
            categoria_label=(
                request.POST.get("categoria_label", "").strip()
                or categoria.nombre
            ),
            descripcion=request.POST.get("descripcion", "").strip(),
            descripcion_larga=request.POST.get(
                "descripcion_larga",
                "",
            ).strip(),
            dimensiones=request.POST.get("dimensiones", "").strip(),
            material=request.POST.get("material", "").strip(),
            capacidad=request.POST.get("capacidad", "").strip(),
            color=request.POST.get("color", "").strip(),
            precio_arriendo=_entero(
                request.POST.get("precio_arriendo"),
                0,
            ),
            unidad_precio=(
                request.POST.get("unidad_precio", "").strip()
                or "Por unidad"
            ),
            imagen=request.POST.get("imagen", "").strip(),
            imagenes=[],
            stock_total=stock_total,
            stock_trabajable=stock_trabajable,
            destacado=request.POST.get("destacado") == "on",
            activo=request.POST.get("activo") == "on",
        )

        return redirect("gestion_inventario")

    inventario_qs = list(
        Articulo.objects
        .filter(negocio=negocio)
        .select_related("categoria")
        .order_by("nombre")
    )

    # Se calcula el comprometido en Python para no depender de related_name
    # específicos en DetalleServicio.
    articulo_ids = [a.id for a in inventario_qs]
    comprometido_por_articulo = {
        articulo_id: 0 for articulo_id in articulo_ids
    }

    if articulo_ids:
        detalles = (
            DetalleServicio.objects
            .filter(
                articulo_id__in=articulo_ids,
                servicio__estado__in=[
                    "Confirmado",
                    "Preparacion",
                    "Despachado",
                    "Devolucion parcial",
                ],
            )
            .values("articulo_id")
            .annotate(total=Sum("cantidad"))
        )

        for fila in detalles:
            comprometido_por_articulo[fila["articulo_id"]] = fila["total"] or 0

    for articulo in inventario_qs:
        articulo.stock_comprometido = comprometido_por_articulo.get(
            articulo.id,
            0,
        )

    categorias = (
        Categoria.objects
        .filter(negocio=negocio, activo=True)
        .order_by("nombre")
    )

    return render(
        request,
        "inventario.html",
        {
            "inventario": inventario_qs,
            "categorias": categorias,
        },
    )


def gestion_producto(request, id):
    articulo = get_object_or_404(
        Articulo.objects.select_related("categoria", "negocio"),
        id=id,
    )

    movimientos = (
        MovimientoInventario.objects
        .filter(articulo=articulo)
        .select_related("usuario")
        .order_by("-fecha")
    )

    return render(
        request,
        "producto.html",
        {
            "articulo": articulo,
            "movimientos": movimientos,
        },
    )


@require_POST
@transaction.atomic
def guardar_producto(request):
    try:
        datos = json.loads(request.body.decode("utf-8"))

        codigo = datos.get("codigo")
        nombre = datos.get("nombre", "").strip()
        categoria_nombre = datos.get("categoria", "").strip()

        stock_total = int(datos.get("stock_total", 0))
        stock_trabajable = int(datos.get("stock_trabajable", 0))
        precio_arriendo = int(datos.get("precio_arriendo", 0))

        if not nombre:
            return JsonResponse(
                {
                    "ok": False,
                    "error": "El nombre es obligatorio.",
                },
                status=400,
            )

        if stock_total < 0:
            return JsonResponse(
                {
                    "ok": False,
                    "error": "El stock total no puede ser negativo.",
                },
                status=400,
            )

        if stock_trabajable < 0:
            return JsonResponse(
                {
                    "ok": False,
                    "error": "El stock trabajable no puede ser negativo.",
                },
                status=400,
            )

        if stock_trabajable > stock_total:
            return JsonResponse(
                {
                    "ok": False,
                    "error": (
                        "El stock trabajable no puede ser mayor "
                        "que el stock total."
                    ),
                },
                status=400,
            )

        if precio_arriendo < 0:
            return JsonResponse(
                {
                    "ok": False,
                    "error": (
                        "El precio de arriendo no puede ser negativo."
                    ),
                },
                status=400,
            )

        categoria = get_object_or_404(
            Categoria,
            nombre=categoria_nombre,
        )

        if codigo:
            producto_obj = get_object_or_404(
                Articulo,
                codigo=codigo,
            )

            producto_obj.nombre = nombre
            producto_obj.categoria = categoria
            producto_obj.categoria_label = categoria.nombre
            producto_obj.stock_total = stock_total
            producto_obj.stock_trabajable = stock_trabajable
            producto_obj.precio_arriendo = precio_arriendo
            producto_obj.save()

            return JsonResponse(
                {
                    "ok": True,
                    "modo": "editar",
                    "mensaje": "Producto actualizado correctamente.",
                    "codigo": producto_obj.codigo,
                }
            )

        codigo_nuevo = generar_codigo_producto(categoria)
        negocio = obtener_negocio()

        producto_obj = Articulo.objects.create(
            negocio=negocio,
            codigo=codigo_nuevo,
            nombre=nombre,
            categoria=categoria,
            categoria_label=categoria.nombre,
            stock_total=stock_total,
            stock_trabajable=stock_trabajable,
            precio_arriendo=precio_arriendo,
            descripcion="",
            descripcion_larga="",
            dimensiones="",
            material="",
            capacidad="",
            color="",
            unidad_precio="Por unidad",
            imagen="",
            imagenes=[],
            destacado=False,
            activo=True,
        )

        return JsonResponse(
            {
                "ok": True,
                "modo": "crear",
                "mensaje": "Producto creado correctamente.",
                "codigo": producto_obj.codigo,
            }
        )

    except json.JSONDecodeError:
        return JsonResponse(
            {
                "ok": False,
                "error": "Los datos enviados no son válidos.",
            },
            status=400,
        )

    except ValueError:
        return JsonResponse(
            {
                "ok": False,
                "error": "Stock y precio deben ser números válidos.",
            },
            status=400,
        )


# ============================================================
# CLIENTES
# ============================================================

def gestion_clientes(request):
    negocio = obtener_negocio()

    if request.method == "POST" and request.POST.get("accion") == "crear":
        Cliente.objects.create(
            negocio=negocio,
            rut=request.POST.get("rut", "").strip(),
            nombre=request.POST.get("nombre", "").strip(),
            apellido=request.POST.get("apellido", "").strip(),
            telefono=request.POST.get("telefono", "").strip(),
            email=request.POST.get("email", "").strip().lower(),
            direccion=request.POST.get("direccion", "").strip(),
            comuna=request.POST.get("comuna", "").strip(),
            observaciones=request.POST.get(
                "observaciones",
                "",
            ).strip(),
            activo=request.POST.get("activo") == "on",
        )

        return redirect("gestion_clientes")

    clientes = list(
        Cliente.objects
        .filter(negocio=negocio)
        .order_by("nombre", "apellido")
    )

    # Añadimos datos auxiliares sin depender de related_name.
    servicios = list(
        Servicio.objects
        .filter(negocio=negocio)
        .only("id", "cliente_id", "fecha_evento")
    )

    conteos = {}
    ultimas_fechas = {}

    for servicio in servicios:
        conteos[servicio.cliente_id] = (
            conteos.get(servicio.cliente_id, 0) + 1
        )

        if servicio.fecha_evento:
            actual = ultimas_fechas.get(servicio.cliente_id)
            if actual is None or servicio.fecha_evento > actual:
                ultimas_fechas[servicio.cliente_id] = servicio.fecha_evento

    for cliente in clientes:
        cliente.servicios_count = conteos.get(cliente.id, 0)
        cliente.ultima_reserva = ultimas_fechas.get(cliente.id)

    return render(
        request,
        "clientes.html",
        {
            "clientes": clientes,
        },
    )


def gestion_cliente(request, id):
    cliente = get_object_or_404(
        Cliente.objects.select_related("negocio"),
        id=id,
    )

    if request.method == "POST" and request.POST.get("accion") == "editar":
        cliente.nombre = request.POST.get("nombre", "").strip()
        cliente.apellido = request.POST.get("apellido", "").strip()
        cliente.rut = request.POST.get("rut", "").strip()
        cliente.telefono = request.POST.get("telefono", "").strip()
        cliente.email = request.POST.get("email", "").strip().lower()
        cliente.direccion = request.POST.get("direccion", "").strip()
        cliente.comuna = request.POST.get("comuna", "").strip()
        cliente.observaciones = request.POST.get(
            "observaciones",
            "",
        ).strip()
        cliente.activo = request.POST.get("activo") == "on"
        cliente.save()

        return redirect(
            "gestion_cliente",
            id=cliente.id,
        )

    servicios = (
        Servicio.objects
        .filter(cliente=cliente)
        .order_by("-fecha_creacion")
    )

    return render(
        request,
        "cliente.html",
        {
            "cliente": cliente,
            "servicios": servicios,
        },
    )


# ============================================================
# COTIZACIONES / SERVICIO
# ============================================================

def gestion_cotizaciones(request):
    negocio = obtener_negocio()

    if request.method == "POST" and request.POST.get("accion") == "crear":
        cliente = get_object_or_404(
            Cliente,
            id=request.POST.get("cliente_id"),
            negocio=negocio,
        )

        codigo = f"COT-{date.today():%Y%m%d}-{uuid4().hex[:6].upper()}"

        with transaction.atomic():
            servicio = Servicio.objects.create(
                negocio=negocio,
                cliente=cliente,
                codigo=codigo,
                estado="Cotizacion",
                tipo_servicio=request.POST.get(
                    "tipo_servicio",
                    "",
                ).strip(),
                fecha_solicitud=date.today(),
                fecha_evento=(
                    request.POST.get("fecha_evento") or None
                ),
                fecha_inicio=(
                    request.POST.get("fecha_inicio") or None
                ),
                fecha_termino=(
                    request.POST.get("fecha_termino") or None
                ),
                direccion_evento=request.POST.get(
                    "direccion_evento",
                    "",
                ).strip(),
                comuna_evento=request.POST.get(
                    "comuna_evento",
                    "",
                ).strip(),
                cantidad_personas=(
                    _entero(
                        request.POST.get("cantidad_personas"),
                        0,
                    )
                    or None
                ),
                subtotal=0,
                descuento=_entero(
                    request.POST.get("descuento"),
                    0,
                ),
                total=0,
                abono=_entero(
                    request.POST.get("abono"),
                    0,
                ),
                garantia=_entero(
                    request.POST.get("garantia"),
                    0,
                ),
                observaciones=request.POST.get(
                    "observaciones",
                    "",
                ).strip(),
            )

            articulo_id = request.POST.get("articulo_id")
            cantidad = _entero(
                request.POST.get("cantidad"),
                1,
            )

            if articulo_id:
                articulo = get_object_or_404(
                    Articulo,
                    id=articulo_id,
                )

                subtotal = articulo.precio_arriendo * cantidad

                DetalleServicio.objects.create(
                    servicio=servicio,
                    articulo=articulo,
                    cantidad=cantidad,
                    precio_unitario=articulo.precio_arriendo,
                    subtotal=subtotal,
                )

                servicio.subtotal = subtotal
                servicio.total = max(
                    0,
                    subtotal - servicio.descuento,
                )
                servicio.save()

        return redirect(
            "gestion_cotizacion",
            id=servicio.id,
        )

    cotizaciones = (
        Servicio.objects
        .filter(
            negocio=negocio,
            estado="Cotizacion",
        )
        .select_related("cliente")
        .order_by("-fecha_creacion")
    )

    clientes = (
        Cliente.objects
        .filter(
            negocio=negocio,
            activo=True,
        )
        .order_by("nombre", "apellido")
    )

    articulos = (
        Articulo.objects
        .filter(
            negocio=negocio,
            activo=True,
        )
        .order_by("nombre")
    )

    return render(
        request,
        "cotizaciones.html",
        {
            "cotizaciones": cotizaciones,
            "clientes": clientes,
            "articulos": articulos,
        },
    )


def gestion_cotizacion(request, id):
    servicio = get_object_or_404(
        Servicio.objects.select_related("cliente", "negocio"),
        id=id,
    )

    if (
        request.method == "POST"
        and request.POST.get("accion") == "cambiar_estado"
    ):
        nuevo_estado = request.POST.get("estado", "").strip()

        servicio.estado = nuevo_estado

        if (
            nuevo_estado == "Confirmado"
            and not servicio.fecha_confirmacion
        ):
            servicio.fecha_confirmacion = datetime.now()

        servicio.save()

        return redirect(
            "gestion_cotizacion",
            id=servicio.id,
        )

    detalles = (
        DetalleServicio.objects
        .filter(servicio=servicio)
        .select_related("articulo")
    )

    estados_servicio = [
        "Cotizacion",
        "Confirmado",
        "Preparacion",
        "Despachado",
        "Devolucion parcial",
        "Finalizado",
        "Cancelado",
    ]

    return render(
        request,
        "cotizacion.html",
        {
            "servicio": servicio,
            "detalles": detalles,
            "estados_servicio": estados_servicio,
        },
    )


# ============================================================
# RESERVAS / SERVICIOS CONFIRMADOS
# ============================================================

def gestion_reservas(request):
    negocio = obtener_negocio()

    reservas = (
        Servicio.objects
        .filter(negocio=negocio)
        .exclude(
            estado__in=[
                "Cotizacion",
                "Cancelado",
            ]
        )
        .select_related("cliente")
        .order_by("-fecha_evento", "-fecha_creacion")
    )

    return render(
        request,
        "reservas.html",
        {
            "reservas": reservas,
        },
    )


def gestion_reserva(request, id):
    servicio = get_object_or_404(
        Servicio.objects.select_related("cliente", "negocio"),
        id=id,
    )

    detalles = (
        DetalleServicio.objects
        .filter(servicio=servicio)
        .select_related("articulo")
    )

    return render(
        request,
        "reserva.html",
        {
            "servicio": servicio,
            "detalles": detalles,
        },
    )


# ============================================================
# PREPARACIÓN
# ============================================================

def gestion_preparacion(request):
    preparaciones = (
        Preparacion.objects
        .select_related(
            "servicio",
            "servicio__cliente",
            "usuario",
        )
        .order_by("-id")
    )

    return render(
        request,
        "preparacion.html",
        {
            "preparaciones": preparaciones,
        },
    )


def gestion_preparacion_documento(request, id):
    preparacion = get_object_or_404(
        Preparacion.objects.select_related(
            "servicio",
            "servicio__cliente",
            "usuario",
        ),
        id=id,
    )

    detalles = list(
        DetallePreparacion.objects
        .filter(preparacion=preparacion)
        .select_related("articulo")
    )

    if request.method == "POST":
        with transaction.atomic():
            for detalle in detalles:
                valor = request.POST.get(
                    f"preparado_{detalle.id}"
                )

                if valor is not None:
                    detalle.cantidad_preparada = max(
                        0,
                        _entero(valor, 0),
                    )
                    detalle.save(
                        update_fields=[
                            "cantidad_preparada",
                        ]
                    )

            preparacion.observaciones = request.POST.get(
                "observaciones",
                "",
            ).strip()

            if detalles and all(
                d.cantidad_preparada >= d.cantidad_solicitada
                for d in detalles
            ):
                preparacion.estado = "Completada"

            preparacion.save()

        return redirect(
            "gestion_preparacion_documento",
            id=id,
        )

    return render(
        request,
        "preparacion-documento.html",
        {
            "preparacion": preparacion,
            "detalles": detalles,
        },
    )


# ============================================================
# DESPACHOS
# ============================================================

def gestion_despachos(request):
    despachos = (
        Despacho.objects
        .select_related(
            "servicio",
            "servicio__cliente",
            "usuario",
        )
        .order_by("-fecha_despacho")
    )

    return render(
        request,
        "despachos.html",
        {
            "despachos": despachos,
        },
    )


def gestion_despacho_documento(request, id):
    despacho = get_object_or_404(
        Despacho.objects.select_related(
            "servicio",
            "servicio__cliente",
            "usuario",
        ),
        id=id,
    )

    detalles = (
        DetalleDespacho.objects
        .filter(despacho=despacho)
        .select_related("articulo")
    )

    return render(
        request,
        "despacho-documento.html",
        {
            "despacho": despacho,
            "detalles": detalles,
        },
    )


# ============================================================
# DEVOLUCIONES
# ============================================================

def gestion_devoluciones(request):
    devoluciones = list(
        Devolucion.objects
        .select_related(
            "servicio",
            "servicio__cliente",
            "usuario",
        )
        .order_by("-fecha_devolucion")
    )

    # Total por devolución sin depender de related_name.
    ids = [d.id for d in devoluciones]
    totales = {}

    if ids:
        filas = (
            DetalleDevolucion.objects
            .filter(devolucion_id__in=ids)
            .values("devolucion_id")
            .annotate(total=Sum("cantidad_devuelta"))
        )

        for fila in filas:
            totales[fila["devolucion_id"]] = fila["total"] or 0

    for devolucion in devoluciones:
        devolucion.total_productos = totales.get(
            devolucion.id,
            0,
        )

    return render(
        request,
        "devoluciones.html",
        {
            "devoluciones": devoluciones,
        },
    )


def gestion_devolucion(request, id):
    devolucion = get_object_or_404(
        Devolucion.objects.select_related(
            "servicio",
            "servicio__cliente",
            "usuario",
        ),
        id=id,
    )

    detalles = list(
        DetalleDevolucion.objects
        .filter(devolucion=devolucion)
        .select_related("articulo")
    )

    if request.method == "POST":
        with transaction.atomic():
            for detalle in detalles:
                detalle.cantidad_devuelta = max(
                    0,
                    _entero(
                        request.POST.get(
                            f"devuelta_{detalle.id}"
                        ),
                        0,
                    ),
                )

                detalle.cantidad_buena = max(
                    0,
                    _entero(
                        request.POST.get(
                            f"buena_{detalle.id}"
                        ),
                        0,
                    ),
                )

                detalle.cantidad_danada = max(
                    0,
                    _entero(
                        request.POST.get(
                            f"danada_{detalle.id}"
                        ),
                        0,
                    ),
                )

                detalle.cantidad_pendiente = max(
                    0,
                    _entero(
                        request.POST.get(
                            f"pendiente_{detalle.id}"
                        ),
                        0,
                    ),
                )

                detalle.save()

            devolucion.observaciones = request.POST.get(
                "observaciones",
                "",
            ).strip()
            devolucion.save()

        return redirect(
            "gestion_devolucion",
            id=id,
        )

    return render(
        request,
        "devolucion.html",
        {
            "devolucion": devolucion,
            "detalles": detalles,
        },
    )


# ============================================================
# MERMAS
# ============================================================

def gestion_mermas(request):
    negocio = obtener_negocio()

    if request.method == "POST" and request.POST.get("accion") == "crear":
        articulo = get_object_or_404(
            Articulo,
            id=request.POST.get("articulo_id"),
        )

        detalle = None
        detalle_id = request.POST.get(
            "detalle_devolucion_id"
        )

        if detalle_id:
            detalle = get_object_or_404(
                DetalleDevolucion,
                id=detalle_id,
            )

        fecha_valor = request.POST.get("fecha")

        Merma.objects.create(
            detalle_devolucion=detalle,
            articulo=articulo,
            cantidad=max(
                1,
                _entero(
                    request.POST.get("cantidad"),
                    1,
                ),
            ),
            tipo=request.POST.get("tipo", "").strip(),
            motivo=request.POST.get("motivo", "").strip(),
            valor_reposicion=max(
                0,
                _entero(
                    request.POST.get("valor_reposicion"),
                    0,
                ),
            ),
            observaciones=request.POST.get(
                "observaciones",
                "",
            ).strip(),
            fecha=fecha_valor or datetime.now(),
        )

        return redirect("gestion_mermas")

    mermas = (
        Merma.objects
        .select_related(
            "articulo",
            "articulo__categoria",
            "detalle_devolucion",
            "detalle_devolucion__devolucion",
            "detalle_devolucion__devolucion__servicio",
            "detalle_devolucion__devolucion__usuario",
        )
        .order_by("-fecha")
    )

    articulos = (
        Articulo.objects
        .filter(
            negocio=negocio,
            activo=True,
        )
        .order_by("nombre")
    )

    detalles_devolucion = (
        DetalleDevolucion.objects
        .select_related(
            "devolucion",
            "devolucion__servicio",
            "articulo",
        )
        .order_by("-id")
    )

    return render(
        request,
        "mermas.html",
        {
            "mermas": mermas,
            "articulos": articulos,
            "detalles_devolucion": detalles_devolucion,
        },
    )


# ============================================================
# CALENDARIO
# ============================================================

def gestion_calendario(request):
    negocio = obtener_negocio()

    servicios = (
        Servicio.objects
        .filter(
            negocio=negocio,
            fecha_evento__isnull=False,
        )
        .exclude(estado="Cancelado")
        .select_related("cliente")
        .order_by("fecha_evento")
    )

    return render(
        request,
        "calendario.html",
        {
            "servicios": servicios,
        },
    )


# ============================================================
# REPORTES
# ============================================================

def gestion_reportes(request):
    negocio = obtener_negocio()

    articulos = Articulo.objects.filter(negocio=negocio)
    servicios = Servicio.objects.filter(negocio=negocio)
    clientes = Cliente.objects.filter(negocio=negocio)

    stock_total = (
        articulos.aggregate(total=Sum("stock_total"))["total"]
        or 0
    )

    stock_trabajable = (
        articulos.aggregate(total=Sum("stock_trabajable"))["total"]
        or 0
    )

    monto_cotizado = (
        servicios
        .filter(estado="Cotizacion")
        .aggregate(total=Sum("total"))["total"]
        or 0
    )

    ticket_promedio = (
        servicios
        .filter(estado="Finalizado")
        .aggregate(promedio=Avg("total"))["promedio"]
        or 0
    )

    metricas = {
        "stock_total": stock_total,
        "stock_trabajable": stock_trabajable,
        "stock_comprometido": max(
            0,
            stock_total - stock_trabajable,
        ),
        "stock_bajo": articulos.filter(
            stock_trabajable__lte=10
        ).count(),
        "reservas_total": servicios.exclude(
            estado="Cotizacion"
        ).count(),
        "reservas_proximas": (
            servicios
            .filter(fecha_evento__gte=date.today())
            .exclude(
                estado__in=[
                    "Cotizacion",
                    "Cancelado",
                    "Finalizado",
                ]
            )
            .count()
        ),
        "reservas_finalizadas": servicios.filter(
            estado="Finalizado"
        ).count(),
        "reservas_canceladas": servicios.filter(
            estado="Cancelado"
        ).count(),
        "clientes_total": clientes.count(),
        "clientes_nuevos": clientes.filter(
            fecha_creacion__year=date.today().year,
            fecha_creacion__month=date.today().month,
        ).count(),
        "monto_cotizado": monto_cotizado,
        "cotizaciones_aceptadas": servicios.filter(
            fecha_confirmacion__isnull=False
        ).count(),
        "cotizaciones_rechazadas": servicios.filter(
            estado="Cancelado"
        ).count(),
        "ticket_promedio": ticket_promedio,
    }

    productos_mas_arrendados = list(
        DetalleServicio.objects
        .filter(
            servicio__negocio=negocio
        )
        .values(
            nombre=F("articulo__nombre")
        )
        .annotate(
            total_arrendado=Sum("cantidad")
        )
        .order_by("-total_arrendado")[:5]
    )

    productos_menos_utilizados = list(
        DetalleServicio.objects
        .filter(
            servicio__negocio=negocio
        )
        .values(
            nombre=F("articulo__nombre")
        )
        .annotate(
            total_arrendado=Sum("cantidad")
        )
        .order_by("total_arrendado")[:5]
    )

    clientes_frecuentes = list(
        Cliente.objects
        .filter(negocio=negocio)
        .values(
            "id",
            "nombre",
            "apellido",
        )
        .annotate(
            total_servicios=Count(
                "servicio",
                distinct=True,
            )
        )
        .order_by("-total_servicios")[:5]
    )

    ingresos_categoria = list(
        DetalleServicio.objects
        .filter(
            servicio__negocio=negocio
        )
        .values(
            categoria=F(
                "articulo__categoria__nombre"
            )
        )
        .annotate(
            total=Sum("subtotal")
        )
        .order_by("-total")
    )

    return render(
        request,
        "reportes.html",
        {
            "metricas": metricas,
            "productos_mas_arrendados":
                productos_mas_arrendados,
            "productos_menos_utilizados":
                productos_menos_utilizados,
            "clientes_frecuentes":
                clientes_frecuentes,
            "ingresos_categoria":
                ingresos_categoria,
        },
    )


# ============================================================
# USUARIOS
# ============================================================

def gestion_usuarios(request):
    negocio = obtener_negocio()

    if request.method == "POST" and request.POST.get("accion") == "crear":
        rol = get_object_or_404(
            Rol,
            id=request.POST.get("rol_id"),
        )

        Usuario.objects.create(
            negocio=negocio,
            rol=rol,
            nombre=request.POST.get("nombre", "").strip(),
            apellido=request.POST.get("apellido", "").strip(),
            email=request.POST.get("email", "").strip().lower(),
            password=make_password(
                request.POST.get("password", "")
            ),
            activo=request.POST.get("activo") == "on",
        )

        return redirect("gestion_usuarios")

    usuarios = (
        Usuario.objects
        .filter(negocio=negocio)
        .select_related("rol")
        .order_by("nombre", "apellido")
    )

    roles = Rol.objects.all().order_by("nombre")

    return render(
        request,
        "usuarios.html",
        {
            "usuarios": usuarios,
            "roles": roles,
        },
    )


# ============================================================
# CONFIGURACIÓN
# ============================================================

def gestion_configuracion(request):
    negocio = obtener_negocio()

    if negocio is None:
        return render(
            request,
            "configuracion.html",
            {
                "negocio": None,
                "error": "No existe un negocio activo configurado.",
            },
        )

    if request.method == "POST":
        negocio.nombre = request.POST.get(
            "nombre",
            "",
        ).strip()

        negocio.nombre_fantasia = request.POST.get(
            "nombre_fantasia",
            "",
        ).strip()

        negocio.rut = request.POST.get(
            "rut",
            "",
        ).strip()

        negocio.telefono = request.POST.get(
            "telefono",
            "",
        ).strip()

        negocio.email = request.POST.get(
            "email",
            "",
        ).strip()

        negocio.direccion = request.POST.get(
            "direccion",
            "",
        ).strip()

        negocio.descripcion = request.POST.get(
            "descripcion",
            "",
        ).strip()

        negocio.porcentaje_abono = (
            request.POST.get("porcentaje_abono")
            or 0
        )

        negocio.porcentaje_garantia = (
            request.POST.get("porcentaje_garantia")
            or 0
        )

        negocio.activo = (
            request.POST.get("activo") == "on"
        )

        negocio.save()

        return redirect("gestion_configuracion")

    return render(
        request,
        "configuracion.html",
        {
            "negocio": negocio,
        },
    )


# ============================================================
# LOGIN
# ============================================================

def gestion_login(request):
    if request.method == "POST":
        email = request.POST.get(
            "email",
            "",
        ).strip().lower()

        password = request.POST.get(
            "password",
            "",
        )

        usuario = (
            Usuario.objects
            .filter(
                email=email,
                activo=True,
            )
            .select_related(
                "rol",
                "negocio",
            )
            .first()
        )

        if usuario:
            password_valida = False

            try:
                password_valida = check_password(
                    password,
                    usuario.password,
                )
            except Exception:
                password_valida = False

            # Compatibilidad temporal con registros antiguos en texto plano.
            if not password_valida:
                password_valida = (
                    usuario.password == password
                )

            if password_valida:
                request.session["usuario_id"] = usuario.id
                request.session["usuario_nombre"] = (
                    f"{usuario.nombre} {usuario.apellido}".strip()
                )
                request.session["usuario_rol"] = usuario.rol.nombre

                return redirect("index")

        return render(
            request,
            "login.html",
            {
                "error": "Correo o contraseña incorrectos.",
            },
        )

    return render(
        request,
        "login.html",
    )
