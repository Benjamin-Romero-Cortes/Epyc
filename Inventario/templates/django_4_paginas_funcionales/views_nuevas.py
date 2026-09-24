from datetime import date
from urllib.parse import quote
from uuid import uuid4

from django.db import transaction
from django.shortcuts import get_object_or_404, render

from .models import Articulo, Categoria, Cliente, Negocio, Servicio


def producto(request, id):
    producto = get_object_or_404(
        Articulo.objects.select_related("categoria", "negocio"),
        id=id,
        activo=True,
    )

    relacionados = list(
        Articulo.objects
        .filter(activo=True, categoria=producto.categoria)
        .exclude(id=producto.id)
        .select_related("categoria")[:4]
    )

    return render(
        request,
        "producto.html",
        {"producto": producto, "relacionados": relacionados},
    )


def nosotros(request):
    return render(request, "nosotros.html")


def contacto(request):
    return render(request, "contacto.html")


def _separar_nombre(nombre_completo):
    partes = nombre_completo.strip().split()
    if not partes:
        return "", ""
    if len(partes) == 1:
        return partes[0], ""
    return partes[0], " ".join(partes[1:])


def cotizador(request):
    negocio = Negocio.objects.filter(activo=True).order_by("id").first()

    if negocio is None:
        return render(
            request,
            "cotizador.html",
            {"categorias": [], "error": "No existe un negocio activo configurado en el sistema."},
        )

    categorias = list(
        Categoria.objects.filter(negocio=negocio, activo=True).order_by("nombre")
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
        empresa = request.POST.get("empresa", "").strip()
        telefono = request.POST.get("telefono", "").strip()
        correo = request.POST.get("correo", "").strip().lower()
        medio_contacto = request.POST.get("medioContacto", "").strip()
        comentarios = request.POST.get("comentarios", "").strip()
        categorias_seleccionadas = request.POST.getlist("categorias")

        if not all([
            tipo_evento, fecha_evento, invitados, comuna,
            despacho, nombre_completo, telefono, correo, medio_contacto
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

        try:
            cantidad_personas = int(invitados)
            if cantidad_personas < 1:
                raise ValueError
        except ValueError:
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
                f"Artículo consultado: {articulo_preseleccionado.codigo} - {articulo_preseleccionado.nombre}"
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
                cliente.nombre = nombre
                cliente.apellido = apellido
                cliente.telefono = telefono
                cliente.email = correo
                cliente.comuna = comuna
                cliente.activo = True
                cliente.save()
            else:
                cliente = Cliente.objects.create(
                    negocio=negocio,
                    nombre=nombre,
                    apellido=apellido,
                    telefono=telefono,
                    email=correo,
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
            f"Hola, envié una solicitud de cotización en la web. "
            f"Mi código es {servicio.codigo}."
        )

        whatsapp_url = "https://wa.me/56942058820?text=" + quote(mensaje)

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
