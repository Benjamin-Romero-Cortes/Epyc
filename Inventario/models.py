from django.db import models
from django.db.models import Q, F


# =========================================================
# NEGOCIO
# =========================================================

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


# =========================================================
# CATEGORIA
# =========================================================

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


# =========================================================
# CLIENTE
# =========================================================

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

    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "cliente"

    def __str__(self):
        return f"{self.nombre} {self.apellido}".strip()


# =========================================================
# ROL
# =========================================================

class Rol(models.Model):
    nombre = models.CharField(max_length=50, unique=True)
    descripcion = models.CharField(max_length=255, blank=True)

    class Meta:
        db_table = "rol"

    def __str__(self):
        return self.nombre


# =========================================================
# USUARIO
# =========================================================

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


# =========================================================
# ARTICULO
# =========================================================

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


# =========================================================
# SERVICIO
# =========================================================

class Servicio(models.Model):
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
        max_length=30
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


# =========================================================
# DETALLE SERVICIO
# =========================================================

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


# =========================================================
# PREPARACION
# =========================================================

class Preparacion(models.Model):
    servicio = models.ForeignKey(
        Servicio,
        on_delete=models.CASCADE,
        related_name="preparaciones"
    )

    usuario = models.ForeignKey(
        Usuario,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="preparaciones"
    )

    estado = models.CharField(
        max_length=30
    )

    fecha_inicio = models.DateTimeField(
        null=True,
        blank=True
    )

    fecha_finalizacion = models.DateTimeField(
        null=True,
        blank=True
    )

    observaciones = models.TextField(blank=True)

    class Meta:
        db_table = "preparacion"

    def __str__(self):
        return f"Preparación {self.id} - {self.servicio.codigo}"


# =========================================================
# DETALLE PREPARACION
# =========================================================

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

    cantidad_solicitada = models.PositiveIntegerField()
    cantidad_preparada = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "detalle_preparacion"

    def __str__(self):
        return f"{self.articulo.nombre} - {self.cantidad_preparada}"


# =========================================================
# DESPACHO
# =========================================================

class Despacho(models.Model):
    servicio = models.ForeignKey(
        Servicio,
        on_delete=models.CASCADE,
        related_name="despachos"
    )

    usuario = models.ForeignKey(
        Usuario,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="despachos"
    )

    fecha_despacho = models.DateTimeField()

    tipo_entrega = models.CharField(
        max_length=50,
        blank=True
    )

    responsable_entrega = models.CharField(
        max_length=150,
        blank=True
    )

    observaciones = models.TextField(blank=True)

    class Meta:
        db_table = "despacho"

    def __str__(self):
        return f"Despacho {self.id} - {self.servicio.codigo}"


# =========================================================
# DETALLE DESPACHO
# =========================================================

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


# =========================================================
# DEVOLUCION
# =========================================================

class Devolucion(models.Model):
    servicio = models.ForeignKey(
        Servicio,
        on_delete=models.CASCADE,
        related_name="devoluciones"
    )

    usuario = models.ForeignKey(
        Usuario,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="devoluciones"
    )

    fecha_devolucion = models.DateTimeField()

    observaciones = models.TextField(blank=True)

    class Meta:
        db_table = "devolucion"

    def __str__(self):
        return f"Devolución {self.id} - {self.servicio.codigo}"


# =========================================================
# DETALLE DEVOLUCION
# =========================================================

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

    cantidad_devuelta = models.PositiveIntegerField(default=0)
    cantidad_buena = models.PositiveIntegerField(default=0)
    cantidad_danada = models.PositiveIntegerField(default=0)
    cantidad_pendiente = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "detalle_devolucion"

    def __str__(self):
        return f"{self.articulo.nombre} - devolución {self.id}"


# =========================================================
# MERMA
# =========================================================

class Merma(models.Model):
    detalle_devolucion = models.ForeignKey(
        DetalleDevolucion,
        on_delete=models.CASCADE,
        related_name="mermas"
    )

    articulo = models.ForeignKey(
        Articulo,
        on_delete=models.PROTECT,
        related_name="mermas"
    )

    cantidad = models.PositiveIntegerField()

    tipo = models.CharField(
        max_length=50
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

    class Meta:
        db_table = "merma"

    def __str__(self):
        return f"{self.tipo} - {self.articulo.nombre}"


# =========================================================
# MOVIMIENTO INVENTARIO
# =========================================================

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