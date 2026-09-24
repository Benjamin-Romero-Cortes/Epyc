PLANTILLAS DJANGO - ENTRE PLATOS Y COPAS
==============================================

Este paquete deja las plantillas preparadas para trabajar con el modelo actual:
negocio, categoria, cliente, articulo, servicio, detalle_servicio, preparacion,
detalle_preparacion, despacho, detalle_despacho, devolucion, detalle_devolucion,
merma, movimiento_inventario, rol y usuario.

IMPORTANTE
- No incluye views.py por petición del proyecto actual.
- Los formularios usan POST + {% csrf_token %}.
- En las pantallas donde una entidad anterior era "cotización" o "reserva", se usa Servicio:
  * Cotizaciones: servicios con estado "Cotizacion".
  * Reservas: servicios confirmados / en preparación / despachados / devolución / finalizados.
- No se usa una tabla Reserva independiente porque no existe en el modelo actual.
- Copia gestion-django.js a static/js/gestion-django.js.

CONTEXTOS ESPERADOS POR TEMPLATE
---------------------------------
clientes.html
  clientes: QuerySet Cliente anotado opcionalmente con servicios_count y ultima_reserva.
  POST crear: nombre, apellido, rut, telefono, email, direccion, comuna,
              observaciones, activo, accion=crear.

cliente.html
  cliente: Cliente.
  servicios: Servicio del cliente.
  POST editar: mismos campos del cliente, accion=editar.

inventario.html
  inventario: QuerySet Articulo con select_related("categoria").
  categorias: QuerySet Categoria activas.
  Campos POST crear: codigo, nombre, categoria_id, categoria_label, descripcion,
  descripcion_larga, dimensiones, material, capacidad, color, precio_arriendo,
  unidad_precio, stock_total, stock_trabajable, imagen, destacado, activo.

producto.html
  articulo: Articulo.
  movimientos: MovimientoInventario del artículo.

cotizaciones.html
  cotizaciones: Servicio filtrado estado="Cotizacion", select_related("cliente").
  clientes: Cliente activos.
  articulos: Articulo activos.
  POST crear: cliente_id, tipo_servicio, fecha_evento, fecha_inicio,
  fecha_termino, comuna_evento, direccion_evento, cantidad_personas,
  descuento, abono, garantia, articulo_id, cantidad, observaciones.

cotizacion.html
  servicio: Servicio.
  detalles: DetalleServicio.
  estados_servicio: lista de estados permitidos.
  POST: accion=cambiar_estado, estado.

reservas.html
  reservas: Servicio excluyendo cotizaciones/cancelados según criterio de la view.

reserva.html
  servicio: Servicio.
  detalles: DetalleServicio.

preparacion.html
  preparaciones: Preparacion con servicio y cliente relacionados.

preparacion-documento.html
  preparacion: Preparacion.
  detalles: DetallePreparacion.
  POST dinámico: preparado_<detalle_id>, observaciones.

despachos.html
  despachos: Despacho con servicio__cliente.

despacho-documento.html
  despacho: Despacho.
  detalles: DetalleDespacho.

devoluciones.html
  devoluciones: Devolucion con servicio__cliente.
  total_productos es una anotación opcional.

devolucion.html
  devolucion: Devolucion.
  detalles: DetalleDevolucion.
  POST dinámico: devuelta_<id>, buena_<id>, danada_<id>, pendiente_<id>, observaciones.

mermas.html
  mermas: Merma con articulo__categoria y detalle_devolucion...
  articulos: Articulo activos.
  detalles_devolucion: DetalleDevolucion disponibles para asociar.
  POST: articulo_id, detalle_devolucion_id, cantidad, tipo, fecha,
        valor_reposicion, motivo, observaciones.

usuarios.html
  usuarios: Usuario con select_related("rol").
  roles: Rol.
  POST: nombre, apellido, email, rol_id, password, activo.

configuracion.html
  negocio: Negocio.
  POST: nombre, nombre_fantasia, rut, telefono, email, direccion, descripcion,
        porcentaje_abono, porcentaje_garantia, activo.

calendario.html
  servicios: Servicio ordenados por fecha_evento para el período deseado.

reportes.html
  metricas: dict/objeto con:
    stock_total, stock_trabajable, stock_comprometido, stock_bajo,
    reservas_total, reservas_proximas, reservas_finalizadas, reservas_canceladas,
    clientes_total, clientes_nuevos, monto_cotizado,
    cotizaciones_aceptadas, cotizaciones_rechazadas, ticket_promedio.
  productos_mas_arrendados: objetos con nombre,total_arrendado
  productos_menos_utilizados: objetos con nombre,total_arrendado
  clientes_frecuentes: objetos con nombre,apellido,total_servicios
  ingresos_categoria: objetos con categoria,total

login.html
  POST email,password,recordarme. La view deberá validar Usuario y contraseña.

URLS QUE LAS PLANTILLAS ESPERAN
-------------------------------
index
gestion_clientes
gestion_cliente <id>
gestion_inventario
gestion_producto <id>
gestion_cotizaciones
gestion_cotizacion <id>
gestion_reservas
gestion_reserva <id>
gestion_preparacion
gestion_preparacion_documento <id>
gestion_despachos
gestion_despacho_documento <id>
gestion_devoluciones
gestion_devolucion <id>
gestion_mermas
gestion_calendario
gestion_reportes
gestion_usuarios
gestion_configuracion
gestion_login
cotizador

SUGERENCIAS PARA LAS FUTURAS VIEWS
----------------------------------
Usar select_related/prefetch_related para evitar N+1 con Supabase:
- Articulo.select_related("categoria")
- Servicio.select_related("cliente","negocio").prefetch_related("detalles__articulo")
- Despacho.select_related("servicio__cliente","usuario")
- Devolucion.select_related("servicio__cliente","usuario")
- Merma.select_related("articulo__categoria",
  "detalle_devolucion__devolucion__servicio","detalle_devolucion__devolucion__usuario")

PASSWORDS
---------
El modelo Usuario actual tiene un campo password propio. Idealmente más adelante conviene
migrar a django.contrib.auth para hashing y autenticación segura. Mientras tanto, nunca
guardar contraseñas en texto plano.
