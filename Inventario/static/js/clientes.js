/**
 * clientes.js
 * Listado de clientes. La cantidad de reservas y la fecha de la última
 * reserva se calculan en vivo a partir de reservas.json (no se guardan
 * como campos fijos) para que siempre reflejen los mismos datos que ven
 * los módulos de Reservas y Cotizaciones.
 */
(function () {
  const tbody = document.getElementById('cli-tbody');
  if (!tbody) return;

  let clientes = [];
  let reservas = [];
  let termino = '';
  let tipo = '';
  let estado = '';

  Promise.all([obtenerDatos('clientes'), obtenerDatos('reservas')]).then(([c, r]) => {
    clientes = c;
    reservas = r;
    renderizar();
  }).catch((err) => {
    tbody.innerHTML = '<tr><td colspan="8" class="empty-state">No pudimos cargar los clientes.</td></tr>';
    console.error(err);
  });

  function statsCliente(clienteId) {
    const propias = reservas.filter((r) => r.clienteId === clienteId);
    const ultima = propias.map((r) => r.fechaEvento).sort().pop();
    return { count: propias.length, ultima };
  }

  function filtrados() {
    return clientes.filter((c) => {
      const t = !termino || c.nombre.toLowerCase().includes(termino) || c.rut.toLowerCase().includes(termino);
      const ti = !tipo || c.tipo === tipo;
      const e = !estado || c.estado === estado;
      return t && ti && e;
    });
  }

  function renderizar() {
    const lista = filtrados();
    document.getElementById('cli-result-count').textContent = `${lista.length} cliente${lista.length === 1 ? '' : 's'} encontrado${lista.length === 1 ? '' : 's'}`;

    if (!lista.length) {
      tbody.innerHTML = '<tr><td colspan="8"><p class="empty-state">No encontramos clientes con ese criterio.</p></td></tr>';
      return;
    }

    tbody.innerHTML = lista.map((c) => {
      const stats = statsCliente(c.id);
      return `
        <tr>
          <td>
            <div style="display:flex;align-items:center;gap:0.7rem;">
              <div class="avatar-sm">${iniciales(c.nombre)}</div>
              <div>
                <span class="cell-strong">${c.nombre}</span><br>
                <span class="cell-muted">${c.tipo}</span>
              </div>
            </div>
          </td>
          <td>${c.rut}</td>
          <td>${c.telefono}</td>
          <td>${c.comuna}</td>
          <td class="cell-num">${stats.count}</td>
          <td>${stats.ultima ? formatearFecha(stats.ultima) : '—'}</td>
          <td>${badgeHtml(c.estado)}</td>
          <td><div class="table-actions"><a href="cliente.html?id=${c.id}" class="icon-btn" title="Ver ficha">👁</a></div></td>
        </tr>
      `;
    }).join('');
  }

  document.getElementById('cli-search').addEventListener('input', (e) => { termino = e.target.value.trim().toLowerCase(); renderizar(); });
  document.getElementById('cli-tipo').addEventListener('change', (e) => { tipo = e.target.value; renderizar(); });
  document.getElementById('cli-estado').addEventListener('change', (e) => { estado = e.target.value; renderizar(); });

  // ---------- Nuevo cliente (simulado, en memoria) ----------
  const modal = document.getElementById('modal-nuevo-cliente');
  document.getElementById('btn-nuevo-cliente').addEventListener('click', () => abrirModal(modal));

  document.getElementById('form-nuevo-cliente').addEventListener('submit', (e) => {
    e.preventDefault();
    const nombre = document.getElementById('nc-nombre').value.trim();
    clientes.unshift({
      id: 'CLI-' + String(Date.now()).slice(-4),
      rut: document.getElementById('nc-rut').value.trim(),
      nombre,
      tipo: document.getElementById('nc-tipo').value,
      telefono: document.getElementById('nc-telefono').value.trim(),
      correo: document.getElementById('nc-correo').value.trim(),
      direccion: document.getElementById('nc-direccion').value.trim(),
      comuna: document.getElementById('nc-comuna').value.trim(),
      clienteDesde: '2026-08-19',
      observaciones: document.getElementById('nc-observaciones').value.trim(),
      estado: 'Prospecto',
    });
    mostrarToast(`Cliente "${nombre}" creado.`);
    e.target.reset();
    cerrarModal(modal);
    renderizar();
  });
})();
