from django.db import models
from django.utils import timezone
from django.db.models import Q, F


# NEGOCIO

class Negocio(models.Model):
    nombre = models.CharField(max_length=150)
    nombre_fantasia = models.CharField(max_length=150, blank=True)
    rut = models.CharField(max_length=20, blank=True)
    telefono = models.CharField(max_length=30, blank=True)
    email = models.EmailField(max_length=150, blank=True)
    direccion = models.CharField(max_length=255, blank=True)
    descripcion = models.TextField(blank=True)

    porcentaje_abono = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0
    )

    porcentaje_garantia = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0
    )

    activo = models.BooleanField(default=True)

    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "negocio"

    def __str__(self):
        return self.nombre_fantasia or self.nombre


# CATEGORIA

class Categoria(models.Model):
    negocio = models.ForeignKey(
        Negocio,
        on_delete=models.CASCADE,
        related_name="categorias"
    )

    nombre = models.CharField(max_length=100)
    descripcion = models.CharField(max_length=255, blank=True)
    activo = models.BooleanField(default=True)

    class Meta:
        db_table = "categoria"

    def __str__(self):
        return self.nombre


# CLIENTE

class Cliente(models.Model):
    negocio = models.ForeignKey(
        Negocio,
        on_delete=models.CASCADE,
        related_name="clientes"
    )

    rut = models.CharField(max_length=20, blank=True)
    nombre = models.CharField(max_length=100)
    apellido = models.CharField(max_length=100, blank=True)

    telefono = models.CharField(max_length=30, blank=True)
    email = models.EmailField(max_length=150, blank=True)

    direccion = models.CharField(max_length=255, blank=True)
    comuna = models.CharField(max_length=100, blank=True)

    observaciones = models.TextField(blank=True)

    activo = models.BooleanField(default=True)

    # Cuenta del sitio público: contraseña cifrada (vacía = el cliente no se ha registrado).
    password = models.CharField(max_length=128, blank=True, default="")
    fecha_registro = models.DateTimeField(null=True, blank=True)

    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "cliente"

        constraints = [
            # Un RUT (ya normalizado) solo puede pertenecer a un cliente por negocio.
            models.UniqueConstraint(
                fields=["negocio", "rut"],
                condition=~Q(rut=""),
                name="cliente_rut_unico_por_negocio"
            ),
            # El correo identifica la cuenta al iniciar sesión: no puede repetirse entre cuentas.
            models.UniqueConstraint(
                fields=["negocio", "email"],
                condition=~Q(password="") & ~Q(email=""),
                name="cliente_cuenta_correo_unico"
            ),
        ]

    def __str__(self):
        return f"{self.nombre} {self.apellido}".strip()

    @property
    def tiene_cuenta(self):
        return bool(self.password)

    @property
    def rut_formateado(self):
        """RUT guardado sin puntos ni guion (123456785) mostrado como 12.345.678-5."""
        rut = (self.rut or "").replace(".", "").replace("-", "").upper()
        if len(rut) < 2:
            return self.rut
        cuerpo, dv = rut[:-1], rut[-1]
        return f"{int(cuerpo):,}".replace(",", ".") + f"-{dv}" if cuerpo.isdigit() else self.rut


# ROL

class Rol(models.Model):
    nombre = models.CharField(max_length=50, unique=True)
    descripcion = models.CharField(max_length=255, blank=True)

    class Meta:
        db_table = "rol"

    def __str__(self):
        return self.nombre


# USUARIO

class Usuario(models.Model):
    negocio = models.ForeignKey(
        Negocio,
        on_delete=models.CASCADE,
        related_name="usuarios"
    )

    rol = models.ForeignKey(
        Rol,
        on_delete=models.PROTECT,
        related_name="usuarios"
    )

    nombre = models.CharField(max_length=100)
    apellido = models.CharField(max_length=100)

    email = models.EmailField(
        max_length=150,
        unique=True
    )

    password = models.CharField(max_length=255)

    activo = models.BooleanField(default=True)

    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "usuario"

    def __str__(self):
        return f"{self.nombre} {self.apellido}"


# ARTICULO

class Articulo(models.Model):
    negocio = models.ForeignKey(
        Negocio,
        on_delete=models.CASCADE,
        related_name="articulos"
    )

    categoria = models.ForeignKey(
        Categoria,
        on_delete=models.PROTECT,
        related_name="articulos"
    )

    codigo = models.CharField(
        max_length=20,
        unique=True
    )

    nombre = models.CharField(max_length=100)

    categoria_label = models.CharField(
        max_length=100,
        blank=True
    )

    descripcion = models.TextField(blank=True)
    descripcion_larga = models.TextField(blank=True)

    dimensiones = models.CharField(max_length=150, blank=True)
    material = models.CharField(max_length=100, blank=True)
    capacidad = models.CharField(max_length=100, blank=True)
    color = models.CharField(max_length=100, blank=True)

    precio_arriendo = models.DecimalField(
        max_digits=10,
        decimal_places=0
    )

    unidad_precio = models.CharField(
        max_length=100,
        blank=True
    )

    imagen = models.CharField(
        max_length=255,
        blank=True
    )

    imagenes = models.JSONField(
        default=list,
        blank=True
    )

    stock_total = models.PositiveIntegerField(default=0)
    stock_trabajable = models.PositiveIntegerField(default=0)

    # Lo que cuesta reponer una unidad: valoriza las mermas.
    costo_reposicion = models.PositiveIntegerField(default=0)

    @property
    def valor_unitario_merma(self):
        """Costo de reposición si está cargado; si no, el precio del producto."""
        return self.costo_reposicion or int(self.precio_arriendo or 0)

    destacado = models.BooleanField(default=False)
    activo = models.BooleanField(default=True)

    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "articulo"

        constraints = [
            models.CheckConstraint(
                condition=Q(stock_trabajable__lte=F("stock_total")),
                name="stock_trabajable_no_supera_total"
            )
        ]

    def __str__(self):
        return f"{self.codigo} - {self.nombre}"


# SERVICIO

class Servicio(models.Model):
    class Estado(models.TextChoices):
        COTIZACION = "Cotizacion", "Cotización"
        CONTACTADO = "Contactado", "Contactado"
        CONFIRMADO = "Confirmado", "Confirmado"
        PREPARACION = "Preparacion", "En preparación"
        PREPARADO = "Preparado", "Preparado"
        DESPACHADO = "Despachado", "Despachado"
        DEVOLUCION_PARCIAL = "Devolucion parcial", "Devolución parcial"
        FINALIZADO = "Finalizado", "Devuelto"
        CERRADO = "Cerrado", "Cerrado"
        CANCELADO = "Cancelado", "Cancelado"

    class MedioContacto(models.TextChoices):
        WHATSAPP = "WhatsApp", "WhatsApp"
        CORREO = "Correo", "Correo"
        LLAMADA = "Llamada", "Llamada"

    negocio = models.ForeignKey(
        Negocio,
        on_delete=models.CASCADE,
        related_name="servicios"
    )

    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.PROTECT,
        related_name="servicios"
    )

    codigo = models.CharField(
        max_length=30,
        unique=True
    )

    estado = models.CharField(
        max_length=30,
        choices=Estado.choices,
        default=Estado.COTIZACION
    )

    tipo_servicio = models.CharField(
        max_length=100,
        blank=True
    )

    fecha_solicitud = models.DateField()
    fecha_evento = models.DateField(null=True, blank=True)

    fecha_inicio = models.DateField(null=True, blank=True)
    fecha_termino = models.DateField(null=True, blank=True)

    hora_inicio = models.TimeField(null=True, blank=True)
    hora_termino = models.TimeField(null=True, blank=True)

    direccion_evento = models.CharField(
        max_length=255,
        blank=True
    )

    comuna_evento = models.CharField(
        max_length=100,
        blank=True
    )

    cantidad_personas = models.IntegerField(
        null=True,
        blank=True
    )

    subtotal = models.DecimalField(
        max_digits=12,
        decimal_places=0,
        default=0
    )

    descuento = models.DecimalField(
        max_digits=12,
        decimal_places=0,
        default=0
    )

    total = models.DecimalField(
        max_digits=12,
        decimal_places=0,
        default=0
    )

    abono = models.DecimalField(
        max_digits=12,
        decimal_places=0,
        default=0
    )

    garantia = models.DecimalField(
        max_digits=12,
        decimal_places=0,
        default=0
    )

    observaciones = models.TextField(blank=True)

    # Lo que el cliente indicó en el cotizador público.
    requiere_despacho = models.BooleanField(default=False, db_default=False)

    medio_contacto = models.CharField(
        max_length=20,
        blank=True,
        default="",
        db_default="",
        choices=MedioContacto.choices
    )

    comentarios = models.TextField(blank=True, default="", db_default="")

    # Cuándo el cliente aceptó la cotización desde su cuenta (la reserva la confirma el administrador).
    aceptada_cliente = models.DateTimeField(null=True, blank=True)

    categorias_solicitadas = models.ManyToManyField(
        Categoria,
        blank=True,
        related_name="servicios_solicitados",
        db_table="servicio_categoria_solicitada"
    )

    categorias_por_definir = models.BooleanField(default=False, db_default=False)

    fecha_confirmacion = models.DateTimeField(
        null=True,
        blank=True
    )

    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "servicio"

        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(fecha_inicio__isnull=True)
                    | Q(fecha_termino__isnull=True)
                    | Q(fecha_termino__gte=F("fecha_inicio"))
                ),
                name="fecha_termino_mayor_inicio"
            )
        ]

    def __str__(self):
        return self.codigo

    @property
    def clase_estado(self):
        """Variante visual de la etiqueta de estado en el panel."""
        return {
            self.Estado.COTIZACION: "info",
            self.Estado.CONTACTADO: "warning",
            self.Estado.CONFIRMADO: "success",
            self.Estado.PREPARACION: "warning",
            self.Estado.PREPARADO: "success",
            self.Estado.DESPACHADO: "success",
            self.Estado.DEVOLUCION_PARCIAL: "warning",
            self.Estado.FINALIZADO: "success",
            self.Estado.CERRADO: "neutral",
            self.Estado.CANCELADO: "danger",
        }.get(self.estado, "neutral")


# DETALLE SERVICIO

class DetalleServicio(models.Model):
    servicio = models.ForeignKey(
        Servicio,
        on_delete=models.CASCADE,
        related_name="detalles"
    )

    articulo = models.ForeignKey(
        Articulo,
        on_delete=models.PROTECT,
        related_name="detalles_servicio"
    )

    cantidad = models.PositiveIntegerField()

    precio_unitario = models.DecimalField(
        max_digits=10,
        decimal_places=0
    )

    subtotal = models.DecimalField(
        max_digits=12,
        decimal_places=0
    )

    class Meta:
        db_table = "detalle_servicio"

    def __str__(self):
        return f"{self.servicio.codigo} - {self.articulo.nombre}"


# PREPARACION

class Preparacion(models.Model):
    class Estado(models.TextChoices):
        PENDIENTE = "Pendiente", "Pendiente"
        EN_PREPARACION = "En preparacion", "En preparación"
        COMPLETA = "Completa", "Completa"
        CANCELADA = "Cancelada", "Cancelada"

    servicio = models.ForeignKey(
        Servicio,
        on_delete=models.CASCADE,
        related_name="preparaciones"
    )

    # Responsable de la preparación (quien la generó).
    usuario = models.ForeignKey(
        Usuario,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="preparaciones"
    )

    estado = models.CharField(
        max_length=30,
        choices=Estado.choices,
        default=Estado.PENDIENTE
    )

    fecha_creacion = models.DateTimeField(default=timezone.now)

    # Primer avance guardado.
    fecha_inicio = models.DateTimeField(
        null=True,
        blank=True
    )

    fecha_finalizacion = models.DateTimeField(
        null=True,
        blank=True
    )

    finalizada_por = models.ForeignKey(
        Usuario,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="preparaciones_finalizadas"
    )

    observaciones = models.TextField(blank=True)

    class Meta:
        db_table = "preparacion"
        constraints = [
            # Una reserva tiene como máximo una preparación.
            models.UniqueConstraint(fields=["servicio"], name="preparacion_unica_por_servicio"),
        ]

    def __str__(self):
        return f"Preparación {self.id} - {self.servicio.codigo}"

    @property
    def clase_estado(self):
        return {
            self.Estado.PENDIENTE: "neutral",
            self.Estado.EN_PREPARACION: "warning",
            self.Estado.COMPLETA: "success",
            self.Estado.CANCELADA: "danger",
        }.get(self.estado, "neutral")


# DETALLE PREPARACION

class DetallePreparacion(models.Model):
    preparacion = models.ForeignKey(
        Preparacion,
        on_delete=models.CASCADE,
        related_name="detalles"
    )

    articulo = models.ForeignKey(
        Articulo,
        on_delete=models.PROTECT,
        related_name="detalles_preparacion"
    )

    # Copiada de la reserva al generar la preparación.
    cantidad_solicitada = models.PositiveIntegerField()
    cantidad_preparada = models.PositiveIntegerField(default=0)

    observaciones = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        db_table = "detalle_preparacion"
        constraints = [
            models.UniqueConstraint(fields=["preparacion", "articulo"], name="detalle_preparacion_articulo_unico"),
            models.CheckConstraint(
                condition=Q(cantidad_preparada__lte=F("cantidad_solicitada")),
                name="preparada_no_supera_solicitada",
            ),
        ]

    def __str__(self):
        return f"{self.articulo.nombre} - {self.cantidad_preparada}"

    @property
    def cantidad_faltante(self):
        return self.cantidad_solicitada - self.cantidad_preparada


# DESPACHO

class Despacho(models.Model):
    class TipoEntrega(models.TextChoices):
        DESPACHO = "Despacho", "Despacho a domicilio"
        RETIRO = "Retiro", "Retiro en bodega"

    class Estado(models.TextChoices):
        PROGRAMADO = "Programado", "Programado"
        ENTREGADO = "Entregado", "Entregado"
        CANCELADO = "Cancelado", "Cancelado"

    servicio = models.ForeignKey(
        Servicio,
        on_delete=models.CASCADE,
        related_name="despachos"
    )

    preparacion = models.ForeignKey(
        Preparacion,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="despachos"
    )

    # Usuario del panel que registró la operación.
    usuario = models.ForeignKey(
        Usuario,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="despachos"
    )

    estado = models.CharField(
        max_length=20,
        choices=Estado.choices,
        default=Estado.ENTREGADO
    )

    fecha_programada = models.DateTimeField(null=True, blank=True)

    # Fecha y hora en que los artículos salieron realmente.
    fecha_despacho = models.DateTimeField()

    tipo_entrega = models.CharField(
        max_length=50,
        blank=True,
        choices=TipoEntrega.choices
    )

    responsable_entrega = models.CharField(
        max_length=150,
        blank=True
    )

    receptor = models.CharField(max_length=150, blank=True, default="")

    observaciones = models.TextField(blank=True)

    fecha_registro = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "despacho"
        constraints = [
            # Un solo despacho vigente por reserva (versión 1.0: despacho completo).
            models.UniqueConstraint(
                fields=["servicio"],
                condition=~Q(estado="Cancelado"),
                name="despacho_vigente_unico_por_servicio",
            ),
        ]

    def __str__(self):
        return f"Despacho {self.id} - {self.servicio.codigo}"

    @property
    def clase_estado(self):
        return {
            self.Estado.PROGRAMADO: "warning",
            self.Estado.ENTREGADO: "success",
            self.Estado.CANCELADO: "danger",
        }.get(self.estado, "neutral")


# DETALLE DESPACHO

class DetalleDespacho(models.Model):
    despacho = models.ForeignKey(
        Despacho,
        on_delete=models.CASCADE,
        related_name="detalles"
    )

    articulo = models.ForeignKey(
        Articulo,
        on_delete=models.PROTECT,
        related_name="detalles_despacho"
    )

    cantidad = models.PositiveIntegerField()

    class Meta:
        db_table = "detalle_despacho"

    def __str__(self):
        return f"{self.articulo.nombre} - {self.cantidad}"


# DEVOLUCION

class Devolucion(models.Model):
    """Una recepción de artículos en bodega. Una reserva puede tener varias (devoluciones parciales)."""

    servicio = models.ForeignKey(
        Servicio,
        on_delete=models.CASCADE,
        related_name="devoluciones"
    )

    despacho = models.ForeignKey(
        "Despacho",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="devoluciones"
    )

    # Usuario del panel que registró la recepción.
    usuario = models.ForeignKey(
        Usuario,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="devoluciones"
    )

    fecha_devolucion = models.DateTimeField()

    entregado_por = models.CharField(max_length=150, blank=True, default="")

    # True cuando con esta recepción no quedó nada pendiente.
    completa = models.BooleanField(default=False)

    observaciones = models.TextField(blank=True)

    fecha_registro = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "devolucion"
        ordering = ["-fecha_devolucion", "-id"]

    def __str__(self):
        return f"Devolución {self.id} - {self.servicio.codigo}"


# DETALLE DEVOLUCION

class DetalleDevolucion(models.Model):
    devolucion = models.ForeignKey(
        Devolucion,
        on_delete=models.CASCADE,
        related_name="detalles"
    )

    articulo = models.ForeignKey(
        Articulo,
        on_delete=models.PROTECT,
        related_name="detalles_devolucion"
    )

    # Recibido físicamente en esta devolución (buenas + dañadas).
    cantidad_devuelta = models.PositiveIntegerField(default=0)
    cantidad_buena = models.PositiveIntegerField(default=0)
    cantidad_danada = models.PositiveIntegerField(default=0)
    cantidad_perdida = models.PositiveIntegerField(default=0)
    # Lo que seguía en el cliente después de esta devolución.
    cantidad_pendiente = models.PositiveIntegerField(default=0)

    observaciones = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        db_table = "detalle_devolucion"
        constraints = [
            models.UniqueConstraint(fields=["devolucion", "articulo"], name="detalle_devolucion_articulo_unico"),
            models.CheckConstraint(
                condition=Q(cantidad_devuelta=F("cantidad_buena") + F("cantidad_danada")),
                name="devuelta_es_buena_mas_danada",
            ),
        ]

    def __str__(self):
        return f"{self.articulo.nombre} - devolución {self.devolucion_id}"

    @property
    def cantidad_resuelta(self):
        return self.cantidad_buena + self.cantidad_danada + self.cantidad_perdida


# MERMA

class Merma(models.Model):
    """
    Unidades que salen del inventario rentable. Nunca se borra: un error se corrige anulándola.
    - Dañado: la unidad existe pero no se puede arrendar → baja solo el stock trabajable.
      Si se repara, vuelve al stock trabajable (cantidad_reparada).
    - Perdido, Roto, No recuperable y Ajuste de inventario → bajan el stock total y el trabajable.
    """

    class Tipo(models.TextChoices):
        DANADO = "Dañado", "Dañado (recuperable)"
        PERDIDO = "Perdido", "Perdido"
        ROTO = "Roto", "Roto"
        NO_RECUPERABLE = "No recuperable", "No recuperable"
        AJUSTE = "Ajuste de inventario", "Ajuste de inventario"

    detalle_devolucion = models.ForeignKey(
        DetalleDevolucion,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="mermas"
    )

    servicio = models.ForeignKey(
        Servicio,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="mermas"
    )

    articulo = models.ForeignKey(
        Articulo,
        on_delete=models.PROTECT,
        related_name="mermas"
    )

    usuario = models.ForeignKey(
        Usuario,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="mermas"
    )

    cantidad = models.PositiveIntegerField()

    tipo = models.CharField(
        max_length=50,
        choices=Tipo.choices
    )

    motivo = models.CharField(
        max_length=255,
        blank=True
    )

    valor_reposicion = models.DecimalField(
        max_digits=12,
        decimal_places=0,
        default=0
    )

    observaciones = models.TextField(blank=True)

    fecha = models.DateTimeField()

    cantidad_reparada = models.PositiveIntegerField(default=0)

    anulada = models.BooleanField(default=False)
    fecha_anulacion = models.DateTimeField(null=True, blank=True)
    anulada_por = models.ForeignKey(
        Usuario,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="mermas_anuladas"
    )
    motivo_anulacion = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        db_table = "merma"
        ordering = ["-fecha", "-id"]
        constraints = [
            models.CheckConstraint(condition=Q(cantidad__gt=0), name="merma_cantidad_positiva"),
            models.CheckConstraint(condition=Q(cantidad_reparada__lte=F("cantidad")), name="merma_reparada_no_supera"),
        ]

    def __str__(self):
        return f"{self.tipo} - {self.articulo.nombre}"

    @property
    def afecta_stock_total(self):
        return self.tipo != self.Tipo.DANADO

    @property
    def pendiente_reparar(self):
        return self.cantidad - self.cantidad_reparada if self.tipo == self.Tipo.DANADO and not self.anulada else 0

    @property
    def valor(self):
        """Valor guardado o, si no se indicó, unidades vigentes × valor unitario del producto."""
        if self.valor_reposicion:
            return self.valor_reposicion
        return (self.cantidad - self.cantidad_reparada) * self.articulo.valor_unitario_merma


# MOVIMIENTO INVENTARIO

class MovimientoInventario(models.Model):
    articulo = models.ForeignKey(
        Articulo,
        on_delete=models.PROTECT,
        related_name="movimientos"
    )

    usuario = models.ForeignKey(
        Usuario,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="movimientos_inventario"
    )

    servicio = models.ForeignKey(
        Servicio,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="movimientos_inventario"
    )

    tipo = models.CharField(
        max_length=50
    )

    cantidad = models.IntegerField()

    stock_anterior = models.IntegerField(
        null=True,
        blank=True
    )

    stock_nuevo = models.IntegerField(
        null=True,
        blank=True
    )

    motivo = models.CharField(
        max_length=255,
        blank=True
    )

    observaciones = models.TextField(blank=True)

    fecha = models.DateTimeField()

    class Meta:
        db_table = "movimiento_inventario"
        ordering = ["-fecha"]

    def __str__(self):
        return f"{self.tipo} - {self.articulo.nombre}"

    # Movimientos que no cambian el stock: se describen por su efecto operativo.
    EFECTOS_SIN_STOCK = {
        "Reserva confirmada": "comprometidas",
        "Salida a cliente": "en cliente",
        "Devolución": "liberadas",
        "Cancelación": "liberadas",
    }

    @property
    def descripcion_cantidad(self):
        efecto = self.EFECTOS_SIN_STOCK.get(self.tipo)
        if efecto:
            return f"{abs(self.cantidad)} {efecto}"
        return f"+{self.cantidad}" if self.cantidad > 0 else str(self.cantidad)


# HISTORIAL DEL SERVICIO

class HistorialServicio(models.Model):
    """Trazabilidad mínima: quién hizo cada operación sobre un servicio y cuándo."""

    servicio = models.ForeignKey(
        Servicio,
        on_delete=models.CASCADE,
        related_name="historial"
    )

    usuario = models.ForeignKey(
        Usuario,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="historial_servicios"
    )

    accion = models.CharField(max_length=100)
    estado_anterior = models.CharField(max_length=30, blank=True)
    estado_nuevo = models.CharField(max_length=30, blank=True)
    observacion = models.TextField(blank=True)
    fecha = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "historial_servicio"
        ordering = ["-fecha", "-id"]

    def __str__(self):
        return f"{self.servicio.codigo} - {self.accion}"

    @staticmethod
    def _etiqueta(valor):
        return Servicio.Estado(valor).label if valor in Servicio.Estado.values else valor

    @property
    def etiqueta_anterior(self):
        return self._etiqueta(self.estado_anterior)

    @property
    def etiqueta_nuevo(self):
        return self._etiqueta(self.estado_nuevo)
