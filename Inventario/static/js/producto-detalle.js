/**
 * producto-detalle.js
 * Renderiza la ficha de un producto según el parámetro ?id= de la URL
 * (ver catalogo-datos.js para el origen de los datos).
 */
(function () {
  const contenedor = document.getElementById('product-detail');
  if (!contenedor) return;

  const params = new URLSearchParams(window.location.search);
  const id = params.get('id');

  async function cargar() {
    try {
      const productos = await obtenerProductos();
      const producto = productos.find((p) => p.id === id);

      if (!producto) {
        contenedor.innerHTML = '<p class="empty-state">No encontramos este producto. <a href="catalogo.html">Volver al catálogo</a>.</p>';
        return;
      }

      document.title = `${producto.nombre} · Entre Platos y Copas`;
      renderizarProducto(producto);
      renderizarRelacionados(productos, producto);
    } catch (err) {
      contenedor.innerHTML = '<p class="empty-state">No pudimos cargar la información del producto.</p>';
      console.error('Error cargando producto', err);
    }
  }

  function renderizarProducto(producto) {
    const imagenes = producto.imagenes && producto.imagenes.length ? producto.imagenes : [producto.imagen];

    contenedor.innerHTML = `
      <div class="product-gallery">
        <div class="product-gallery-main">
          <img id="gallery-main-img" src="${imagenes[0]}" alt="${producto.nombre}">
        </div>
        ${imagenes.length > 1 ? `
          <div class="product-gallery-thumbs">
            ${imagenes.map((img, i) => `
              <button data-img="${img}" class="${i === 0 ? 'is-active' : ''}">
                <img src="${img}" alt="Vista ${i + 1} de ${producto.nombre}">
              </button>
            `).join('')}
          </div>` : ''}
      </div>
      <div class="product-info">
        <span class="category-tag">${producto.categoriaLabel}</span>
        <h1>${producto.nombre}</h1>
        <p class="product-desc">${producto.descripcionLarga || producto.descripcion}</p>
        <table class="spec-table">
          ${producto.dimensiones ? `<tr><td>Dimensiones</td><td>${producto.dimensiones}</td></tr>` : ''}
          ${producto.material ? `<tr><td>Material</td><td>${producto.material}</td></tr>` : ''}
          ${producto.capacidad ? `<tr><td>Capacidad</td><td>${producto.capacidad}</td></tr>` : ''}
          ${producto.color ? `<tr><td>Color</td><td>${producto.color}</td></tr>` : ''}
        </table>
        <div class="availability-note">
          <span>ℹ️</span>
          <p>La disponibilidad de este producto dependerá de la fecha de tu evento y de la cantidad solicitada. Confírmala con nuestro equipo al solicitar tu cotización.</p>
        </div>
        <div class="product-detail-actions">
          <a class="btn btn-accent" href="cotizador.html">Ir a cotizar mi evento</a>
        </div>
      </div>
    `;

    const mainImg = document.getElementById('gallery-main-img');
    contenedor.querySelectorAll('.product-gallery-thumbs button').forEach((btn) => {
      btn.addEventListener('click', () => {
        mainImg.src = btn.dataset.img;
        contenedor.querySelectorAll('.product-gallery-thumbs button').forEach((b) => b.classList.remove('is-active'));
        btn.classList.add('is-active');
      });
    });
  }

  function renderizarRelacionados(productos, actual) {
    const wrap = document.getElementById('related-grid');
    if (!wrap) return;
    const relacionados = productos
      .filter((p) => p.categoria === actual.categoria && p.id !== actual.id)
      .slice(0, 4);

    if (!relacionados.length) {
      document.getElementById('related-products').hidden = true;
      return;
    }

    wrap.innerHTML = relacionados.map((p) => `
      <article class="product-card">
        <a href="producto.html?id=${p.id}" class="product-card-img">
          <span class="product-card-category">${p.categoriaLabel}</span>
          <img src="${p.imagen}" alt="${p.nombre}" loading="lazy">
        </a>
        <div class="product-card-body">
          <h3><a href="producto.html?id=${p.id}">${p.nombre}</a></h3>
          <p class="product-card-desc">${p.descripcion}</p>
          <div class="product-card-actions">
            <a class="btn btn-outline btn-sm" href="producto.html?id=${p.id}">Ver detalle</a>
          </div>
        </div>
      </article>
    `).join('');
  }

  cargar();
})();
