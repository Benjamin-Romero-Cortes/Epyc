/**
 * reservas.js
 * Listado de reservas con filtros por estado y accesos rápidos a
 * próximas entregas/retiros (relativos a la fecha de referencia del
 * panel, 2026-08-19).
 */
(function () {
  const tbody = document.getElementById('res-tbody');
  if (!tbody) return;

  const HOY = '2026-08-19';
  let reservas = [];
  let termino = '';
  let estado = '';
  let soloEntregas = false;
  let soloRetiros = false;

  obtenerDatos('reservas').then((data) => {
    reservas = data;
    renderizar();
  }).catch((err) => {
    tbody.innerHTML = '<tr><td colspan="9" class="empty-state">No pudimos cargar las reservas.</td></tr>';
    console.error(err);
  });

  function filtradas() {
    return reservas.filter((r) => {
      const t = !termino || r.id.toLowerCase().includes(termino) || r.clienteNombre.toLowerCase().includes(termino);
      const e = !estado || r.estado === estado;
      const entrega = !soloEntregas || r.fechaDespacho >= HOY;
      const retiro = !soloRetiros || r.fechaRetiro >= HOY;
      return t && e && entrega && retiro;
    }).sort((a, b) => a.fechaEvento.localeCompare(b.fechaEvento));
  }

  function renderizar() {
    const lista = filtradas();
    document.getElementById('res-result-count').textContent = `${lista.length} reserva${lista.length === 1 ? '' : 's'} encontrada${lista.length === 1 ? '' : 's'}`;
    if (!lista.length) {
      tbody.innerHTML = '<tr><td colspan="9"><p class="empty-state">No encontramos reservas con ese criterio.</p></td></tr>';
      return;
    }
    tbody.innerHTML = lista.map((r) => `
      <tr>
        <td class="cell-strong"><a href="reserva.html?id=${r.id}">${r.id}</a></td>
        <td>${r.clienteNombre}</td>
        <td>${r.tipoEvento}</td>
        <td>${formatearFecha(r.fechaEvento)}</td>
        <td>${formatearFecha(r.fechaDespacho)}</td>
        <td>${formatearFecha(r.fechaRetiro)}</td>
        <td class="cell-num">${formatearMoneda(r.monto)}</td>
        <td>${badgeHtml(r.estado)}</td>
        <td><div class="table-actions"><a href="reserva.html?id=${r.id}" class="icon-btn" title="Ver">👁</a></div></td>
      </tr>
    `).join('');
  }

  document.getElementById('res-search').addEventListener('input', (e) => { termino = e.target.value.trim().toLowerCase(); renderizar(); });
  document.getElementById('res-estado').addEventListener('change', (e) => { estado = e.target.value; renderizar(); });
  document.getElementById('res-chip-entregas').addEventListener('click', (e) => { soloEntregas = !soloEntregas; e.target.classList.toggle('is-active', soloEntregas); renderizar(); });
  document.getElementById('res-chip-retiros').addEventListener('click', (e) => { soloRetiros = !soloRetiros; e.target.classList.toggle('is-active', soloRetiros); renderizar(); });
})();
