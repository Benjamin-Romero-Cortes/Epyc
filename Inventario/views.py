from datetime import date, datetime, timedelta
from functools import wraps
import json
import logging
import re
import unicodedata
from urllib.parse import quote
from uuid import uuid4

from django.contrib import messages
from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.utils.http import url_has_allowed_host_and_scheme
from django.db import transaction
from django.db.models import Sum, Avg, Count, F, Max, Q, Value
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.views.decorators.http import require_POST
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from django.db.models.functions import Coalesce, Replace, Upper, TruncMonth
from django.utils import timezone
from django.utils.text import slugify

from Inventario.disponibilidad import (
    ESTADOS_EN_CLIENTE,
    ESTADOS_QUE_BLOQUEAN,
    NIVELES_ALERTA,
    comprometido_vigente,
    estado_stock,
    nivel_stock as _nivel_stock,
    porcentaje as _porcentaje,
    StockInsuficiente,
    confirmar_servicio,
    disponibilidad_servicio,
    periodo_servicio,
    calcular_disponibilidad,
)
from Inventario.validaciones import (
    correo_valido,
    normalizar_rut,
    normalizar_telefono,
    rut_valido,
    telefono_valido,
)

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
    HistorialServicio,
    Rol,
    Usuario,
)
from Inventario.operaciones import (
    ESTADOS_CANCELABLES,
    OperacionInvalida,
    anular_merma,
    cancelar_servicio,
    cerrar_servicio,
    estado_devolucion,
    registrar_devolucion,
    registrar_merma_manual,
    registrar_movimientos_servicio,
    reparar_merma,
    finalizar_preparacion,
    generar_preparacion,
    guardar_avance,
    registrar_despacho,
    registrar_historial,
    resumen_despacho,
    resumen_unidades,
)


logger = logging.getLogger(__name__)

# Servicios que ya son reservas (confirmadas, en curso o devueltas); excluye cotizaciones y cancelados.
ESTADOS_RESERVA = [*ESTADOS_QUE_BLOQUEAN, Servicio.Estado.FINALIZADO, Servicio.Estado.CERRADO]
# Todo lo cotizado que no se canceló (desde Cotización hasta Cerrado).
ESTADOS_COTIZADOS = [Servicio.Estado.COTIZACION, Servicio.Estado.CONTACTADO, *ESTADOS_RESERVA]


# UTILIDADES

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


# SITIO PÚBLICO

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


TIPOS_EVENTO = [
    "Matrimonio",
    "Cumpleaños",
    "Evento empresarial",
    "Cena / Banquete",
    "Evento familiar",
    "Celebración",
    "Otro",
]

ETIQUETAS_CATEGORIA = {
    "vajilla": "Vajilla",
    "cristaleria": "Cristalería",
    "cubiertos": "Cubiertos",
    "manteleria": "Mantelería",
    "mesas-sillas": "Mesas y sillas",
    "decoracion": "Decoración",
    "equipamiento": "Equipamiento",
    "carpas-exteriores": "Carpas",
}

CATEGORIA_POR_DEFINIR = "por-definir"

MENSAJE_SOLICITUD_ENVIADA = (
    "Tu solicitud de cotización fue enviada correctamente. "
    "Nos comunicaremos contigo por WhatsApp o correo."
)

MENSAJE_ERROR_INTERNO = (
    "No pudimos registrar tu solicitud. Inténtalo nuevamente en unos minutos."
)


def etiqueta_categoria(categoria):
    return ETIQUETAS_CATEGORIA.get(
        categoria.nombre,
        categoria.nombre.replace("-", " ").capitalize(),
    )


def _quiere_json(request):
    return request.headers.get("x-requested-with") == "XMLHttpRequest"


def _validar_solicitud(post, categorias):
    """Valida y limpia los datos del cotizador. Devuelve (errores, datos)."""
    errores = {}
    datos = {}

    tipo_evento = post.get("tipoEvento", "").strip()
    if tipo_evento not in TIPOS_EVENTO:
        errores["tipoEvento"] = "Selecciona un tipo de evento."
    datos["tipo_evento"] = tipo_evento

    try:
        fecha_evento = date.fromisoformat(post.get("fecha", "").strip())
    except ValueError:
        fecha_evento = None
        errores["fecha"] = "Selecciona una fecha válida."
    else:
        if fecha_evento < timezone.localdate():
            errores["fecha"] = "La fecha no puede ser anterior a hoy."
    datos["fecha_evento"] = fecha_evento

    invitados = _entero(post.get("invitados", "").strip(), 0)
    if invitados < 1:
        errores["invitados"] = "Ingresa una cantidad de invitados mayor que cero."
    elif invitados > 10000:
        errores["invitados"] = "Ingresa una cantidad de invitados realista."
    datos["invitados"] = invitados

    comuna = post.get("comuna", "").strip()
    if not comuna:
        errores["comuna"] = "Ingresa la comuna."
    datos["comuna"] = comuna[:100]

    despacho = post.get("despacho", "").strip()
    if despacho not in ("Sí", "No, retiro yo"):
        errores["despacho"] = "Indica si requieres despacho."
    datos["requiere_despacho"] = despacho == "Sí"

    por_id = {str(c.id): c for c in categorias}
    elegidas = post.getlist("categorias")
    desconocidas = [v for v in elegidas if v != CATEGORIA_POR_DEFINIR and v not in por_id]
    if not elegidas:
        errores["categorias"] = 'Selecciona al menos una categoría o "Aún no estoy seguro/a".'
    elif desconocidas:
        errores["categorias"] = "Selecciona categorías válidas."
    # "Aún no estoy seguro/a" es excluyente: si viene, se ignoran las demás.
    datos["categorias_por_definir"] = CATEGORIA_POR_DEFINIR in elegidas
    datos["categorias"] = (
        [] if datos["categorias_por_definir"]
        else [por_id[v] for v in elegidas if v in por_id]
    )

    nombre_completo = post.get("nombre", "").strip()
    if not nombre_completo:
        errores["nombre"] = "Ingresa tu nombre."
    datos["nombre"], datos["apellido"] = _separar_nombre(nombre_completo[:200])

    rut = normalizar_rut(post.get("rut", ""))
    if not rut:
        errores["rut"] = "Ingresa tu RUT."
    elif not rut_valido(rut):
        errores["rut"] = "El RUT no es válido. Revisa el número y el dígito verificador."
    datos["rut"] = rut

    telefono = post.get("telefono", "").strip()
    if telefono and not telefono_valido(telefono):
        errores["telefono"] = "Ingresa un teléfono válido o déjalo en blanco."
    datos["telefono"] = normalizar_telefono(telefono)[:30]

    correo = post.get("correo", "").strip().lower()
    if correo and not correo_valido(correo):
        errores["correo"] = "Ingresa un correo válido o déjalo en blanco."
    datos["correo"] = correo[:150]

    medio = post.get("medioContacto", "").strip()
    if medio and medio not in Servicio.MedioContacto.values:
        errores["medioContacto"] = "Selecciona un medio de contacto válido."
    datos["medio_contacto"] = medio

    datos["direccion"] = post.get("direccion", "").strip()[:255]
    datos["empresa"] = post.get("empresa", "").strip()[:150]
    datos["comentarios"] = post.get("comentarios", "").strip()[:2000]

    return errores, datos


def _buscar_cliente_por_rut(negocio, rut, bloquear=False):
    """
    Busca por RUT normalizado.

    Los registros nuevos se encuentran por igualdad directa. Para conservar
    compatibilidad con datos antiguos que todavía tengan puntos, guion o
    espacios, el fallback normaliza el RUT dentro de la propia consulta SQL,
    evitando cargar todos los clientes en Python.
    """
    base = Cliente.objects
    if bloquear:
        base = base.select_for_update()

    cliente = base.filter(negocio=negocio, rut=rut).first()
    if cliente is not None:
        return cliente

    rut_normalizado_db = Upper(
        Replace(
            Replace(
                Replace("rut", Value("."), Value("")),
                Value("-"),
                Value(""),
            ),
            Value(" "),
            Value(""),
        )
    )

    return (
        base
        .filter(negocio=negocio)
        .exclude(rut="")
        .annotate(_rut_normalizado=rut_normalizado_db)
        .filter(_rut_normalizado=rut)
        .first()
    )


def _palabras_nombre(texto):
    """Palabras de un nombre en minúsculas y sin tildes, para comparar nombres escritos distinto."""
    sin_tildes = unicodedata.normalize("NFD", texto or "").encode("ascii", "ignore").decode()
    return set(re.findall(r"[a-z]+", sin_tildes.lower()))


def _nombre_coincide(cliente, nombre_completo):
    """El nombre escrito coincide si uno contiene todas las palabras del otro
    (permite "Ana Pérez" frente a "Ana María Pérez Soto", pero no "Juan Soto")."""
    registrado = _palabras_nombre(f"{cliente.nombre} {cliente.apellido}")
    escrito = _palabras_nombre(nombre_completo)
    if not registrado or not escrito:
        return True
    return registrado <= escrito or escrito <= registrado


def _obtener_o_crear_cliente(negocio, datos):
    """Busca al cliente por RUT normalizado; si existe solo completa los datos opcionales nuevos."""
    cliente = _buscar_cliente_por_rut(negocio, datos["rut"], bloquear=True)

    if cliente is None:
        return Cliente.objects.create(
            negocio=negocio,
            rut=datos["rut"],
            nombre=datos["nombre"],
            apellido=datos["apellido"],
            telefono=datos["telefono"],
            email=datos["correo"],
            direccion=datos["direccion"],
            comuna=datos["comuna"],
            activo=True,
        )

    cliente.rut = datos["rut"]
    cliente.telefono = datos["telefono"] or cliente.telefono
    cliente.email = datos["correo"] or cliente.email
    cliente.direccion = datos["direccion"] or cliente.direccion
    cliente.comuna = cliente.comuna or datos["comuna"]
    cliente.activo = True
    cliente.save()
    return cliente


def _registrar_solicitud(negocio, datos, articulo_consultado=None):
    """Crea (o reutiliza) el cliente y crea el servicio con sus categorías en una sola transacción."""
    notas = []
    if datos["empresa"]:
        notas.append(f"Empresa: {datos['empresa']}")
    if articulo_consultado:
        notas.append(
            f"Artículo consultado desde el catálogo: "
            f"{articulo_consultado.codigo} - {articulo_consultado.nombre}"
        )

    with transaction.atomic():
        cliente = _obtener_o_crear_cliente(negocio, datos)

        servicio = Servicio.objects.create(
            negocio=negocio,
            cliente=cliente,
            codigo=f"COT-{timezone.localdate():%Y%m%d}-{uuid4().hex[:6].upper()}",
            estado=Servicio.Estado.COTIZACION,
            tipo_servicio=datos["tipo_evento"],
            fecha_solicitud=timezone.localdate(),
            fecha_evento=datos["fecha_evento"],
            fecha_inicio=datos["fecha_evento"],
            fecha_termino=datos["fecha_evento"],
            direccion_evento=datos["direccion"],
            comuna_evento=datos["comuna"],
            cantidad_personas=datos["invitados"],
            requiere_despacho=datos["requiere_despacho"],
            medio_contacto=datos["medio_contacto"],
            comentarios=datos["comentarios"],
            categorias_por_definir=datos["categorias_por_definir"],
            observaciones="\n".join(notas),
        )
        servicio.categorias_solicitadas.set(datos["categorias"])

    return servicio


def cotizador(request):
    negocio = obtener_negocio()

    if negocio is None:
        return render(
            request,
            "cotizador.html",
            {
                "categorias": [],
                "error": "El cotizador no está disponible en este momento.",
            },
        )

    categorias = list(
        Categoria.objects
        .filter(negocio=negocio, activo=True)
        .order_by("nombre")
    )
    for categoria in categorias:
        categoria.etiqueta = etiqueta_categoria(categoria)

    articulo_id = request.GET.get("articulo") or request.POST.get("articulo_id")
    articulo_preseleccionado = None
    if articulo_id and str(articulo_id).isdigit():
        articulo_preseleccionado = (
            Articulo.objects
            .filter(id=articulo_id, negocio=negocio, activo=True)
            .first()
        )

    contexto = {
        "categorias": categorias,
        "categoria_por_definir": CATEGORIA_POR_DEFINIR,
        "articulo_preseleccionado": articulo_preseleccionado,
    }

    cliente_cuenta_actual = cliente_de_sesion(request)
    contexto["cliente_cuenta"] = cliente_cuenta_actual

    if request.method != "POST":
        return render(request, "cotizador.html", contexto)

    post = request.POST
    if cliente_cuenta_actual:
        # La solicitud queda a nombre de la cuenta: el RUT no se puede cambiar desde el formulario.
        post = request.POST.copy()
        post["rut"] = cliente_cuenta_actual.rut
        post["nombre"] = f"{cliente_cuenta_actual.nombre} {cliente_cuenta_actual.apellido}".strip()
    errores, datos = _validar_solicitud(post, categorias)

    # Un RUT ya registrado no puede usarse con el nombre de otra persona.
    if not errores:
        existente = _buscar_cliente_por_rut(negocio, datos["rut"])
        if existente and not _nombre_coincide(existente, post.get("nombre", "")):
            errores["rut"] = (
                "Este RUT ya está registrado con otro nombre. "
                "Revisa que tu nombre y tu RUT estén bien escritos."
            )

    if errores:
        mensaje = "Revisa los campos marcados antes de enviar."
        if _quiere_json(request):
            return JsonResponse({"ok": False, "message": mensaje, "errors": errores}, status=400)
        return render(request, "cotizador.html", {**contexto, "error": mensaje, "errores": errores})

    try:
        _registrar_solicitud(negocio, datos, articulo_preseleccionado)
    except Exception:
        logger.exception("Error al registrar una solicitud de cotización")
        if _quiere_json(request):
            return JsonResponse({"ok": False, "message": MENSAJE_ERROR_INTERNO}, status=500)
        return render(request, "cotizador.html", {**contexto, "error": MENSAJE_ERROR_INTERNO})

    if _quiere_json(request):
        return JsonResponse({"ok": True, "message": MENSAJE_SOLICITUD_ENVIADA})
    return render(request, "cotizador.html", {**contexto, "enviado": True, "mensaje": MENSAJE_SOLICITUD_ENVIADA})


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


# CUENTA DE CLIENTE (sitio público)
# Sesión separada de la del panel: "cliente_id" nunca da acceso a la gestión.

ESTADOS_PUBLICOS = {
    Servicio.Estado.COTIZACION: ("Solicitud recibida", "info"),
    Servicio.Estado.CONTACTADO: ("Cotización enviada", "warning"),
    Servicio.Estado.CONFIRMADO: ("Reserva confirmada", "success"),
    Servicio.Estado.PREPARACION: ("Preparando tu pedido", "success"),
    Servicio.Estado.PREPARADO: ("Pedido listo", "success"),
    Servicio.Estado.DESPACHADO: ("Entregado", "success"),
    Servicio.Estado.DEVOLUCION_PARCIAL: ("Devolución en curso", "warning"),
    Servicio.Estado.FINALIZADO: ("Finalizado", "neutral"),
    Servicio.Estado.CERRADO: ("Finalizado", "neutral"),
    Servicio.Estado.CANCELADO: ("Cancelado", "danger"),
}


def estado_publico(servicio):
    """Etiqueta y color del estado tal como lo ve el cliente."""
    if servicio.estado == Servicio.Estado.CONTACTADO and servicio.aceptada_cliente:
        return "Aceptada · por confirmar", "success"
    return ESTADOS_PUBLICOS.get(servicio.estado, (servicio.get_estado_display(), "neutral"))


def cliente_de_sesion(request):
    cliente_id = request.session.get("cliente_id")
    if not cliente_id:
        return None
    cliente = Cliente.objects.filter(id=cliente_id, activo=True).exclude(password="").first()
    if cliente is None:
        for clave in ("cliente_id", "cliente_nombre"):
            request.session.pop(clave, None)
    return cliente


def _iniciar_sesion_cliente(request, cliente):
    request.session.cycle_key()
    request.session["cliente_id"] = cliente.id
    request.session["cliente_nombre"] = cliente.nombre


def _validar_registro(post, negocio):
    """Devuelve (errores por campo, datos limpios, cliente existente a vincular o None)."""
    errores = {}
    nombre_completo = post.get("nombre", "").strip()
    rut = normalizar_rut(post.get("rut", ""))
    email = post.get("email", "").strip().lower()
    telefono = post.get("telefono", "").strip()
    clave = post.get("password", "")
    clave2 = post.get("password2", "")

    if not nombre_completo:
        errores["nombre"] = "Ingresa tu nombre."
    if not rut:
        errores["rut"] = "Ingresa tu RUT."
    elif not rut_valido(rut):
        errores["rut"] = "El RUT no es válido. Revisa el número y el dígito verificador."
    if not email:
        errores["email"] = "Ingresa tu correo."
    elif not correo_valido(email):
        errores["email"] = "Ingresa un correo válido."
    if telefono and not telefono_valido(telefono):
        errores["telefono"] = "Ingresa un teléfono válido o déjalo en blanco."
    if not clave:
        errores["password"] = "Crea una contraseña."
    else:
        try:
            validate_password(clave)
        except ValidationError as error:
            errores["password"] = " ".join(error.messages)
    if clave and clave != clave2:
        errores["password2"] = "Las contraseñas no coinciden."

    existente = None
    if "rut" not in errores:
        existente = _buscar_cliente_por_rut(negocio, rut)
        if existente and existente.tiene_cuenta:
            errores["rut"] = "Ya existe una cuenta con este RUT. Inicia sesión."
        elif existente and (
            not _nombre_coincide(existente, nombre_completo)
            or (existente.email and email and existente.email.lower() != email)
        ):
            # Sin revelar los datos registrados: solo se vincula si coinciden nombre y correo.
            errores["rut"] = "Este RUT ya está registrado con otros datos. Escríbenos para activar tu cuenta."
    if "email" not in errores and email:
        otra_cuenta = Cliente.objects.filter(negocio=negocio, email__iexact=email).exclude(password="")
        if existente:
            otra_cuenta = otra_cuenta.exclude(id=existente.id)
        if otra_cuenta.exists() or Usuario.objects.filter(email__iexact=email).exists():
            errores["email"] = "Este correo ya tiene una cuenta. Inicia sesión."

    nombre, apellido = _separar_nombre(nombre_completo[:200])
    datos = {"nombre_completo": nombre_completo, "nombre": nombre, "apellido": apellido, "rut": rut,
             "email": email, "telefono": normalizar_telefono(telefono)[:30], "password": clave}
    return errores, datos, existente


def cliente_registro(request):
    if cliente_de_sesion(request):
        return redirect("cliente_cuenta")
    negocio = obtener_negocio()
    errores, valores = {}, {}

    if request.method == "POST" and negocio is not None:
        errores, datos, existente = _validar_registro(request.POST, negocio)
        valores = {k: datos[k] for k in ("nombre_completo", "email", "telefono")}
        valores["rut"] = request.POST.get("rut", "").strip()
        if not errores:
            try:
                with transaction.atomic():
                    if existente:
                        # Quien ya cotizó sin cuenta la activa con los mismos datos.
                        cliente = Cliente.objects.select_for_update().get(id=existente.id)
                        cliente.email = cliente.email or datos["email"]
                        cliente.telefono = cliente.telefono or datos["telefono"]
                    else:
                        cliente = Cliente(negocio=negocio, rut=datos["rut"], nombre=datos["nombre"],
                                          apellido=datos["apellido"], email=datos["email"],
                                          telefono=datos["telefono"], activo=True)
                    cliente.password = make_password(datos["password"])
                    cliente.fecha_registro = timezone.now()
                    cliente.save()
            except IntegrityError:
                errores["email"] = "Este correo ya tiene una cuenta. Inicia sesión."
            else:
                _iniciar_sesion_cliente(request, cliente)
                messages.success(request, f"¡Bienvenid@, {cliente.nombre}! Tu cuenta quedó creada.")
                return redirect("cliente_cuenta")

    return render(request, "registro.html", {"errores": errores, "valores": valores},
                  status=400 if errores else 200)


ESTADOS_HISTORIAL = (Servicio.Estado.FINALIZADO, Servicio.Estado.CERRADO, Servicio.Estado.CANCELADO)


def _etapas_cliente(estado):
    if estado == Servicio.Estado.CANCELADO:
        return []
    actual = next((i for i, (_, estados) in enumerate(ETAPAS_CLIENTE) if estado in estados), -1)
    return [{"nombre": nombre, "hecha": i < actual, "actual": i == actual} for i, (nombre, _) in enumerate(ETAPAS_CLIENTE)]


def cliente_cuenta(request):
    cliente = cliente_de_sesion(request)
    if cliente is None:
        return redirect(f"{reverse('gestion_login')}?next={reverse('cliente_cuenta')}")

    errores = {}
    accion = request.POST.get("accion") if request.method == "POST" else None
    if accion == "datos":
        telefono = request.POST.get("telefono", "").strip()
        if telefono and not telefono_valido(telefono):
            errores["telefono"] = "Ingresa un teléfono válido o déjalo en blanco."
        else:
            cliente.telefono = normalizar_telefono(telefono)[:30]
            cliente.direccion = request.POST.get("direccion", "").strip()[:255]
            cliente.comuna = request.POST.get("comuna", "").strip()[:100]
            cliente.save(update_fields=["telefono", "direccion", "comuna", "fecha_actualizacion"])
            messages.success(request, "Tus datos quedaron actualizados.")
            return redirect("cliente_cuenta")
    elif accion == "clave":
        actual = request.POST.get("actual", "")
        nueva = request.POST.get("nueva", "")
        if not check_password(actual, cliente.password):
            errores["actual"] = "La contraseña actual no es correcta."
        elif nueva != request.POST.get("nueva2", ""):
            errores["nueva2"] = "Las contraseñas nuevas no coinciden."
        else:
            try:
                validate_password(nueva)
            except ValidationError as error:
                errores["nueva"] = " ".join(error.messages)
        if not errores:
            cliente.password = make_password(nueva)
            cliente.save(update_fields=["password", "fecha_actualizacion"])
            messages.success(request, "Tu contraseña quedó actualizada.")
            return redirect("cliente_cuenta")

    hoy = timezone.localdate()
    servicios = list(
        Servicio.objects.filter(cliente=cliente)
        .prefetch_related("categorias_solicitadas")
        .order_by("fecha_evento", "-fecha_creacion")
    )
    for servicio in servicios:
        servicio.estado_publico, servicio.clase_publica = estado_publico(servicio)
        servicio.es_reserva = servicio.estado in ESTADOS_RESERVA
        servicio.dias_restantes = (servicio.fecha_evento - hoy).days if servicio.fecha_evento else None

    en_curso = [s for s in servicios if s.estado not in ESTADOS_HISTORIAL]
    historial = sorted((s for s in servicios if s.estado in ESTADOS_HISTORIAL),
                       key=lambda s: s.fecha_evento or hoy, reverse=True)
    proximo = next((s for s in en_curso if s.fecha_evento and s.fecha_evento >= hoy), None)
    if proximo:
        proximo.etapas = _etapas_cliente(proximo.estado)

    return render(request, "cuenta.html", {
        "cliente": cliente,
        "en_curso": en_curso,
        "historial": historial,
        "proximo": proximo,
        "resumen": {
            "en_curso": len(en_curso),
            "confirmadas": sum(1 for s in en_curso if s.es_reserva),
            "realizados": sum(1 for s in historial if s.estado != Servicio.Estado.CANCELADO),
        },
        "iniciales": (cliente.nombre[:1] + (cliente.apellido[:1] or cliente.nombre[1:2])).upper(),
        "errores": errores,
        "abrir": accion,
        "campos_clave": [
            ("actual", "Contraseña actual", "current-password"),
            ("nueva", "Nueva contraseña", "new-password"),
            ("nueva2", "Repite la nueva contraseña", "new-password"),
        ],
    }, status=400 if errores else 200)


# Etapas que ve el cliente en el detalle de su reserva.
ETAPAS_CLIENTE = [
    ("Solicitud", [Servicio.Estado.COTIZACION, Servicio.Estado.CONTACTADO]),
    ("Confirmada", [Servicio.Estado.CONFIRMADO]),
    ("En preparación", [Servicio.Estado.PREPARACION, Servicio.Estado.PREPARADO]),
    ("Entregada", [Servicio.Estado.DESPACHADO, Servicio.Estado.DEVOLUCION_PARCIAL]),
    ("Finalizada", [Servicio.Estado.FINALIZADO, Servicio.Estado.CERRADO]),
]


def cliente_reserva(request, id):
    cliente = cliente_de_sesion(request)
    if cliente is None:
        return redirect(f"{reverse('gestion_login')}?next={request.path}")
    # Solo sus propias solicitudes: cualquier otro id responde "no encontrada".
    servicio = get_object_or_404(Servicio, id=id, cliente=cliente)
    puede_cancelar = servicio.estado in (Servicio.Estado.COTIZACION, Servicio.Estado.CONTACTADO)
    # Solo se acepta una cotización ya enviada, con productos y que no se haya aceptado antes.
    puede_aceptar = (
        servicio.estado == Servicio.Estado.CONTACTADO
        and servicio.aceptada_cliente is None
        and servicio.detalles.exists()
    )

    if request.method == "POST" and request.POST.get("accion") == "aceptar":
        if not puede_aceptar:
            messages.error(request, "Esta cotización ya no se puede aceptar desde aquí.")
        else:
            servicio.aceptada_cliente = timezone.now()
            servicio.save(update_fields=["aceptada_cliente", "fecha_actualizacion"])
            registrar_historial(servicio, ACCION_ACEPTA_CLIENTE, None, servicio.estado,
                                f"Total aceptado ${servicio.total:,.0f}".replace(",", "."))
            try:
                _avisar_aceptacion(request, servicio)
            except Exception:
                logger.exception("No se pudo avisar por correo la aceptación de %s", servicio.codigo)
            messages.success(request, "¡Gracias! Recibimos tu aceptación. Te avisaremos cuando confirmemos la reserva.")
        return redirect("cliente_reserva", id=servicio.id)

    if request.method == "POST" and request.POST.get("accion") == "cancelar":
        if not puede_cancelar:
            messages.error(request, "Esta reserva ya está confirmada. Para cancelarla, escríbenos por WhatsApp o correo.")
        else:
            try:
                cancelar_servicio(servicio.id, None, "Cancelada por el cliente desde su cuenta. "
                                  + request.POST.get("motivo", "").strip()[:200])
            except OperacionInvalida as error:
                messages.error(request, error.mensaje)
            else:
                messages.success(request, "Tu solicitud quedó cancelada.")
        return redirect("cliente_reserva", id=servicio.id)

    etiqueta, clase = estado_publico(servicio)
    despacho = servicio.despachos.exclude(estado=Despacho.Estado.CANCELADO).first()

    return render(request, "cuenta-reserva.html", {
        "cliente": cliente,
        "servicio": servicio,
        "estado_publico": etiqueta,
        "clase_estado": clase,
        "etapas": _etapas_cliente(servicio.estado),
        "detalles": servicio.detalles.select_related("articulo").order_by("articulo__nombre"),
        "categorias": [etiqueta_categoria(c) for c in servicio.categorias_solicitadas.all()],
        "despacho": despacho,
        "puede_cancelar": puede_cancelar,
        "puede_aceptar": puede_aceptar,
        "aceptada": servicio.estado == Servicio.Estado.CONTACTADO and servicio.aceptada_cliente,
        "es_reserva": servicio.estado in ESTADOS_RESERVA,
    })


def _avisar_aceptacion(request, servicio):
    """Correo a la empresa: un cliente aceptó su cotización y espera la confirmación."""
    negocio = servicio.negocio
    destino = negocio.email or settings.EMAIL_HOST_USER
    if not destino:
        return
    cliente = servicio.cliente
    enlace = request.build_absolute_uri(reverse("gestion_cotizacion", args=[servicio.id]))
    fecha = f" · {servicio.fecha_evento:%d/%m/%Y}" if servicio.fecha_evento else ""
    total = f"${servicio.total:,.0f}".replace(",", ".")
    EmailMultiAlternatives(
        f"Cotización {servicio.codigo} aceptada por {cliente.nombre} {cliente.apellido}".strip(),
        (
            f"{cliente.nombre} {cliente.apellido} aceptó la cotización {servicio.codigo} desde su cuenta.\n\n"
            f"Evento: {servicio.tipo_servicio or 'Sin tipo'}{fecha}\n"
            f"Total: {total}\n\n"
            f"Revisa el stock y confirma la reserva en el panel: {enlace}\n"
        ),
        settings.DEFAULT_FROM_EMAIL,
        [destino],
    ).send()


@require_POST
def cliente_logout(request):
    for clave in ("cliente_id", "cliente_nombre"):
        request.session.pop(clave, None)
    messages.success(request, "Cerraste tu sesión.")
    return redirect("index")


def solo_administrador(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):

        usuario_id = request.session.get("usuario_id")

        # No ha iniciado sesión
        if not usuario_id:
            login_url = reverse("gestion_login")

            return redirect(
                f"{login_url}?next={request.get_full_path()}"
            )

        usuario = (
            Usuario.objects
            .filter(
                id=usuario_id,
                activo=True
            )
            .select_related(
                "rol",
                "negocio"
            )
            .first()
        )

        # La sesión apunta a un usuario que ya no existe o fue desactivado.
        if usuario is None:
            request.session.flush()

            return redirect("gestion_login")

        # Solo Administrador
        if (
            not usuario.rol
            or usuario.rol.nombre != "Administrador"
        ):
            # Página 403 controlada (403.html), sin detalles técnicos.
            raise PermissionDenied("No tienes permisos para acceder a esta sección.")

        # Dejamos el usuario disponible para la vista
        request.usuario_panel = usuario

        return view_func(
            request,
            *args,
            **kwargs
        )

    return wrapper

# LOGIN

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

            # Registros antiguos con la contraseña en texto plano: si coincide, se guarda
            # cifrada en ese mismo momento para que no vuelva a quedar legible.
            if not password_valida and usuario.password and not usuario.password.startswith(("pbkdf2_", "argon2", "bcrypt")):
                password_valida = usuario.password == password
                if password_valida:
                    usuario.password = make_password(password)
                    usuario.save(update_fields=["password"])

            if password_valida:
                request.session["usuario_id"] = usuario.id
                request.session["usuario_nombre"] = (
                    f"{usuario.nombre} {usuario.apellido}".strip()
                )
                request.session["usuario_rol"] = usuario.rol.nombre

                destino = request.GET.get("next")

                # Solo se redirige dentro del mismo sitio (evita enviar a páginas externas).
                if destino and url_has_allowed_host_and_scheme(destino, allowed_hosts={request.get_host()}):
                    return redirect(destino)

                return redirect("inicio")

        negocio = obtener_negocio()
        cliente = (
            Cliente.objects.filter(negocio=negocio, email__iexact=email, activo=True).exclude(password="").first()
            if email and negocio else None
        )
        if cliente and check_password(password, cliente.password):
            _iniciar_sesion_cliente(request, cliente)
            destino = request.GET.get("next")
            if destino and url_has_allowed_host_and_scheme(destino, allowed_hosts={request.get_host()}) and not destino.startswith("/gestion"):
                return redirect(destino)
            return redirect("cliente_cuenta")

        return render(
            request,
            "login.html",
            {
                "error": "Correo o contraseña incorrectos.",
                "email": email,
            },
            status=400,
        )

    return render(
        request,
        "login.html",
    )

@solo_administrador
def gestion_logout(request):
    request.session.flush()
    return redirect("gestion_login")

# GESTIÓN - INICIO
@solo_administrador
def gestionIndex(request):
    negocio = request.usuario_panel.negocio
    hoy = timezone.localdate()
    proximos_7 = hoy + timedelta(days=7)
    estados_activos = list(ESTADOS_QUE_BLOQUEAN)

    servicios_negocio = Servicio.objects.filter(negocio=negocio)

    # Un solo viaje a la BD para la mayoría de los contadores del dashboard.
    stats = servicios_negocio.aggregate(
        reservas_activas=Count(
            "id",
            filter=Q(estado__in=estados_activos),
        ),
        reservas_proximas_7_dias=Count(
            "id",
            filter=Q(
                estado__in=estados_activos,
                fecha_evento__gte=hoy,
                fecha_evento__lte=proximos_7,
            ),
        ),
        cotizaciones_pendientes=Count(
            "id",
            filter=Q(estado=Servicio.Estado.COTIZACION),
        ),
        cotizaciones_mes=Count(
            "id",
            filter=Q(
                estado=Servicio.Estado.COTIZACION,
                fecha_creacion__year=hoy.year,
                fecha_creacion__month=hoy.month,
            ),
        ),
        monto_cotizado_mes=Sum(
            "total",
            filter=Q(
                estado__in=ESTADOS_COTIZADOS,
                fecha_creacion__year=hoy.year,
                fecha_creacion__month=hoy.month,
            ),
        ),
        retiros_hoy=Count(
            "id",
            filter=(
                Q(fecha_termino=hoy)
                & ~Q(
                    estado__in=[
                        Servicio.Estado.COTIZACION,
                        Servicio.Estado.CONTACTADO,
                        Servicio.Estado.CANCELADO,
                    ]
                )
            ),
        ),
        pendientes_preparar=Count(
            "id",
            filter=Q(
                estado__in=[
                    Servicio.Estado.CONFIRMADO,
                    Servicio.Estado.PREPARACION,
                ]
            ),
        ),
        devoluciones_pendientes=Count(
            "id",
            filter=Q(estado__in=ESTADOS_EN_CLIENTE),
        ),
        confirmadas=Count(
            "id",
            filter=Q(estado=Servicio.Estado.CONFIRMADO),
        ),
        en_preparacion=Count(
            "id",
            filter=Q(estado=Servicio.Estado.PREPARACION),
        ),
        preparadas=Count(
            "id",
            filter=Q(estado=Servicio.Estado.PREPARADO),
        ),
    )

    proximos_eventos = list(
        servicios_negocio
        .filter(
            estado__in=estados_activos,
            fecha_evento__gte=hoy,
        )
        .select_related("cliente")
        .only(
            "id", "codigo", "estado", "tipo_servicio", "fecha_evento",
            "cliente__id", "cliente__nombre", "cliente__apellido",
        )
        .order_by("fecha_evento")[:5]
    )

    # Estado de inventario: se calcula una sola vez para reutilizar sus KPIs.
    inventario_qs = (
        Articulo.objects
        .filter(negocio=negocio, activo=True)
        .select_related("categoria")
    )
    _, stock = estado_stock(inventario_qs)
    articulos_totales = stock["trabajable"]
    articulos_disponibles = stock["disponible"]
    alertas_inventario = stock["alertas"][:6]
    alertas_inventario_count = stock["alertas_count"]

    entregas_hoy = (
        Despacho.objects
        .filter(
            servicio__negocio=negocio,
            fecha_despacho__date=hoy,
        )
        .exclude(estado=Despacho.Estado.CANCELADO)
        .count()
    )

    merma_stats = (
        Merma.objects
        .filter(articulo__negocio=negocio)
        .aggregate(
            registros=Count("id"),
            vigentes=Sum(
                F("cantidad") - F("cantidad_reparada"),
                filter=Q(anulada=False),
            ),
        )
    )
    registros_merma = merma_stats["registros"] or 0
    mermas_vigentes = merma_stats["vigentes"] or 0

    en_cliente_qs = servicios_negocio.filter(
        estado__in=ESTADOS_EN_CLIENTE
    ).annotate(
        fin=Coalesce("fecha_termino", "fecha_evento", "fecha_inicio")
    )

    ciclo = [
        (
            "Reservas confirmadas",
            stats["confirmadas"],
            reverse("gestion_preparacion"),
        ),
        (
            "En preparación",
            stats["en_preparacion"],
            f"{reverse('gestion_preparacion')}?estado=En+preparacion",
        ),
        (
            "Listas para despacho",
            stats["preparadas"],
            f"{reverse('gestion_despachos')}?vista=pendientes",
        ),
        (
            "Despachos de hoy",
            entregas_hoy,
            f"{reverse('gestion_despachos')}?vista=hoy",
        ),
        (
            "Devoluciones pendientes",
            stats["devoluciones_pendientes"],
            f"{reverse('gestion_devoluciones')}?estado=pendientes",
        ),
        (
            "Unidades en merma",
            mermas_vigentes,
            reverse("gestion_mermas"),
        ),
    ]

    productos_mas_arrendados = list(
        DetalleServicio.objects
        .filter(
            servicio__negocio=negocio,
            servicio__estado__in=ESTADOS_RESERVA,
        )
        .values(nombre=F("articulo__nombre"))
        .annotate(cantidad=Sum("cantidad"))
        .order_by("-cantidad")[:5]
    )

    categorias_solicitadas = list(
        DetalleServicio.objects
        .filter(servicio__negocio=negocio)
        .values(categoria=F("articulo__categoria__nombre"))
        .annotate(cantidad=Sum("cantidad"))
        .order_by("-cantidad")[:5]
    )

    # Antes se cargaban todos los clientes y luego se cruzaban en Python.
    # Ahora el nombre y el conteo salen en una sola consulta.
    clientes_frecuentes = list(
        servicios_negocio
        .exclude(
            estado__in=[
                Servicio.Estado.COTIZACION,
                Servicio.Estado.CONTACTADO,
            ]
        )
        .values(
            nombre=F("cliente__nombre"),
            apellido=F("cliente__apellido"),
        )
        .annotate(cantidad=Count("id"))
        .order_by("-cantidad")[:5]
    )

    # Agrupación mensual hecha por la BD en vez de traer todos los servicios.
    ingresos_rows = list(
        servicios_negocio
        .filter(
            estado__in=ESTADOS_RESERVA,
            fecha_evento__isnull=False,
        )
        .annotate(_mes=TruncMonth("fecha_evento"))
        .values("_mes")
        .annotate(total=Sum("total"))
        .order_by("-_mes")[:6]
    )
    ingresos_mensuales = [
        {
            "mes": fila["_mes"].strftime("%m/%Y"),
            "total": fila["total"] or 0,
        }
        for fila in reversed(ingresos_rows)
    ]

    dias_semana = [
        "lunes", "martes", "miércoles", "jueves",
        "viernes", "sábado", "domingo",
    ]
    nombres_meses = [
        "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
        "agosto", "septiembre", "octubre", "noviembre", "diciembre",
    ]
    fecha_hoy_texto = (
        f"{dias_semana[hoy.weekday()]}, {hoy.day} de "
        f"{nombres_meses[hoy.month - 1]}"
    )

    usuario_nombre = request.session.get("usuario_nombre", "")
    usuario_rol = request.session.get("usuario_rol", "")
    usuario_iniciales = ""

    if usuario_nombre:
        usuario_iniciales = "".join(
            palabra[0].upper()
            for palabra in usuario_nombre.split()[:2]
            if palabra
        )

    return render(
        request,
        "inicio.html",
        {
            "fecha_hoy": hoy,
            "fecha_hoy_texto": fecha_hoy_texto,
            "porcentaje_disponible": stock["porcentaje_disponible"],

            "reservas_activas": stats["reservas_activas"],
            "reservas_proximas_7_dias": stats["reservas_proximas_7_dias"],

            "articulos_totales": articulos_totales,
            "articulos_disponibles": articulos_disponibles,

            "cotizaciones_pendientes": stats["cotizaciones_pendientes"],
            "cotizaciones_mes": stats["cotizaciones_mes"],
            "monto_cotizado_mes": stats["monto_cotizado_mes"] or 0,

            "proximos_eventos": proximos_eventos,

            "alertas_inventario": alertas_inventario,
            "alertas_inventario_count": alertas_inventario_count,

            "entregas_hoy": entregas_hoy,
            "retiros_hoy": stats["retiros_hoy"],
            "pendientes_preparar": stats["pendientes_preparar"],
            "devoluciones_pendientes": stats["devoluciones_pendientes"],
            "en_mantencion": 0,
            "registros_merma": registros_merma,
            "ciclo": [
                {"etiqueta": etiqueta, "valor": valor, "url": url}
                for etiqueta, valor, url in ciclo
            ],

            "ingresos_mensuales": ingresos_mensuales,
            "categorias_solicitadas": categorias_solicitadas,
            "productos_mas_arrendados": productos_mas_arrendados,
            "clientes_frecuentes": clientes_frecuentes,

            "usuario_nombre": usuario_nombre,
            "usuario_rol": usuario_rol,
            "usuario_iniciales": usuario_iniciales,
        },
    )


# INVENTARIO

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

def _stock_desde_post(post, actual_total=0, actual_trabajable=0):
    """Lee y valida stock total y trabajable. Devuelve (total, trabajable, error)."""
    total = _entero(post.get("stock_total"), -1)
    trabajable = _entero(post.get("stock_trabajable"), -1)
    if total < 0 or trabajable < 0:
        return actual_total, actual_trabajable, "El stock debe ser un número entero igual o mayor que cero."
    if trabajable > total:
        return actual_total, actual_trabajable, "El stock trabajable no puede ser mayor que el stock total."
    return total, trabajable, None


def unidades_fuera_de_bodega(articulo_ids):
    """Unidades despachadas que siguen en clientes (aún sin devolución registrada), por artículo."""
    salidas = (
        DetalleDespacho.objects
        .filter(articulo_id__in=articulo_ids, despacho__servicio__estado__in=ESTADOS_EN_CLIENTE)
        .exclude(despacho__estado=Despacho.Estado.CANCELADO)
        .values("articulo_id")
        .annotate(total=Sum("cantidad"))
    )
    resueltas = (
        DetalleDevolucion.objects
        .filter(articulo_id__in=articulo_ids, devolucion__servicio__estado__in=ESTADOS_EN_CLIENTE)
        .values("articulo_id")
        .annotate(total=Sum(F("cantidad_buena") + F("cantidad_danada") + F("cantidad_perdida")))
    )
    resultado = {fila["articulo_id"]: fila["total"] or 0 for fila in salidas}
    for fila in resueltas:
        resultado[fila["articulo_id"]] = max(0, resultado.get(fila["articulo_id"], 0) - (fila["total"] or 0))
    return resultado


# Relaciones que impiden eliminar un artículo (los movimientos de stock se borran con él).
RELACIONES_ARTICULO_EN_USO = (
    DetalleServicio, DetallePreparacion, DetalleDespacho, DetalleDevolucion, Merma,
)


def _articulos_en_uso(articulo_ids):
    """IDs de artículos usados en alguna reserva u operación, con un solo viaje a la BD."""
    ids = list(articulo_ids)
    if not ids:
        return set()

    consultas = [
        modelo.objects
        .filter(articulo_id__in=ids)
        .values_list("articulo_id", flat=True)
        for modelo in RELACIONES_ARTICULO_EN_USO
    ]

    combinado = consultas[0]
    for consulta in consultas[1:]:
        combinado = combinado.union(consulta)

    return set(combinado)


def _articulo_en_uso(articulo):
    return bool(_articulos_en_uso([articulo.id]))


@solo_administrador
def inventario(request):
    negocio = request.usuario_panel.negocio

    if request.method == "POST" and request.POST.get("accion") == "eliminar":
        articulo = get_object_or_404(Articulo, id=request.POST.get("articulo_id"), negocio=negocio)
        # Un producto usado en operaciones no se elimina, para no perder historial.
        if _articulo_en_uso(articulo):
            messages.error(request, f"No se puede eliminar {articulo.nombre}: tiene reservas u operaciones asociadas.")
            return redirect("gestion_inventario")

        nombre = articulo.nombre
        with transaction.atomic():
            articulo.movimientos.all().delete()
            articulo.delete()
        messages.success(request, f"Producto {nombre} eliminado.")
        return redirect("gestion_inventario")

    if request.method == "POST" and request.POST.get("accion") == "crear":
        categoria = get_object_or_404(Categoria, id=request.POST.get("categoria_id"), negocio=negocio)
        nombre = request.POST.get("nombre", "").strip()
        precio = _entero(request.POST.get("precio_arriendo"), -1)
        stock_total, stock_trabajable, error = _stock_desde_post(request.POST)

        if not nombre:
            error = "El nombre del producto es obligatorio."
        elif precio < 0:
            error = "El precio de arriendo debe ser un número igual o mayor que cero."

        codigo = request.POST.get("codigo", "").strip() or generar_codigo_producto(categoria)
        if not error and Articulo.objects.filter(codigo=codigo).exists():
            error = f"Ya existe un producto con el código {codigo}."

        if error:
            messages.error(request, f"No se creó el producto: {error}")
            return redirect("gestion_inventario")

        with transaction.atomic():
            articulo = Articulo.objects.create(
                negocio=negocio,
                categoria=categoria,
                codigo=codigo,
                nombre=nombre,
                categoria_label=request.POST.get("categoria_label", "").strip() or categoria.nombre,
                descripcion=request.POST.get("descripcion", "").strip(),
                descripcion_larga=request.POST.get("descripcion_larga", "").strip(),
                dimensiones=request.POST.get("dimensiones", "").strip(),
                material=request.POST.get("material", "").strip(),
                capacidad=request.POST.get("capacidad", "").strip(),
                color=request.POST.get("color", "").strip(),
                precio_arriendo=precio,
                costo_reposicion=max(0, _entero(request.POST.get("costo_reposicion"), 0)),
                unidad_precio=request.POST.get("unidad_precio", "").strip() or "Por unidad",
                imagen=request.POST.get("imagen", "").strip(),
                imagenes=[],
                stock_total=stock_total,
                stock_trabajable=stock_trabajable,
                destacado=request.POST.get("destacado") == "on",
                activo=request.POST.get("activo") == "on",
            )
            if stock_total:
                MovimientoInventario.objects.create(
                    articulo=articulo,
                    usuario=request.usuario_panel,
                    tipo="Ingreso",
                    cantidad=stock_total,
                    stock_anterior=0,
                    stock_nuevo=stock_total,
                    motivo="Stock inicial al crear el producto",
                    fecha=timezone.now(),
                )

        messages.success(request, f"Producto {articulo.nombre} creado con código {articulo.codigo}.")
        return redirect("gestion_inventario")

    inventario_qs = list(
        Articulo.objects
        .filter(negocio=negocio)
        .select_related("categoria")
        .order_by("nombre")
    )

    inventario_qs, stock = estado_stock(inventario_qs)
    en_uso = _articulos_en_uso([a.id for a in inventario_qs])
    fuera = unidades_fuera_de_bodega([a.id for a in inventario_qs])
    mermas = {
        fila["articulo_id"]: fila["total"] or 0
        for fila in (
            Merma.objects.filter(articulo__in=inventario_qs, anulada=False)
            .values("articulo_id").annotate(total=Sum(F("cantidad") - F("cantidad_reparada")))
        )
    }
    for articulo in inventario_qs:
        articulo.en_uso = articulo.id in en_uso
        articulo.fuera_de_bodega = fuera.get(articulo.id, 0)
        articulo.mermas_vigentes = mermas.get(articulo.id, 0)
        articulo.porcentaje_disponible = _porcentaje(articulo.stock_disponible, articulo.stock_trabajable)
        articulo.porcentaje_comprometido = min(
            100 - articulo.porcentaje_disponible,
            _porcentaje(articulo.stock_comprometido, articulo.stock_trabajable),
        )

    # Agrupado por categoría, con totales para ver de un vistazo cuánto queda libre.
    grupos = {}
    for articulo in inventario_qs:
        grupo = grupos.setdefault(articulo.categoria_id, {
            "categoria": articulo.categoria,
            "etiqueta": etiqueta_categoria(articulo.categoria),
            "productos": [],
        })
        grupo["productos"].append(articulo)
    categorias_inventario = sorted(grupos.values(), key=lambda g: g["etiqueta"].lower())
    for grupo in categorias_inventario:
        productos = grupo["productos"]
        grupo["total"] = sum(a.stock_total for a in productos)
        grupo["trabajable"] = sum(a.stock_trabajable for a in productos)
        grupo["disponible"] = sum(a.stock_disponible for a in productos)
        grupo["comprometido"] = sum(a.stock_comprometido for a in productos)
        grupo["en_cliente"] = sum(a.fuera_de_bodega for a in productos)
        grupo["porcentaje"] = _porcentaje(grupo["disponible"], grupo["trabajable"])
        grupo["porcentaje_comprometido"] = min(100 - grupo["porcentaje"], _porcentaje(grupo["comprometido"], grupo["trabajable"]))
        grupo["nivel"] = _nivel_stock(grupo["disponible"], grupo["trabajable"])
        grupo["bajos"] = sum(1 for a in productos if a.activo and a.nivel_stock in NIVELES_ALERTA)
        grupo["slug"] = slugify(grupo["categoria"].nombre) or f"cat-{grupo['categoria'].id}"

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
            "categorias_inventario": categorias_inventario,
            "categorias": categorias,
            "totales_inventario": {
                "productos": len(inventario_qs),
                "trabajable": stock["trabajable"],
                "disponible": stock["disponible"],
                "comprometido": stock["comprometido"],
                "en_cliente": sum(g["en_cliente"] for g in categorias_inventario),
                "bajos": stock["alertas_count"],
            },
        },
    )


@solo_administrador
def gestion_producto(request, id):
    articulo = get_object_or_404(
        Articulo.objects.select_related("categoria", "negocio"),
        id=id,
    )

    if request.method == "POST" and request.POST.get("accion") == "editar":
        nombre = request.POST.get("nombre", "").strip()
        precio = _entero(request.POST.get("precio_arriendo"), -1)
        categoria = Categoria.objects.filter(
            id=request.POST.get("categoria_id"), negocio=articulo.negocio
        ).first()
        stock_total, stock_trabajable, error = _stock_desde_post(
            request.POST, articulo.stock_total, articulo.stock_trabajable
        )

        if not nombre:
            error = "El nombre del producto es obligatorio."
        elif precio < 0:
            error = "El precio de arriendo debe ser un número igual o mayor que cero."
        elif categoria is None:
            error = "Selecciona una categoría válida."

        if error:
            messages.error(request, f"No se guardaron los cambios: {error}")
            return redirect(f"{reverse('gestion_producto', args=[articulo.id])}?editar=1")

        with transaction.atomic():
            articulo = Articulo.objects.select_for_update().get(id=articulo.id)
            anterior_total, anterior_trabajable = articulo.stock_total, articulo.stock_trabajable

            articulo.nombre = nombre
            articulo.categoria = categoria
            articulo.precio_arriendo = precio
            articulo.costo_reposicion = max(0, _entero(request.POST.get("costo_reposicion"), articulo.costo_reposicion))
            articulo.unidad_precio = request.POST.get("unidad_precio", "").strip() or "Por unidad"
            articulo.descripcion = request.POST.get("descripcion", "").strip()
            articulo.stock_total = stock_total
            articulo.stock_trabajable = stock_trabajable
            articulo.activo = request.POST.get("activo") == "on"
            articulo.save()

            # Cada cambio de stock queda en el historial de movimientos del producto.
            if (stock_total, stock_trabajable) != (anterior_total, anterior_trabajable):
                motivo = request.POST.get("motivo", "").strip() or "Ajuste manual desde el panel"
                MovimientoInventario.objects.create(
                    articulo=articulo,
                    usuario=request.usuario_panel,
                    tipo="Ajuste",
                    cantidad=stock_total - anterior_total,
                    stock_anterior=anterior_total,
                    stock_nuevo=stock_total,
                    motivo=motivo[:255],
                    observaciones=(
                        f"Stock trabajable: {anterior_trabajable} → {stock_trabajable}."
                    ),
                    fecha=timezone.now(),
                )

        comprometido = comprometido_vigente([articulo.id]).get(articulo.id, 0)
        aviso = ""
        if comprometido > stock_trabajable:
            aviso = (
                f" Atención: hay {comprometido} unidades comprometidas en reservas vigentes, "
                "más que el stock trabajable."
            )
        messages.success(
            request,
            f"{articulo.nombre} actualizado: stock total {stock_total}, "
            f"trabajable {stock_trabajable}, disponible {max(0, stock_trabajable - comprometido)}.{aviso}",
        )
        return redirect("gestion_inventario")

    comprometido = comprometido_vigente([articulo.id]).get(articulo.id, 0)

    movimientos = (
        MovimientoInventario.objects
        .filter(articulo=articulo)
        .select_related("usuario", "servicio")
        .order_by("-fecha", "-id")
    )

    return render(
        request,
        "producto-admin.html",
        {
            "articulo": articulo,
            "movimientos": movimientos,
            "categorias": Categoria.objects.filter(negocio=articulo.negocio, activo=True).order_by("nombre"),
            "comprometido": comprometido,
            "disponible": max(0, articulo.stock_trabajable - comprometido),
        },
    )


@solo_administrador
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

        negocio = request.usuario_panel.negocio
        categoria = get_object_or_404(
            Categoria,
            negocio=negocio,
            nombre=categoria_nombre,
        )

        if codigo:
            producto_obj = get_object_or_404(
                Articulo,
                negocio=negocio,
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


# CLIENTES
@solo_administrador
def gestion_clientes(request):
    negocio = request.usuario_panel.negocio

    if request.method == "POST" and request.POST.get("accion") == "crear":
        rut = normalizar_rut(request.POST.get("rut", ""))
        if rut and Cliente.objects.filter(negocio=negocio, rut=rut).exists():
            return redirect(f"{reverse('gestion_clientes')}?aviso=rut-duplicado")

        Cliente.objects.create(
            negocio=negocio,
            rut=rut,
            nombre=request.POST.get("nombre", "").strip(),
            apellido=request.POST.get("apellido", "").strip(),
            telefono=normalizar_telefono(request.POST.get("telefono", "")),
            email=request.POST.get("email", "").strip().lower(),
            direccion=request.POST.get("direccion", "").strip(),
            comuna=request.POST.get("comuna", "").strip(),
            observaciones=request.POST.get("observaciones", "").strip(),
            activo=request.POST.get("activo") == "on",
        )
        return redirect("gestion_clientes")

    # Count y fecha de última reserva se calculan en SQL.
    clientes = (
        Cliente.objects
        .filter(negocio=negocio)
        .annotate(
            servicios_count=Count("servicios", distinct=True),
            ultima_reserva=Max("servicios__fecha_evento"),
        )
        .order_by("nombre", "apellido")
    )

    return render(
        request,
        "clientes.html",
        {"clientes": clientes},
    )

@solo_administrador
def gestion_cliente(request, id):
    cliente = get_object_or_404(
        Cliente.objects.select_related("negocio"),
        id=id,
    )

    if request.method == "POST" and request.POST.get("accion") == "eliminar":
        # Un cliente con cotizaciones o reservas no se elimina, para no perder historial.
        if Servicio.objects.filter(cliente=cliente).exists():
            destino = (
                reverse("gestion_clientes")
                if request.POST.get("origen") == "lista"
                else reverse("gestion_cliente", args=[cliente.id])
            )
            return redirect(f"{destino}?aviso=con-servicios")

        cliente.delete()

        return redirect(
            f"{reverse('gestion_clientes')}?aviso=eliminado"
        )

    if request.method == "POST" and request.POST.get("accion") == "editar":
        rut = normalizar_rut(request.POST.get("rut", ""))
        if rut and Cliente.objects.filter(negocio=cliente.negocio, rut=rut).exclude(id=cliente.id).exists():
            return redirect(f"{reverse('gestion_cliente', args=[cliente.id])}?aviso=rut-duplicado")

        cliente.nombre = request.POST.get("nombre", "").strip()
        cliente.apellido = request.POST.get("apellido", "").strip()
        cliente.rut = rut
        cliente.telefono = normalizar_telefono(request.POST.get("telefono", ""))
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

    servicios = list(
        Servicio.objects
        .filter(cliente=cliente)
        .prefetch_related("preparaciones", "despachos", "devoluciones")
        .order_by("-fecha_creacion")
    )
    _totales_devolucion(servicios)
    for servicio in servicios:
        servicio.preparacion = next(iter(servicio.preparaciones.all()), None)
        servicio.despacho = next((d for d in servicio.despachos.all() if d.estado != Despacho.Estado.CANCELADO), None)
        servicio.es_cotizacion = servicio.estado in (Servicio.Estado.COTIZACION, Servicio.Estado.CONTACTADO)

    return render(
        request,
        "cliente.html",
        {
            "cliente": cliente,
            "servicios": servicios,
            "mermas": Merma.objects.filter(servicio__cliente=cliente).select_related("articulo", "servicio")[:20],
            "historial": (
                HistorialServicio.objects.filter(servicio__cliente=cliente)
                .select_related("usuario", "servicio")[:25]
            ),
        },
    )


# COTIZACIONES / SERVICIO
@solo_administrador
def gestion_cotizaciones(request):
    negocio = request.usuario_panel.negocio

    if request.method == "POST" and request.POST.get("accion") == "crear":
        cliente = get_object_or_404(
            Cliente,
            id=request.POST.get("cliente_id"),
            negocio=negocio,
        )

        codigo = f"COT-{timezone.localdate():%Y%m%d}-{uuid4().hex[:6].upper()}"

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
                fecha_solicitud=timezone.localdate(),
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

    # Filtros de la lista: texto (nombre, RUT o correo), estado y rango de fecha del evento.
    filtros = {
        "q": request.GET.get("q", "").strip(),
        "estado": request.GET.get("estado", "").strip(),
        "desde": request.GET.get("desde", "").strip(),
        "hasta": request.GET.get("hasta", "").strip(),
    }

    cotizaciones = (
        Servicio.objects
        .filter(negocio=negocio)
        .select_related("cliente")
        .prefetch_related("categorias_solicitadas")
        .order_by("-fecha_creacion")
    )

    if filtros["q"]:
        texto = filtros["q"]
        rut = normalizar_rut(texto)
        condicion = (
            Q(cliente__nombre__icontains=texto)
            | Q(cliente__apellido__icontains=texto)
            | Q(cliente__email__icontains=texto)
            | Q(cliente__rut__icontains=texto)
        )
        if rut:
            condicion |= Q(cliente__rut__icontains=rut)
        partes = texto.split()
        if len(partes) > 1:
            condicion |= Q(cliente__nombre__icontains=partes[0], cliente__apellido__icontains=" ".join(partes[1:]))
        cotizaciones = cotizaciones.filter(condicion)

    if filtros["estado"] in Servicio.Estado.values:
        cotizaciones = cotizaciones.filter(estado=filtros["estado"])

    # Aceptadas por el cliente desde su cuenta, a la espera de que el administrador confirme.
    por_confirmar = Servicio.objects.filter(
        negocio=negocio, estado=Servicio.Estado.CONTACTADO, aceptada_cliente__isnull=False
    )
    filtros["aceptadas"] = request.GET.get("aceptadas") == "1"
    if filtros["aceptadas"]:
        cotizaciones = cotizaciones.filter(estado=Servicio.Estado.CONTACTADO, aceptada_cliente__isnull=False)

    for clave, lookup in (("desde", "fecha_evento__gte"), ("hasta", "fecha_evento__lte")):
        try:
            cotizaciones = cotizaciones.filter(**{lookup: date.fromisoformat(filtros[clave])})
        except ValueError:
            filtros[clave] = ""

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
            "filtros": filtros,
            "estados": Servicio.Estado.choices,
            "por_confirmar": por_confirmar.count(),
        },
    )

def _recalcular_totales(servicio):
    servicio.subtotal = (
        DetalleServicio.objects
        .filter(servicio=servicio)
        .aggregate(total=Sum("subtotal"))["total"]
        or 0
    )
    servicio.total = max(0, servicio.subtotal - servicio.descuento)
    servicio.save(update_fields=["subtotal", "total", "fecha_actualizacion"])


def _mensaje_faltantes(faltantes):
    detalle = "; ".join(
        f"{f['articulo'].nombre}: solicitado {f['solicitado']}, disponible {f['disponible']}"
        for f in faltantes
    )
    return f"No hay stock suficiente para las fechas del evento. {detalle}."


def _sumar_articulo(servicio, articulo, cantidad):
    """Suma `cantidad` del artículo al servicio. Devuelve un mensaje de error o None si se agregó."""
    with transaction.atomic():
        # Si la reserva ya bloquea stock, la nueva cantidad también debe caber.
        if servicio.estado in ESTADOS_QUE_BLOQUEAN:
            articulo = Articulo.objects.select_for_update().get(id=articulo.id)
            actual = (
                DetalleServicio.objects
                .filter(servicio=servicio, articulo=articulo)
                .aggregate(total=Sum("cantidad"))["total"]
                or 0
            )
            inicio, fin = periodo_servicio(servicio)
            resultado = calcular_disponibilidad(
                articulo, inicio, fin, excluir_servicio=servicio, solicitado=actual + cantidad
            )
            if resultado["faltante"]:
                return _mensaje_faltantes([resultado])

        detalle = DetalleServicio.objects.filter(servicio=servicio, articulo=articulo).first()
        if detalle:
            detalle.cantidad += cantidad
        else:
            detalle = DetalleServicio(servicio=servicio, articulo=articulo, cantidad=cantidad)
        detalle.precio_unitario = articulo.precio_arriendo
        detalle.subtotal = detalle.cantidad * detalle.precio_unitario
        detalle.save()
        _recalcular_totales(servicio)
    return None


def _agregar_articulo(request, servicio):
    articulo = get_object_or_404(
        Articulo,
        id=request.POST.get("articulo_id"),
        negocio=servicio.negocio,
        activo=True,
    )
    cantidad = max(1, _entero(request.POST.get("cantidad"), 1))
    error = _sumar_articulo(servicio, articulo, cantidad)
    if error:
        messages.error(request, error)
    else:
        messages.success(request, f"Se agregó {articulo.nombre} a la cotización.")


def _agregar_articulos(request, servicio):
    """Agrega varias filas en una sola transacción y recalcula totales una sola vez."""
    ids = request.POST.getlist("articulo_id")
    cantidades = request.POST.getlist("cantidad")

    if len(ids) != len(cantidades):
        messages.error(
            request,
            "El formulario llegó incompleto. Recarga la página e inténtalo de nuevo.",
        )
        return

    pedidos = {}
    for articulo_id, texto in zip(ids, cantidades):
        texto = (texto or "").strip()

        if not texto or texto == "0":
            continue

        if not articulo_id.isdigit() or not texto.isdigit() or int(texto) <= 0:
            messages.error(
                request,
                "Las cantidades deben ser números enteros mayores que 0. No se agregó nada.",
            )
            return

        articulo_id = int(articulo_id)
        pedidos[articulo_id] = pedidos.get(articulo_id, 0) + int(texto)

    if not pedidos:
        messages.error(request, "Escribe la cantidad de al menos un producto.")
        return

    inicio, fin = periodo_servicio(servicio)
    agregados = []
    errores = []

    with transaction.atomic():
        articulos_qs = (
            Articulo.objects
            .filter(
                id__in=pedidos,
                negocio=servicio.negocio,
                activo=True,
            )
        )

        if servicio.estado in ESTADOS_QUE_BLOQUEAN:
            articulos_qs = articulos_qs.select_for_update()

        articulos = {articulo.id: articulo for articulo in articulos_qs}

        detalles_qs = DetalleServicio.objects.filter(
            servicio=servicio,
            articulo_id__in=pedidos,
        )
        if servicio.estado in ESTADOS_QUE_BLOQUEAN:
            detalles_qs = detalles_qs.select_for_update()

        existentes = {
            detalle.articulo_id: detalle
            for detalle in detalles_qs
        }

        crear = []
        actualizar = []

        for articulo_id, cantidad in pedidos.items():
            articulo = articulos.get(articulo_id)

            if articulo is None:
                errores.append(
                    "Uno de los productos ya no está disponible en el catálogo."
                )
                continue

            detalle = existentes.get(articulo_id)
            cantidad_actual = detalle.cantidad if detalle else 0

            if inicio:
                disponibilidad = calcular_disponibilidad(
                    articulo,
                    inicio,
                    fin,
                    excluir_servicio=servicio,
                    solicitado=(
                        cantidad_actual + cantidad
                        if servicio.estado in ESTADOS_QUE_BLOQUEAN
                        else None
                    ),
                )

                if servicio.estado in ESTADOS_QUE_BLOQUEAN:
                    if disponibilidad["faltante"]:
                        errores.append(_mensaje_faltantes([disponibilidad]))
                        continue
                elif disponibilidad["disponible"] <= 0:
                    errores.append(
                        f"{articulo.nombre} no tiene stock disponible para la fecha del evento."
                    )
                    continue

            if detalle is None:
                detalle = DetalleServicio(
                    servicio=servicio,
                    articulo=articulo,
                    cantidad=cantidad,
                    precio_unitario=articulo.precio_arriendo,
                    subtotal=articulo.precio_arriendo * cantidad,
                )
                crear.append(detalle)
            else:
                detalle.cantidad += cantidad
                detalle.precio_unitario = articulo.precio_arriendo
                detalle.subtotal = detalle.cantidad * detalle.precio_unitario
                actualizar.append(detalle)

            agregados.append(f"{cantidad} × {articulo.nombre}")

        if crear:
            DetalleServicio.objects.bulk_create(crear)

        if actualizar:
            DetalleServicio.objects.bulk_update(
                actualizar,
                ["cantidad", "precio_unitario", "subtotal"],
            )

        if crear or actualizar:
            _recalcular_totales(servicio)

    if agregados:
        messages.success(
            request,
            f"Se agregaron {len(agregados)} producto"
            f"{'s' if len(agregados) != 1 else ''}: "
            f"{', '.join(agregados)}.",
        )

    for error in errores:
        messages.error(request, error)


def _cargar_sugeridos(request, servicio):
    """Agrega los sugeridos sin ejecutar una consulta por cada regla."""
    preset = PREDETERMINADOS_EVENTO.get(servicio.tipo_servicio, {})

    if servicio.categorias_por_definir:
        claves = list(preset.keys())
    else:
        claves = list(
            servicio.categorias_solicitadas.values_list("nombre", flat=True)
        )

    invitados = servicio.cantidad_personas or 0

    reglas = []
    for clave in claves:
        reglas.extend(preset.get(clave, []))

    if not reglas:
        messages.error(
            request,
            "No hay artículos sugeridos nuevos para este tipo de evento y categorías.",
        )
        return

    codigos = {regla["codigo"] for regla in reglas}

    existentes = set(
        DetalleServicio.objects
        .filter(servicio=servicio, articulo__codigo__in=codigos)
        .values_list("articulo__codigo", flat=True)
    )

    articulos = {
        articulo.codigo: articulo
        for articulo in Articulo.objects.filter(
            negocio=servicio.negocio,
            codigo__in=codigos,
            activo=True,
        )
    }

    nuevos = []
    usados = set(existentes)

    for regla in reglas:
        codigo = regla["codigo"]

        if codigo in usados:
            continue

        articulo = articulos.get(codigo)
        cantidad = calcular_cantidad_predeterminada(regla, invitados)

        if articulo is None or cantidad <= 0:
            continue

        nuevos.append(
            DetalleServicio(
                servicio=servicio,
                articulo=articulo,
                cantidad=cantidad,
                precio_unitario=articulo.precio_arriendo,
                subtotal=articulo.precio_arriendo * cantidad,
            )
        )
        usados.add(codigo)

    if not nuevos:
        messages.error(
            request,
            "No hay artículos sugeridos nuevos para este tipo de evento y categorías.",
        )
        return

    with transaction.atomic():
        DetalleServicio.objects.bulk_create(nuevos)
        _recalcular_totales(servicio)

    messages.success(
        request,
        f"Se agregaron {len(nuevos)} artículos sugeridos. Revisa y ajusta las cantidades.",
    )


# Estados que se pueden elegir a mano. Preparación, despacho y devolución solo avanzan
# con su acción específica, que es la que valida y deja historial.
ESTADOS_EDITABLES = (Servicio.Estado.COTIZACION, Servicio.Estado.CONTACTADO, Servicio.Estado.CONFIRMADO)
TRANSICIONES_MANUALES = {
    Servicio.Estado.COTIZACION: (Servicio.Estado.CONTACTADO, Servicio.Estado.CONFIRMADO, Servicio.Estado.CANCELADO),
    Servicio.Estado.CONTACTADO: (Servicio.Estado.COTIZACION, Servicio.Estado.CONFIRMADO, Servicio.Estado.CANCELADO),
    Servicio.Estado.CONFIRMADO: (Servicio.Estado.CANCELADO,),
}


def _cambiar_estado(request, servicio, nuevo_estado):
    if nuevo_estado not in Servicio.Estado.values or nuevo_estado == servicio.estado:
        return

    if nuevo_estado not in TRANSICIONES_MANUALES.get(servicio.estado, ()):
        messages.error(
            request,
            f"No se puede pasar de {servicio.get_estado_display()} a {Servicio.Estado(nuevo_estado).label} "
            "desde aquí. Usa la acción correspondiente (preparación, despacho o devolución).",
        )
        return

    anterior = servicio.estado

    if nuevo_estado == Servicio.Estado.CANCELADO:
        try:
            cancelar_servicio(servicio.id, request.usuario_panel, request.POST.get("motivo", ""))
        except OperacionInvalida as error:
            messages.error(request, error.mensaje)
            return
        messages.success(request, "Servicio cancelado. Si tenía stock comprometido, quedó liberado.")
        return

    # Pasar a un estado que bloquea stock exige comprobar disponibilidad en ese momento.
    if nuevo_estado in ESTADOS_QUE_BLOQUEAN and servicio.estado not in ESTADOS_QUE_BLOQUEAN:
        try:
            servicio = confirmar_servicio(servicio.id, nuevo_estado)
        except StockInsuficiente as error:
            messages.error(request, _mensaje_faltantes(error.faltantes))
            return
        except ValueError as error:
            messages.error(request, f"No se puede confirmar: {error}")
            return
        registrar_historial(servicio, "Confirmar reserva", request.usuario_panel, anterior)
        registrar_movimientos_servicio(
            servicio, "Reserva confirmada", request.usuario_panel, 1,
            f"Reserva {servicio.codigo} confirmada: unidades comprometidas (no modifica el stock)",
        )
        messages.success(request, f"Reserva confirmada. Estado actual: {Servicio.Estado(nuevo_estado).label}.")
        return

    servicio.estado = nuevo_estado
    servicio.save(update_fields=["estado", "fecha_actualizacion"])
    registrar_historial(servicio, "Cambiar estado", request.usuario_panel, anterior)
    messages.success(request, f"Estado actualizado a {Servicio.Estado(nuevo_estado).label}.")


@solo_administrador
def gestion_cotizacion(request, id):
    servicio = get_object_or_404(
        Servicio.objects.select_related("cliente", "negocio"),
        id=id,
    )

    if request.method == "POST":
        accion = request.POST.get("accion")

        if accion in ("agregar_articulo", "agregar_articulos", "quitar_articulo", "cargar_sugeridos") and servicio.estado not in ESTADOS_EDITABLES:
            messages.error(
                request,
                f"La reserva está {servicio.get_estado_display().lower()}: sus artículos ya no se pueden modificar.",
            )
            return redirect("gestion_cotizacion", id=servicio.id)

        if accion == "agregar_articulo":
            _agregar_articulo(request, servicio)
        elif accion == "agregar_articulos":
            _agregar_articulos(request, servicio)
        elif accion == "quitar_articulo":
            with transaction.atomic():
                DetalleServicio.objects.filter(servicio=servicio, id=request.POST.get("detalle_id")).delete()
                _recalcular_totales(servicio)
            messages.success(request, "Artículo quitado de la cotización.")
        elif accion == "cargar_sugeridos":
            _cargar_sugeridos(request, servicio)
        elif accion == "confirmar":
            _cambiar_estado(request, servicio, Servicio.Estado.CONFIRMADO)
        elif accion == "marcar_enviada":
            # Cotización entregada por WhatsApp o teléfono, sin pasar por el correo del sistema.
            medio = request.POST.get("medio", "").strip()
            if medio not in ("WhatsApp", "Teléfono", "En persona"):
                messages.error(request, "Indica por qué medio enviaste la cotización.")
            elif not servicio.detalles.exists():
                messages.error(request, "Agrega al menos un producto antes de enviar la cotización.")
            elif servicio.estado != Servicio.Estado.COTIZACION:
                messages.error(request, "Esta cotización ya figura como enviada.")
            else:
                anterior = servicio.estado
                servicio.estado = Servicio.Estado.CONTACTADO
                servicio.save(update_fields=["estado", "fecha_actualizacion"])
                registrar_historial(servicio, f"Cotización enviada por {medio}", request.usuario_panel, anterior)
                messages.success(request, f"Listo: la cotización quedó como enviada por {medio}. Cuando el cliente acepte, confirma la reserva.")
        elif accion == "cancelar":
            _cambiar_estado(request, servicio, Servicio.Estado.CANCELADO)
        elif accion == "rechazar":
            # El cliente no aceptó la cotización: queda cancelada con el motivo del rechazo.
            motivo = request.POST.get("motivo_rechazo", "").strip()
            detalle = request.POST.get("detalle_rechazo", "").strip()[:200]
            if motivo not in MOTIVOS_RECHAZO:
                messages.error(request, "Indica por qué el cliente no aceptó la cotización.")
            elif servicio.estado not in (Servicio.Estado.COTIZACION, Servicio.Estado.CONTACTADO):
                messages.error(request, "Solo una cotización que aún no se confirma puede marcarse como rechazada.")
            else:
                try:
                    cancelar_servicio(servicio.id, request.usuario_panel,
                                      motivo + (f": {detalle}" if detalle else ""), accion=ACCION_RECHAZO)
                except OperacionInvalida as error:
                    messages.error(request, error.mensaje)
                else:
                    messages.success(request, "La cotización quedó marcada como rechazada por el cliente.")
        elif accion == "cambiar_estado":
            _cambiar_estado(request, servicio, request.POST.get("estado", "").strip())

        # Si cambian los productos, lo que el cliente aceptó ya no es la misma cotización.
        if accion in ("agregar_articulo", "agregar_articulos", "quitar_articulo", "cargar_sugeridos") and servicio.aceptada_cliente:
            servicio.aceptada_cliente = None
            servicio.save(update_fields=["aceptada_cliente", "fecha_actualizacion"])
            messages.warning(request, "Cambiaste los productos: el cliente deberá aceptar nuevamente la cotización. Reenvíasela.")

        return redirect("gestion_cotizacion", id=servicio.id)

    detalles = list(
        DetalleServicio.objects
        .filter(servicio=servicio)
        .select_related("articulo")
        .order_by("articulo__nombre")
    )

    # Disponibilidad por artículo para las fechas del evento (sin contar este mismo servicio).
    por_articulo = {r["articulo_id"]: r for r in disponibilidad_servicio(servicio)}
    for detalle in detalles:
        detalle.disponibilidad = por_articulo.get(detalle.articulo_id)

    categorias = [etiqueta_categoria(c) for c in servicio.categorias_solicitadas.all()]
    hay_faltantes = any(r["faltante"] for r in por_articulo.values())

    return render(
        request,
        "cotizacion.html",
        {
            "servicio": servicio,
            "detalles": detalles,
            "categorias": categorias,
            "catalogo": _catalogo_cotizacion(servicio, detalles),
            "estados_servicio": [
                (valor, etiqueta) for valor, etiqueta in Servicio.Estado.choices
                if valor == servicio.estado or valor in TRANSICIONES_MANUALES.get(servicio.estado, ())
            ],
            "articulos_editables": servicio.estado in ESTADOS_EDITABLES,
            "bloquea_stock": servicio.estado in ESTADOS_QUE_BLOQUEAN,
            "puede_confirmar": (
                servicio.estado in (Servicio.Estado.COTIZACION, Servicio.Estado.CONTACTADO)
                and bool(detalles)
                and servicio.fecha_evento is not None
            ),
            "hay_faltantes": hay_faltantes,
            "envio": servicio.historial.filter(accion__startswith="Cotización enviada").select_related("usuario").first(),
            "envio_preferido": _medio_envio_preferido(servicio, detalles),
            "motivos_rechazo": MOTIVOS_RECHAZO,
            "aceptada": servicio.aceptada_cliente if servicio.estado == Servicio.Estado.CONTACTADO else None,
            "historial": servicio.historial.select_related("usuario")[:40],
            "cierre": (
                servicio.historial.filter(accion__in=[ACCION_RECHAZO, "Cancelar cotización", "Cancelar reserva"]).first()
                if servicio.estado == Servicio.Estado.CANCELADO else None
            ),
            "puede_cancelar": servicio.estado in ESTADOS_CANCELABLES,
        },
    )


def _catalogo_cotizacion(servicio, detalles):
    """
    Productos activos con stock disponible para la fecha del evento, agrupados por categoría
    (en orden alfabético). Los que no tienen unidades libres no se ofrecen.
    """
    inicio, fin = periodo_servicio(servicio)
    en_cotizacion = {d.articulo_id: d.cantidad for d in detalles}
    grupos = {}
    articulos = (
        Articulo.objects
        .filter(negocio=servicio.negocio, activo=True)
        .select_related("categoria")
        .order_by("nombre")
    )
    for articulo in articulos:
        if inicio:
            articulo.disponible_fecha = calcular_disponibilidad(
                articulo, inicio, fin, excluir_servicio=servicio
            )["disponible"]
        else:
            articulo.disponible_fecha = articulo.stock_trabajable
        if articulo.disponible_fecha <= 0:
            continue
        articulo.en_cotizacion = en_cotizacion.get(articulo.id, 0)
        grupo = grupos.setdefault(articulo.categoria_id, {
            "id": articulo.categoria_id,
            "etiqueta": etiqueta_categoria(articulo.categoria),
            "productos": [],
        })
        grupo["productos"].append(articulo)
    return sorted(grupos.values(), key=lambda g: g["etiqueta"].lower())


def _telefono_whatsapp(telefono):
    """Número para wa.me: solo dígitos y con código de Chile (56) si viene sin él."""
    digitos = re.sub(r"\D", "", telefono or "")
    if len(digitos) == 9 and digitos.startswith("9"):
        digitos = "56" + digitos
    return digitos if len(digitos) >= 10 else ""


def _formato_pesos(valor):
    return "$" + f"{int(valor or 0):,}".replace(",", ".")


def _medio_envio_preferido(servicio, detalles):
    """
    Cómo enviar la cotización según lo que el cliente eligió en el cotizador.
    Si falta el dato para ese medio (sin teléfono o sin correo), se usa el que esté disponible.
    """
    cliente = servicio.cliente
    whatsapp = _telefono_whatsapp(cliente.telefono)
    preferido = servicio.medio_contacto or ""
    if preferido == "WhatsApp" and not whatsapp:
        preferido = ""
    if preferido == "Llamada" and not cliente.telefono:
        preferido = ""
    if not preferido:
        preferido = "Correo" if cliente.email else ("WhatsApp" if whatsapp else "Llamada" if cliente.telefono else "")

    whatsapp_url = ""
    if whatsapp:
        lineas = [f"Hola {cliente.nombre}, te enviamos la cotización {servicio.codigo} de Entre Platos y Copas"
                  + (f" para tu {servicio.tipo_servicio.lower()}" if servicio.tipo_servicio else "")
                  + (f" del {servicio.fecha_evento:%d/%m/%Y}" if servicio.fecha_evento else "") + ":", ""]
        lineas += [f"• {d.cantidad} × {d.articulo.nombre}: {_formato_pesos(d.subtotal)}" for d in detalles]
        lineas += ["", f"Total: {_formato_pesos(servicio.total)}", "",
                   "¿Te gustaría confirmar la reserva? Quedamos atentos."]
        whatsapp_url = f"https://wa.me/{whatsapp}?text={quote(chr(10).join(lineas))}"

    return {
        "medio": preferido,
        "etiqueta": {"Correo": "correo", "WhatsApp": "WhatsApp", "Llamada": "teléfono"}.get(preferido, ""),
        "elegido_por_cliente": bool(servicio.medio_contacto) and preferido == servicio.medio_contacto,
        "whatsapp_url": whatsapp_url,
        "telefono": cliente.telefono,
        "email": cliente.email,
    }


# RESERVAS / SERVICIOS CONFIRMADOS
@solo_administrador
def gestion_reservas(request):
    negocio = request.usuario_panel.negocio

    reservas = (
        Servicio.objects
        .filter(negocio=negocio)
        .exclude(
            estado__in=[
                "Cotizacion",
                "Contactado",
                "Cancelado",
            ]
        )
        .select_related("cliente")
        .only(
            "id", "codigo", "estado", "tipo_servicio", "fecha_evento",
            "fecha_inicio", "fecha_termino", "total",
            "cliente__id", "cliente__nombre", "cliente__apellido", "cliente__rut",
        )
        .order_by("-fecha_evento", "-fecha_creacion")
    )

    return render(
        request,
        "reservas.html",
        {
            "reservas": reservas,
        },
    )

@solo_administrador
def gestion_reserva(request, id):
    servicio = get_object_or_404(
        Servicio.objects.select_related("cliente", "negocio"),
        id=id,
        negocio=request.usuario_panel.negocio,
    )

    if request.method == "POST" and request.POST.get("accion") == "generar_preparacion":
        return _generar_preparacion_y_redirigir(
            request,
            servicio.id,
            "gestion_reserva",
            servicio.id,
        )

    if request.method == "POST" and request.POST.get("accion") in ("cancelar", "cerrar"):
        try:
            if request.POST["accion"] == "cancelar":
                cancelar_servicio(
                    servicio.id,
                    request.usuario_panel,
                    request.POST.get("motivo", ""),
                )
                messages.success(
                    request,
                    "Reserva cancelada. El stock comprometido quedó liberado.",
                )
            else:
                cerrar_servicio(servicio.id, request.usuario_panel)
                messages.success(
                    request,
                    "Reserva cerrada. Ya solo se puede consultar.",
                )
        except OperacionInvalida as error:
            messages.error(request, " ".join([error.mensaje, *error.detalles]))

        return redirect("gestion_reserva", id=servicio.id)

    detalles = list(
        DetalleServicio.objects
        .filter(servicio=servicio)
        .select_related("articulo")
    )

    preparacion = (
        Preparacion.objects
        .filter(servicio=servicio)
        .select_related("usuario")
        .first()
    )

    despacho = (
        servicio.despachos
        .exclude(estado=Despacho.Estado.CANCELADO)
        .select_related("usuario")
        .first()
    )

    historial = list(
        servicio.historial
        .select_related("usuario")
        .order_by("-fecha", "-id")[:30]
    )

    return render(
        request,
        "reserva.html",
        {
            "servicio": servicio,
            "detalles": detalles,
            "preparacion": preparacion,
            "puede_generar_preparacion": (
                servicio.estado == Servicio.Estado.CONFIRMADO
                and preparacion is None
                and bool(detalles)
            ),
            "historial": historial,
            "despacho": despacho,
            "puede_cancelar": servicio.estado in ESTADOS_CANCELABLES,
            "puede_cerrar": servicio.estado == Servicio.Estado.FINALIZADO,
            "con_devolucion": servicio.estado in (
                Servicio.Estado.DESPACHADO,
                Servicio.Estado.DEVOLUCION_PARCIAL,
                Servicio.Estado.FINALIZADO,
                Servicio.Estado.CERRADO,
            ),
        },
    )


def _generar_preparacion_y_redirigir(request, servicio_id, vista_error, *args):
    try:
        preparacion = generar_preparacion(servicio_id, request.usuario_panel)
    except OperacionInvalida as error:
        messages.error(request, error.mensaje)
        return redirect(vista_error, *args)
    except Servicio.DoesNotExist:
        messages.error(request, "La reserva no existe.")
        return redirect(vista_error, *args)
    messages.success(request, "Preparación generada. Registra las cantidades a medida que se preparan.")
    return redirect("gestion_preparacion_documento", id=preparacion.id)


# PREPARACIÓN
@solo_administrador
def gestion_preparacion(request):
    negocio = request.usuario_panel.negocio

    if request.method == "POST" and request.POST.get("accion") == "generar":
        servicio_id = _entero(request.POST.get("servicio_id"), 0)
        if not Servicio.objects.filter(id=servicio_id, negocio=negocio).exists():
            messages.error(request, "La reserva no existe.")
            return redirect("gestion_preparacion")
        return _generar_preparacion_y_redirigir(request, servicio_id, "gestion_preparacion")

    filtros = {
        "estado": request.GET.get("estado", "").strip(),
        "desde": request.GET.get("desde", "").strip(),
        "hasta": request.GET.get("hasta", "").strip(),
        "q": request.GET.get("q", "").strip(),
        "responsable": request.GET.get("responsable", "").strip(),
    }

    preparaciones = (
        Preparacion.objects
        .filter(servicio__negocio=negocio)
        .select_related("servicio", "servicio__cliente", "usuario")
        .order_by("servicio__fecha_evento", "-id")
    )
    if filtros["estado"] in Preparacion.Estado.values:
        preparaciones = preparaciones.filter(estado=filtros["estado"])
    desde = _fecha_desde_texto(filtros["desde"])
    hasta = _fecha_desde_texto(filtros["hasta"])
    if desde:
        preparaciones = preparaciones.filter(servicio__fecha_evento__gte=desde)
    if hasta:
        preparaciones = preparaciones.filter(servicio__fecha_evento__lte=hasta)
    if filtros["q"]:
        texto = filtros["q"]
        condicion = (
            Q(servicio__cliente__nombre__icontains=texto)
            | Q(servicio__cliente__apellido__icontains=texto)
            | Q(servicio__codigo__icontains=texto)
        )
        if normalizar_rut(texto):
            condicion |= Q(servicio__cliente__rut__icontains=normalizar_rut(texto))
        preparaciones = preparaciones.filter(condicion)
    if filtros["responsable"].isdigit():
        preparaciones = preparaciones.filter(usuario_id=int(filtros["responsable"]))

    preparaciones = list(preparaciones)
    totales = {
        fila["preparacion_id"]: fila
        for fila in (
            DetallePreparacion.objects
            .filter(preparacion__in=preparaciones)
            .values("preparacion_id")
            .annotate(requeridas=Sum("cantidad_solicitada"), preparadas=Sum("cantidad_preparada"))
        )
    }
    for preparacion in preparaciones:
        fila = totales.get(preparacion.id, {})
        requeridas, preparadas = fila.get("requeridas") or 0, fila.get("preparadas") or 0
        preparacion.unidades_requeridas = requeridas
        preparacion.unidades_preparadas = preparadas
        preparacion.porcentaje = round(preparadas * 100 / requeridas) if requeridas else 0

    por_preparar = (
        Servicio.objects
        .filter(negocio=negocio, estado=Servicio.Estado.CONFIRMADO, preparaciones__isnull=True)
        .select_related("cliente")
        .annotate(unidades=Sum("detalles__cantidad"))
        .order_by("fecha_evento")
    )

    return render(
        request,
        "preparacion.html",
        {
            "preparaciones": preparaciones,
            "por_preparar": por_preparar,
            "filtros": filtros,
            "estados_preparacion": Preparacion.Estado.choices,
            "responsables": Usuario.objects.filter(preparaciones__isnull=False).distinct().order_by("nombre"),
        },
    )


def _fecha_desde_texto(texto):
    try:
        return date.fromisoformat(texto)
    except (TypeError, ValueError):
        return None


@solo_administrador
def gestion_preparacion_documento(request, id):
    preparacion = get_object_or_404(
        Preparacion.objects.select_related(
            "servicio",
            "servicio__cliente",
            "usuario",
            "finalizada_por",
        ),
        id=id,
        servicio__negocio=request.usuario_panel.negocio,
    )

    errores = []
    enviados = {}

    if request.method == "POST":
        accion = request.POST.get("accion")
        ids = request.POST.getlist("detalle_id")
        cantidades = request.POST.getlist("cantidad_preparada")
        # La observación por artículo es opcional: si no viene, se conserva la guardada.
        observaciones_detalle = request.POST.getlist("observacion_detalle") or [None] * len(ids)

        try:
            if accion == "guardar":
                if not (len(ids) == len(cantidades) == len(observaciones_detalle)):
                    raise OperacionInvalida("El formulario llegó incompleto. Recarga la página e inténtalo de nuevo.")
                guardar_avance(
                    preparacion.id,
                    request.usuario_panel,
                    list(zip(ids, cantidades, observaciones_detalle)),
                    request.POST.get("observaciones", ""),
                )
                messages.success(request, "Avance guardado.")
            elif accion == "finalizar":
                finalizar_preparacion(preparacion.id, request.usuario_panel)
                messages.success(request, "Preparación finalizada. La reserva quedó en estado Preparado.")
            elif accion == "observaciones":
                guardar_avance(preparacion.id, request.usuario_panel, [], request.POST.get("observaciones", ""))
                messages.success(request, "Observaciones guardadas.")
            elif accion == "completar":
                # La preparación se trabaja con las hojas impresas; lo enviado se verifica en Despacho.
                # Aquí solo se deja todo como preparado y la reserva pasa a "Preparado".
                with transaction.atomic():
                    filas = [
                        (str(d.id), str(d.cantidad_solicitada), None)
                        for d in DetallePreparacion.objects.filter(preparacion=preparacion)
                    ]
                    guardar_avance(preparacion.id, request.usuario_panel, filas, request.POST.get("observaciones"))
                    finalizar_preparacion(preparacion.id, request.usuario_panel)
                messages.success(request, "Pedido marcado como preparado. Ya puedes registrar su despacho.")
            else:
                raise OperacionInvalida("Acción no reconocida.")
            return redirect("gestion_preparacion_documento", id=preparacion.id)
        except OperacionInvalida as error:
            errores = [error.mensaje, *error.detalles]
            # Se conserva lo que la persona escribió para que no tenga que repetirlo.
            if accion == "guardar":
                enviados = {
                    detalle_id: {"cantidad": cantidad, "observacion": observacion or ""}
                    for detalle_id, cantidad, observacion in zip(ids, cantidades, observaciones_detalle)
                }
            preparacion.refresh_from_db()
            if accion == "guardar":
                preparacion.observaciones = request.POST.get("observaciones", preparacion.observaciones)

    detalles = list(
        DetallePreparacion.objects
        .filter(preparacion=preparacion)
        .select_related("articulo", "articulo__categoria")
        .order_by("articulo__categoria__nombre", "articulo__nombre")
    )
    for detalle in detalles:
        enviado = enviados.get(str(detalle.id))
        detalle.valor_cantidad = enviado["cantidad"] if enviado else detalle.cantidad_preparada
        detalle.valor_observacion = enviado["observacion"] if enviado else detalle.observaciones

    return render(
        request,
        "preparacion-documento.html",
        {
            "preparacion": preparacion,
            "servicio": preparacion.servicio,
            "detalles": detalles,
            "resumen": resumen_unidades(detalles),
            "editable": (
                preparacion.estado != Preparacion.Estado.COMPLETA
                and preparacion.servicio.estado == Servicio.Estado.PREPARACION
            ),
            "errores": errores,
            "despacho": preparacion.servicio.despachos.exclude(estado=Despacho.Estado.CANCELADO).first(),
            "por_categoria": _detalles_por_categoria(detalles),
        },
        status=400 if errores else 200,
    )


def _detalles_por_categoria(detalles):
    """Artículos de la preparación agrupados por categoría: una hoja impresa por cada grupo."""
    grupos = {}
    for detalle in detalles:
        categoria = detalle.articulo.categoria
        grupo = grupos.setdefault(categoria.id, {
            "id": categoria.id,
            "etiqueta": etiqueta_categoria(categoria),
            "detalles": [],
            "unidades": 0,
        })
        grupo["detalles"].append(detalle)
        grupo["unidades"] += detalle.cantidad_solicitada
    return sorted(grupos.values(), key=lambda g: g["etiqueta"].lower())


# DESPACHOS
@solo_administrador
def gestion_despachos(request):
    negocio = request.usuario_panel.negocio
    hoy = timezone.localdate()

    filtros = {
        "vista": request.GET.get("vista", "").strip(),
        "q": request.GET.get("q", "").strip(),
        "comuna": request.GET.get("comuna", "").strip(),
    }

    def filtrar_texto(qs, prefijo=""):
        if filtros["q"]:
            texto = filtros["q"]
            condicion = (
                Q(**{f"{prefijo}cliente__nombre__icontains": texto})
                | Q(**{f"{prefijo}cliente__apellido__icontains": texto})
                | Q(**{f"{prefijo}codigo__icontains": texto})
            )
            if normalizar_rut(texto):
                condicion |= Q(**{f"{prefijo}cliente__rut__icontains": normalizar_rut(texto)})
            qs = qs.filter(condicion)
        if filtros["comuna"]:
            qs = qs.filter(**{f"{prefijo}comuna_evento__icontains": filtros["comuna"]})
        return qs

    # Pendientes: reservas con la preparación finalizada que aún no salen.
    pendientes = filtrar_texto(
        Servicio.objects
        .filter(negocio=negocio, estado=Servicio.Estado.PREPARADO)
        .select_related("cliente")
        .order_by("fecha_evento")
    )
    despachos = filtrar_texto(
        Despacho.objects
        .filter(servicio__negocio=negocio)
        .select_related("servicio", "servicio__cliente", "usuario")
        .order_by("-fecha_despacho"),
        "servicio__",
    )

    if filtros["vista"] == "hoy":
        pendientes = pendientes.filter(fecha_evento=hoy)
        despachos = despachos.filter(fecha_despacho__date=hoy)
    elif filtros["vista"] == "semana":
        pendientes = pendientes.filter(fecha_evento__gte=hoy, fecha_evento__lte=hoy + timedelta(days=7))
        despachos = despachos.filter(servicio__fecha_evento__gte=hoy, servicio__fecha_evento__lte=hoy + timedelta(days=7))
    elif filtros["vista"] == "pendientes":
        despachos = despachos.none()
    elif filtros["vista"] == "despachados":
        pendientes = pendientes.none()

    unidades = {
        fila["despacho_id"]: fila["total"]
        for fila in DetalleDespacho.objects.filter(despacho__in=despachos).values("despacho_id").annotate(total=Sum("cantidad"))
    }
    despachos = list(despachos)
    for despacho in despachos:
        despacho.unidades = unidades.get(despacho.id, 0)

    return render(
        request,
        "despachos.html",
        {
            "despachos": despachos,
            "pendientes": pendientes,
            "filtros": filtros,
            "vistas": [("", "Todos"), ("hoy", "Hoy"), ("semana", "Próximos 7 días"), ("pendientes", "Pendientes"), ("despachados", "Despachados")],
        },
    )


def _fecha_hora_desde_texto(texto):
    """Lee el valor de un <input type="datetime-local"> (AAAA-MM-DDTHH:MM)."""
    try:
        valor = datetime.fromisoformat((texto or "").strip())
    except ValueError:
        return None
    return timezone.make_aware(valor) if timezone.is_naive(valor) else valor


@solo_administrador
def gestion_registrar_despacho(request, servicio_id):
    servicio = get_object_or_404(
        Servicio.objects.select_related("cliente"),
        id=servicio_id,
        negocio=request.usuario_panel.negocio,
    )
    vigente = Despacho.objects.filter(servicio=servicio).exclude(estado=Despacho.Estado.CANCELADO).first()
    if vigente:
        messages.error(request, "Esta reserva ya tiene un despacho registrado.")
        return redirect("gestion_despacho_documento", id=vigente.id)

    preparacion = Preparacion.objects.filter(servicio=servicio).first()
    usuario = request.usuario_panel
    datos = {
        "tipo_entrega": Despacho.TipoEntrega.DESPACHO if servicio.requiere_despacho else Despacho.TipoEntrega.RETIRO,
        "fecha_salida": timezone.localtime().strftime("%Y-%m-%dT%H:%M"),
        "responsable": f"{usuario.nombre} {usuario.apellido}".strip(),
        "receptor": "",
        "observaciones": "",
        "fecha_devolucion": (servicio.fecha_termino or servicio.fecha_evento or timezone.localdate()).isoformat(),
    }
    errores = []

    enviados, por_fila = {}, {}
    if request.method == "POST":
        datos = {campo: request.POST.get(campo, "").strip() for campo in datos}
        ids = request.POST.getlist("articulo_id")
        cantidades = request.POST.getlist("enviado")
        enviados = {int(i): c for i, c in zip(ids, cantidades) if i.isdigit()}
        try:
            despacho = registrar_despacho(
                servicio.id,
                usuario,
                datos["tipo_entrega"],
                _fecha_hora_desde_texto(datos["fecha_salida"]),
                datos["responsable"],
                datos["receptor"],
                datos["observaciones"],
                cantidades=enviados if ids else None,
                fecha_devolucion=_fecha_desde_texto(datos["fecha_devolucion"]),
            )
        except OperacionInvalida as error:
            errores = [error.mensaje, *error.detalles]
            por_fila = error.por_fila
        else:
            messages.success(request, "Despacho registrado. La reserva quedó en estado Despachado.")
            return redirect("gestion_despacho_documento", id=despacho.id)

    detalles = (
        list(preparacion.detalles.select_related("articulo").order_by("articulo__nombre"))
        if preparacion else []
    )
    for detalle in detalles:
        # Por defecto sale todo lo preparado; si el servidor rechazó el envío se conserva lo escrito.
        detalle.valor_enviado = enviados.get(detalle.articulo_id, detalle.cantidad_preparada)
        detalle.error_enviado = por_fila.get(detalle.articulo_id, "")
    puede_registrar = (
        servicio.estado == Servicio.Estado.PREPARADO
        and preparacion is not None
        and preparacion.estado == Preparacion.Estado.COMPLETA
    )
    if not puede_registrar and not errores:
        errores = [
            "Esta reserva todavía no se puede despachar: primero debe finalizarse su preparación "
            f"(estado actual: {servicio.get_estado_display()})."
        ]

    return render(
        request,
        "despacho-registrar.html",
        {
            "servicio": servicio,
            "preparacion": preparacion,
            "detalles": detalles,
            "resumen": resumen_despacho(preparacion) if preparacion else {"articulos": 0, "unidades": 0},
            "datos": datos,
            "tipos_entrega": Despacho.TipoEntrega.choices,
            "errores": errores,
            "puede_registrar": puede_registrar,
        },
        status=400 if errores and request.method == "POST" else 200,
    )


@solo_administrador
def gestion_despacho_documento(request, id):
    despacho = get_object_or_404(
        Despacho.objects.select_related(
            "servicio",
            "servicio__cliente",
            "usuario",
            "preparacion",
        ),
        id=id,
        servicio__negocio=request.usuario_panel.negocio,
    )

    detalles = list(
        DetalleDespacho.objects
        .filter(despacho=despacho)
        .select_related("articulo")
        .order_by("articulo__nombre")
    )

    return render(
        request,
        "despacho-documento.html",
        {
            "despacho": despacho,
            "servicio": despacho.servicio,
            "detalles": detalles,
            "total_unidades": sum(d.cantidad for d in detalles),
            "historial": despacho.servicio.historial.select_related("usuario")[:20],
        },
    )


# DEVOLUCIONES
ESTADOS_CON_DEVOLUCION = [
    Servicio.Estado.DESPACHADO,
    Servicio.Estado.DEVOLUCION_PARCIAL,
    Servicio.Estado.FINALIZADO,
    Servicio.Estado.CERRADO,
]


def _totales_devolucion(servicios):
    """Despachado, resuelto (buenas + dañadas + perdidas) y pendiente por servicio."""
    ids = [s.id for s in servicios]
    despachado = {
        f["despacho__servicio_id"]: f["total"]
        for f in (
            DetalleDespacho.objects
            .filter(despacho__servicio_id__in=ids)
            .exclude(despacho__estado=Despacho.Estado.CANCELADO)
            .values("despacho__servicio_id")
            .annotate(total=Sum("cantidad"))
        )
    }
    resuelto = {
        f["devolucion__servicio_id"]: f
        for f in (
            DetalleDevolucion.objects
            .filter(devolucion__servicio_id__in=ids)
            .values("devolucion__servicio_id")
            .annotate(buenas=Sum("cantidad_buena"), merma=Sum(F("cantidad_danada") + F("cantidad_perdida")))
        )
    }
    for servicio in servicios:
        fila = resuelto.get(servicio.id, {})
        servicio.total_despachado = despachado.get(servicio.id) or 0
        servicio.total_devuelto = fila.get("buenas") or 0
        servicio.total_merma = fila.get("merma") or 0
        servicio.total_pendiente = servicio.total_despachado - servicio.total_devuelto - servicio.total_merma


@solo_administrador
def gestion_devoluciones(request):
    negocio = request.usuario_panel.negocio
    hoy = timezone.localdate()
    filtros = {
        "estado": request.GET.get("estado", "").strip(),
        "q": request.GET.get("q", "").strip(),
        "desde": request.GET.get("desde", "").strip(),
        "hasta": request.GET.get("hasta", "").strip(),
    }

    servicios = (
        Servicio.objects
        .filter(negocio=negocio, estado__in=ESTADOS_CON_DEVOLUCION)
        .select_related("cliente")
        .annotate(
            fin=Coalesce("fecha_termino", "fecha_evento", "fecha_inicio"),
            fecha_salida=Max("despachos__fecha_despacho"),
        )
        .order_by("fin", "codigo")
    )
    if filtros["estado"] == "pendientes":
        servicios = servicios.filter(estado__in=ESTADOS_EN_CLIENTE)
    elif filtros["estado"] == "parcial":
        servicios = servicios.filter(estado=Servicio.Estado.DEVOLUCION_PARCIAL)
    elif filtros["estado"] == "devueltos":
        servicios = servicios.filter(estado__in=[Servicio.Estado.FINALIZADO, Servicio.Estado.CERRADO])
    elif filtros["estado"] == "vencidos":
        servicios = servicios.filter(estado__in=ESTADOS_EN_CLIENTE, fin__lt=hoy)
    if filtros["q"]:
        texto = filtros["q"]
        condicion = Q(cliente__nombre__icontains=texto) | Q(cliente__apellido__icontains=texto) | Q(codigo__icontains=texto)
        if normalizar_rut(texto):
            condicion |= Q(cliente__rut__icontains=normalizar_rut(texto))
        servicios = servicios.filter(condicion)
    desde = _fecha_desde_texto(filtros["desde"])
    hasta = _fecha_desde_texto(filtros["hasta"])
    if desde:
        servicios = servicios.filter(fecha_evento__gte=desde)
    if hasta:
        servicios = servicios.filter(fecha_evento__lte=hasta)

    servicios = list(servicios)
    _totales_devolucion(servicios)
    for servicio in servicios:
        servicio.vencido = servicio.estado in ESTADOS_EN_CLIENTE and servicio.fin and servicio.fin < hoy
        servicio.acepta_devolucion = servicio.estado in ESTADOS_EN_CLIENTE

    return render(
        request,
        "devoluciones.html",
        {
            "servicios": servicios,
            "filtros": filtros,
            "estados": [("", "Todas"), ("pendientes", "Con pendientes"), ("parcial", "Devolución parcial"),
                        ("devueltos", "Devueltos"), ("vencidos", "Vencidos")],
        },
    )


@solo_administrador
def gestion_devolucion(request, id):
    """Ruta antigua por devolución individual: lleva al detalle de la reserva."""
    devolucion = get_object_or_404(Devolucion, id=id, servicio__negocio=request.usuario_panel.negocio)
    return redirect("gestion_devolucion_servicio", servicio_id=devolucion.servicio_id)


@solo_administrador
def gestion_devolucion_servicio(request, servicio_id):
    servicio = get_object_or_404(Servicio.objects.select_related("cliente"), id=servicio_id, negocio=request.usuario_panel.negocio)
    despacho, estado = estado_devolucion(servicio)
    devoluciones = list(
        servicio.devoluciones.select_related("usuario").prefetch_related("detalles__articulo")
    )
    mermas = list(servicio.mermas.select_related("articulo", "usuario"))
    return render(
        request,
        "devolucion.html",
        {
            "servicio": servicio,
            "despacho": despacho,
            "filas": estado,
            "totales": {
                "despachado": sum(f["despachado"] for f in estado),
                "buenas": sum(f["buenas"] for f in estado),
                "merma": sum(f["danadas"] + f["perdidas"] for f in estado),
                "pendiente": sum(f["pendiente"] for f in estado),
            },
            "devoluciones": devoluciones,
            "mermas": mermas,
            "acepta_devolucion": servicio.estado in ESTADOS_EN_CLIENTE,
            "puede_cerrar": servicio.estado == Servicio.Estado.FINALIZADO,
            "historial": servicio.historial.select_related("usuario")[:30],
        },
    )


@solo_administrador
def gestion_registrar_devolucion(request, servicio_id):
    servicio = get_object_or_404(Servicio.objects.select_related("cliente"), id=servicio_id, negocio=request.usuario_panel.negocio)
    despacho, estado = estado_devolucion(servicio)
    errores, por_fila = [], {}
    datos = {
        "fecha": timezone.localtime().strftime("%Y-%m-%dT%H:%M"),
        "entregado_por": f"{servicio.cliente.nombre} {servicio.cliente.apellido}".strip(),
        "observaciones": "",
    }
    enviados = {}

    if request.method == "POST":
        datos = {campo: request.POST.get(campo, "").strip() for campo in datos}
        ids = request.POST.getlist("articulo_id")
        if "merma" in request.POST:
            # Formulario actual: lo que no vuelve en buen estado va a una sola columna "Merma" (baja definitiva).
            mermas = request.POST.getlist("merma")
            columnas = [request.POST.getlist("buenas"), ["0"] * len(mermas), mermas, request.POST.getlist("observacion")]
        else:
            columnas = [request.POST.getlist(c) for c in ("buenas", "danadas", "perdidas", "observacion")]
        try:
            if any(len(c) != len(ids) for c in columnas):
                raise OperacionInvalida("El formulario llegó incompleto. Recarga la página e inténtalo de nuevo.")
            if "merma" in request.POST:
                _exigir_todo_definido(estado, ids, columnas)
            registrar_devolucion(
                servicio.id, request.usuario_panel, _fecha_hora_desde_texto(datos["fecha"]),
                datos["entregado_por"], list(zip(ids, *columnas)), datos["observaciones"],
            )
        except OperacionInvalida as error:
            errores, por_fila = [error.mensaje, *error.detalles], error.por_fila
            enviados = {i: dict(zip(("buenas", "danadas", "perdidas", "observacion"), v)) for i, *v in zip(ids, *columnas)}
            despacho, estado = estado_devolucion(servicio)
        else:
            servicio.refresh_from_db()
            if servicio.estado == Servicio.Estado.FINALIZADO:
                messages.success(request, "Devolución registrada. Todas las unidades quedaron resueltas: ya puedes cerrar la reserva.")
            else:
                messages.success(request, "Devolución parcial registrada. Las unidades pendientes siguen comprometidas.")
            return redirect("gestion_devolucion_servicio", servicio_id=servicio.id)

    for fila in estado:
        enviado = enviados.get(str(fila["articulo_id"]), {})
        fila["valor_buenas"] = enviado.get("buenas", "0")
        fila["valor_danadas"] = enviado.get("danadas", "0")
        fila["valor_perdidas"] = enviado.get("perdidas", "0")
        fila["merma_previa"] = fila["danadas"] + fila["perdidas"]
        fila["valor_observacion"] = enviado.get("observacion", "")
        fila["errores"] = por_fila.get(fila["articulo_id"], [])

    acepta = servicio.estado in ESTADOS_EN_CLIENTE and despacho is not None
    if not acepta and not errores:
        errores = [f"Esta reserva no tiene artículos pendientes de devolución (estado: {servicio.get_estado_display()})."]

    return render(
        request,
        "devolucion-registrar.html",
        {
            "servicio": servicio,
            "despacho": despacho,
            "filas": [f for f in estado if f["pendiente"] > 0],
            "datos": datos,
            "errores": errores,
            "acepta": acepta,
        },
        status=400 if errores and request.method == "POST" else 200,
    )


def _exigir_todo_definido(estado, ids, columnas):
    """En la pantalla de devolución cada unidad pendiente debe quedar como 'vuelve bien' o 'merma'."""
    pendientes = {f["articulo_id"]: f for f in estado}
    sin_definir = []
    for articulo_id, buenas, danadas, perdidas, _ in zip(ids, *columnas):
        fila = pendientes.get(int(articulo_id)) if articulo_id.isdigit() else None
        valores = [v.strip() for v in (buenas, danadas, perdidas)]
        if fila is None or not all(v.isdigit() for v in valores):
            continue  # registrar_devolucion informa estos errores
        faltan = fila["pendiente"] - sum(int(v) for v in valores)
        if faltan > 0:
            sin_definir.append(f"{fila['articulo'].nombre}: faltan {faltan} por definir.")
    if sin_definir:
        raise OperacionInvalida("Indica para cada unidad si vuelve bien o va a merma.", sin_definir)


# MERMAS
@solo_administrador
def gestion_mermas(request):
    negocio = request.usuario_panel.negocio
    errores, datos = [], {}

    if request.method == "POST":
        accion = request.POST.get("accion")
        try:
            if accion == "crear":
                datos = {c: request.POST.get(c, "").strip() for c in ("articulo_id", "tipo", "cantidad", "motivo", "observaciones", "valor_reposicion")}
                if not Articulo.objects.filter(id=_entero(datos["articulo_id"], 0), negocio=negocio).exists():
                    raise OperacionInvalida("No se registró la merma.", ["Selecciona un artículo."])
                registrar_merma_manual(
                    int(datos["articulo_id"]), request.usuario_panel, datos["tipo"], datos["cantidad"],
                    datos["motivo"], datos["observaciones"], datos["valor_reposicion"],
                )
                messages.success(request, "Merma registrada y descontada del stock.")
            elif accion in ("reparar", "anular"):
                merma = get_object_or_404(Merma, id=request.POST.get("merma_id"), articulo__negocio=negocio)
                if accion == "reparar":
                    reparar_merma(merma.id, request.usuario_panel, request.POST.get("cantidad", ""))
                    messages.success(request, "Reparación registrada: las unidades volvieron al stock trabajable.")
                else:
                    anular_merma(merma.id, request.usuario_panel, request.POST.get("motivo", ""))
                    messages.success(request, "Merma anulada y stock restituido. El registro se conserva como anulado.")
            return redirect(f"{reverse('gestion_mermas')}?{request.GET.urlencode()}")
        except OperacionInvalida as error:
            errores = [error.mensaje, *error.detalles]

    filtros = {c: request.GET.get(c, "").strip() for c in ("articulo", "categoria", "tipo", "desde", "hasta", "servicio")}
    mermas = (
        Merma.objects
        .filter(articulo__negocio=negocio)
        .select_related("articulo", "articulo__categoria", "servicio", "usuario", "anulada_por")
    )
    if filtros["articulo"].isdigit():
        mermas = mermas.filter(articulo_id=int(filtros["articulo"]))
    if filtros["categoria"].isdigit():
        mermas = mermas.filter(articulo__categoria_id=int(filtros["categoria"]))
    if filtros["tipo"] in Merma.Tipo.values:
        mermas = mermas.filter(tipo=filtros["tipo"])
    desde = _fecha_desde_texto(filtros["desde"])
    hasta = _fecha_desde_texto(filtros["hasta"])
    if desde:
        mermas = mermas.filter(fecha__date__gte=desde)
    if hasta:
        mermas = mermas.filter(fecha__date__lte=hasta)
    if filtros["servicio"]:
        mermas = mermas.filter(servicio__codigo__icontains=filtros["servicio"])

    mermas = list(mermas)
    vigentes = [m for m in mermas if not m.anulada]
    articulos = Articulo.objects.filter(negocio=negocio).order_by("nombre")

    return render(
        request,
        "mermas.html",
        {
            "mermas": mermas,
            "filtros": filtros,
            "kpis": {
                "registros": len(vigentes),
                "unidades": sum(m.cantidad - m.cantidad_reparada for m in vigentes),
                "valor": sum(m.valor for m in vigentes),
                "sin_costo": len({m.articulo_id for m in vigentes if not m.valor}),
            },
            "articulos": articulos,
            "categorias": Categoria.objects.filter(negocio=negocio).order_by("nombre"),
            "tipos": Merma.Tipo.choices,
            "errores": errores,
            "datos": datos,
        },
        status=400 if errores else 200,
    )


# CALENDARIO
@solo_administrador
def gestion_calendario(request):
    negocio = request.usuario_panel.negocio

    servicios = (
        Servicio.objects
        .filter(negocio=negocio)
        .filter(Q(fecha_evento__isnull=False) | Q(fecha_inicio__isnull=False))
        .exclude(estado=Servicio.Estado.CANCELADO)
        .select_related("cliente")
    )

    def url_servicio(servicio):
        if servicio.estado in (Servicio.Estado.COTIZACION, Servicio.Estado.CONTACTADO):
            return reverse("gestion_cotizacion", args=[servicio.id])
        return reverse("gestion_reserva", args=[servicio.id])

    def cliente_de(servicio):
        return f"{servicio.cliente.nombre} {servicio.cliente.apellido}".strip()

    eventos = []
    for servicio in servicios:
        inicio = servicio.fecha_inicio or servicio.fecha_evento
        fin = servicio.fecha_termino or inicio
        eventos.append({
            "tipo": "evento",
            "titulo": f"{servicio.tipo_servicio or 'Evento'} · {cliente_de(servicio)}",
            "inicio": inicio.isoformat(),
            "fin": max(fin, inicio).isoformat(),
            "hora_inicio": servicio.hora_inicio.strftime("%H:%M") if servicio.hora_inicio else None,
            "hora_fin": servicio.hora_termino.strftime("%H:%M") if servicio.hora_termino else None,
            "codigo": servicio.codigo,
            "cliente": cliente_de(servicio),
            "estado": servicio.get_estado_display(),
            # Las cotizaciones aún no están confirmadas: se dibujan como tentativas.
            "tentativo": servicio.estado in (Servicio.Estado.COTIZACION, Servicio.Estado.CONTACTADO),
            "lugar": ", ".join(filter(None, [servicio.direccion_evento, servicio.comuna_evento])),
            "personas": servicio.cantidad_personas,
            "url": url_servicio(servicio),
        })

    movimientos = [
        ("entrega", "🚚 Entrega", d.servicio, d.fecha_despacho, reverse("gestion_despacho_documento", args=[d.id]))
        for d in Despacho.objects.filter(servicio__negocio=negocio).exclude(estado=Despacho.Estado.CANCELADO).select_related("servicio__cliente")
    ] + [
        ("retiro", "↩ Devolución recibida", d.servicio, d.fecha_devolucion,
         reverse("gestion_devolucion_servicio", args=[d.servicio_id]))
        for d in Devolucion.objects.filter(servicio__negocio=negocio).select_related("servicio__cliente")
    ]

    # Devolución esperada: lo que sigue en el cliente, el día de término (o atrasada si ya pasó).
    hoy = timezone.localdate()
    for servicio in servicios.filter(estado__in=ESTADOS_EN_CLIENTE):
        fin = servicio.fecha_termino or servicio.fecha_evento or servicio.fecha_inicio
        atrasada = fin < hoy
        eventos.append({
            "tipo": "devolucion",
            "titulo": f"{'⚠ Devolución atrasada' if atrasada else '⏳ Devolución esperada'} · {cliente_de(servicio)}",
            "inicio": fin.isoformat(),
            "fin": fin.isoformat(),
            "hora_inicio": None,
            "hora_fin": None,
            "codigo": servicio.codigo,
            "cliente": cliente_de(servicio),
            "estado": servicio.get_estado_display() + (" · atrasada" if atrasada else ""),
            "tentativo": False,
            "atrasado": atrasada,
            "lugar": ", ".join(filter(None, [servicio.direccion_evento, servicio.comuna_evento])),
            "personas": servicio.cantidad_personas,
            "url": reverse("gestion_devolucion_servicio", args=[servicio.id]),
        })

    for tipo, etiqueta, servicio, momento, url in movimientos:
        momento = timezone.localtime(momento) if timezone.is_aware(momento) else momento
        eventos.append({
            "tipo": tipo,
            "titulo": f"{etiqueta} · {cliente_de(servicio)}",
            "inicio": momento.date().isoformat(),
            "fin": momento.date().isoformat(),
            "hora_inicio": momento.strftime("%H:%M"),
            "hora_fin": None,
            "codigo": servicio.codigo,
            "cliente": cliente_de(servicio),
            "estado": servicio.get_estado_display(),
            "tentativo": False,
            "lugar": ", ".join(filter(None, [servicio.direccion_evento, servicio.comuna_evento])),
            "personas": servicio.cantidad_personas,
            "url": url,
        })

    return render(
        request,
        "calendario.html",
        {
            "eventos": eventos,
        },
    )


# REPORTES
@solo_administrador
def gestion_reportes(request):
    negocio = request.usuario_panel.negocio
    hoy = timezone.localdate()

    articulos = Articulo.objects.filter(negocio=negocio)
    servicios = Servicio.objects.filter(negocio=negocio)
    clientes = Cliente.objects.filter(negocio=negocio)

    periodo = {
        "desde": request.GET.get("desde", "").strip(),
        "hasta": request.GET.get("hasta", "").strip(),
    }
    desde = _fecha_desde_texto(periodo["desde"])
    hasta = _fecha_desde_texto(periodo["hasta"])

    def en_periodo(qs, campo):
        if desde:
            qs = qs.filter(**{f"{campo}__gte": desde})
        if hasta:
            qs = qs.filter(**{f"{campo}__lte": hasta})
        return qs

    servicios_periodo = (
        en_periodo(servicios, "fecha_evento")
        if (desde or hasta)
        else servicios
    )

    # KPIs comerciales calculados en una única consulta.
    comercial = servicios_periodo.aggregate(
        cantidad_cotizaciones=Count(
            "id",
            filter=Q(estado__in=ESTADOS_COTIZADOS),
        ),
        cantidad_reservas=Count(
            "id",
            filter=Q(estado__in=ESTADOS_RESERVA),
        ),
        monto_cotizado=Sum(
            "total",
            filter=Q(estado__in=ESTADOS_COTIZADOS),
        ),
        monto_confirmado=Sum(
            "total",
            filter=Q(estado__in=ESTADOS_RESERVA),
        ),
        reservas_finalizadas=Count(
            "id",
            filter=Q(
                estado__in=[
                    Servicio.Estado.FINALIZADO,
                    Servicio.Estado.CERRADO,
                ]
            ),
        ),
        reservas_canceladas=Count(
            "id",
            filter=Q(estado=Servicio.Estado.CANCELADO),
        ),
    )

    cantidad_cotizaciones = comercial["cantidad_cotizaciones"]
    cantidad_reservas = comercial["cantidad_reservas"]
    monto_cotizado = comercial["monto_cotizado"] or 0
    monto_confirmado = comercial["monto_confirmado"] or 0
    ticket_promedio = (
        monto_confirmado / cantidad_reservas
        if cantidad_reservas
        else 0
    )

    cotizados = servicios_periodo.filter(estado__in=ESTADOS_COTIZADOS)
    confirmados = servicios_periodo.filter(estado__in=ESTADOS_RESERVA)

    _, stock = estado_stock(articulos)
    ids_articulos = list(articulos.values_list("id", flat=True))

    mermas_vigentes = en_periodo(
        Merma.objects.filter(
            articulo__negocio=negocio,
            anulada=False,
        ),
        "fecha__date",
    )

    clientes_stats = clientes.aggregate(
        total=Count("id"),
        nuevos=Count(
            "id",
            filter=Q(
                fecha_creacion__year=hoy.year,
                fecha_creacion__month=hoy.month,
            ),
        ),
    )

    unidades_merma = (
        mermas_vigentes
        .aggregate(
            total=Sum(F("cantidad") - F("cantidad_reparada"))
        )["total"]
        or 0
    )

    # valor es una propiedad calculada en Python, por eso esta parte sí requiere
    # materializar las mermas del período.
    mermas_lista = list(
        mermas_vigentes.select_related("articulo")
    )
    valor_merma = sum(merma.valor for merma in mermas_lista)

    metricas = {
        "stock_total": stock["total"],
        "stock_trabajable": stock["trabajable"],
        "stock_comprometido": stock["comprometido"],
        "stock_disponible": stock["disponible"],
        "stock_bajo": stock["alertas_count"],
        "stock_en_cliente": sum(
            unidades_fuera_de_bodega(ids_articulos).values()
        ),
        "unidades_merma": unidades_merma,
        "valor_merma": valor_merma,

        "reservas_total": cantidad_reservas,
        "reservas_proximas": (
            servicios
            .filter(
                fecha_evento__gte=hoy,
                estado__in=ESTADOS_QUE_BLOQUEAN,
            )
            .count()
        ),
        "reservas_finalizadas": comercial["reservas_finalizadas"],
        "reservas_canceladas": comercial["reservas_canceladas"],

        "clientes_total": clientes_stats["total"],
        "clientes_nuevos": clientes_stats["nuevos"],

        "cotizaciones_total": cantidad_cotizaciones,
        "tasa_conversion": (
            round(cantidad_reservas * 100 / cantidad_cotizaciones)
            if cantidad_cotizaciones
            else 0
        ),
        "monto_cotizado": monto_cotizado,
        "monto_confirmado": monto_confirmado,
        "cotizaciones_aceptadas": cantidad_reservas,
        "cotizaciones_rechazadas": comercial["reservas_canceladas"],
        "ticket_promedio": ticket_promedio,

        "preparaciones_completas": en_periodo(
            Preparacion.objects.filter(
                servicio__negocio=negocio,
                estado=Preparacion.Estado.COMPLETA,
            ),
            "fecha_finalizacion__date",
        ).count(),

        "despachos": en_periodo(
            Despacho.objects
            .filter(servicio__negocio=negocio)
            .exclude(estado=Despacho.Estado.CANCELADO),
            "fecha_despacho__date",
        ).count(),

        "devoluciones_pendientes": servicios.filter(
            estado__in=ESTADOS_EN_CLIENTE
        ).count(),

        "unidades_devueltas": (
            en_periodo(
                DetalleDevolucion.objects.filter(
                    devolucion__servicio__negocio=negocio
                ),
                "devolucion__fecha_devolucion__date",
            )
            .aggregate(total=Sum("cantidad_buena"))["total"]
            or 0
        ),
    }

    mermas_por_articulo = list(
        mermas_vigentes
        .values(nombre=F("articulo__nombre"))
        .annotate(
            total=Sum(F("cantidad") - F("cantidad_reparada"))
        )
        .order_by("-total")[:6]
    )

    detalles_periodo = DetalleServicio.objects.filter(
        servicio__in=confirmados
    )

    productos_mas_arrendados = _con_barras(
        list(
            detalles_periodo
            .values(nombre=F("articulo__nombre"))
            .annotate(total=Sum("cantidad"))
            .order_by("-total")[:6]
        )
    )

    ingresos_categoria = _con_barras(
        list(
            detalles_periodo
            .values(categoria=F("articulo__categoria__nombre"))
            .annotate(total=Sum("subtotal"))
            .order_by("-total")[:6]
        )
    )

    for fila in ingresos_categoria:
        nombre = fila["categoria"] or ""
        fila["categoria"] = ETIQUETAS_CATEGORIA.get(
            nombre,
            nombre.replace("-", " ").capitalize(),
        )

    clientes_frecuentes = _con_barras(
        list(
            confirmados
            .values(
                nombre=F("cliente__nombre"),
                apellido=F("cliente__apellido"),
            )
            .annotate(
                reservas=Count("id"),
                monto=Sum("total"),
            )
            .order_by("-reservas", "-monto")[:6]
        ),
        campo="reservas",
    )

    mermas_por_articulo = _con_barras(mermas_por_articulo)

    atajos = [
        ("Este mes", hoy.replace(day=1), hoy),
        (
            "Últimos 3 meses",
            (hoy.replace(day=1) - timedelta(days=62)).replace(day=1),
            hoy,
        ),
        ("Este año", hoy.replace(month=1, day=1), hoy),
    ]

    return render(
        request,
        "reportes.html",
        {
            "metricas": metricas,
            "productos_mas_arrendados": productos_mas_arrendados,
            "ingresos_categoria": ingresos_categoria,
            "clientes_frecuentes": clientes_frecuentes,
            "mermas_por_articulo": mermas_por_articulo,
            "periodo": periodo,
            "atajos": [
                {
                    "etiqueta": etiqueta,
                    "desde": fecha_desde.isoformat(),
                    "hasta": fecha_hasta.isoformat(),
                    "activo": (
                        periodo["desde"] == fecha_desde.isoformat()
                        and periodo["hasta"] == fecha_hasta.isoformat()
                    ),
                }
                for etiqueta, fecha_desde, fecha_hasta in atajos
            ],
        },
    )


@solo_administrador
def gestion_buscar(request):
    """Buscador de la barra superior del panel: productos, clientes, cotizaciones y reservas."""
    termino = request.GET.get("q", "").strip()
    if len(termino) < 2:
        return JsonResponse({"grupos": []})
    negocio = request.usuario_panel.negocio

    productos = (
        Articulo.objects.filter(negocio=negocio)
        .filter(Q(nombre__icontains=termino) | Q(codigo__icontains=termino))
        .select_related("categoria").order_by("nombre")[:4]
    )
    rut = normalizar_rut(termino)
    clientes = (
        Cliente.objects.filter(negocio=negocio)
        .filter(
            Q(nombre__icontains=termino) | Q(apellido__icontains=termino) | Q(email__icontains=termino)
            | (Q(rut__icontains=rut) if len(rut) >= 3 else Q(pk__in=[]))
        )
        .order_by("nombre")[:4]
    )
    servicios = (
        Servicio.objects.filter(negocio=negocio)
        .filter(Q(codigo__icontains=termino) | Q(cliente__nombre__icontains=termino) | Q(cliente__apellido__icontains=termino))
        .select_related("cliente").order_by("-id")[:12]
    )
    cotizaciones = [s for s in servicios if s.estado not in ESTADOS_RESERVA][:4]
    reservas = [s for s in servicios if s.estado in ESTADOS_RESERVA][:4]

    grupos = [
        ("Productos", [(reverse("gestion_producto", args=[a.id]), a.nombre, a.categoria.nombre) for a in productos]),
        ("Clientes", [(reverse("gestion_cliente", args=[c.id]), str(c), c.rut_formateado or c.email) for c in clientes]),
        ("Cotizaciones", [(reverse("gestion_cotizacion", args=[s.id]), s.codigo, str(s.cliente)) for s in cotizaciones]),
        ("Reservas", [(reverse("gestion_reserva", args=[s.id]), s.codigo, str(s.cliente)) for s in reservas]),
    ]
    return JsonResponse({"grupos": [
        {"titulo": titulo, "items": [{"href": h, "titulo": t, "sub": sub or ""} for h, t, sub in items]}
        for titulo, items in grupos if items
    ]})


def _con_barras(filas, campo="total"):
    """Agrega a cada fila el ancho relativo (%) para dibujar una barra respecto del mayor valor."""
    mayor = max((f[campo] or 0 for f in filas), default=0)
    for fila in filas:
        fila["pct"] = round((fila[campo] or 0) * 100 / mayor) if mayor else 0
    return filas


# USUARIOS
@solo_administrador
def gestion_usuarios(request):
    negocio = request.usuario_panel.negocio

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


# CONFIGURACIÓN
@solo_administrador
def gestion_configuracion(request):
    negocio = request.usuario_panel.negocio

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


ACCION_ENVIO_CORREO = "Cotización enviada por correo"
ACCION_RECHAZO = "Cotización rechazada por el cliente"
ACCION_ACEPTA_CLIENTE = "Cotización aceptada por el cliente"
MOTIVOS_RECHAZO = (
    "Precio",
    "Cambió la fecha del evento",
    "Contrató otro proveedor",
    "Se canceló el evento",
    "Sin respuesta del cliente",
    "Otro motivo",
)


@solo_administrador
@require_POST
def enviar_cotizacion_email(request, id):
    """Envía la cotización al cliente y, si es la primera vez, la deja en estado Contactado."""
    servicio = get_object_or_404(
        Servicio.objects.select_related("cliente", "negocio"),
        id=id,
        negocio=request.usuario_panel.negocio,
    )
    if servicio.estado not in (Servicio.Estado.COTIZACION, Servicio.Estado.CONTACTADO):
        messages.error(request, "Esta solicitud ya no está en etapa de cotización.")
    elif not servicio.cliente.email:
        messages.error(request, "El cliente no tiene correo registrado. Envía la cotización por WhatsApp o teléfono y márcala como enviada.")
    elif not servicio.detalles.exists():
        messages.error(request, "Agrega al menos un producto antes de enviar la cotización.")
    else:
        try:
            _enviar_correo_cotizacion(servicio)
        except Exception:
            logger.exception("No se pudo enviar la cotización %s por correo", servicio.codigo)
            messages.error(request, "No se pudo enviar el correo. Revisa la configuración del correo o inténtalo nuevamente en unos minutos.")
        else:
            anterior = servicio.estado
            if servicio.estado == Servicio.Estado.COTIZACION:
                servicio.estado = Servicio.Estado.CONTACTADO
                servicio.save(update_fields=["estado", "fecha_actualizacion"])
            registrar_historial(servicio, ACCION_ENVIO_CORREO, request.usuario_panel, anterior,
                                f"Enviada a {servicio.cliente.email}. Total ${servicio.total:,.0f}".replace(",", "."))
            messages.success(request, f"✓ Cotización enviada a {servicio.cliente.email}. La solicitud quedó como Contactado.")
    return redirect("gestion_cotizacion", id=servicio.id)


def _enviar_correo_cotizacion(servicio):
    cliente = servicio.cliente

    detalles = (
        DetalleServicio.objects
        .filter(servicio=servicio)
        .select_related("articulo")
        .order_by("articulo__nombre")
    )

    subject = (
        f"Cotización {servicio.codigo} "
        f"· Entre Platos y Copas"
    )

    from_email = settings.DEFAULT_FROM_EMAIL

    to = [
        cliente.email
    ]

    text_content = f"""
Hola {cliente.nombre},

Te enviamos la cotización {servicio.codigo}
para tu evento.

Fecha del evento: {servicio.fecha_evento}
Total: ${servicio.total}

Si deseas realizar algún cambio o confirmar la cotización,
puedes responder este correo o comunicarte con nosotros.

Entre Platos y Copas
"""

    filas_articulos = ""

    for detalle in detalles:
        filas_articulos += f"""
        <tr>
            <td style="padding:8px;border-bottom:1px solid #ddd;">
                {detalle.articulo.nombre}
            </td>

            <td style="padding:8px;border-bottom:1px solid #ddd;text-align:center;">
                {detalle.cantidad}
            </td>

            <td style="padding:8px;border-bottom:1px solid #ddd;text-align:right;">
                ${detalle.precio_unitario:,.0f}
            </td>

            <td style="padding:8px;border-bottom:1px solid #ddd;text-align:right;">
                ${detalle.subtotal:,.0f}
            </td>
        </tr>
        """

    html_content = f"""
    <div style="
        font-family:Arial,sans-serif;
        max-width:700px;
        margin:auto;
        color:#333;
    ">

        <h2 style="color:#b98b52;">
            Entre Platos y Copas
        </h2>

        <p>
            Hola <strong>{cliente.nombre}</strong>,
        </p>

        <p>
            Te enviamos la cotización
            <strong>{servicio.codigo}</strong>
            correspondiente a tu evento.
        </p>

        <table
            style="
                width:100%;
                border-collapse:collapse;
                margin-top:20px;
            "
        >

            <thead>
                <tr style="background:#f3ede4;">
                    <th style="padding:8px;text-align:left;">
                        Artículo
                    </th>

                    <th style="padding:8px;">
                        Cantidad
                    </th>

                    <th style="padding:8px;text-align:right;">
                        Precio
                    </th>

                    <th style="padding:8px;text-align:right;">
                        Subtotal
                    </th>
                </tr>
            </thead>

            <tbody>
                {filas_articulos}
            </tbody>

        </table>

        <div style="
            margin-top:20px;
            text-align:right;
        ">

            <p>
                Subtotal:
                <strong>
                    ${servicio.subtotal:,.0f}
                </strong>
            </p>

            <p>
                Descuento:
                <strong>
                    ${servicio.descuento:,.0f}
                </strong>
            </p>

            <p style="font-size:20px;">
                Total:
                <strong>
                    ${servicio.total:,.0f}
                </strong>
            </p>

        </div>

        <hr style="
            border:none;
            border-top:1px solid #ddd;
            margin:30px 0;
        ">

        <p>
            <strong>Fecha del evento:</strong>
            {servicio.fecha_evento or "Por confirmar"}
        </p>

        <p>
            <strong>Comuna:</strong>
            {servicio.comuna_evento or "Por confirmar"}
        </p>

        <p>
            Si estás de acuerdo, puedes aceptarla desde <strong>Mi cuenta</strong> en nuestro sitio.
            Si deseas modificarla, responde este correo o comunícate con nosotros.
        </p>

        <p>
            Saludos,<br>
            <strong>Entre Platos y Copas</strong>
        </p>

    </div>
    """

    msg = EmailMultiAlternatives(
        subject,
        text_content,
        from_email,
        to,
    )

    msg.attach_alternative(
        html_content,
        "text/html",
    )

    msg.send()


import math


PREDETERMINADOS_EVENTO = {

    "Matrimonio": {

        "vajilla": [
            {
                "codigo": "vaj-003",
                "regla": "por_persona",
                "factor": 1,
            },
        ],

        "cristaleria": [
            {
                "codigo": "cris-001",
                "regla": "por_persona",
                "factor": 1.05,
            },
            {
                "codigo": "cris-003",
                "regla": "por_persona",
                "factor": 1.05,
            },
        ],

        "cubiertos": [
            {
                "codigo": "cub-001",
                "regla": "por_persona",
                "factor": 1,
            },
        ],

        "mesas-sillas": [
            {
                "codigo": "sil-001",
                "regla": "por_persona",
                "factor": 1,
            },
            {
                "codigo": "mes-001",
                "regla": "por_capacidad",
                "capacidad": 10,
            },
        ],

        "manteleria": [
            {
                "codigo": "man-001",
                "regla": "por_capacidad",
                "capacidad": 10,
            },
            {
                "codigo": "man-004",
                "regla": "por_persona",
                "factor": 1,
            },
        ],
    },


    "Cumpleaños": {

        "vajilla": [
            {
                "codigo": "vaj-001",
                "regla": "por_persona",
                "factor": 1,
            },
        ],

        "cubiertos": [
            {
                "codigo": "cub-001",
                "regla": "por_persona",
                "factor": 1,
            },
        ],

        "mesas-sillas": [
            {
                "codigo": "sil-001",
                "regla": "por_persona",
                "factor": 1,
            },
            {
                "codigo": "mes-001",
                "regla": "por_capacidad",
                "capacidad": 10,
            },
        ],

        "cristaleria": [
            {
                "codigo": "cris-004",
                "regla": "por_persona",
                "factor": 1,
            },
        ],
    },


    "Evento empresarial": {

        "vajilla": [
            {
                "codigo": "vaj-004",
                "regla": "por_persona",
                "factor": 1,
            },
        ],

        "cubiertos": [
            {
                "codigo": "cub-001",
                "regla": "por_persona",
                "factor": 1,
            },
        ],

        "cristaleria": [
            {
                "codigo": "cris-004",
                "regla": "por_persona",
                "factor": 1,
            },
        ],

        "mesas-sillas": [
            {
                "codigo": "mes-002",
                "regla": "por_capacidad",
                "capacidad": 10,
            },
        ],

        "equipamiento": [
            {
                "codigo": "equ-003",
                "regla": "fijo",
                "cantidad": 1,
            },
        ],
    },


    "Cena / Banquete": {

        "vajilla": [
            {
                "codigo": "vaj-003",
                "regla": "por_persona",
                "factor": 1,
            },
        ],

        "cubiertos": [
            {
                "codigo": "cub-001",
                "regla": "por_persona",
                "factor": 1,
            },
        ],

        "cristaleria": [
            {
                "codigo": "cris-001",
                "regla": "por_persona",
                "factor": 1,
            },
            {
                "codigo": "cris-002",
                "regla": "por_persona",
                "factor": 1,
            },
        ],

        "mesas-sillas": [
            {
                "codigo": "mes-002",
                "regla": "por_capacidad",
                "capacidad": 10,
            },
        ],

        "manteleria": [
            {
                "codigo": "man-002",
                "regla": "por_capacidad",
                "capacidad": 10,
            },
            {
                "codigo": "man-004",
                "regla": "por_persona",
                "factor": 1,
            },
        ],
    },


    "Evento familiar": {

        "vajilla": [
            {
                "codigo": "vaj-001",
                "regla": "por_persona",
                "factor": 1,
            },
        ],

        "cubiertos": [
            {
                "codigo": "cub-001",
                "regla": "por_persona",
                "factor": 1,
            },
        ],

        "mesas-sillas": [
            {
                "codigo": "sil-001",
                "regla": "por_persona",
                "factor": 1,
            },
            {
                "codigo": "mes-001",
                "regla": "por_capacidad",
                "capacidad": 10,
            },
        ],
    },


    "Celebración": {

        "cristaleria": [
            {
                "codigo": "cris-003",
                "regla": "por_persona",
                "factor": 1,
            },
            {
                "codigo": "cris-004",
                "regla": "por_persona",
                "factor": 1,
            },
        ],

        "equipamiento": [
            {
                "codigo": "equ-002",
                "regla": "fijo",
                "cantidad": 1,
            },
        ],
    },


    "Otro": {},
}

def calcular_cantidad_predeterminada(regla, invitados):

    if regla["regla"] == "por_persona":
        return math.ceil(
            invitados
            * regla.get("factor", 1)
        )

    if regla["regla"] == "por_capacidad":
        return math.ceil(
            invitados
            / regla.get("capacidad", 1)
        )

    if regla["regla"] == "fijo":
        return regla.get(
            "cantidad",
            1
        )

    return 0

