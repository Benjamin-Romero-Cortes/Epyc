// Punto único para obtener los productos del catálogo.
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
