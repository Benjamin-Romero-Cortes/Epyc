from pathlib import Path
import threading
import unittest
from datetime import date, timedelta
from unittest import mock

from django.db import IntegrityError, connection, transaction
from django.core import mail
from django.test import TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from Inventario.disponibilidad import (
    StockInsuficiente,
    calcular_disponibilidad,
    confirmar_servicio,
    disponibilidad_servicio,
)
from Inventario.models import (
    Articulo,
    Categoria,
    Cliente,
    DetalleDespacho,
    DetallePreparacion,
    DetalleServicio,
    Despacho,
    Devolucion,
    Merma,
    MovimientoInventario,
    HistorialServicio,
    Negocio,
    Preparacion,
    Rol,
    Servicio,
    Usuario,
)
from Inventario.operaciones import (
    OperacionInvalida,
    generar_preparacion,
    registrar_despacho,
    registrar_devolucion,
)
from Inventario.validaciones import normalizar_rut, normalizar_telefono, rut_valido, telefono_valido

EN_10_DIAS = date.today() + timedelta(days=10)
RUT_VALIDO = "12.345.678-5"


def crear_base():
    """Negocio, dos categorías y un artículo con 100 unidades trabajables."""
    negocio = Negocio.objects.create(nombre="Entre Platos y Copas")
    vajilla = Categoria.objects.create(negocio=negocio, nombre="vajilla")
    cristaleria = Categoria.objects.create(negocio=negocio, nombre="cristaleria")
    plato = Articulo.objects.create(
        negocio=negocio, categoria=vajilla, codigo="vaj-001", nombre="Plato principal",
        precio_arriendo=500, stock_total=100, stock_trabajable=100,
    )
    return negocio, vajilla, cristaleria, plato


def crear_servicio(negocio, articulo, cantidad, inicio, fin=None, estado=Servicio.Estado.CONFIRMADO, rut="111111111"):
    cliente, _ = Cliente.objects.get_or_create(negocio=negocio, rut=rut, defaults={"nombre": "Cliente"})
    servicio = Servicio.objects.create(
        negocio=negocio, cliente=cliente, codigo=f"COT-{Servicio.objects.count() + 1}",
        estado=estado, fecha_solicitud=date.today(), fecha_evento=inicio,
        fecha_inicio=inicio, fecha_termino=fin or inicio,
    )
    DetalleServicio.objects.create(
        servicio=servicio, articulo=articulo, cantidad=cantidad,
        precio_unitario=articulo.precio_arriendo, subtotal=articulo.precio_arriendo * cantidad,
    )
    return servicio


class ValidacionesTests(TestCase):
    def test_normaliza_rut(self):
        self.assertEqual(normalizar_rut("12.345.678-k"), "12345678K")
        self.assertEqual(normalizar_rut(" 12345678-5 "), "123456785")

    def test_digito_verificador(self):
        self.assertTrue(rut_valido("123456785"))
        self.assertFalse(rut_valido("123456789"))
        self.assertFalse(rut_valido("12A"))

    def test_telefono(self):
        self.assertTrue(telefono_valido("+56 9 4205 8820"))
        self.assertFalse(telefono_valido("123"))
        self.assertFalse(telefono_valido("hola"))

    def test_normaliza_celular_chileno(self):
        for entrada in ("+56936243259", "56 9 3624 3259", "936243259", "+56 9 3624-3259",
                        "0056936243259", "0936243259", "+56 (9) 3624 3259"):
            self.assertEqual(normalizar_telefono(entrada), "+56 9 3624 3259")
        self.assertEqual(normalizar_telefono("22 345 6789"), "22 345 6789")


class CotizadorPublicoTests(TestCase):
    def setUp(self):
        self.negocio, self.vajilla, self.cristaleria, self.plato = crear_base()
        self.url = reverse("cotizador")

    def datos(self, **cambios):
        datos = {
            "tipoEvento": "Matrimonio",
            "fecha": EN_10_DIAS.isoformat(),
            "invitados": "80",
            "comuna": "Maipú",
            "despacho": "Sí",
            "categorias": [str(self.vajilla.id), str(self.cristaleria.id)],
            "nombre": "Ana María Pérez",
            "rut": RUT_VALIDO,
            "telefono": "+56 9 1234 5678",
            "correo": "ana@ejemplo.cl",
            "medioContacto": "WhatsApp",
            "comentarios": "Matrimonio al aire libre.",
        }
        datos.update(cambios)
        return {k: v for k, v in datos.items() if v is not None}

    def enviar(self, **cambios):
        return self.client.post(self.url, self.datos(**cambios), HTTP_X_REQUESTED_WITH="XMLHttpRequest")

    def test_solicitud_valida_crea_cliente_y_servicio(self):
        respuesta = self.enviar()
        self.assertEqual(respuesta.status_code, 200)
        cuerpo = respuesta.json()
        self.assertTrue(cuerpo["ok"])
        self.assertEqual(set(cuerpo), {"ok", "message"})

        cliente = Cliente.objects.get()
        self.assertEqual(cliente.rut, "123456785")
        self.assertEqual((cliente.nombre, cliente.apellido), ("Ana", "María Pérez"))

        servicio = Servicio.objects.get()
        self.assertEqual(servicio.estado, Servicio.Estado.COTIZACION)
        self.assertEqual(servicio.cantidad_personas, 80)
        self.assertTrue(servicio.requiere_despacho)
        self.assertEqual(servicio.medio_contacto, "WhatsApp")
        self.assertEqual(servicio.comentarios, "Matrimonio al aire libre.")
        self.assertEqual(set(servicio.categorias_solicitadas.all()), {self.vajilla, self.cristaleria})
        # Solo se guarda lo que pidió el cliente: sin artículos ni cantidades inventadas.
        self.assertFalse(DetalleServicio.objects.exists())

    def test_respuesta_no_expone_codigo(self):
        respuesta = self.enviar()
        servicio = Servicio.objects.get()
        self.assertNotIn(servicio.codigo, respuesta.content.decode())
        self.assertNotIn(str(servicio.id), respuesta.json()["message"])

    def test_reutiliza_cliente_con_otro_formato_de_rut(self):
        self.enviar()
        self.enviar(rut="12345678-5", telefono="", correo="", comentarios="")
        self.assertEqual(Cliente.objects.count(), 1)
        self.assertEqual(Servicio.objects.count(), 2)
        cliente = Cliente.objects.get()
        # Los datos opcionales que vienen vacíos no borran los anteriores.
        self.assertEqual(cliente.email, "ana@ejemplo.cl")
        self.assertEqual(cliente.telefono, "+56 9 1234 5678")

    def test_reconoce_cliente_antiguo_con_rut_con_puntos(self):
        Cliente.objects.create(negocio=self.negocio, rut="12.345.678-5", nombre="Ana")
        self.enviar()
        self.assertEqual(Cliente.objects.count(), 1)
        self.assertEqual(Cliente.objects.get().rut, "123456785")

    def test_rut_registrado_con_otro_nombre_se_rechaza(self):
        self.enviar()
        respuesta = self.enviar(nombre="Juan Soto")
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("rut", respuesta.json()["errors"])
        # No expone el nombre registrado.
        self.assertNotIn("Ana", respuesta.content.decode())
        self.assertEqual(Servicio.objects.count(), 1)

    def test_rut_registrado_acepta_variantes_del_mismo_nombre(self):
        self.enviar()
        for nombre in ("ana perez", "Ana María Pérez Soto", "ANA MARIA PEREZ"):
            self.assertTrue(self.enviar(nombre=nombre).json()["ok"], nombre)
        self.assertEqual(Cliente.objects.count(), 1)

    def test_campos_opcionales_vacios(self):
        respuesta = self.enviar(telefono="", correo="", medioContacto="", comentarios="", direccion="")
        self.assertTrue(respuesta.json()["ok"])

    def test_aun_no_estoy_seguro_es_excluyente(self):
        self.enviar(categorias=["por-definir", str(self.vajilla.id)])
        servicio = Servicio.objects.get()
        self.assertTrue(servicio.categorias_por_definir)
        self.assertFalse(servicio.categorias_solicitadas.exists())

    def test_errores_de_validacion(self):
        casos = {
            "rut": {"rut": "12.345.678-9"},
            "fecha": {"fecha": (date.today() - timedelta(days=1)).isoformat()},
            "invitados": {"invitados": "0"},
            "categorias": {"categorias": []},
            "correo": {"correo": "no-es-correo"},
            "telefono": {"telefono": "12"},
            "tipoEvento": {"tipoEvento": "Fiesta inventada"},
            "nombre": {"nombre": ""},
        }
        for campo, cambios in casos.items():
            with self.subTest(campo=campo):
                respuesta = self.enviar(**cambios)
                self.assertEqual(respuesta.status_code, 400)
                self.assertIn(campo, respuesta.json()["errors"])
        self.assertFalse(Servicio.objects.exists())
        self.assertFalse(Cliente.objects.exists())

    def test_categoria_desconocida(self):
        respuesta = self.enviar(categorias=["99999"])
        self.assertIn("categorias", respuesta.json()["errors"])

    def test_envio_sin_javascript_muestra_mensaje(self):
        respuesta = self.client.post(self.url, self.datos())
        self.assertContains(respuesta, "fue enviada correctamente")
        self.assertNotContains(respuesta, Servicio.objects.get().codigo)


class AdministracionTests(TestCase):
    def setUp(self):
        self.negocio, self.vajilla, _, self.plato = crear_base()
        rol = Rol.objects.create(nombre="Administrador")
        self.admin = Usuario.objects.create(
            negocio=self.negocio, rol=rol, nombre="Helen", apellido="Cortés",
            email="admin@ejemplo.cl", password="x",
        )
        self.client.post(reverse("cotizador"), {
            "tipoEvento": "Cumpleaños", "fecha": EN_10_DIAS.isoformat(), "invitados": "40",
            "comuna": "Maipú", "despacho": "No, retiro yo", "categorias": [str(self.vajilla.id)],
            "nombre": "Pedro Soto", "rut": RUT_VALIDO, "correo": "pedro@ejemplo.cl",
            "medioContacto": "Correo", "comentarios": "Necesito platos negros.",
        }, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.servicio = Servicio.objects.get()

    def iniciar_sesion(self, usuario=None):
        sesion = self.client.session
        sesion["usuario_id"] = (usuario or self.admin).id
        sesion.save()

    def test_sin_sesion_redirige_al_login(self):
        for url in (reverse("gestion_cotizaciones"), reverse("gestion_cotizacion", args=[self.servicio.id])):
            respuesta = self.client.get(url)
            self.assertEqual(respuesta.status_code, 302)
            self.assertIn(reverse("gestion_login"), respuesta["Location"])

    def test_rol_sin_permiso_recibe_403(self):
        otro_rol = Rol.objects.create(nombre="Bodega")
        usuario = Usuario.objects.create(
            negocio=self.negocio, rol=otro_rol, nombre="B", apellido="B", email="b@ejemplo.cl", password="x",
        )
        self.iniciar_sesion(usuario)
        self.assertEqual(self.client.get(reverse("gestion_cotizaciones")).status_code, 403)

    def test_lista_muestra_y_filtra_la_solicitud(self):
        self.iniciar_sesion()
        url = reverse("gestion_cotizaciones")
        fila = reverse("gestion_cotizacion", args=[self.servicio.id])
        self.assertContains(self.client.get(url), fila)
        self.assertContains(self.client.get(url, {"q": "12.345.678-5"}), fila)
        self.assertContains(self.client.get(url, {"q": "pedro@ejemplo"}), fila)
        self.assertContains(self.client.get(url, {"q": "Pedro Soto"}), fila)
        self.assertContains(self.client.get(url, {"estado": "Cotizacion"}), fila)
        self.assertNotContains(self.client.get(url, {"estado": "Confirmado"}), fila)
        self.assertNotContains(self.client.get(url, {"desde": (EN_10_DIAS + timedelta(days=1)).isoformat()}), fila)

    def test_detalle_muestra_categorias_y_comentarios(self):
        self.iniciar_sesion()
        respuesta = self.client.get(reverse("gestion_cotizacion", args=[self.servicio.id]))
        self.assertContains(respuesta, "Vajilla")
        self.assertContains(respuesta, "Necesito platos negros.")
        self.assertContains(respuesta, "12.345.678-5")

    def test_confirmar_desde_el_detalle(self):
        self.iniciar_sesion()
        url = reverse("gestion_cotizacion", args=[self.servicio.id])
        self.client.post(url, {"accion": "agregar_articulo", "articulo_id": self.plato.id, "cantidad": 40})
        self.client.post(url, {"accion": "confirmar"})
        self.servicio.refresh_from_db()
        self.assertEqual(self.servicio.estado, Servicio.Estado.CONFIRMADO)
        self.assertIsNotNone(self.servicio.fecha_confirmacion)

    def test_catalogo_agrega_varios_productos_de_una_vez(self):
        self.iniciar_sesion()
        copa = Articulo.objects.create(negocio=self.negocio, categoria=self.vajilla, codigo="vaj-009", nombre="Copa",
                                       precio_arriendo=300, stock_total=50, stock_trabajable=50)
        url = reverse("gestion_cotizacion", args=[self.servicio.id])
        catalogo = self.client.get(url).context["catalogo"]
        # Cada producto trae la disponibilidad para la fecha del evento.
        self.assertEqual(catalogo[0]["etiqueta"], "Vajilla")
        self.assertEqual({a.nombre: a.disponible_fecha for a in catalogo[0]["productos"]}, {"Copa": 50, "Plato principal": 100})

        respuesta = self.client.post(url, {
            "accion": "agregar_articulos",
            "articulo_id": [self.plato.id, copa.id],
            "cantidad": ["40", ""],
        }, follow=True)
        self.assertContains(respuesta, "Se agregaron 1 producto: 40 × Plato principal")
        self.client.post(url, {"accion": "agregar_articulos", "articulo_id": [self.plato.id, copa.id], "cantidad": ["5", "20"]})
        cantidades = dict(self.servicio.detalles.values_list("articulo__nombre", "cantidad"))
        self.assertEqual(cantidades, {"Plato principal": 45, "Copa": 20})
        self.servicio.refresh_from_db()
        self.assertEqual(self.servicio.total, 45 * 500 + 20 * 300)

    def test_catalogo_solo_ofrece_productos_con_stock(self):
        self.iniciar_sesion()
        Articulo.objects.create(negocio=self.negocio, categoria=self.vajilla, codigo="vaj-010", nombre="Sin stock",
                                precio_arriendo=100, stock_total=0, stock_trabajable=0)
        agotado = Articulo.objects.create(negocio=self.negocio, categoria=self.vajilla, codigo="vaj-011", nombre="Agotado",
                                          precio_arriendo=100, stock_total=10, stock_trabajable=10)
        confirmar_servicio(crear_servicio(self.negocio, agotado, 10, EN_10_DIAS, estado=Servicio.Estado.COTIZACION, rut="9").id)
        url = reverse("gestion_cotizacion", args=[self.servicio.id])
        nombres = [a.nombre for g in self.client.get(url).context["catalogo"] for a in g["productos"]]
        self.assertEqual(nombres, ["Plato principal"])
        # Aunque llegue en el formulario, el servidor no lo agrega.
        respuesta = self.client.post(url, {"accion": "agregar_articulos", "articulo_id": [agotado.id], "cantidad": ["2"]}, follow=True)
        self.assertContains(respuesta, "Agotado no tiene stock disponible")
        self.assertFalse(self.servicio.detalles.filter(articulo=agotado).exists())

    def test_catalogo_rechaza_cantidades_invalidas_sin_agregar_nada(self):
        self.iniciar_sesion()
        url = reverse("gestion_cotizacion", args=[self.servicio.id])
        for cantidad in ("-3", "2.5", "abc"):
            respuesta = self.client.post(url, {"accion": "agregar_articulos", "articulo_id": [self.plato.id], "cantidad": [cantidad]}, follow=True)
            self.assertContains(respuesta, "No se agregó nada")
        self.assertFalse(self.servicio.detalles.exists())

    def test_confirmar_sin_stock_no_cambia_el_estado(self):
        self.iniciar_sesion()
        crear_servicio(self.negocio, self.plato, 80, EN_10_DIAS)
        url = reverse("gestion_cotizacion", args=[self.servicio.id])
        self.client.post(url, {"accion": "agregar_articulo", "articulo_id": self.plato.id, "cantidad": 40})
        respuesta = self.client.post(url, {"accion": "confirmar"}, follow=True)
        self.servicio.refresh_from_db()
        self.assertEqual(self.servicio.estado, Servicio.Estado.COTIZACION)
        self.assertContains(respuesta, "Plato principal: solicitado 40, disponible 20")

    def test_no_se_puede_saltar_a_preparacion_con_el_selector(self):
        self.iniciar_sesion()
        crear_servicio(self.negocio, self.plato, 80, EN_10_DIAS)
        url = reverse("gestion_cotizacion", args=[self.servicio.id])
        self.client.post(url, {"accion": "agregar_articulo", "articulo_id": self.plato.id, "cantidad": 40})
        self.client.post(url, {"accion": "cambiar_estado", "estado": "Preparacion"})
        self.servicio.refresh_from_db()
        self.assertEqual(self.servicio.estado, Servicio.Estado.COTIZACION)


class DisponibilidadTests(TestCase):
    def setUp(self):
        self.negocio, _, _, self.plato = crear_base()
        self.dia = EN_10_DIAS

    def cotizacion(self, cantidad, inicio=None, fin=None):
        return crear_servicio(
            self.negocio, self.plato, cantidad, inicio or self.dia, fin,
            estado=Servicio.Estado.COTIZACION, rut="222222222",
        )

    def test_1_sin_reservas_superpuestas(self):
        servicio = self.cotizacion(80)
        confirmar_servicio(servicio.id)
        servicio.refresh_from_db()
        self.assertEqual(servicio.estado, Servicio.Estado.CONFIRMADO)

    def test_2_reserva_existente_con_stock_suficiente(self):
        crear_servicio(self.negocio, self.plato, 30, self.dia)
        servicio = self.cotizacion(70)
        confirmar_servicio(servicio.id)
        resultado = calcular_disponibilidad(self.plato, self.dia, self.dia)
        self.assertEqual(resultado["comprometido"], 100)
        self.assertEqual(resultado["disponible"], 0)

    def test_3_la_suma_supera_el_stock(self):
        crear_servicio(self.negocio, self.plato, 70, self.dia)
        servicio = self.cotizacion(40)
        with self.assertRaises(StockInsuficiente) as error:
            confirmar_servicio(servicio.id)
        faltante = error.exception.faltantes[0]
        self.assertEqual((faltante["solicitado"], faltante["disponible"], faltante["faltante"]), (40, 30, 10))
        servicio.refresh_from_db()
        self.assertEqual(servicio.estado, Servicio.Estado.COTIZACION)

    def test_4_reserva_en_otras_fechas_no_afecta(self):
        crear_servicio(self.negocio, self.plato, 90, self.dia + timedelta(days=5), self.dia + timedelta(days=7))
        servicio = self.cotizacion(80, self.dia, self.dia + timedelta(days=2))
        confirmar_servicio(servicio.id)

    def test_rangos_que_se_tocan_si_se_superponen(self):
        crear_servicio(self.negocio, self.plato, 90, self.dia, self.dia + timedelta(days=2))
        servicio = self.cotizacion(80, self.dia + timedelta(days=2), self.dia + timedelta(days=3))
        with self.assertRaises(StockInsuficiente):
            confirmar_servicio(servicio.id)

    def test_5_cotizacion_no_confirmada_no_bloquea(self):
        self.cotizacion(90)
        crear_servicio(self.negocio, self.plato, 90, self.dia, estado=Servicio.Estado.CANCELADO)
        servicio = self.cotizacion(80)
        confirmar_servicio(servicio.id)

    def test_6_el_mismo_servicio_no_se_cuenta_dos_veces(self):
        servicio = crear_servicio(self.negocio, self.plato, 60, self.dia)
        fila = disponibilidad_servicio(servicio)[0]
        self.assertEqual(fila["disponible"], 100)
        self.assertEqual(fila["faltante"], 0)

    def test_7_dos_confirmaciones_seguidas_no_sobrevenden(self):
        primera = self.cotizacion(60)
        segunda = self.cotizacion(60)
        confirmar_servicio(primera.id)
        with self.assertRaises(StockInsuficiente):
            confirmar_servicio(segunda.id)


class InventarioPanelTests(TestCase):
    def setUp(self):
        self.negocio, self.vajilla, _, self.plato = crear_base()
        self.plato.stock_total = self.plato.stock_trabajable = 0
        self.plato.save()
        rol = Rol.objects.create(nombre="Administrador")
        admin = Usuario.objects.create(
            negocio=self.negocio, rol=rol, nombre="Helen", apellido="Cortés", email="a@ejemplo.cl", password="x",
        )
        sesion = self.client.session
        sesion["usuario_id"] = admin.id
        sesion.save()
        self.url = reverse("gestion_producto", args=[self.plato.id])

    def editar(self, **cambios):
        datos = {
            "accion": "editar", "nombre": self.plato.nombre, "categoria_id": self.vajilla.id,
            "precio_arriendo": 500, "stock_total": 40, "stock_trabajable": 40, "activo": "on",
        }
        datos.update(cambios)
        return self.client.post(self.url, datos, follow=True)

    def test_ficha_es_la_del_panel(self):
        respuesta = self.client.get(self.url)
        self.assertTemplateUsed(respuesta, "producto-admin.html")
        self.assertContains(respuesta, "Editar producto y stock")

    def test_editar_stock_vuelve_al_listado_y_registra_movimiento(self):
        respuesta = self.editar(motivo="Compra inicial")
        self.assertRedirects(respuesta, reverse("gestion_inventario"))
        self.assertContains(respuesta, "stock total 40")
        self.plato.refresh_from_db()
        self.assertEqual((self.plato.stock_total, self.plato.stock_trabajable), (40, 40))
        movimiento = self.plato.movimientos.get()
        self.assertEqual((movimiento.tipo, movimiento.cantidad, movimiento.motivo), ("Ajuste", 40, "Compra inicial"))

    def test_stock_invalido_no_se_guarda(self):
        self.editar(stock_total=10, stock_trabajable=20)
        self.editar(stock_total=-5, stock_trabajable=0)
        self.plato.refresh_from_db()
        self.assertEqual(self.plato.stock_total, 0)

    def test_listado_muestra_comprometido_y_disponible(self):
        self.editar()
        servicio = crear_servicio(self.negocio, self.plato, 15, EN_10_DIAS, estado=Servicio.Estado.COTIZACION)
        confirmar_servicio(servicio.id)
        crear_servicio(self.negocio, self.plato, 30, date.today() - timedelta(days=30))  # reserva pasada
        fila = next(a for a in self.client.get(reverse("gestion_inventario")).context["inventario"] if a.id == self.plato.id)
        self.assertEqual((fila.stock_comprometido, fila.stock_disponible), (15, 25))

    def test_inventario_agrupado_por_categoria_con_totales(self):
        self.editar()
        Articulo.objects.create(negocio=self.negocio, categoria=self.vajilla, codigo="vaj-002", nombre="Plato hondo",
                                precio_arriendo=400, stock_total=8, stock_trabajable=8)
        servicio = crear_servicio(self.negocio, self.plato, 15, EN_10_DIAS, estado=Servicio.Estado.COTIZACION)
        confirmar_servicio(servicio.id)
        respuesta = self.client.get(reverse("gestion_inventario"))
        grupo = respuesta.context["categorias_inventario"][0]
        self.assertEqual(grupo["etiqueta"], "Vajilla")
        self.assertEqual((grupo["trabajable"], grupo["disponible"], grupo["comprometido"]), (48, 33, 15))
        # El plato hondo (8 unidades) queda marcado con stock bajo.
        self.assertEqual(grupo["bajos"], 1)
        self.assertContains(respuesta, "−15 por reservas")
        self.assertContains(respuesta, "33</strong> de 48 disponibles")

    def test_crear_producto_con_codigo_automatico(self):
        respuesta = self.client.post(reverse("gestion_inventario"), {
            "accion": "crear", "nombre": "Copa flauta", "categoria_id": self.vajilla.id,
            "precio_arriendo": 300, "stock_total": 50, "stock_trabajable": 50, "activo": "on",
        }, follow=True)
        articulo = Articulo.objects.get(nombre="Copa flauta")
        self.assertTrue(articulo.codigo)
        self.assertContains(respuesta, "Producto Copa flauta creado")
        self.assertEqual(articulo.movimientos.get().cantidad, 50)

    def test_resumen_y_reportes_cuentan_solo_reservas(self):
        self.editar()
        cotizacion = crear_servicio(self.negocio, self.plato, 10, EN_10_DIAS, estado=Servicio.Estado.COTIZACION)
        respuesta = self.client.get(reverse("inicio"))
        self.assertEqual(respuesta.context["productos_mas_arrendados"], [])
        confirmar_servicio(cotizacion.id)
        respuesta = self.client.get(reverse("inicio"))
        self.assertEqual(respuesta.context["productos_mas_arrendados"][0]["cantidad"], 10)
        self.assertEqual(len(respuesta.context["proximos_eventos"]), 1)
        self.assertNotContains(respuesta, "Datos de ejemplo")
        self.assertEqual(respuesta.context["articulos_disponibles"], 30)
        reportes = self.client.get(reverse("gestion_reportes"))
        self.assertEqual(reportes.context["metricas"]["reservas_total"], 1)


@unittest.skipUnless(connection.vendor == "postgresql", "Requiere PostgreSQL para probar bloqueos reales.")
class ConcurrenciaTests(TransactionTestCase):
    """Caso 7 con dos hilos reales: solo una de las dos confirmaciones puede pasar."""

    def test_confirmaciones_simultaneas(self):
        negocio, _, _, plato = crear_base()
        servicios = [
            crear_servicio(negocio, plato, 60, EN_10_DIAS, estado=Servicio.Estado.COTIZACION, rut=f"{i}11111111")
            for i in (1, 2)
        ]
        resultados = []
        barrera = threading.Barrier(2)

        def confirmar(servicio_id):
            barrera.wait()
            try:
                confirmar_servicio(servicio_id)
                resultados.append("ok")
            except StockInsuficiente:
                resultados.append("sin stock")
            finally:
                connection.close()

        hilos = [threading.Thread(target=confirmar, args=(s.id,)) for s in servicios]
        for hilo in hilos:
            hilo.start()
        for hilo in hilos:
            hilo.join()
        self.assertEqual(sorted(resultados), ["ok", "sin stock"])


class EscenarioReserva(TestCase):
    """Reserva confirmada con 40 platos y 20 copas, y un administrador con sesión iniciada."""

    def setUp(self):
        self.negocio, self.vajilla, self.cristaleria, self.plato = crear_base()
        self.copa = Articulo.objects.create(
            negocio=self.negocio, categoria=self.cristaleria, codigo="cris-001", nombre="Copa de vino",
            precio_arriendo=300, stock_total=50, stock_trabajable=50,
        )
        rol = Rol.objects.create(nombre="Administrador")
        self.admin = Usuario.objects.create(
            negocio=self.negocio, rol=rol, nombre="Helen", apellido="Cortés", email="a@ejemplo.cl", password="x",
        )
        self.servicio = crear_servicio(self.negocio, self.plato, 40, EN_10_DIAS)
        DetalleServicio.objects.create(
            servicio=self.servicio, articulo=self.copa, cantidad=20, precio_unitario=300, subtotal=6000,
        )
        self.iniciar_sesion()

    def iniciar_sesion(self, usuario=None):
        sesion = self.client.session
        sesion["usuario_id"] = (usuario or self.admin).id
        sesion.save()

    def generar(self, servicio=None):
        servicio = servicio or self.servicio
        return self.client.post(
            reverse("gestion_reserva", args=[servicio.id]), {"accion": "generar_preparacion"}, follow=True,
        )

    def preparacion(self):
        return Preparacion.objects.get(servicio=self.servicio)

    def url_hoja(self):
        return reverse("gestion_preparacion_documento", args=[self.preparacion().id])

    def guardar(self, cantidades, observaciones=None, **extra):
        """`observaciones`: dict por artículo (formato anterior) o texto de observaciones generales."""
        detalles = {d.articulo_id: d for d in self.preparacion().detalles.all()}
        datos = {
            "accion": "guardar",
            "detalle_id": [detalles[a].id for a in cantidades],
            "cantidad_preparada": [str(c) for c in cantidades.values()],
            "observaciones": observaciones if isinstance(observaciones, str) else "",
        }
        if isinstance(observaciones, dict):
            datos["observacion_detalle"] = [observaciones.get(a, "") for a in cantidades]
        datos.update(extra)
        return self.client.post(self.url_hoja(), datos, follow=True)

    def finalizar(self):
        return self.client.post(self.url_hoja(), {"accion": "finalizar"}, follow=True)



class PreparacionTests(EscenarioReserva):
    """Flujo Reserva confirmada → preparación → preparación completa."""

    # 1 y 4
    def test_1_reserva_confirmada_genera_preparacion_con_sus_articulos(self):
        respuesta = self.generar()
        preparacion = self.preparacion()
        self.assertRedirects(respuesta, self.url_hoja())
        self.assertEqual(preparacion.estado, Preparacion.Estado.PENDIENTE)
        self.assertEqual(preparacion.usuario, self.admin)
        self.assertEqual(
            {(d.articulo_id, d.cantidad_solicitada, d.cantidad_preparada) for d in preparacion.detalles.all()},
            {(self.plato.id, 40, 0), (self.copa.id, 20, 0)},
        )

    def test_2_cotizacion_sin_confirmar_no_genera_preparacion(self):
        cotizacion = crear_servicio(self.negocio, self.plato, 10, EN_10_DIAS, estado=Servicio.Estado.COTIZACION)
        respuesta = self.generar(cotizacion)
        self.assertContains(respuesta, "Solo una reserva confirmada")
        self.assertFalse(Preparacion.objects.filter(servicio=cotizacion).exists())

    def test_3_no_se_crean_dos_preparaciones(self):
        self.generar()
        self.servicio.estado = Servicio.Estado.CONFIRMADO  # aunque alguien fuerce el estado
        self.servicio.save()
        with self.assertRaises(OperacionInvalida):
            generar_preparacion(self.servicio.id, self.admin)
        self.assertEqual(Preparacion.objects.filter(servicio=self.servicio).count(), 1)

    def test_reserva_sin_articulos_o_con_evento_pasado_no_genera(self):
        sin_articulos = crear_servicio(self.negocio, self.plato, 1, EN_10_DIAS)
        sin_articulos.detalles.all().delete()
        pasada = crear_servicio(self.negocio, self.plato, 1, date.today() - timedelta(days=1))
        for servicio in (sin_articulos, pasada):
            with self.assertRaises(OperacionInvalida):
                generar_preparacion(servicio.id, self.admin)
        self.assertFalse(Preparacion.objects.filter(servicio__in=[sin_articulos, pasada]).exists())

    def test_5_y_6_cantidades_invalidas_se_rechazan_sin_guardar_nada(self):
        self.generar()
        for valor in ("-1", "2.5", "abc", "", "41"):
            with self.subTest(valor=valor):
                respuesta = self.guardar({self.plato.id: 10, self.copa.id: valor})
                self.assertEqual(respuesta.status_code, 400)
                self.assertContains(respuesta, "No se guardó el avance", status_code=400)
        self.assertEqual(sum(d.cantidad_preparada for d in self.preparacion().detalles.all()), 0)

    def test_hoja_lista_por_categoria_y_una_hoja_impresa_por_categoria(self):
        self.generar()
        pagina = self.client.get(self.url_hoja())
        self.assertEqual([g["etiqueta"] for g in pagina.context["por_categoria"]], ["Cristalería", "Vajilla"])
        self.assertEqual(pagina.content.decode().count('class="hoja" data-hoja='), 2)
        self.assertNotContains(pagina, 'name="cantidad_preparada"')
        self.assertContains(pagina, "Marcar pedido como preparado")

    def test_marcar_pedido_como_preparado_habilita_el_despacho(self):
        self.generar()
        respuesta = self.client.post(self.url_hoja(), {"accion": "completar", "observaciones": "Copas envueltas"}, follow=True)
        self.assertContains(respuesta, "Pedido marcado como preparado")
        preparacion = self.preparacion()
        self.servicio.refresh_from_db()
        self.assertEqual((preparacion.estado, self.servicio.estado), (Preparacion.Estado.COMPLETA, Servicio.Estado.PREPARADO))
        self.assertEqual(preparacion.observaciones, "Copas envueltas")
        self.assertTrue(all(d.cantidad_faltante == 0 for d in preparacion.detalles.all()))
        self.assertContains(respuesta, reverse("gestion_registrar_despacho", args=[self.servicio.id]))

    def test_articulo_ajeno_o_repetido_se_rechaza(self):
        self.generar()
        otro = crear_servicio(self.negocio, self.plato, 5, EN_10_DIAS)
        ajena = generar_preparacion(otro.id, self.admin).detalles.get()
        propio = self.preparacion().detalles.get(articulo=self.plato)
        for ids in ([ajena.id], [propio.id, propio.id]):
            respuesta = self.client.post(self.url_hoja(), {
                "accion": "guardar", "detalle_id": ids, "cantidad_preparada": ["1"] * len(ids),
                "observacion_detalle": [""] * len(ids),
            })
            self.assertEqual(respuesta.status_code, 400)
        ajena.refresh_from_db()
        self.assertEqual(ajena.cantidad_preparada, 0)

    def test_avance_sin_observacion_por_articulo_conserva_la_existente(self):
        self.generar()
        self.guardar({self.plato.id: 10, self.copa.id: 5}, observaciones={self.copa.id: "5 trizadas"})
        self.guardar({self.plato.id: 40, self.copa.id: 20}, observaciones="Todo listo")
        copa = self.preparacion().detalles.get(articulo=self.copa)
        self.assertEqual((copa.cantidad_preparada, copa.observaciones), (20, "5 trizadas"))
        self.assertEqual(self.preparacion().observaciones, "Todo listo")

    def test_guardar_avance_registra_cantidades_y_observacion(self):
        self.generar()
        self.guardar({self.plato.id: 40, self.copa.id: 15}, observaciones={self.copa.id: "5 trizadas"})
        preparacion = self.preparacion()
        self.assertEqual(preparacion.estado, Preparacion.Estado.EN_PREPARACION)
        self.assertIsNotNone(preparacion.fecha_inicio)
        copa = preparacion.detalles.get(articulo=self.copa)
        self.assertEqual((copa.cantidad_preparada, copa.cantidad_faltante, copa.observaciones), (15, 5, "5 trizadas"))
        self.assertTrue(HistorialServicio.objects.filter(servicio=self.servicio, accion="Guardar avance de preparación").exists())

    def test_7_no_se_puede_finalizar_con_faltantes(self):
        self.generar()
        self.guardar({self.plato.id: 40, self.copa.id: 15})
        respuesta = self.finalizar()
        self.assertContains(respuesta, "hay artículos incompletos", status_code=400)
        self.assertContains(respuesta, "Copa de vino: preparado 15 de 20 (faltan 5)", status_code=400)
        self.assertEqual(self.preparacion().estado, Preparacion.Estado.EN_PREPARACION)
        self.servicio.refresh_from_db()
        self.assertEqual(self.servicio.estado, Servicio.Estado.PREPARACION)

    def test_8_y_9_flujo_completo_cambia_estados_y_deja_historial(self):
        self.generar()
        self.servicio.refresh_from_db()
        self.assertEqual(self.servicio.estado, Servicio.Estado.PREPARACION)

        self.guardar({self.plato.id: 40, self.copa.id: 20})
        self.finalizar()

        preparacion = self.preparacion()
        self.servicio.refresh_from_db()
        self.assertEqual(preparacion.estado, Preparacion.Estado.COMPLETA)
        self.assertEqual(preparacion.finalizada_por, self.admin)
        self.assertIsNotNone(preparacion.fecha_finalizacion)
        self.assertEqual(self.servicio.estado, Servicio.Estado.PREPARADO)
        self.assertEqual(
            list(self.servicio.historial.order_by("fecha", "id").values_list("accion", "estado_anterior", "estado_nuevo")),
            [
                ("Generar preparación", "Confirmado", "Preparacion"),
                ("Guardar avance de preparación", "Preparacion", "Preparacion"),
                ("Finalizar preparación", "Preparacion", "Preparado"),
            ],
        )

    def test_preparacion_completa_no_se_puede_editar(self):
        self.generar()
        self.guardar({self.plato.id: 40, self.copa.id: 20})
        self.finalizar()
        respuesta = self.guardar({self.plato.id: 0, self.copa.id: 0})
        self.assertContains(respuesta, "ya está completa", status_code=400)
        self.assertEqual(self.preparacion().detalles.get(articulo=self.plato).cantidad_preparada, 40)

    def test_preparado_sigue_reteniendo_stock_y_no_permite_editar_articulos(self):
        self.generar()
        self.guardar({self.plato.id: 40, self.copa.id: 20})
        self.finalizar()
        # Las 40 unidades siguen comprometidas: otra reserva el mismo día solo puede tomar 60.
        otra = crear_servicio(self.negocio, self.plato, 61, EN_10_DIAS, estado=Servicio.Estado.COTIZACION, rut="222222222")
        with self.assertRaises(StockInsuficiente):
            confirmar_servicio(otra.id)
        url = reverse("gestion_cotizacion", args=[self.servicio.id])
        self.client.post(url, {"accion": "agregar_articulo", "articulo_id": self.plato.id, "cantidad": 5})
        self.assertEqual(self.servicio.detalles.get(articulo=self.plato).cantidad, 40)

    def test_reserva_cancelada_no_admite_avance(self):
        self.generar()
        Servicio.objects.filter(id=self.servicio.id).update(estado=Servicio.Estado.CANCELADO)
        respuesta = self.guardar({self.plato.id: 1, self.copa.id: 1})
        self.assertContains(respuesta, "no admite cambios", status_code=400)

    def test_10_usuario_sin_permisos_recibe_rechazo(self):
        self.generar()
        url_hoja = self.url_hoja()
        bodega = Usuario.objects.create(
            negocio=self.negocio, rol=Rol.objects.create(nombre="Bodega"), nombre="B", apellido="B",
            email="b@ejemplo.cl", password="x",
        )
        self.iniciar_sesion(bodega)
        for url in (reverse("gestion_preparacion"), url_hoja):
            self.assertEqual(self.client.get(url).status_code, 403)
        respuesta = self.client.post(url_hoja, {"accion": "finalizar"})
        self.assertEqual(respuesta.status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get(url_hoja).status_code, 302)

    def test_listado_muestra_pendientes_progreso_y_filtros(self):
        url = reverse("gestion_preparacion")
        self.assertContains(self.client.get(url), "Reservas confirmadas sin preparación (1)")
        self.client.post(url, {"accion": "generar", "servicio_id": self.servicio.id})
        self.guardar({self.plato.id: 40, self.copa.id: 5})
        respuesta = self.client.get(url)
        self.assertNotContains(respuesta, "Reservas confirmadas sin preparación")
        self.assertContains(respuesta, "45/60 · 75 %")
        self.assertContains(self.client.get(url, {"estado": "En preparacion"}), self.servicio.codigo)
        self.assertNotContains(self.client.get(url, {"estado": "Completa"}), self.servicio.codigo)
        self.assertContains(self.client.get(url, {"q": "111111111"}), self.servicio.codigo)
        manana = (EN_10_DIAS + timedelta(days=1)).isoformat()
        self.assertNotContains(self.client.get(url, {"desde": manana}), self.servicio.codigo)

    def test_selector_de_estado_solo_ofrece_transiciones_permitidas(self):
        url = reverse("gestion_cotizacion", args=[self.servicio.id])
        opciones = [valor for valor, _ in self.client.get(url).context["estados_servicio"]]
        self.assertEqual(opciones, [Servicio.Estado.CONFIRMADO, Servicio.Estado.CANCELADO])
        self.client.post(url, {"accion": "cambiar_estado", "estado": Servicio.Estado.DESPACHADO})
        self.servicio.refresh_from_db()
        self.assertEqual(self.servicio.estado, Servicio.Estado.CONFIRMADO)


class DespachoTests(EscenarioReserva):
    """Flujo preparación completa → despacho registrado."""

    def preparar_completo(self):
        self.generar()
        self.guardar({self.plato.id: 40, self.copa.id: 20})
        self.finalizar()

    def url_registrar(self):
        return reverse("gestion_registrar_despacho", args=[self.servicio.id])

    def despachar(self, **cambios):
        datos = {
            "tipo_entrega": "Despacho",
            "fecha_salida": timezone.localtime().strftime("%Y-%m-%dT%H:%M"),
            "responsable": "Carlos Rojas",
            "receptor": "Juan Pérez",
            "observaciones": "Dejar en conserjería.",
        }
        datos.update(cambios)
        return self.client.post(self.url_registrar(), datos, follow=True)

    def test_d1_preparacion_incompleta_no_se_despacha(self):
        self.generar()
        self.guardar({self.plato.id: 40, self.copa.id: 10})
        respuesta = self.despachar()
        self.assertEqual(respuesta.status_code, 400)
        self.assertContains(respuesta, "Solo una reserva con la preparación finalizada", status_code=400)
        self.assertFalse(Despacho.objects.exists())

    def test_d2_d4_d5_d6_preparacion_completa_genera_despacho(self):
        self.preparar_completo()
        respuesta = self.despachar()
        despacho = Despacho.objects.get()
        self.assertRedirects(respuesta, reverse("gestion_despacho_documento", args=[despacho.id]))
        self.servicio.refresh_from_db()
        self.assertEqual(self.servicio.estado, Servicio.Estado.DESPACHADO)
        self.assertEqual(
            (despacho.estado, despacho.tipo_entrega, despacho.responsable_entrega, despacho.receptor, despacho.usuario),
            (Despacho.Estado.ENTREGADO, "Despacho", "Carlos Rojas", "Juan Pérez", self.admin),
        )
        self.assertEqual(despacho.preparacion, self.preparacion())
        self.assertIsNotNone(despacho.fecha_despacho)
        self.assertEqual(
            {(d.articulo_id, d.cantidad) for d in despacho.detalles.all()},
            {(d.articulo_id, d.cantidad_preparada) for d in self.preparacion().detalles.all()},
        )
        self.assertContains(respuesta, "60 unidades · 2 artículos")
        self.assertContains(respuesta, "Juan Pérez")

    def test_d3_no_se_despacha_dos_veces(self):
        self.preparar_completo()
        self.despachar()
        respuesta = self.despachar()
        self.assertContains(respuesta, "ya tiene un despacho registrado")
        with self.assertRaises(OperacionInvalida):
            registrar_despacho(self.servicio.id, self.admin, "Despacho", timezone.now(), "Otro")
        self.assertEqual(Despacho.objects.count(), 1)

    def test_d7_despacho_no_descuenta_stock_dos_veces(self):
        self.preparar_completo()
        self.plato.refresh_from_db()
        antes = (self.plato.stock_total, self.plato.stock_trabajable)
        self.despachar()
        self.plato.refresh_from_db()
        self.assertEqual((self.plato.stock_total, self.plato.stock_trabajable), antes)
        # Sigue comprometido (40 de 100): otra reserva el mismo día puede tomar 60, no 61.
        otra = crear_servicio(self.negocio, self.plato, 61, EN_10_DIAS, estado=Servicio.Estado.COTIZACION, rut="222222222")
        with self.assertRaises(StockInsuficiente):
            confirmar_servicio(otra.id)
        otra.detalles.update(cantidad=60)
        confirmar_servicio(otra.id)
        # La salida queda como trazabilidad sin cifras de stock.
        movimiento = MovimientoInventario.objects.get(articulo=self.plato, tipo="Salida a cliente")
        self.assertEqual((movimiento.cantidad, movimiento.stock_anterior, movimiento.stock_nuevo), (-40, None, None))
        fila = next(a for a in self.client.get(reverse("gestion_inventario")).context["inventario"] if a.id == self.plato.id)
        self.assertEqual(fila.fuera_de_bodega, 40)

    def test_d8_aparece_en_calendario_resumen_y_listado(self):
        self.preparar_completo()
        self.despachar()
        eventos = self.client.get(reverse("gestion_calendario")).context["eventos"]
        self.assertTrue(any(e["tipo"] == "entrega" and e["codigo"] == self.servicio.codigo for e in eventos))
        resumen = self.client.get(reverse("inicio")).context
        self.assertEqual(resumen["entregas_hoy"], 1)
        self.assertEqual(resumen["devoluciones_pendientes"], 1)
        listado = self.client.get(reverse("gestion_despachos"), {"vista": "despachados"})
        self.assertContains(listado, self.servicio.codigo)
        self.assertEqual(list(listado.context["pendientes"]), [])

    def test_listado_separa_pendientes_y_filtra(self):
        self.preparar_completo()
        url = reverse("gestion_despachos")
        self.assertContains(self.client.get(url), "Pendientes de despacho (1)")
        self.assertContains(self.client.get(url, {"q": "111111111"}), self.url_registrar())
        self.assertNotContains(self.client.get(url, {"comuna": "Las Condes"}), self.url_registrar())

    def test_d9_si_algo_falla_no_queda_nada_a_medias(self):
        self.preparar_completo()
        with mock.patch("Inventario.operaciones.registrar_historial", side_effect=RuntimeError("falla simulada")):
            with self.assertRaises(RuntimeError):
                registrar_despacho(self.servicio.id, self.admin, "Despacho", timezone.now(), "Carlos")
        self.servicio.refresh_from_db()
        self.assertEqual(self.servicio.estado, Servicio.Estado.PREPARADO)
        self.assertFalse(Despacho.objects.exists())
        self.assertFalse(DetalleDespacho.objects.exists())
        self.assertFalse(MovimientoInventario.objects.filter(tipo="Salida a cliente").exists())

    def test_se_puede_enviar_menos_de_lo_preparado(self):
        self.preparar_completo()
        self.despachar(articulo_id=[self.plato.id, self.copa.id], enviado=["40", "19"])
        despacho = Despacho.objects.get()
        self.assertEqual(dict(despacho.detalles.values_list("articulo_id", "cantidad")), {self.plato.id: 40, self.copa.id: 19})
        self.assertIn("Copa de vino: 19 de 20", self.servicio.historial.first().observacion)
        # La devolución espera solo lo enviado.
        from Inventario.operaciones import estado_devolucion
        _, filas = estado_devolucion(self.servicio)
        self.assertEqual({f["articulo_id"]: f["pendiente"] for f in filas}, {self.plato.id: 40, self.copa.id: 19})

    def test_fecha_de_devolucion_define_el_termino_de_la_reserva(self):
        self.preparar_completo()
        devolucion = EN_10_DIAS + timedelta(days=3)
        self.despachar(fecha_devolucion=devolucion.isoformat())
        self.servicio.refresh_from_db()
        self.assertEqual(self.servicio.fecha_termino, devolucion)
        esperada = next(e for e in self.client.get(reverse("gestion_calendario")).context["eventos"] if e["tipo"] == "devolucion")
        self.assertEqual(esperada["inicio"], devolucion.isoformat())

    def test_fecha_de_devolucion_invalida_o_sin_stock(self):
        self.preparar_completo()
        antes = (date.today() - timedelta(days=1)).isoformat()
        self.assertContains(self.despachar(fecha_devolucion=antes), "no puede ser anterior", status_code=400)
        # Otra reserva usa 61 platos el día siguiente al evento: ampliar la devolución no alcanza.
        otra = crear_servicio(self.negocio, self.plato, 61, EN_10_DIAS + timedelta(days=1), rut="222222222")
        respuesta = self.despachar(fecha_devolucion=(EN_10_DIAS + timedelta(days=2)).isoformat())
        self.assertContains(respuesta, "no alcanza el stock", status_code=400)
        self.assertFalse(Despacho.objects.exists())

    def test_no_se_envia_mas_de_lo_preparado_ni_nada(self):
        self.preparar_completo()
        respuesta = self.despachar(articulo_id=[self.plato.id, self.copa.id], enviado=["41", "20"])
        self.assertContains(respuesta, "No puedes enviar más de lo preparado (40)", status_code=400)
        self.assertContains(respuesta, 'value="41"', status_code=400)
        respuesta = self.despachar(articulo_id=[self.plato.id, self.copa.id], enviado=["0", "0"])
        self.assertContains(respuesta, "Debe salir al menos una unidad", status_code=400)
        self.assertFalse(Despacho.objects.exists())

    def test_datos_invalidos_se_rechazan_y_se_conservan(self):
        self.preparar_completo()
        futuro = (timezone.localtime() + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M")
        for cambios in ({"responsable": ""}, {"tipo_entrega": "Dron"}, {"fecha_salida": "ayer"}, {"fecha_salida": futuro}):
            with self.subTest(cambios=cambios):
                respuesta = self.despachar(**cambios)
                self.assertEqual(respuesta.status_code, 400)
                self.assertContains(respuesta, "Dejar en conserjería.", status_code=400)
        self.assertFalse(Despacho.objects.exists())

    def test_d10_usuario_sin_permisos_no_puede_despachar(self):
        self.preparar_completo()
        bodega = Usuario.objects.create(
            negocio=self.negocio, rol=Rol.objects.create(nombre="Bodega"), nombre="B", apellido="B",
            email="b@ejemplo.cl", password="x",
        )
        self.iniciar_sesion(bodega)
        self.assertEqual(self.client.post(self.url_registrar(), {"tipo_entrega": "Despacho"}).status_code, 403)
        self.assertEqual(self.client.get(reverse("gestion_despachos")).status_code, 403)
        self.assertFalse(Despacho.objects.exists())


class FlujoCompletoTests(TestCase):
    """Cotización → artículos → reserva confirmada → preparación → despacho, todo desde el panel."""

    def test_caso_integral(self):
        negocio, vajilla, _, plato = crear_base()
        rol = Rol.objects.create(nombre="Administrador")
        admin = Usuario.objects.create(negocio=negocio, rol=rol, nombre="Helen", apellido="Cortés",
                                       email="a@ejemplo.cl", password="x")
        self.client.post(reverse("cotizador"), {
            "tipoEvento": "Matrimonio", "fecha": EN_10_DIAS.isoformat(), "invitados": "80", "comuna": "Maipú",
            "despacho": "Sí", "categorias": [str(vajilla.id)], "nombre": "Ana Pérez", "rut": RUT_VALIDO,
        }, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        servicio = Servicio.objects.get()
        sesion = self.client.session
        sesion["usuario_id"] = admin.id
        sesion.save()

        url_cot = reverse("gestion_cotizacion", args=[servicio.id])
        self.client.post(url_cot, {"accion": "agregar_articulo", "articulo_id": plato.id, "cantidad": 80})
        self.client.post(url_cot, {"accion": "confirmar"})
        self.client.post(reverse("gestion_reserva", args=[servicio.id]), {"accion": "generar_preparacion"})
        preparacion = Preparacion.objects.get(servicio=servicio)
        detalle = preparacion.detalles.get()
        url_hoja = reverse("gestion_preparacion_documento", args=[preparacion.id])
        self.client.post(url_hoja, {"accion": "guardar", "detalle_id": [detalle.id], "cantidad_preparada": ["80"],
                                    "observacion_detalle": [""], "observaciones": ""})
        self.client.post(url_hoja, {"accion": "finalizar"})
        self.client.post(reverse("gestion_registrar_despacho", args=[servicio.id]), {
            "tipo_entrega": "Despacho", "fecha_salida": timezone.localtime().strftime("%Y-%m-%dT%H:%M"),
            "responsable": "Carlos", "receptor": "Ana Pérez",
        })

        servicio.refresh_from_db()
        plato.refresh_from_db()
        despacho = Despacho.objects.get(servicio=servicio)
        self.assertEqual(servicio.estado, Servicio.Estado.DESPACHADO)
        self.assertEqual(servicio.detalles.get().cantidad, 80)
        self.assertEqual(despacho.detalles.get().cantidad, 80)
        self.assertEqual((plato.stock_total, plato.stock_trabajable), (100, 100))
        self.assertEqual(calcular_disponibilidad(plato, EN_10_DIAS, EN_10_DIAS)["comprometido"], 80)
        self.assertEqual(
            list(servicio.historial.order_by("fecha", "id").values_list("accion", flat=True)),
            ["Confirmar reserva", "Generar preparación", "Guardar avance de preparación",
             "Finalizar preparación", "Registrar despacho"],
        )
        self.assertTrue(any(e["tipo"] == "entrega" for e in self.client.get(reverse("gestion_calendario")).context["eventos"]))


class DevolucionTests(EscenarioReserva):
    """Despacho → devolución (completa o parcial) → merma → cierre."""

    def despachar_todo(self):
        self.generar()
        self.guardar({self.plato.id: 40, self.copa.id: 20})
        self.finalizar()
        self.client.post(reverse("gestion_registrar_despacho", args=[self.servicio.id]), {
            "tipo_entrega": "Despacho", "fecha_salida": timezone.localtime().strftime("%Y-%m-%dT%H:%M"),
            "responsable": "Carlos",
        })
        self.servicio.refresh_from_db()
        self.assertEqual(self.servicio.estado, Servicio.Estado.DESPACHADO)

    def devolver(self, filas, **extra):
        """filas: {articulo: (buenas, dañadas, perdidas)}"""
        datos = {
            "fecha": timezone.localtime().strftime("%Y-%m-%dT%H:%M"),
            "entregado_por": "Pedro Soto",
            "observaciones": "",
            "articulo_id": [a.id for a in filas],
            "buenas": [str(v[0]) for v in filas.values()],
            "danadas": [str(v[1]) for v in filas.values()],
            "perdidas": [str(v[2]) for v in filas.values()],
            "observacion": ["" for _ in filas],
        }
        datos.update(extra)
        return self.client.post(reverse("gestion_registrar_devolucion", args=[self.servicio.id]), datos, follow=True)

    def disponible(self, articulo, dia=EN_10_DIAS):
        articulo.refresh_from_db()
        return calcular_disponibilidad(articulo, dia, dia)["disponible"]

    def test_devolucion_completa_libera_stock_y_permite_cerrar(self):
        self.despachar_todo()
        self.assertEqual(self.disponible(self.plato), 60)
        respuesta = self.devolver({self.plato: (40, 0, 0), self.copa: (20, 0, 0)})
        self.assertRedirects(respuesta, reverse("gestion_devolucion_servicio", args=[self.servicio.id]))
        self.servicio.refresh_from_db()
        self.assertEqual(self.servicio.estado, Servicio.Estado.FINALIZADO)
        self.assertTrue(Devolucion.objects.get().completa)
        self.assertEqual(self.disponible(self.plato), 100)

        self.client.post(reverse("gestion_reserva", args=[self.servicio.id]), {"accion": "cerrar"})
        self.servicio.refresh_from_db()
        self.assertEqual(self.servicio.estado, Servicio.Estado.CERRADO)
        # Cerrada: no admite más devoluciones.
        respuesta = self.devolver({self.plato: (1, 0, 0)})
        self.assertEqual(respuesta.status_code, 400)

    def test_ejemplo_80_buenas_5_danadas_2_perdidas_13_pendientes(self):
        self.plato.stock_total = self.plato.stock_trabajable = 200
        self.plato.save()
        self.servicio.detalles.filter(articulo=self.plato).update(cantidad=100)
        self.despachar_todo_con(100)
        self.devolver({self.plato: (80, 5, 2), self.copa: (20, 0, 0)})

        self.servicio.refresh_from_db()
        self.plato.refresh_from_db()
        self.assertEqual(self.servicio.estado, Servicio.Estado.DEVOLUCION_PARCIAL)
        # 5 dañadas bajan solo el trabajable; 2 perdidas bajan total y trabajable.
        self.assertEqual((self.plato.stock_total, self.plato.stock_trabajable), (198, 193))
        # Siguen comprometidas las 13 pendientes: 193 - 13 = 180 disponibles.
        self.assertEqual(self.disponible(self.plato), 180)
        self.assertEqual(
            sorted(Merma.objects.filter(articulo=self.plato).values_list("tipo", "cantidad")),
            [("Dañado", 5), ("Perdido", 2)],
        )
        fila = next(a for a in self.client.get(reverse("gestion_inventario")).context["inventario"] if a.id == self.plato.id)
        self.assertEqual(fila.fuera_de_bodega, 13)

        # Vuelven las 13: se liberan, queda Devuelto y se puede cerrar.
        self.devolver({self.plato: (13, 0, 0)})
        self.servicio.refresh_from_db()
        self.assertEqual(self.servicio.estado, Servicio.Estado.FINALIZADO)
        self.assertEqual(self.disponible(self.plato), 193)
        self.assertEqual(Devolucion.objects.count(), 2)

    def despachar_todo_con(self, platos):
        self.generar()
        self.guardar({self.plato.id: platos, self.copa.id: 20})
        self.finalizar()
        self.client.post(reverse("gestion_registrar_despacho", args=[self.servicio.id]), {
            "tipo_entrega": "Despacho", "fecha_salida": timezone.localtime().strftime("%Y-%m-%dT%H:%M"),
            "responsable": "Carlos",
        })

    def test_pendientes_siguen_bloqueando_aunque_el_evento_haya_pasado(self):
        self.despachar_todo()
        self.devolver({self.plato: (30, 0, 0), self.copa: (20, 0, 0)})
        Servicio.objects.filter(id=self.servicio.id).update(
            fecha_evento=date.today() - timedelta(days=3), fecha_inicio=date.today() - timedelta(days=3),
            fecha_termino=date.today() - timedelta(days=3),
        )
        # 10 platos siguen en el cliente: bloquean cualquier fecha futura.
        self.assertEqual(self.disponible(self.plato, date.today() + timedelta(days=30)), 90)
        listado = self.client.get(reverse("gestion_devoluciones"), {"estado": "vencidos"})
        self.assertContains(listado, self.servicio.codigo)

    def test_calendario_muestra_devolucion_esperada_y_luego_recibida(self):
        self.despachar_todo()
        eventos = self.client.get(reverse("gestion_calendario")).context["eventos"]
        esperada = next(e for e in eventos if e["tipo"] == "devolucion")
        self.assertIn("Devolución esperada", esperada["titulo"])
        self.assertEqual(esperada["url"], reverse("gestion_devolucion_servicio", args=[self.servicio.id]))
        self.devolver({self.plato: (40, 0, 0), self.copa: (20, 0, 0)})
        tipos = [e["tipo"] for e in self.client.get(reverse("gestion_calendario")).context["eventos"]]
        self.assertNotIn("devolucion", tipos)
        self.assertIn("retiro", tipos)

    def test_detalle_del_cliente_muestra_el_ciclo(self):
        self.despachar_todo()
        self.devolver({self.plato: (38, 0, 2)})
        cliente = self.servicio.cliente
        respuesta = self.client.get(reverse("gestion_cliente", args=[cliente.id]))
        self.assertContains(respuesta, reverse("gestion_despacho_documento", args=[Despacho.objects.get().id]))
        self.assertContains(respuesta, "20 pendientes")
        self.assertContains(respuesta, "2 en merma")
        self.assertContains(respuesta, "Registrar devolución")

    def test_formulario_con_columna_unica_de_merma(self):
        self.despachar_todo()
        respuesta = self.client.post(reverse("gestion_registrar_devolucion", args=[self.servicio.id]), {
            "fecha": timezone.localtime().strftime("%Y-%m-%dT%H:%M"), "entregado_por": "", "observaciones": "",
            "articulo_id": [self.plato.id, self.copa.id], "buenas": ["37", "20"], "merma": ["3", "0"],
            "observacion": ["Trizados", ""],
        }, follow=True)
        self.assertContains(respuesta, "Devolución registrada")
        merma = Merma.objects.get()
        self.assertEqual((merma.articulo, merma.cantidad, merma.tipo), (self.plato, 3, "Perdido"))
        self.plato.refresh_from_db()
        self.assertEqual(self.plato.stock_total, 97)

    def test_formulario_exige_definir_todas_las_unidades(self):
        self.despachar_todo()
        respuesta = self.client.post(reverse("gestion_registrar_devolucion", args=[self.servicio.id]), {
            "fecha": timezone.localtime().strftime("%Y-%m-%dT%H:%M"), "entregado_por": "", "observaciones": "",
            "articulo_id": [self.plato.id, self.copa.id], "buenas": ["40", "19"], "merma": ["0", "0"],
            "observacion": ["", ""],
        })
        self.assertContains(respuesta, "Copa de vino: faltan 1 por definir", status_code=400)
        self.assertFalse(Devolucion.objects.exists())

    def test_validaciones_de_cantidades(self):
        self.despachar_todo()
        casos = [
            {self.plato: (41, 0, 0)},           # supera lo despachado
            {self.plato: (30, 8, 3)},           # la suma supera lo pendiente
            {self.plato: (-1, 0, 0)},           # negativo
            {self.plato: ("2.5", 0, 0)},        # decimal
            {self.plato: (0, 0, 0)},            # nada que registrar
        ]
        for filas in casos:
            with self.subTest(filas=filas):
                respuesta = self.devolver(filas)
                self.assertEqual(respuesta.status_code, 400)
        self.assertFalse(Devolucion.objects.exists())
        self.assertFalse(Merma.objects.exists())

    def test_error_se_muestra_en_la_fila_y_conserva_los_datos(self):
        self.despachar_todo()
        respuesta = self.devolver({self.plato: (35, 4, 3), self.copa: (7, 0, 0)})
        self.assertContains(respuesta, "solo quedan 40 pendientes", status_code=400)
        self.assertContains(respuesta, 'value="35"', status_code=400)
        self.assertContains(respuesta, 'value="7"', status_code=400)

    def test_no_se_devuelve_dos_veces_la_misma_unidad_ni_articulos_ajenos(self):
        self.despachar_todo()
        self.devolver({self.plato: (40, 0, 0)})
        self.assertEqual(self.devolver({self.plato: (1, 0, 0)}).status_code, 400)
        otro = Articulo.objects.create(negocio=self.negocio, categoria=self.vajilla, codigo="x-1", nombre="Ajeno",
                                       precio_arriendo=1, stock_total=5, stock_trabajable=5)
        self.assertEqual(self.devolver({otro: (1, 0, 0)}).status_code, 400)
        self.assertEqual(Devolucion.objects.count(), 1)

    def test_no_se_devuelve_sin_despacho(self):
        with self.assertRaises(OperacionInvalida):
            registrar_devolucion(self.servicio.id, self.admin, timezone.now(), "", [(self.plato.id, "1", "0", "0", "")])

    def test_no_se_cierra_con_pendientes(self):
        self.despachar_todo()
        self.devolver({self.plato: (40, 0, 0)})
        respuesta = self.client.post(reverse("gestion_reserva", args=[self.servicio.id]), {"accion": "cerrar"}, follow=True)
        self.assertContains(respuesta, "Solo se cierra una reserva devuelta")
        self.servicio.refresh_from_db()
        self.assertEqual(self.servicio.estado, Servicio.Estado.DEVOLUCION_PARCIAL)

    def test_movimientos_explican_el_ciclo(self):
        self.client.post(reverse("gestion_cotizacion", args=[self.servicio.id]), {"accion": "cambiar_estado", "estado": "Confirmado"})
        self.despachar_todo()
        self.devolver({self.plato: (38, 0, 2), self.copa: (20, 0, 0)})
        tipos = list(
            MovimientoInventario.objects.filter(articulo=self.plato).order_by("fecha", "id").values_list("tipo", flat=True)
        )
        self.assertEqual(tipos[-3:], ["Salida a cliente", "Devolución", "Merma"])
        ficha = self.client.get(reverse("gestion_producto", args=[self.plato.id]))
        self.assertContains(ficha, "40 en cliente")
        self.assertContains(ficha, "38 liberadas")
        self.assertContains(ficha, self.servicio.codigo)

    def test_usuario_sin_permisos_no_registra_devoluciones_ni_mermas(self):
        self.despachar_todo()
        bodega = Usuario.objects.create(negocio=self.negocio, rol=Rol.objects.create(nombre="Bodega"),
                                        nombre="B", apellido="B", email="b@ejemplo.cl", password="x")
        self.iniciar_sesion(bodega)
        self.assertEqual(self.devolver({self.plato: (40, 0, 0)}).status_code, 403)
        respuesta = self.client.post(reverse("gestion_mermas"), {"accion": "crear", "articulo_id": self.plato.id,
                                                                  "tipo": "Roto", "cantidad": "1", "motivo": "x"})
        self.assertEqual(respuesta.status_code, 403)
        self.assertFalse(Devolucion.objects.exists())
        self.assertFalse(Merma.objects.exists())


class MermaTests(EscenarioReserva):
    def crear(self, **cambios):
        datos = {"accion": "crear", "articulo_id": self.plato.id, "tipo": "Roto", "cantidad": "3",
                 "motivo": "Caída en bodega", "observaciones": "", "valor_reposicion": "1500"}
        datos.update(cambios)
        return self.client.post(reverse("gestion_mermas"), datos, follow=True)

    def stock(self):
        self.plato.refresh_from_db()
        return self.plato.stock_total, self.plato.stock_trabajable

    def test_merma_definitiva_baja_total_y_trabajable_una_sola_vez(self):
        self.crear()
        self.assertEqual(self.stock(), (97, 97))
        merma = Merma.objects.get()
        self.assertEqual((merma.usuario, merma.valor_reposicion), (self.admin, 1500))
        movimiento = MovimientoInventario.objects.get(tipo="Merma")
        self.assertEqual((movimiento.stock_anterior, movimiento.stock_nuevo), (100, 97))

    def test_dano_recuperable_baja_solo_trabajable_y_se_puede_reparar(self):
        self.crear(tipo="Dañado", cantidad="4")
        self.assertEqual(self.stock(), (100, 96))
        merma = Merma.objects.get()
        self.client.post(reverse("gestion_mermas"), {"accion": "reparar", "merma_id": merma.id, "cantidad": "3"})
        self.assertEqual(self.stock(), (100, 99))
        respuesta = self.client.post(reverse("gestion_mermas"), {"accion": "reparar", "merma_id": merma.id, "cantidad": "2"})
        self.assertContains(respuesta, "solo quedan 1 unidades", status_code=400)

    def test_merma_no_se_borra_se_anula_y_restituye(self):
        self.crear()
        merma = Merma.objects.get()
        respuesta = self.client.post(reverse("gestion_mermas"), {"accion": "anular", "merma_id": merma.id, "motivo": ""})
        self.assertContains(respuesta, "Indica por qué se anula", status_code=400)
        self.client.post(reverse("gestion_mermas"), {"accion": "anular", "merma_id": merma.id, "motivo": "Duplicada"})
        merma.refresh_from_db()
        self.assertTrue(merma.anulada)
        self.assertEqual(merma.anulada_por, self.admin)
        self.assertEqual(self.stock(), (100, 100))
        self.assertEqual(Merma.objects.count(), 1)
        listado = self.client.get(reverse("gestion_mermas"))
        self.assertEqual(listado.context["kpis"]["unidades"], 0)

    def test_validaciones(self):
        for cambios in ({"cantidad": "0"}, {"cantidad": "-2"}, {"cantidad": "101"}, {"tipo": "Robado"}, {"motivo": ""},
                        {"tipo": "Dañado", "cantidad": "101"}):
            with self.subTest(cambios=cambios):
                self.assertEqual(self.crear(**cambios).status_code, 400)
        self.assertFalse(Merma.objects.exists())
        self.assertEqual(self.stock(), (100, 100))

    def test_filtros(self):
        self.crear()
        self.crear(tipo="Perdido", cantidad="1")
        url = reverse("gestion_mermas")
        self.assertEqual(len(self.client.get(url, {"tipo": "Roto"}).context["mermas"]), 1)
        self.assertEqual(len(self.client.get(url, {"categoria": self.cristaleria.id}).context["mermas"]), 0)
        self.assertEqual(len(self.client.get(url, {"articulo": self.plato.id}).context["mermas"]), 2)


class CancelacionTests(EscenarioReserva):
    def cancelar(self, motivo="El cliente suspendió el evento"):
        return self.client.post(reverse("gestion_reserva", args=[self.servicio.id]), {"accion": "cancelar", "motivo": motivo}, follow=True)

    def test_cancelar_antes_del_despacho_libera_stock_y_cancela_preparacion(self):
        self.generar()
        self.assertEqual(calcular_disponibilidad(self.plato, EN_10_DIAS, EN_10_DIAS)["disponible"], 60)
        self.cancelar()
        self.servicio.refresh_from_db()
        self.assertEqual(self.servicio.estado, Servicio.Estado.CANCELADO)
        self.assertEqual(Preparacion.objects.get().estado, Preparacion.Estado.CANCELADA)
        self.assertEqual(calcular_disponibilidad(self.plato, EN_10_DIAS, EN_10_DIAS)["disponible"], 100)
        self.assertTrue(MovimientoInventario.objects.filter(tipo="Cancelación", servicio=self.servicio).exists())
        self.assertEqual(self.servicio.historial.first().accion, "Cancelar reserva")
        # Ya no se puede preparar ni despachar.
        self.assertEqual(
            self.client.post(reverse("gestion_registrar_despacho", args=[self.servicio.id]), {}).status_code, 400,
        )
        self.assertFalse(Despacho.objects.exists())

    def test_cancelar_reserva_exige_motivo(self):
        respuesta = self.cancelar(motivo="")
        self.assertContains(respuesta, "Indica el motivo")
        self.servicio.refresh_from_db()
        self.assertEqual(self.servicio.estado, Servicio.Estado.CONFIRMADO)

    def test_no_se_cancela_despues_del_despacho(self):
        DevolucionTests.despachar_todo(self)
        respuesta = self.cancelar()
        self.assertContains(respuesta, "primero registra la devolución")
        self.servicio.refresh_from_db()
        self.assertEqual(self.servicio.estado, Servicio.Estado.DESPACHADO)


class CicloCompletoTests(EscenarioReserva):
    """Casos integrales: éxito, devolución parcial y merma, de principio a fin."""

    def ciclo_hasta_despacho(self):
        DevolucionTests.despachar_todo(self)

    devolver = DevolucionTests.devolver

    def cerrar(self):
        self.client.post(reverse("gestion_reserva", args=[self.servicio.id]), {"accion": "cerrar"})
        self.servicio.refresh_from_db()
        return self.servicio.estado

    def test_exito_devolver_todo_y_cerrar(self):
        self.ciclo_hasta_despacho()
        self.devolver({self.plato: (40, 0, 0), self.copa: (20, 0, 0)})
        self.assertEqual(self.cerrar(), Servicio.Estado.CERRADO)
        self.assertEqual(
            list(self.servicio.historial.order_by("fecha", "id").values_list("accion", flat=True))[-3:],
            ["Registrar despacho", "Registrar devolución", "Cerrar reserva"],
        )

    def test_parcial_luego_resto_y_cerrar(self):
        self.ciclo_hasta_despacho()
        self.devolver({self.plato: (32, 0, 0), self.copa: (20, 0, 0)})
        self.assertEqual(self.cerrar(), Servicio.Estado.DEVOLUCION_PARCIAL)
        self.devolver({self.plato: (8, 0, 0)})
        self.assertEqual(self.cerrar(), Servicio.Estado.CERRADO)

    def test_merma_descuenta_y_libera_lo_bueno(self):
        self.ciclo_hasta_despacho()
        self.devolver({self.plato: (35, 3, 2), self.copa: (20, 0, 0)})
        self.plato.refresh_from_db()
        self.assertEqual((self.plato.stock_total, self.plato.stock_trabajable), (98, 95))
        self.assertEqual(calcular_disponibilidad(self.plato, EN_10_DIAS, EN_10_DIAS)["disponible"], 95)
        self.assertEqual(self.cerrar(), Servicio.Estado.CERRADO)


class ReportesTests(EscenarioReserva):
    def test_metricas_comerciales_con_estados_definidos(self):
        # Escenario: reserva confirmada de $26.000 (40 platos a $500 + 20 copas a $300).
        Servicio.objects.filter(id=self.servicio.id).update(total=26000)
        cotizacion = crear_servicio(self.negocio, self.plato, 10, EN_10_DIAS, estado=Servicio.Estado.COTIZACION, rut="2")
        Servicio.objects.filter(id=cotizacion.id).update(total=4000)
        cancelada = crear_servicio(self.negocio, self.plato, 10, EN_10_DIAS, estado=Servicio.Estado.CANCELADO, rut="3")
        Servicio.objects.filter(id=cancelada.id).update(total=99999)
        cerrada = crear_servicio(self.negocio, self.plato, 1, EN_10_DIAS, estado=Servicio.Estado.CERRADO, rut="4")
        Servicio.objects.filter(id=cerrada.id).update(total=10000)

        m = self.client.get(reverse("gestion_reportes")).context["metricas"]
        self.assertEqual(m["cotizaciones_total"], 3)
        self.assertEqual(m["reservas_total"], 2)
        self.assertEqual(m["monto_cotizado"], 40000)
        self.assertEqual(m["monto_confirmado"], 36000)
        self.assertEqual(m["ticket_promedio"], 18000)
        self.assertEqual(m["tasa_conversion"], 67)
        self.assertEqual(m["cotizaciones_rechazadas"], 1)

    def test_periodo_filtra_por_fecha_del_evento(self):
        manana = (EN_10_DIAS + timedelta(days=1)).isoformat()
        m = self.client.get(reverse("gestion_reportes"), {"desde": manana}).context["metricas"]
        self.assertEqual(m["reservas_total"], 0)

    def test_resumen_tiene_indicadores_del_ciclo_con_enlaces(self):
        ciclo = {i["etiqueta"]: i for i in self.client.get(reverse("inicio")).context["ciclo"]}
        self.assertEqual(ciclo["Reservas confirmadas"]["valor"], 1)
        for quitado in ("Clientes contactados", "Unidades en cliente", "Devoluciones atrasadas"):
            self.assertNotIn(quitado, ciclo)
        for item in ciclo.values():
            self.assertEqual(self.client.get(item["url"]).status_code, 200, item["url"])


class CifrasUnificadasTests(EscenarioReserva):
    """Resumen, Inventario y Reportes muestran el mismo stock y las mismas alertas."""

    def setUp(self):
        super().setUp()
        # Trabajable menor que el total y un producto sin stock cargado.
        Articulo.objects.filter(id=self.copa.id).update(stock_trabajable=30)
        Articulo.objects.create(negocio=self.negocio, categoria=self.vajilla, codigo="vaj-002",
                                nombre="Plato sin stock", precio_arriendo=100)

    def test_resumen_inventario_y_reportes_coinciden(self):
        inicio = self.client.get(reverse("inicio")).context
        inventario = self.client.get(reverse("gestion_inventario")).context["totales_inventario"]
        reportes = self.client.get(reverse("gestion_reportes")).context["metricas"]
        # Trabajable 100 + 30; comprometido 40 platos + 20 copas.
        self.assertEqual((inicio["articulos_disponibles"], inicio["articulos_totales"]), (70, 130))
        self.assertEqual((inventario["disponible"], inventario["trabajable"]), (70, 130))
        self.assertEqual((reportes["stock_disponible"], reportes["stock_trabajable"]), (70, 130))
        self.assertEqual(inicio["alertas_inventario_count"], inventario["bajos"])
        self.assertEqual(inventario["bajos"], reportes["stock_bajo"])
        # Copa: 10 libres (bajo) y el plato sin stock cargado.
        self.assertEqual({a.nombre for a in inicio["alertas_inventario"]}, {"Copa de vino", "Plato sin stock"})


class ValorMermaTests(EscenarioReserva):
    def test_merma_sin_valor_se_valoriza_con_el_costo_de_reposicion(self):
        Articulo.objects.filter(id=self.plato.id).update(costo_reposicion=2500)
        self.client.post(reverse("gestion_mermas"), {"accion": "crear", "articulo_id": self.plato.id, "tipo": "Roto",
                                                     "cantidad": "2", "motivo": "Caída", "valor_reposicion": ""})
        self.assertEqual(Merma.objects.get().valor_reposicion, 5000)
        self.assertEqual(self.client.get(reverse("gestion_mermas")).context["kpis"]["valor"], 5000)

    def test_sin_costo_usa_el_precio_del_producto(self):
        self.client.post(reverse("gestion_mermas"), {"accion": "crear", "articulo_id": self.plato.id, "tipo": "Roto",
                                                     "cantidad": "3", "motivo": "Caída", "valor_reposicion": ""})
        self.assertEqual(Merma.objects.get().valor_reposicion, 1500)  # 3 × precio $500
        self.assertEqual(self.client.get(reverse("gestion_mermas")).context["kpis"]["sin_costo"], 0)

    def test_costo_cargado_despues_valoriza_mermas_antiguas(self):
        Articulo.objects.filter(id=self.plato.id).update(precio_arriendo=0)
        self.client.post(reverse("gestion_mermas"), {"accion": "crear", "articulo_id": self.plato.id, "tipo": "Roto",
                                                     "cantidad": "3", "motivo": "Caída", "valor_reposicion": ""})
        kpis = self.client.get(reverse("gestion_mermas")).context["kpis"]
        self.assertEqual((kpis["valor"], kpis["sin_costo"]), (0, 1))
        Articulo.objects.filter(id=self.plato.id).update(costo_reposicion=1000)
        self.assertEqual(self.client.get(reverse("gestion_mermas")).context["kpis"]["valor"], 3000)
        self.assertEqual(self.client.get(reverse("gestion_reportes")).context["metricas"]["valor_merma"], 3000)


class BuscadorPanelTests(EscenarioReserva):
    def test_busca_productos_y_reservas_con_enlaces_del_panel(self):
        datos = self.client.get(reverse("gestion_buscar"), {"q": "plato"}).json()
        productos = next(g for g in datos["grupos"] if g["titulo"] == "Productos")
        self.assertEqual(productos["items"][0]["href"], reverse("gestion_producto", args=[self.plato.id]))
        datos = self.client.get(reverse("gestion_buscar"), {"q": self.servicio.codigo}).json()
        self.assertEqual(datos["grupos"][0]["titulo"], "Reservas")

    def test_solo_administradores(self):
        self.client.session.flush()
        self.client.logout()
        self.assertNotEqual(self.client.get(reverse("gestion_buscar"), {"q": "plato"}).status_code, 200)


class SeguridadTests(EscenarioReserva):
    def test_403_controlado_y_404_para_ids_inexistentes(self):
        bodega = Usuario.objects.create(negocio=self.negocio, rol=Rol.objects.create(nombre="Bodega"),
                                        nombre="B", apellido="B", email="b@ejemplo.cl", password="x")
        self.iniciar_sesion(bodega)
        respuesta = self.client.get(reverse("gestion_reportes"))
        self.assertEqual(respuesta.status_code, 403)
        self.assertContains(respuesta, "No tienes acceso a esta sección", status_code=403)
        self.iniciar_sesion()
        for nombre in ("gestion_reserva", "gestion_preparacion_documento", "gestion_despacho_documento",
                       "gestion_devolucion_servicio", "gestion_registrar_devolucion", "gestion_registrar_despacho"):
            with self.subTest(vista=nombre):
                self.assertEqual(self.client.get(reverse(nombre, args=[999999])).status_code, 404)

    def test_todas_las_secciones_del_panel_exigen_sesion_y_rol(self):
        nombres = ["inicio", "gestion_clientes", "gestion_cotizaciones", "gestion_reservas", "gestion_preparacion",
                   "gestion_despachos", "gestion_devoluciones", "gestion_mermas", "gestion_inventario",
                   "gestion_calendario", "gestion_reportes", "gestion_usuarios", "gestion_configuracion"]
        # El modelo exige rol: "sin permisos" se prueba con un rol distinto de Administrador.
        bodega = Usuario.objects.create(negocio=self.negocio, rol=Rol.objects.create(nombre="Invitado"), nombre="S", apellido="R",
                                        email="s@ejemplo.cl", password="x")
        self.client.logout()
        for nombre in nombres:
            with self.subTest(vista=nombre, caso="sin sesión"):
                self.assertEqual(self.client.get(reverse(nombre)).status_code, 302)
                self.assertEqual(self.client.post(reverse(nombre), {"accion": "crear"}).status_code, 302)
        self.iniciar_sesion(bodega)
        for nombre in nombres:
            with self.subTest(vista=nombre, caso="sin permisos"):
                self.assertEqual(self.client.get(reverse(nombre)).status_code, 403)
                self.assertEqual(self.client.post(reverse(nombre), {"accion": "crear"}).status_code, 403)

    def test_contrasena_antigua_en_texto_plano_se_cifra_al_entrar(self):
        self.client.logout()
        self.admin.password = "secreta123"
        self.admin.save()
        self.client.post(reverse("gestion_login"), {"email": self.admin.email, "password": "secreta123"})
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.password.startswith("pbkdf2_"))
        self.assertEqual(self.client.session.get("usuario_id"), self.admin.id)


class CuentaClienteTests(TestCase):
    def setUp(self):
        self.negocio, self.vajilla, _, self.plato = crear_base()

    def registrar(self, **cambios):
        datos = {"nombre": "Ana María Pérez", "rut": RUT_VALIDO, "email": "ana@ejemplo.cl",
                 "telefono": "+56 9 1234 5678", "password": "Copas2026!", "password2": "Copas2026!"}
        datos.update(cambios)
        return self.client.post(reverse("cliente_registro"), datos, follow=True)

    def test_registro_crea_cuenta_cifrada_e_inicia_sesion(self):
        respuesta = self.registrar()
        self.assertRedirects(respuesta, reverse("cliente_cuenta"))
        cliente = Cliente.objects.get()
        self.assertEqual((cliente.rut, cliente.nombre, cliente.email), ("123456785", "Ana", "ana@ejemplo.cl"))
        self.assertTrue(cliente.password.startswith("pbkdf2_"))
        self.assertEqual(self.client.session["cliente_id"], cliente.id)
        self.assertContains(respuesta, "Hola, Ana")

    def test_validaciones_del_registro(self):
        casos = [
            {"rut": "12.345.678-0"},                       # dígito verificador inválido
            {"email": "no-es-correo"},
            {"password": "123", "password2": "123"},       # contraseña débil
            {"password2": "OtraClave2026!"},              # no coinciden
            {"nombre": ""},
        ]
        for cambios in casos:
            with self.subTest(cambios=cambios):
                self.assertEqual(self.registrar(**cambios).status_code, 400)
        self.assertFalse(Cliente.objects.exists())

    def test_quien_ya_cotizo_activa_su_cuenta_solo_con_los_mismos_datos(self):
        Cliente.objects.create(negocio=self.negocio, rut="123456785", nombre="Ana", apellido="María Pérez",
                               email="ana@ejemplo.cl")
        # Otro nombre con el mismo RUT: no se vincula ni revela los datos registrados.
        respuesta = self.registrar(nombre="Juan Soto", email="juan@ejemplo.cl")
        self.assertContains(respuesta, "registrado con otros datos", status_code=400)
        self.assertNotContains(respuesta, "ana@ejemplo.cl", status_code=400)
        self.registrar()
        self.assertEqual(Cliente.objects.count(), 1)
        self.assertTrue(Cliente.objects.get().tiene_cuenta)

    def test_no_se_duplican_cuentas(self):
        self.registrar()
        self.client.post(reverse("cliente_logout"))
        self.assertContains(self.registrar(), "Ya existe una cuenta con este RUT", status_code=400)
        self.assertContains(self.registrar(rut="11.111.111-1"), "Este correo ya tiene una cuenta", status_code=400)

    def test_login_de_cliente_y_sin_acceso_al_panel(self):
        self.registrar()
        self.client.post(reverse("cliente_logout"))
        respuesta = self.client.post(reverse("gestion_login"), {"email": "ANA@ejemplo.cl", "password": "Copas2026!"})
        self.assertRedirects(respuesta, reverse("cliente_cuenta"))
        # La sesión de cliente no abre el panel.
        self.assertEqual(self.client.get(reverse("inicio")).status_code, 302)
        self.assertEqual(self.client.get(reverse("gestion_cotizaciones")).status_code, 302)
        malo = self.client.post(reverse("gestion_login"), {"email": "ana@ejemplo.cl", "password": "mala"})
        self.assertContains(malo, "Correo o contraseña incorrectos", status_code=400)

    def test_login_no_redirige_a_sitios_externos(self):
        self.registrar()
        self.client.post(reverse("cliente_logout"))
        respuesta = self.client.post(reverse("gestion_login") + "?next=https://malicioso.com/",
                                     {"email": "ana@ejemplo.cl", "password": "Copas2026!"})
        self.assertRedirects(respuesta, reverse("cliente_cuenta"))

    def test_cotizar_con_cuenta_usa_sus_datos_y_ve_solo_lo_suyo(self):
        self.registrar()
        otro = crear_servicio(self.negocio, self.plato, 5, EN_10_DIAS, rut="111111111")
        self.assertContains(self.client.get(reverse("cotizador")), 'value="123456785" readonly')
        # Aunque se manipule el RUT del formulario, la solicitud queda a nombre de la cuenta.
        self.client.post(reverse("cotizador"), {
            "tipoEvento": "Cumpleaños", "fecha": EN_10_DIAS.isoformat(), "invitados": "30", "comuna": "Maipú",
            "despacho": "Sí", "categorias": [str(self.vajilla.id)], "nombre": "Otro", "rut": "11.111.111-1",
        }, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        propio = Servicio.objects.get(cliente__rut="123456785")
        cuenta = self.client.get(reverse("cliente_cuenta"))
        self.assertContains(cuenta, propio.codigo)
        self.assertNotContains(cuenta, otro.codigo)
        self.assertContains(cuenta, "Solicitud recibida")
        self.assertEqual(self.client.get(reverse("cliente_reserva", args=[otro.id])).status_code, 404)

        detalle = self.client.get(reverse("cliente_reserva", args=[propio.id]))
        self.assertContains(detalle, "Cancelar esta solicitud")
        self.client.post(reverse("cliente_reserva", args=[propio.id]), {"accion": "cancelar", "motivo": "Cambio de planes"})
        propio.refresh_from_db()
        self.assertEqual(propio.estado, Servicio.Estado.CANCELADO)
        self.assertIn("Cancelada por el cliente", propio.historial.first().observacion)

    def test_reserva_confirmada_no_se_cancela_desde_la_cuenta(self):
        self.registrar()
        cliente = Cliente.objects.get()
        reserva = crear_servicio(self.negocio, self.plato, 5, EN_10_DIAS, rut=cliente.rut)
        self.client.post(reverse("cliente_reserva", args=[reserva.id]), {"accion": "cancelar"})
        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, Servicio.Estado.CONFIRMADO)
        self.assertContains(self.client.get(reverse("cliente_reserva", args=[reserva.id])), "Reserva confirmada")

    def test_cambiar_contrasena(self):
        self.registrar()
        url = reverse("cliente_cuenta")
        malo = self.client.post(url, {"accion": "clave", "actual": "equivocada", "nueva": "Nueva2026!", "nueva2": "Nueva2026!"})
        self.assertContains(malo, "La contraseña actual no es correcta", status_code=400)
        self.client.post(url, {"accion": "clave", "actual": "Copas2026!", "nueva": "Nueva2026!", "nueva2": "Nueva2026!"})
        self.client.post(reverse("cliente_logout"))
        respuesta = self.client.post(reverse("gestion_login"), {"email": "ana@ejemplo.cl", "password": "Nueva2026!"})
        self.assertRedirects(respuesta, reverse("cliente_cuenta"))

    def test_resumen_separa_en_curso_e_historial(self):
        self.registrar()
        cliente = Cliente.objects.get()
        proxima = crear_servicio(self.negocio, self.plato, 5, EN_10_DIAS, rut=cliente.rut)
        crear_servicio(self.negocio, self.plato, 5, date.today() - timedelta(days=20), estado=Servicio.Estado.CERRADO, rut=cliente.rut)
        contexto = self.client.get(reverse("cliente_cuenta")).context
        self.assertEqual(contexto["proximo"], proxima)
        self.assertEqual(contexto["proximo"].dias_restantes, 10)
        self.assertEqual(contexto["resumen"], {"en_curso": 1, "confirmadas": 1, "realizados": 1})

    def test_cuenta_exige_sesion(self):
        respuesta = self.client.get(reverse("cliente_cuenta"))
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn(reverse("gestion_login"), respuesta["Location"])


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class AceptarCotizacionTests(TestCase):
    """El cliente acepta la cotización enviada; la reserva la confirma el administrador."""

    def setUp(self):
        self.negocio, self.vajilla, _, self.plato = crear_base()
        self.negocio.email = "empresa@ejemplo.cl"
        self.negocio.save()
        CuentaClienteTests.registrar(self)
        self.cliente = Cliente.objects.get()
        self.servicio = crear_servicio(self.negocio, self.plato, 10, EN_10_DIAS,
                                       estado=Servicio.Estado.CONTACTADO, rut=self.cliente.rut)
        self.url = reverse("cliente_reserva", args=[self.servicio.id])

    def aceptar(self):
        return self.client.post(self.url, {"accion": "aceptar"}, follow=True)

    def test_aceptar_avisa_a_la_empresa_sin_confirmar_la_reserva(self):
        self.assertContains(self.client.get(self.url), "Aceptar cotización")
        respuesta = self.aceptar()
        self.servicio.refresh_from_db()
        self.assertIsNotNone(self.servicio.aceptada_cliente)
        self.assertEqual(self.servicio.estado, Servicio.Estado.CONTACTADO)
        self.assertEqual(self.servicio.historial.first().accion, "Cotización aceptada por el cliente")
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["empresa@ejemplo.cl"])
        self.assertIn(self.servicio.codigo, mail.outbox[0].subject)
        self.assertContains(respuesta, "Aceptaste esta cotización")
        self.assertNotContains(respuesta, 'value="aceptar"')
        self.assertContains(self.client.get(reverse("cliente_cuenta")), "Aceptada · por confirmar")

        # Aceptar dos veces no repite el aviso ni cambia la fecha.
        fecha = self.servicio.aceptada_cliente
        self.aceptar()
        self.servicio.refresh_from_db()
        self.assertEqual(self.servicio.aceptada_cliente, fecha)
        self.assertEqual(len(mail.outbox), 1)

    def test_solo_se_acepta_una_cotizacion_ya_enviada(self):
        self.servicio.estado = Servicio.Estado.COTIZACION
        self.servicio.save()
        self.assertNotContains(self.client.get(self.url), "Aceptar cotización")
        self.aceptar()
        self.servicio.refresh_from_db()
        self.assertIsNone(self.servicio.aceptada_cliente)
        self.assertEqual(len(mail.outbox), 0)

    def test_panel_destaca_la_aceptada_y_cambiar_productos_la_anula(self):
        self.aceptar()
        rol = Rol.objects.create(nombre="Administrador")
        admin = Usuario.objects.create(negocio=self.negocio, rol=rol, nombre="Helen", apellido="Cortés",
                                       email="a@ejemplo.cl", password="x")
        sesion = self.client.session
        sesion["usuario_id"] = admin.id
        sesion.save()

        lista = self.client.get(reverse("gestion_cotizaciones"))
        self.assertEqual(lista.context["por_confirmar"], 1)
        self.assertContains(lista, "Aceptada por cliente")
        self.assertContains(self.client.get(reverse("gestion_cotizacion", args=[self.servicio.id])),
                            "El cliente aceptó esta cotización")

        detalle = self.servicio.detalles.get()
        self.client.post(reverse("gestion_cotizacion", args=[self.servicio.id]),
                         {"accion": "quitar_articulo", "detalle_id": detalle.id})
        self.servicio.refresh_from_db()
        self.assertIsNone(self.servicio.aceptada_cliente)


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class FlujoCotizacionTests(TestCase):
    """Cotización → productos → enviar (correo u otro medio) → Contactado → confirmar."""

    # Mismo escenario que AdministracionTests (solicitud real desde el cotizador), sin repetir sus pruebas.
    setUp = AdministracionTests.setUp
    iniciar_sesion = AdministracionTests.iniciar_sesion

    def url(self):
        return reverse("gestion_cotizacion", args=[self.servicio.id])

    def agregar_productos(self):
        self.client.post(self.url(), {"accion": "agregar_articulos", "articulo_id": [self.plato.id], "cantidad": ["40"]})

    def test_enviar_por_correo_avisa_y_pasa_a_contactado(self):
        self.iniciar_sesion()
        self.agregar_productos()
        respuesta = self.client.post(reverse("enviar_cotizacion_email", args=[self.servicio.id]), follow=True)
        self.assertContains(respuesta, "Cotización enviada a pedro@ejemplo.cl")
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["pedro@ejemplo.cl"])
        self.servicio.refresh_from_db()
        self.assertEqual(self.servicio.estado, Servicio.Estado.CONTACTADO)
        self.assertTrue(self.servicio.historial.filter(accion="Cotización enviada por correo").exists())
        self.assertContains(respuesta, "Confirmar reserva</button>")
        self.assertNotContains(respuesta, "Enviar cotización por")

    def test_no_se_envia_sin_productos_ni_por_get(self):
        self.iniciar_sesion()
        self.assertEqual(self.client.get(reverse("enviar_cotizacion_email", args=[self.servicio.id])).status_code, 405)
        respuesta = self.client.post(reverse("enviar_cotizacion_email", args=[self.servicio.id]), follow=True)
        self.assertContains(respuesta, "Agrega al menos un producto")
        self.assertEqual(len(mail.outbox), 0)

    def test_si_falla_el_correo_avisa_y_no_cambia_el_estado(self):
        self.iniciar_sesion()
        self.agregar_productos()
        with mock.patch("Inventario.views._enviar_correo_cotizacion", side_effect=OSError("smtp caído")):
            respuesta = self.client.post(reverse("enviar_cotizacion_email", args=[self.servicio.id]), follow=True)
        self.assertContains(respuesta, "No se pudo enviar el correo")
        self.servicio.refresh_from_db()
        self.assertEqual(self.servicio.estado, Servicio.Estado.COTIZACION)

    def test_marcar_enviada_por_whatsapp_y_luego_confirmar(self):
        self.iniciar_sesion()
        self.agregar_productos()
        self.client.post(self.url(), {"accion": "marcar_enviada", "medio": "WhatsApp"})
        self.servicio.refresh_from_db()
        self.assertEqual(self.servicio.estado, Servicio.Estado.CONTACTADO)
        self.assertContains(self.client.get(self.url()), "Confirmar reserva")
        self.client.post(self.url(), {"accion": "confirmar"})
        self.servicio.refresh_from_db()
        self.assertEqual(self.servicio.estado, Servicio.Estado.CONFIRMADO)
        self.assertEqual(calcular_disponibilidad(self.plato, EN_10_DIAS, EN_10_DIAS)["comprometido"], 40)

    def test_pantalla_muestra_solo_el_siguiente_paso(self):
        self.iniciar_sesion()
        pagina = self.client.get(self.url())
        self.assertContains(pagina, '<li class="is-actual">Productos</li>')
        self.assertNotContains(pagina, "Enviar cotización por")
        self.assertNotContains(pagina, "Cargar sugeridos")
        self.assertNotContains(pagina, "Actualizar estado")
        self.agregar_productos()
        pagina = self.client.get(self.url())
        self.assertContains(pagina, "Enviar cotización por correo</button>")
        self.assertNotContains(pagina, "Confirmar reserva</button>")


class EnvioSegunPreferenciaTests(TestCase):
    setUp = AdministracionTests.setUp
    iniciar_sesion = AdministracionTests.iniciar_sesion

    def pagina(self, medio, telefono="+56 9 1234 5678", email="pedro@ejemplo.cl"):
        Servicio.objects.filter(id=self.servicio.id).update(medio_contacto=medio)
        Cliente.objects.filter(id=self.servicio.cliente_id).update(telefono=telefono, email=email)
        url = reverse("gestion_cotizacion", args=[self.servicio.id])
        if not self.servicio.detalles.exists():
            self.client.post(url, {"accion": "agregar_articulos", "articulo_id": [self.plato.id], "cantidad": ["10"]})
        return self.client.get(url)

    def test_boton_principal_segun_preferencia(self):
        self.iniciar_sesion()
        self.assertContains(self.pagina("Correo"), "Enviar cotización por correo</button>")
        whatsapp = self.pagina("WhatsApp")
        self.assertContains(whatsapp, "Enviar cotización por WhatsApp</button>")
        self.assertContains(whatsapp, "https://wa.me/56912345678?text=")
        self.assertContains(whatsapp, "10%20%C3%97%20Plato%20principal")
        llamada = self.pagina("Llamada")
        self.assertContains(llamada, "Registrar llamada</button>")
        self.assertContains(llamada, 'href="tel:+56 9 1234 5678"')

    def test_si_falta_el_dato_usa_el_medio_disponible(self):
        self.iniciar_sesion()
        sin_telefono = self.pagina("WhatsApp", telefono="")
        self.assertContains(sin_telefono, "Enviar cotización por correo</button>")
        self.assertContains(sin_telefono, "no dejó los datos para ese medio")
        self.assertContains(self.pagina("", email=""), "Enviar cotización por WhatsApp</button>")


class RechazoCotizacionTests(TestCase):
    setUp = AdministracionTests.setUp
    iniciar_sesion = AdministracionTests.iniciar_sesion

    def test_cliente_rechaza_y_queda_cancelada_con_motivo(self):
        self.iniciar_sesion()
        url = reverse("gestion_cotizacion", args=[self.servicio.id])
        self.client.post(url, {"accion": "agregar_articulos", "articulo_id": [self.plato.id], "cantidad": ["10"]})
        self.client.post(url, {"accion": "marcar_enviada", "medio": "WhatsApp"})
        self.assertContains(self.client.get(url), "No aceptó")
        respuesta = self.client.post(url, {"accion": "rechazar", "motivo_rechazo": "Precio", "detalle_rechazo": "Muy caro"}, follow=True)
        self.servicio.refresh_from_db()
        self.assertEqual(self.servicio.estado, Servicio.Estado.CANCELADO)
        registro = self.servicio.historial.first()
        self.assertEqual((registro.accion, registro.observacion), ("Cotización rechazada por el cliente", "Precio: Muy caro"))
        self.assertContains(respuesta, "Rechazada por el cliente")
        self.assertContains(respuesta, "Precio: Muy caro")

    def test_historial_en_el_detalle_de_la_cotizacion(self):
        self.iniciar_sesion()
        url = reverse("gestion_cotizacion", args=[self.servicio.id])
        self.client.post(url, {"accion": "agregar_articulos", "articulo_id": [self.plato.id], "cantidad": ["10"]})
        self.client.post(url, {"accion": "marcar_enviada", "medio": "WhatsApp"})
        self.client.post(url, {"accion": "rechazar", "motivo_rechazo": "Precio", "detalle_rechazo": ""})
        pagina = self.client.get(url).content.decode()
        # Lo más reciente arriba; la solicitud recibida al final.
        orden = [pagina.index(t) for t in ("Cotización rechazada por el cliente", "Cotización enviada por WhatsApp", "Solicitud recibida")]
        self.assertEqual(orden, sorted(orden))
        self.assertIn("Contactado → Cancelado", pagina)

    def test_rechazo_exige_motivo_valido_y_no_aplica_a_reservas(self):
        self.iniciar_sesion()
        url = reverse("gestion_cotizacion", args=[self.servicio.id])
        self.client.post(url, {"accion": "rechazar", "motivo_rechazo": "inventado"})
        self.servicio.refresh_from_db()
        self.assertEqual(self.servicio.estado, Servicio.Estado.COTIZACION)
        reserva = crear_servicio(self.negocio, self.plato, 5, EN_10_DIAS, rut="2")
        self.client.post(reverse("gestion_cotizacion", args=[reserva.id]), {"accion": "rechazar", "motivo_rechazo": "Precio"})
        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, Servicio.Estado.CONFIRMADO)


class GestionCategoriasTests(TestCase):
    """Alta, edición, desactivación y borrado de categorías desde el panel de inventario."""

    def setUp(self):
        self.negocio, self.vajilla, self.cristaleria, self.plato = crear_base()
        rol = Rol.objects.create(nombre="Administrador")
        self.admin = Usuario.objects.create(
            negocio=self.negocio, rol=rol, nombre="Helen", apellido="Cortés",
            email="admin@ejemplo.cl", password="x",
        )
        self.url = reverse("gestion_categorias")

    def iniciar_sesion(self, usuario=None):
        sesion = self.client.session
        sesion["usuario_id"] = (usuario or self.admin).id
        sesion.save()

    def crear(self, nombre, **extra):
        return self.client.post(self.url, {"accion": "crear", "nombre": nombre, **extra})

    def datos_producto(self, categoria, **extra):
        return {
            "accion": "crear", "categoria_id": categoria.id, "nombre": "Guirnalda LED",
            "precio_arriendo": "3500", "stock_total": "10", "stock_trabajable": "10", "activo": "on",
            **extra,
        }

    # --- permisos
    def test_sin_sesion_no_crea_categorias(self):
        respuesta = self.crear("Iluminación")
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn(reverse("gestion_login"), respuesta["Location"])
        self.assertFalse(Categoria.objects.filter(nombre="Iluminación").exists())

    def test_usuario_que_no_es_administrador_recibe_403(self):
        rol = Rol.objects.create(nombre="Operador")
        operador = Usuario.objects.create(
            negocio=self.negocio, rol=rol, nombre="Ana", apellido="Rojas", email="ana@ejemplo.cl", password="x",
        )
        self.iniciar_sesion(operador)
        self.assertEqual(self.crear("Iluminación").status_code, 403)
        self.assertFalse(Categoria.objects.filter(nombre="Iluminación").exists())

    # --- creación y validaciones
    def test_admin_crea_categoria_y_aparece_en_formulario_de_producto(self):
        self.iniciar_sesion()
        self.crear("  Iluminación  ")
        categoria = Categoria.objects.get(nombre="Iluminación")
        self.assertEqual(categoria.negocio, self.negocio)
        self.assertTrue(categoria.activo)
        pagina = self.client.get(reverse("gestion_inventario"))
        self.assertIn(categoria, pagina.context["categorias"])

    def test_nombre_vacio_se_rechaza(self):
        self.iniciar_sesion()
        total = Categoria.objects.count()
        self.crear("    ")
        self.assertEqual(Categoria.objects.count(), total)

    def test_nombre_duplicado_ignora_mayusculas_y_espacios(self):
        self.iniciar_sesion()
        self.crear("Iluminación")
        for variante in ("iluminación", " ILUMINACIÓN ", "Iluminación"):
            self.crear(variante)
        self.assertEqual(
            [c.nombre for c in Categoria.objects.filter(negocio=self.negocio, nombre__icontains="lumin")],
            ["Iluminación"],
        )

    def test_otro_negocio_puede_repetir_el_nombre(self):
        otro = Negocio.objects.create(nombre="Otro negocio")
        Categoria.objects.create(negocio=otro, nombre="Iluminación")
        self.iniciar_sesion()
        self.crear("Iluminación")
        self.assertEqual(Categoria.objects.filter(nombre="Iluminación").count(), 2)

    def test_restriccion_de_base_impide_duplicado_por_mayusculas(self):
        Categoria.objects.create(negocio=self.negocio, nombre="Iluminacion")
        with self.assertRaises(IntegrityError), transaction.atomic():
            Categoria.objects.create(negocio=self.negocio, nombre="ILUMINACION")

    # --- edición
    def test_editar_nombre_y_rechazar_duplicado(self):
        self.iniciar_sesion()
        self.crear("Iluminación")
        categoria = Categoria.objects.get(nombre="Iluminación")
        self.client.post(self.url, {"accion": "editar", "categoria_id": categoria.id, "nombre": "Luces"})
        categoria.refresh_from_db()
        self.assertEqual(categoria.nombre, "Luces")
        self.client.post(self.url, {"accion": "editar", "categoria_id": categoria.id, "nombre": "VAJILLA"})
        categoria.refresh_from_db()
        self.assertEqual(categoria.nombre, "Luces")

    def test_editar_sin_cambiar_el_nombre_mostrado_conserva_el_codigo_interno(self):
        self.iniciar_sesion()
        mesas = Categoria.objects.create(negocio=self.negocio, nombre="mesas-sillas")
        self.client.post(self.url, {"accion": "editar", "categoria_id": mesas.id, "nombre": "Mesas y sillas"})
        mesas.refresh_from_db()
        self.assertEqual(mesas.nombre, "mesas-sillas")

    def test_no_se_puede_modificar_categoria_de_otro_negocio(self):
        otro = Negocio.objects.create(nombre="Otro negocio")
        ajena = Categoria.objects.create(negocio=otro, nombre="Ajena")
        self.iniciar_sesion()
        for accion in ("editar", "desactivar", "eliminar"):
            respuesta = self.client.post(self.url, {"accion": accion, "categoria_id": ajena.id, "nombre": "Hackeada"})
            self.assertEqual(respuesta.status_code, 404)
        ajena.refresh_from_db()
        self.assertEqual((ajena.nombre, ajena.activo), ("Ajena", True))

    # --- eliminación
    def test_no_se_elimina_categoria_con_productos(self):
        self.iniciar_sesion()
        respuesta = self.client.post(self.url, {"accion": "eliminar", "categoria_id": self.vajilla.id}, follow=True)
        self.assertTrue(Categoria.objects.filter(id=self.vajilla.id).exists())
        self.assertContains(respuesta, "No se puede eliminar la categoría porque contiene productos.")

    def test_se_elimina_categoria_vacia(self):
        self.iniciar_sesion()
        self.client.post(self.url, {"accion": "eliminar", "categoria_id": self.cristaleria.id})
        self.assertFalse(Categoria.objects.filter(id=self.cristaleria.id).exists())

    # --- productos
    def test_producto_nuevo_en_categoria_nueva_conserva_stock_inicial(self):
        self.iniciar_sesion()
        self.crear("Iluminación")
        categoria = Categoria.objects.get(nombre="Iluminación")
        self.client.post(reverse("gestion_inventario"), self.datos_producto(categoria))
        producto = Articulo.objects.get(nombre="Guirnalda LED")
        self.assertEqual((producto.categoria, producto.stock_total, producto.stock_trabajable), (categoria, 10, 10))

    def test_producto_nuevo_no_acepta_categoria_inactiva_ni_ajena(self):
        self.iniciar_sesion()
        self.cristaleria.activo = False
        self.cristaleria.save()
        otro = Negocio.objects.create(nombre="Otro negocio")
        ajena = Categoria.objects.create(negocio=otro, nombre="Ajena")
        for categoria in (self.cristaleria, ajena):
            respuesta = self.client.post(reverse("gestion_inventario"), self.datos_producto(categoria))
            self.assertEqual(respuesta.status_code, 404)
        self.assertFalse(Articulo.objects.filter(nombre="Guirnalda LED").exists())

    def test_selector_de_producto_nuevo_solo_muestra_categorias_activas(self):
        self.iniciar_sesion()
        self.cristaleria.activo = False
        self.cristaleria.save()
        pagina = self.client.get(reverse("gestion_inventario"))
        self.assertIn(self.vajilla, pagina.context["categorias"])
        self.assertNotIn(self.cristaleria, pagina.context["categorias"])

    def test_cambiar_categoria_del_producto_no_altera_stock_ni_precio(self):
        self.iniciar_sesion()
        antes = (self.plato.stock_total, self.plato.stock_trabajable, self.plato.precio_arriendo)
        self.client.post(reverse("gestion_producto", args=[self.plato.id]), {
            "accion": "editar", "nombre": self.plato.nombre, "categoria_id": self.cristaleria.id,
            "precio_arriendo": self.plato.precio_arriendo, "costo_reposicion": self.plato.costo_reposicion,
            "stock_total": self.plato.stock_total, "stock_trabajable": self.plato.stock_trabajable, "activo": "on",
        })
        self.plato.refresh_from_db()
        self.assertEqual(self.plato.categoria, self.cristaleria)
        self.assertEqual((self.plato.stock_total, self.plato.stock_trabajable, self.plato.precio_arriendo), antes)
        self.assertFalse(MovimientoInventario.objects.filter(articulo=self.plato).exists())

    def test_producto_existente_conserva_categoria_desactivada_en_su_formulario(self):
        self.iniciar_sesion()
        self.vajilla.activo = False
        self.vajilla.save()
        pagina = self.client.get(reverse("gestion_producto", args=[self.plato.id]))
        self.assertIn(self.vajilla, pagina.context["categorias"])

    # --- desactivación y catálogo público
    def test_desactivar_oculta_categoria_del_catalogo_y_conserva_productos(self):
        self.iniciar_sesion()
        self.client.post(self.url, {"accion": "desactivar", "categoria_id": self.vajilla.id})
        self.vajilla.refresh_from_db()
        self.assertFalse(self.vajilla.activo)
        self.assertTrue(Articulo.objects.filter(id=self.plato.id).exists())
        catalogo = self.client.get(reverse("catalogo"))
        self.assertNotIn(self.vajilla, catalogo.context["categorias"])
        self.assertNotIn(self.plato, catalogo.context["productos"])
        self.client.post(self.url, {"accion": "activar", "categoria_id": self.vajilla.id})
        catalogo = self.client.get(reverse("catalogo"))
        self.assertIn(self.vajilla, catalogo.context["categorias"])
        self.assertIn(self.plato, catalogo.context["productos"])

    def test_catalogo_oculta_categoria_activa_sin_productos_activos(self):
        catalogo = self.client.get(reverse("catalogo"))
        self.assertIn(self.vajilla, catalogo.context["categorias"])
        self.assertNotIn(self.cristaleria, catalogo.context["categorias"])

    def test_categoria_nueva_con_producto_aparece_en_catalogo(self):
        self.iniciar_sesion()
        self.crear("Iluminación")
        categoria = Categoria.objects.get(nombre="Iluminación")
        self.client.post(reverse("gestion_inventario"), self.datos_producto(categoria))
        catalogo = self.client.get(reverse("catalogo"))
        self.assertIn(categoria, catalogo.context["categorias"])
        self.assertContains(catalogo, "Guirnalda LED")

    def test_desactivar_no_altera_reservas_ni_detalles_historicos(self):
        servicio = crear_servicio(self.negocio, self.plato, 20, EN_10_DIAS)
        self.iniciar_sesion()
        self.client.post(self.url, {"accion": "desactivar", "categoria_id": self.vajilla.id})
        servicio.refresh_from_db()
        self.assertEqual(servicio.estado, Servicio.Estado.CONFIRMADO)
        self.assertEqual(DetalleServicio.objects.get(servicio=servicio).cantidad, 20)

    def test_panel_muestra_cantidad_de_productos_por_categoria(self):
        self.iniciar_sesion()
        pagina = self.client.get(reverse("gestion_inventario"))
        filas = {c.id: c.total_productos for c in pagina.context["categorias_gestion"]}
        self.assertEqual(filas[self.vajilla.id], 1)
        self.assertEqual(filas[self.cristaleria.id], 0)

    def test_cotizador_publico_solo_ofrece_categorias_activas(self):
        self.cristaleria.activo = False
        self.cristaleria.save()
        cotizador = self.client.get(reverse("cotizador"))
        self.assertIn(self.vajilla, cotizador.context["categorias"])
        self.assertNotIn(self.cristaleria, cotizador.context["categorias"])

    def test_botones_de_categorias_estan_conectados_a_sus_modales(self):
        """Cada botón del panel debe existir en la página y estar registrado en el JS que abre los modales."""
        self.iniciar_sesion()
        pagina = self.client.get(reverse("gestion_inventario"))
        script = (Path(__file__).resolve().parent / "static" / "js" / "gestion-django.js").read_text(encoding="utf-8")
        for boton, modal in (
            ("btn-nueva-categoria", "modal-nueva-categoria"),
            ("btn-gestionar-categorias", "modal-gestionar-categorias"),
        ):
            self.assertContains(pagina, f'id="{boton}"')
            self.assertContains(pagina, f'id="{modal}"')
            self.assertIn(f"'{boton}': '{modal}'", script)

    def test_producto_sin_foto_usa_imagen_predeterminada(self):
        """Un producto sin fotografía no debe mostrar una imagen rota en el catálogo ni en su ficha."""
        sin_foto = Articulo.objects.create(
            negocio=self.negocio, categoria=self.vajilla, codigo="vaj-900", nombre="Fuente sin foto",
            precio_arriendo=1000, stock_total=5, stock_trabajable=5,
        )
        self.plato.imagen = "/static/images/loza1.jpg"
        self.plato.save()
        catalogo = self.client.get(reverse("catalogo"))
        self.assertContains(catalogo, "sin-imagen")
        self.assertContains(catalogo, "/static/images/loza1.jpg")
        self.assertNotContains(catalogo, 'src=""')
        ficha = self.client.get(reverse("producto", args=[sin_foto.id]))
        self.assertContains(ficha, "sin-imagen")


class TelefonosGuardadosTests(TestCase):
    """Los teléfonos se guardan siempre como +56 9 1234 5678, sin importar cómo se escriban."""

    def setUp(self):
        self.negocio = Negocio.objects.create(nombre="Entre Platos y Copas")

    def test_migracion_ordena_los_telefonos_ya_guardados(self):
        import importlib
        from django.apps import apps
        migracion = importlib.import_module("Inventario.migrations.0010_normalizar_telefonos")
        datos = {"111111111": "+56936243259", "222222222": "936243259", "333333333": "+56 9 4827 1935",
                 "444444444": "22 345 6789", "555555555": ""}
        for rut, telefono in datos.items():
            Cliente.objects.create(negocio=self.negocio, rut=rut, nombre="Cliente", telefono=telefono)
        migracion.normalizar(apps, None)
        guardados = {c.rut: c.telefono for c in Cliente.objects.all()}
        self.assertEqual(guardados["111111111"], "+56 9 3624 3259")
        self.assertEqual(guardados["222222222"], "+56 9 3624 3259")
        self.assertEqual(guardados["333333333"], "+56 9 4827 1935")
        self.assertEqual(guardados["444444444"], "22 345 6789")
        self.assertEqual(guardados["555555555"], "")
