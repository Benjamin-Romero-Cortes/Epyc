/**
 * cliente.js
 * Ficha de cliente con pestañas (información general, cotizaciones,
 * reservas, historial). Todo se calcula cruzando clientes.json con
 * cotizaciones.json y reservas.json por clienteId, para que el total de
 * reservas y montos coincida siempre con lo que muestran esos módulos.
 */
(function () {
  const contenedor = document.getElementById('cliente-detalle');
  if (!contenedor) return;

  const id = new URLSearchParams(window.location.search).get('id');
  let cliente = null;
  let misCotizaciones = [];
  let misReservas = [];

  Promise.all([obtenerDatos('clientes'), obtenerDatos('cotizaciones'), obtenerDatos('reservas')])
    .then(([clientes, cotizaciones, reservas]) => {
      cliente = clientes.find((c) => c.id === id);
      if (!cliente) {
        contenedor.innerHTML = '<p class="empty-state">No encontramos este cliente. <a href="clientes.html">Volver a clientes</a>.</p>';
        return;
      }
      misCotizaciones = cotizaciones.filter((c) => c.clienteId === id);
      misReservas = reservas.filter((r) => r.clienteId === id);
      document.title = `${cliente.nombre} · Panel Entre Platos y Copas`;
      render(misCotizaciones, misReservas);
    }).catch((err) => {
      contenedor.innerHTML = '<p class="empty-state">No pudimos cargar el cliente.</p>';
      console.error(err);
    });

  function render(cotizaciones, reservas) {
    const montoTotal = reservas.reduce((s, r) => s + r.monto, 0);
    const ultima = [...reservas].sort((a, b) => b.fechaEvento.localeCompare(a.fechaEvento))[0];

    contenedor.innerHTML = `
      <div class="page-head">
        <div style="display:flex;align-items:center;gap:1rem;">
          <div class="avatar-sm" style="width:56px;height:56px;font-size:1.2rem;">${iniciales(cliente.nombre)}</div>
          <div>
            <span class="eyebrow">${cliente.tipo} · ${cliente.rut}</span>
            <h1>${cliente.nombre}</h1>
          </div>
        </div>
        <div class="page-head-actions" style="align-items:center;gap:0.7rem;">
          <button class="btn btn-outline btn-sm" id="btn-editar-cliente">✎ Editar</button>
          ${badgeHtml(cliente.estado)}
        </div>
      </div>

      <div class="kpi-grid" style="grid-template-columns:repeat(auto-fit,minmax(180px,1fr));">
        <div class="kpi-card"><span class="kpi-label">Total de reservas</span><div class="kpi-value" style="font-size:1.6rem;">${reservas.length}</div></div>
        <div class="kpi-card"><span class="kpi-label">Monto total histórico</span><div class="kpi-value" style="font-size:1.6rem;">${formatearMoneda(montoTotal)}</div></div>
        <div class="kpi-card"><span class="kpi-label">Última reserva</span><div class="kpi-value" style="font-size:1.6rem;">${ultima ? formatearFecha(ultima.fechaEvento) : '—'}</div></div>
        <div class="kpi-card"><span class="kpi-label">Cliente desde</span><div class="kpi-value" style="font-size:1.6rem;">${formatearFecha(cliente.clienteDesde)}</div></div>
      </div>

      <div class="card">
        <div class="tabs">
          <button class="tab-btn is-active" data-tab="info">Información general</button>
          <button class="tab-btn" data-tab="cot">Cotizaciones (${cotizaciones.length})</button>
          <button class="tab-btn" data-tab="res">Reservas (${reservas.length})</button>
          <button class="tab-btn" data-tab="hist">Historial</button>
        </div>

        <div class="tab-panel is-active" data-panel="info">
          <table class="data-table" style="min-width:0;">
            <tbody>
              <tr><td class="cell-muted" style="width:180px;">Teléfono</td><td>${cliente.telefono}</td></tr>
              <tr><td class="cell-muted">Correo</td><td>${cliente.correo}</td></tr>
              <tr><td class="cell-muted">Dirección</td><td>${cliente.direccion}</td></tr>
              <tr><td class="cell-muted">Comuna</td><td>${cliente.comuna}</td></tr>
              <tr><td class="cell-muted">Tipo de cliente</td><td>${cliente.tipo}</td></tr>
              <tr><td class="cell-muted">Observaciones</td><td>${cliente.observaciones || '—'}</td></tr>
            </tbody>
          </table>
        </div>

        <div class="tab-panel" data-panel="cot">
          ${cotizaciones.length ? `
            <table class="data-table" style="min-width:0;">
              <thead><tr><th>N°</th><th>Evento</th><th>Fecha evento</th><th class="cell-num">Monto</th><th>Estado</th></tr></thead>
              <tbody>
                ${cotizaciones.map((c) => `
                  <tr>
                    <td><a href="cotizacion.html?id=${c.id}">${c.id}</a></td>
                    <td>${c.tipoEvento}</td>
                    <td>${formatearFecha(c.fechaEvento)}</td>
                    <td class="cell-num">${formatearMoneda(c.monto)}</td>
                    <td>${badgeHtml(c.estado)}</td>
                  </tr>
                `).join('')}
              </tbody>
            </table>
          ` : '<p class="empty-state">Sin cotizaciones registradas.</p>'}
        </div>

        <div class="tab-panel" data-panel="res">
          ${reservas.length ? `
            <table class="data-table" style="min-width:0;">
              <thead><tr><th>N°</th><th>Evento</th><th>Fecha evento</th><th class="cell-num">Monto</th><th>Estado</th></tr></thead>
              <tbody>
                ${reservas.map((r) => `
                  <tr>
                    <td><a href="reserva.html?id=${r.id}">${r.id}</a></td>
                    <td>${r.tipoEvento}</td>
                    <td>${formatearFecha(r.fechaEvento)}</td>
                    <td class="cell-num">${formatearMoneda(r.monto)}</td>
                    <td>${badgeHtml(r.estado)}</td>
                  </tr>
                `).join('')}
              </tbody>
            </table>
          ` : '<p class="empty-state">Sin reservas registradas.</p>'}
        </div>

        <div class="tab-panel" data-panel="hist">
          ${reservas.length ? `
            <table class="data-table" style="min-width:0;">
              <thead><tr><th>Fecha</th><th>Evento</th><th>Estado</th><th class="cell-num">Total</th></tr></thead>
              <tbody>
                ${[...reservas].sort((a, b) => b.fechaEvento.localeCompare(a.fechaEvento)).map((r) => `
                  <tr>
                    <td>${formatearFecha(r.fechaEvento)}</td>
                    <td>${r.tipoEvento}</td>
                    <td>${badgeHtml(r.estado)}</td>
                    <td class="cell-num">${formatearMoneda(r.monto)}</td>
                  </tr>
                `).join('')}
              </tbody>
            </table>
          ` : '<p class="empty-state">Sin historial todavía.</p>'}
        </div>
      </div>
    `;

    contenedor.querySelectorAll('.tab-btn').forEach((btn) => {
      btn.addEventListener('click', () => {
        contenedor.querySelectorAll('.tab-btn').forEach((b) => b.classList.remove('is-active'));
        contenedor.querySelectorAll('.tab-panel').forEach((p) => p.classList.remove('is-active'));
        btn.classList.add('is-active');
        contenedor.querySelector(`[data-panel="${btn.dataset.tab}"]`).classList.add('is-active');
      });
    });

    document.getElementById('btn-editar-cliente').addEventListener('click', abrirEdicion);
  }

  // ---------- Editar cliente ----------
  const modal = document.getElementById('modal-editar-cliente');
  const form = document.getElementById('form-editar-cliente');

  function abrirEdicion() {
    document.getElementById('ec-nombre').value = cliente.nombre;
    document.getElementById('ec-rut').value = cliente.rut;
    document.getElementById('ec-tipo').value = cliente.tipo;
    document.getElementById('ec-telefono').value = cliente.telefono;
    document.getElementById('ec-correo').value = cliente.correo;
    document.getElementById('ec-direccion').value = cliente.direccion || '';
    document.getElementById('ec-comuna').value = cliente.comuna || '';
    document.getElementById('ec-observaciones').value = cliente.observaciones || '';
    abrirModal(modal);
  }

  form.addEventListener('submit', (e) => {
    e.preventDefault();
    Object.assign(cliente, {
      nombre: document.getElementById('ec-nombre').value.trim(),
      rut: document.getElementById('ec-rut').value.trim(),
      tipo: document.getElementById('ec-tipo').value,
      telefono: document.getElementById('ec-telefono').value.trim(),
      correo: document.getElementById('ec-correo').value.trim(),
      direccion: document.getElementById('ec-direccion').value.trim(),
      comuna: document.getElementById('ec-comuna').value.trim(),
      observaciones: document.getElementById('ec-observaciones').value.trim(),
    });
    document.title = `${cliente.nombre} · Panel Entre Platos y Copas`;
    mostrarToast(`Cliente "${cliente.nombre}" actualizado.`);
    cerrarModal(modal);
    render(misCotizaciones, misReservas);
  });
})();
