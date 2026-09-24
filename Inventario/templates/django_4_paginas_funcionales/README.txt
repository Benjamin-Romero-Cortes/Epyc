PAQUETE DJANGO - 4 PÁGINAS

Incluye:
- templates/producto.html
- templates/contacto.html
- templates/cotizador.html
- templates/nosotros.html
- static/js/cotizador-django.js
- views_nuevas.py
- urls_nuevas.py

Qué quedó funcional:
1. producto.html
   - Carga un Articulo desde PostgreSQL.
   - Muestra sus datos reales.
   - Muestra hasta 4 artículos relacionados de la misma categoría.
   - Ya no depende de productos-data.js ni producto-detalle.js.
   - Enlace "Cotizar este artículo" manda ?articulo=<id> al cotizador.

2. contacto.html
   - Usa {% static %} y {% url %}.
   - Conserva FAQ, mapa y enlaces de contacto.
   - Usa faq.js y main.js existentes.

3. nosotros.html
   - Usa {% static %} y {% url %}.
   - Conserva el diseño y el contenido original.

4. cotizador.html
   - Usa CSRF.
   - Carga categorías desde la BD.
   - Conserva el wizard de 3 pasos.
   - Crea o actualiza Cliente según el correo.
   - Crea Servicio con estado "Cotizacion".
   - Genera código COT-AAAAMMDD-XXXXXX.
   - Guarda despacho, empresa, medio preferido, categorías, artículo consultado
     y comentarios dentro de Servicio.observaciones.
   - Al terminar muestra confirmación y enlace a WhatsApp.

CÓMO INSTALARLO

A) Copia los HTML a:
   Inventario/templates/

B) Copia cotizador-django.js a:
   Inventario/static/js/

C) NO reemplaces views.py completo.
   Copia las funciones/imports de views_nuevas.py dentro de Inventario/views.py.

D) NO reemplaces urls.py completo.
   Agrega las rutas de urls_nuevas.py a tu urlpatterns existente.

E) Asegúrate de tener estos modelos:
   Articulo, Categoria, Cliente, Negocio, Servicio

F) Prueba:
   python manage.py check
   python manage.py runserver

IMPORTANTE:
- Debe existir al menos un Negocio activo.
- Si usas namespace/app_name en tus URLs, ajusta los {% url %}.
- El modelo actual no tiene columnas independientes para empresa, despacho,
  medio de contacto o categorías solicitadas, por eso se guardan en observaciones.
