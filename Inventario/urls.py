from django.urls import path
from Inventario import views


urlpatterns = [

    # =========================
    # SITIO PÚBLICO
    # =========================

    path('', views.index, name='index'),

    path(
        'catalogo/',
        views.catalogo,
        name='catalogo'
    ),

    path(
        'cotizador/',
        views.cotizador,
        name='cotizador'
    ),

    path(
        'nosotros/',
        views.nosotros,
        name='nosotros'
    ),

    path(
        'contacto/',
        views.contacto,
        name='contacto'
    ),

    path(
        'producto/<int:id>/',
        views.producto,
        name='producto'
    ),


    # =========================
    # GESTIÓN - INICIO
    # =========================

    path(
        'gestion/',
        views.gestionIndex,
        name='inicio'
    ),


    # =========================
    # INVENTARIO
    # =========================

    path(
        'gestion/inventario/',
        views.inventario,
        name='gestion_inventario'
    ),

    path(
        'gestion/inventario/<int:id>/',
        views.gestion_producto,
        name='gestion_producto'
    ),

    path(
        'gestion/inventario/guardar/',
        views.guardar_producto,
        name='gestion_guardar_producto'
    ),


    # =========================
    # CLIENTES
    # =========================

    path(
        'gestion/clientes/',
        views.gestion_clientes,
        name='gestion_clientes'
    ),

    path(
        'gestion/clientes/<int:id>/',
        views.gestion_cliente,
        name='gestion_cliente'
    ),


    # =========================
    # COTIZACIONES
    # =========================

    path(
        'gestion/cotizaciones/',
        views.gestion_cotizaciones,
        name='gestion_cotizaciones'
    ),

    path(
        'gestion/cotizaciones/<int:id>/',
        views.gestion_cotizacion,
        name='gestion_cotizacion'
    ),


    # =========================
    # RESERVAS
    # =========================

    path(
        'gestion/reservas/',
        views.gestion_reservas,
        name='gestion_reservas'
    ),

    path(
        'gestion/reservas/<int:id>/',
        views.gestion_reserva,
        name='gestion_reserva'
    ),


    # =========================
    # PREPARACIÓN
    # =========================

    path(
        'gestion/preparacion/',
        views.gestion_preparacion,
        name='gestion_preparacion'
    ),

    path(
        'gestion/preparacion/<int:id>/',
        views.gestion_preparacion_documento,
        name='gestion_preparacion_documento'
    ),


    # =========================
    # DESPACHOS
    # =========================

    path(
        'gestion/despachos/',
        views.gestion_despachos,
        name='gestion_despachos'
    ),

    path(
        'gestion/despachos/<int:id>/',
        views.gestion_despacho_documento,
        name='gestion_despacho_documento'
    ),


    # =========================
    # DEVOLUCIONES
    # =========================

    path(
        'gestion/devoluciones/',
        views.gestion_devoluciones,
        name='gestion_devoluciones'
    ),

    path(
        'gestion/devoluciones/<int:id>/',
        views.gestion_devolucion,
        name='gestion_devolucion'
    ),


    # =========================
    # MERMAS
    # =========================

    path(
        'gestion/mermas/',
        views.gestion_mermas,
        name='gestion_mermas'
    ),


    # =========================
    # CALENDARIO
    # =========================

    path(
        'gestion/calendario/',
        views.gestion_calendario,
        name='gestion_calendario'
    ),


    # =========================
    # REPORTES
    # =========================

    path(
        'gestion/reportes/',
        views.gestion_reportes,
        name='gestion_reportes'
    ),


    # =========================
    # USUARIOS
    # =========================

    path(
        'gestion/usuarios/',
        views.gestion_usuarios,
        name='gestion_usuarios'
    ),


    # =========================
    # CONFIGURACIÓN
    # =========================

    path(
        'gestion/configuracion/',
        views.gestion_configuracion,
        name='gestion_configuracion'
    ),


    # =========================
    # LOGIN
    # =========================

    path(
        'gestion/login/',
        views.gestion_login,
        name='gestion_login'
    ),

]