/**
 * admin-search.js
 * Buscador general de la barra superior: busca en productos, clientes,
 * cotizaciones y reservas a la vez, y muestra resultados agrupados que
 * llevan directo a la ficha correspondiente.
 */
document.addEventListener('DOMContentLoaded', () => {
  const input = document.getElementById('global-search');
  if (!input) return;

  const results = document.createElement('div');
  results.className = 'global-search-results';
  results.hidden = true;
  results.style.cssText = 'position:absolute;top:calc(100% + 6px);left:0;right:0;background:var(--color-white-warm);border:1px solid var(--color-gray-light);border-radius:12px;box-shadow:var(--shadow-lg);max-height:360px;overflow-y:auto;z-index:400;';
  input.closest('.topbar-search').style.position = 'relative';
  input.closest('.topbar-search').appendChild(results);

  let datos = null;
  Promise.all([
    obtenerDatos('inventario'), obtenerDatos('clientes'),
    obtenerDatos('cotizaciones'), obtenerDatos('reservas'),
  ]).then(([inventario, clientes, cotizaciones, reservas]) => {
    datos = { inventario, clientes, cotizaciones, reservas };
  }).catch(() => { datos = null; });

  input.addEventListener('input', () => {
    const term = input.value.trim().toLowerCase();
    if (!term || !datos) { results.hidden = true; return; }

    const grupos = [
      { titulo: 'Productos', items: datos.inventario.filter((p) => p.nombre.toLowerCase().includes(term)).slice(0, 4).map((p) => ({ href: `producto.html?codigo=${p.codigo}`, titulo: p.nombre, sub: p.categoria })) },
      { titulo: 'Clientes', items: datos.clientes.filter((c) => c.nombre.toLowerCase().includes(term) || c.rut.includes(term)).slice(0, 4).map((c) => ({ href: `cliente.html?id=${c.id}`, titulo: c.nombre, sub: c.rut })) },
      { titulo: 'Cotizaciones', items: datos.cotizaciones.filter((c) => c.id.toLowerCase().includes(term) || c.clienteNombre.toLowerCase().includes(term)).slice(0, 4).map((c) => ({ href: `cotizacion.html?id=${c.id}`, titulo: c.id, sub: c.clienteNombre })) },
      { titulo: 'Reservas', items: datos.reservas.filter((r) => r.id.toLowerCase().includes(term) || r.clienteNombre.toLowerCase().includes(term)).slice(0, 4).map((r) => ({ href: `reserva.html?id=${r.id}`, titulo: r.id, sub: r.clienteNombre })) },
    ].filter((g) => g.items.length);

    if (!grupos.length) {
      results.innerHTML = '<div style="padding:1rem;font-size:0.85rem;opacity:0.6;">Sin resultados para "' + input.value + '"</div>';
      results.hidden = false;
      return;
    }

    results.innerHTML = grupos.map((g) => `
      <div style="padding:0.6rem 0.9rem 0.2rem;font-size:0.68rem;letter-spacing:0.08em;text-transform:uppercase;color:var(--color-accent-dark);font-weight:700;">${g.titulo}</div>
      ${g.items.map((item) => `
        <a href="${item.href}" style="display:flex;justify-content:space-between;gap:0.6rem;padding:0.55rem 0.9rem;font-size:0.86rem;border-top:1px solid var(--color-gray-light);">
          <span>${item.titulo}</span><span style="opacity:0.55;">${item.sub}</span>
        </a>
      `).join('')}
    `).join('');
    results.hidden = false;
  });

  document.addEventListener('click', (e) => {
    if (!results.contains(e.target) && e.target !== input) results.hidden = true;
  });
});
