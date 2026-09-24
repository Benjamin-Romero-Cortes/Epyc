/**
 * devoluciones.js
 * Lista de reservas cuyos productos ya deberían estar volviendo
 * (despachadas o en arriendo, con fecha de retiro alcanzada) o que ya
 * están formalmente en estado "En devolución".
 */
(function () {
  const tbody = document.getElementById('dev-tbody');
  if (!tbody) return;

  const HOY = '2026-08-19';

  obtenerDatos('reservas').then((reservas) => {
    const items = reservas
      .filter((r) => ['Despachada', 'En arriendo', 'En devolución'].includes(r.estado) && r.fechaRetiro <= HOY)
      .sort((a, b) => a.fechaRetiro.localeCompare(b.fechaRetiro));

    document.getElementById('dev-result-count').textContent = `${items.length} reserva${items.length === 1 ? '' : 's'} pendiente${items.length === 1 ? '' : 's'} de devolución`;

    if (!items.length) {
      tbody.innerHTML = '<tr><td colspan="6"><p class="empty-state">No hay devoluciones pendientes por ahora.</p></td></tr>';
      return;
    }

    tbody.innerHTML = items.map((r) => {
      const atrasada = r.estado !== 'Finalizada' && r.fechaRetiro < HOY;
      return `
        <tr>
          <td class="cell-strong"><a href="reserva.html?id=${r.id}">${r.id}</a></td>
          <td>${r.clienteNombre}</td>
          <td>${formatearFecha(r.fechaRetiro)} ${atrasada ? '<span class="badge badge--danger">Atrasada</span>' : ''}</td>
          <td class="cell-num">${r.productos.length}</td>
          <td>${badgeHtml(r.estado)}</td>
          <td><a href="devolucion.html?id=${r.id}" class="btn btn-primary btn-sm">Registrar devolución</a></td>
        </tr>
      `;
    }).join('');
  }).catch((err) => {
    tbody.innerHTML = '<tr><td colspan="6" class="empty-state">No pudimos cargar las devoluciones.</td></tr>';
    console.error(err);
  });
})();
