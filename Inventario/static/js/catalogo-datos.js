/**
 * catalogo-datos.js
 * Punto único para obtener los productos del catálogo. Intenta cargar
 * data/productos.json (lo necesario cuando el sitio esté en un servidor
 * real o conectado a una API). Si el navegador bloquea esa carga -por
 * ejemplo, al abrir el archivo HTML directamente con doble clic, sin
 * servidor- usa la copia embebida en data/productos-data.js como
 * respaldo, para que el catálogo funcione igual.
 */
function obtenerProductos() {
  return fetch('data/productos.json')
    .then((res) => {
      if (!res.ok) throw new Error('Respuesta no válida de productos.json');
      return res.json();
    })
    .catch(() => {
      if (typeof PRODUCTOS_DATA !== 'undefined') return PRODUCTOS_DATA;
      throw new Error('No se pudo cargar el catálogo de productos.');
    });
}
