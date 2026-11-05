import re

from django.core.exceptions import ValidationError
from django.core.validators import validate_email


def normalizar_rut(rut):
    """Deja el RUT en un formato único: sin puntos, guion ni espacios y con K mayúscula."""
    return (
        (rut or "")
        .replace(".", "")
        .replace("-", "")
        .replace(" ", "")
        .upper()
    )


def digito_verificador(cuerpo):
    """Calcula el dígito verificador de un RUT chileno (módulo 11)."""
    suma, factor = 0, 2
    for digito in reversed(cuerpo):
        suma += int(digito) * factor
        factor = 2 if factor == 7 else factor + 1
    resto = 11 - (suma % 11)
    return {11: "0", 10: "K"}.get(resto, str(resto))


def rut_valido(rut):
    """Recibe un RUT normalizado y comprueba formato y dígito verificador."""
    if not re.fullmatch(r"\d{7,8}[0-9K]", rut or ""):
        return False
    return digito_verificador(rut[:-1]) == rut[-1]


def correo_valido(correo):
    try:
        validate_email(correo)
    except ValidationError:
        return False
    return True


def normalizar_telefono(telefono):
    """Celulares chilenos en un formato único: +56 9 1234 5678. Otros números quedan como vienen."""
    telefono = (telefono or "").strip()
    digitos = re.sub(r"\D", "", telefono)
    # Prefijo internacional de marcado (0056...) y cero inicial de marcación nacional (09...).
    if digitos.startswith("00"):
        digitos = digitos[2:]
    elif len(digitos) == 10 and digitos.startswith("09"):
        digitos = digitos[1:]
    if len(digitos) == 11 and digitos.startswith("569"):
        digitos = digitos[2:]
    if len(digitos) == 9 and digitos.startswith("9"):
        return f"+56 9 {digitos[1:5]} {digitos[5:]}"
    return telefono


def telefono_valido(telefono):
    """Acepta dígitos, espacios, +, guiones y paréntesis, con 8 a 15 dígitos."""
    if not re.fullmatch(r"[\d\s+()\-]+", telefono or ""):
        return False
    return 8 <= len(re.sub(r"\D", "", telefono)) <= 15
