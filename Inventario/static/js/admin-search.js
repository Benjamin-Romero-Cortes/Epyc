// Buscador general de la barra superior del panel: consulta /gestion/buscar/ mientras se escribe.
document.addEventListener('DOMContentLoaded', () => {
  const input = document.getElementById('global-search');
  if (!input) return;
  const caja = input.closest('.topbar-search');
  if (!caja) return;

  const results = document.createElement('div');
  results.className = 'global-search-results';
  results.hidden = true;
  results.style.cssText = 'position:absolute;top:calc(100% + 6px);left:0;right:0;background:var(--color-white-warm);border:1px solid var(--color-gray-light);border-radius:12px;box-shadow:var(--shadow-lg);max-height:360px;overflow-y:auto;z-index:400;';
  caja.style.position = 'relative';
  caja.appendChild(results);

  const escapar = (texto) => String(texto).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const url = input.dataset.url || '/gestion/buscar/';
  let espera = null;
  let consulta = 0;

  function mostrar(grupos, termino) {
    if (!grupos.length) {
      results.innerHTML = `<div style="padding:1rem;font-size:0.85rem;opacity:0.6;">Sin resultados para "${escapar(termino)}"</div>`;
    } else {
      results.innerHTML = grupos.map((g) => `
        <div style="padding:0.6rem 0.9rem 0.2rem;font-size:0.68rem;letter-spacing:0.08em;text-transform:uppercase;color:var(--color-accent-dark);font-weight:700;">${escapar(g.titulo)}</div>
        ${g.items.map((item) => `
          <a href="${escapar(item.href)}" style="display:flex;justify-content:space-between;gap:0.6rem;padding:0.55rem 0.9rem;font-size:0.86rem;border-top:1px solid var(--color-gray-light);">
            <span>${escapar(item.titulo)}</span><span style="opacity:0.55;">${escapar(item.sub)}</span>
          </a>
        `).join('')}
      `).join('');
    }
    results.hidden = false;
  }

  input.addEventListener('input', () => {
    const termino = input.value.trim();
    clearTimeout(espera);
    if (termino.length < 2) { results.hidden = true; return; }
    espera = setTimeout(() => {
      const actual = ++consulta;
      fetch(`${url}?q=${encodeURIComponent(termino)}`, { headers: { Accept: 'application/json' } })
        .then((r) => (r.ok ? r.json() : { grupos: [] }))
        .then((datos) => { if (actual === consulta) mostrar(datos.grupos || [], termino); })
        .catch(() => { results.hidden = true; });
    }, 200);
  });

  document.addEventListener('click', (e) => {
    if (!results.contains(e.target) && e.target !== input) results.hidden = true;
  });
});
