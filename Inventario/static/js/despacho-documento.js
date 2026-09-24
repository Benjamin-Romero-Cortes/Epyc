/**
 * despacho-documento.js
 * Hoja de despacho / detalle de reserva imprimible, con espacio para
 * firma y observaciones de entrega en terreno.
 */
(function () {
  const contenedor = document.getElementById('despacho-doc');
  if (!contenedor) return;

  const id = new URLSearchParams(window.location.search).get('id');

  Promise.all([obtenerDatos('reservas'), obtenerDatos('clientes')]).then(([reservas, clientes]) => {
    const reserva = reservas.find((r) => r.id === id);
    if (!reserva) {
      contenedor.innerHTML = `<p class="empty-state">No encontramos esta reserva.</p>`;
      return;
    }
    const cliente = clientes.find((c) => c.id === reserva.clienteId);
    document.title = `Hoja de despacho ${reserva.id} · Panel Entre Platos y Copas`;
    render(reserva, cliente);
  }).catch((err) => {
    contenedor.innerHTML = '<p class="empty-state">No pudimos cargar la hoja de despacho.</p>';
    console.error(err);
  });

  function render(r, cliente) {
    contenedor.innerHTML = `
      <div class="doc-page">
        <div class="doc-head">
          <div>
            <h2>Entre Platos y Copas</h2>
            <span class="tagline">Hoja de despacho / detalle de reserva</span>
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
            ${cliente ? `${cliente.telefono}` : ''}
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
            <div class="label">Evento</div>
            <strong style="display:block;font-size:1.02rem;">${r.tipoEvento}</strong>
            <span>Retiro programado: ${formatearFechaLarga(r.fechaRetiro)}</span>
          </div>
          <div style="text-align:right;">
            <strong style="display:block;">${r.direccion}</strong>
            <span>${r.comuna}</span>
          </div>
        </div>

        <table class="doc-table">
          <thead><tr><th>Producto</th><th class="num">Cantidad</th></tr></thead>
          <tbody>
            ${r.productos.map((p) => `<tr><td>${p.nombre}</td><td class="num cell-strong">${p.cantidad}</td></tr>`).join('')}
          </tbody>
        </table>

        <div class="doc-notes">
          <p class="label">Observaciones</p>
          <p style="min-height:2.4rem;border-bottom:1px dashed var(--color-gray-light);">&nbsp;</p>
        </div>

        <div class="doc-signoff">
          <div>
            <div class="sign-line">Nombre de quien recibe</div>
          </div>
          <div>
            <div class="sign-line">Firma / confirmación de entrega</div>
          </div>
        </div>

        <div class="doc-footer">
          <span>Entre Platos y Copas · Arriendo de implementos para eventos</span>
          <span>Documento generado el 19 de agosto de 2026</span>
        </div>
      </div>
    `;
  }
})();
