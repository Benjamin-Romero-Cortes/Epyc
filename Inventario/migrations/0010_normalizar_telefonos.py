from django.db import migrations

from Inventario.validaciones import normalizar_telefono


def normalizar(apps, schema_editor):
    """Deja los celulares ya guardados en el mismo formato: +56 9 1234 5678."""
    Cliente = apps.get_model("Inventario", "Cliente")
    for cliente in Cliente.objects.exclude(telefono=""):
        nuevo = normalizar_telefono(cliente.telefono)[:30]
        if nuevo != cliente.telefono:
            cliente.telefono = nuevo
            cliente.save(update_fields=["telefono"])


class Migration(migrations.Migration):

    dependencies = [
        ("Inventario", "0009_gestion_categorias"),
    ]

    operations = [
        migrations.RunPython(normalizar, migrations.RunPython.noop),
    ]
