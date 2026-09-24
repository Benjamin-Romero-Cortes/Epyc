/**
 * preparacion-documento.js
 * Hojas de preparación imprimibles para una reserva: una hoja por
 * categoría de producto (sin precios, solo nombre y cantidad), para
 * repartir entre distintos encargados según lo que a cada uno le
 * corresponda preparar. Cada categoría se imprime en una página aparte.
 */
(function () {
  const contenedor = document.getElementById('preparacion-doc');
  if (!contenedor) return;

  const id = new URLSearchParams(window.location.search).get('id');

  Promise.all([obtenerDatos('reservas'), obtenerDatos('inventario')]).then(([reservas, inventario]) => {
    const reserva = reservas.find((r) => r.id === id);
    if (!reserva) {
      contenedor.innerHTML = `<p class="empty-state">No encontramos esta reserva.</p>`;
      return;
    }
    document.title = `Hoja de preparación ${reserva.id} · Panel Entre Platos y Copas`;
    render(reserva, inventario);
  }).catch((err) => {
    contenedor.innerHTML = '<p class="empty-state">No pudimos cargar la hoja de preparación.</p>';
    console.error(err);
  });

  function agruparPorCategoria(productos, inventario) {
    const grupos = new Map();
    productos.forEach((p) => {
      const info = inventario.find((inv) => inv.codigo === p.codigo);
      const categoria = (info && info.categoria) || 'Sin categoría';
      if (!grupos.has(categoria)) grupos.set(categoria, []);
      grupos.get(categoria).push(p);
    });
    return grupos;
  }

  function render(r, inventario) {
    const grupos = agruparPorCategoria(r.productos, inventario);

    contenedor.innerHTML = [...grupos.entries()].map(([categoria, productos], i, arr) => {
      const totalUnidades = productos.reduce((s, p) => s + p.cantidad, 0);
      const ultima = i === arr.length - 1;
      return `
        <div class="doc-page" style="${ultima ? '' : 'page-break-after:always;margin-bottom:2rem;'}">
          <div class="doc-head">
            <div>
              <h2>Entre Platos y Copas</h2>
              <span class="tagline">Hoja de preparación</span>
            </div>
            <div class="doc-meta">
              <span class="label">Reserva</span>
              <strong>${r.id}</strong>
              ${badgeHtml(r.estado)}
            </div>
          </div>

          <div class="doc-grid">
            <div>
              <div class="label">Cliente</div>
              <strong style="display:block;font-size:1rem;">${r.clienteNombre}</strong>
              <span>${r.tipoEvento}</span>
            </div>
            <div style="text-align:right;">
              <div class="label">Fecha de despacho</div>
              <strong style="display:block;">${formatearFechaLarga(r.fechaDespacho)}</strong>
              <div class="label" style="margin-top:0.5rem;">Responsable</div>
              <strong style="display:block;">${r.responsable}</strong>
            </div>
          </div>

          <div class="doc-event-box">
            <div>
              <div class="label">Categoría a preparar</div>
              <strong style="display:block;font-size:1.3rem;">${categoria}</strong>
            </div>
            <div style="text-align:right;">
              <strong style="display:block;">${productos.length} producto${productos.length === 1 ? '' : 's'}</strong>
              <span>${totalUnidades} unidades en total</span>
            </div>
          </div>

          <table class="doc-table">
            <thead><tr><th style="width:2.4rem;"></th><th>Producto</th><th class="num">Cantidad</th></tr></thead>
            <tbody>
              ${productos.map((p) => `
                <tr>
                  <td><span style="display:inline-block;width:16px;height:16px;border:1.5px solid var(--color-gray-dark);border-radius:3px;"></span></td>
                  <td>${p.nombre}</td>
                  <td class="num cell-strong">${p.cantidad}</td>
                </tr>
              `).join('')}
            </tbody>
          </table>

          <div class="doc-notes">
            <p class="label">Observaciones</p>
            <p style="min-height:2.4rem;border-bottom:1px dashed var(--color-gray-light);">&nbsp;</p>
          </div>

          <div class="doc-footer">
            <span>Entre Platos y Copas · Arriendo de implementos para eventos</span>
            <span>Categoría ${i + 1} de ${arr.length}</span>
          </div>
        </div>
      `;
    }).join('');
  }
})();
