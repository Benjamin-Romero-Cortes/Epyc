# Configuración para correr las pruebas en SQLite local, sin tocar la base compartida.
from .settings import *  # noqa: F401,F403

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "test_local.sqlite3",
    }
}

STATICFILES_STORAGE = "django.contrib.staticfiles.storage.StaticFilesStorage"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
# Se usa el mismo cifrado de contraseñas que en producción: las pruebas de seguridad lo verifican.

# Las pruebas provocan a propósito respuestas 400/403/404 y las verifican con asserts;
# se silencia su registro en consola para que la salida muestre solo el resultado de cada prueba.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "loggers": {
        "django.request": {"level": "CRITICAL"},
        "Inventario": {"level": "CRITICAL"},  # p. ej. la prueba que simula una falla del servidor de correo
    },
}
