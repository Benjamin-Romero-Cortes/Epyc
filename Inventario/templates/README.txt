TEMPLATES CON BASE.HTML

Archivos:
- base.html
- index.html
- catalogo.html
- producto.html
- cotizador.html
- nosotros.html
- contacto.html

base.html contiene:
- head común
- style.css global
- header y navegación
- footer
- WhatsApp flotante
- main.js

Bloques:
- title
- meta_description
- extra_css
- content
- extra_js

Cada plantilla hija conserva sus estilos/scripts particulares.

Importante:
Se cambiaron los enlaces públicos que usaban {% url 'inicio' %} por {% url 'index' %},
porque en tu urls.py actual `inicio` corresponde al panel de gestión y `index` es el inicio público.

Coloca todos estos archivos en:
Inventario/templates/
