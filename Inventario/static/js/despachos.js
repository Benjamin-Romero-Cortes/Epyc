/**
 * despachos.js
 * Pedidos preparados listos para salir a entrega. Confirmar el despacho
 * simula el traspaso de stock de "reservado" a "arrendado" en el
 * inventario y cambia la reserva a estado Despachada, previa
 * confirmación (acción crítica).
 */
(function () {
  const tbody = document.getElementById('desp-tbody');
  if (!tbody) return;

  let reservas = [], inventario = [];

  Promise.all([obtenerDatos('reservas'), obtenerDatos('inventario')]).then(([r, inv]) => {
    reservas = r; inventario = inv;
    renderizar();
  }).catch((err) => {
    tbody.innerHTML = '<tr><td colspan="8" class="empty-state">No pudimos cargar los despachos.</td></tr>';
    console.error(err);
  });

  const ESTADOS_VISIBLES = ['Preparada', 'Despachada', 'En arriendo'];

  function lista() {
    return reservas.filter((r) => ESTADOS_VISIBLES.includes(r.estado)).sort((a, b) => a.fechaDespacho.localeCompare(b.fechaDespacho));
  }

  function renderizar() {
    const items = lista();
    document.getElementById('desp-result-count').textContent = `${items.length} pedido${items.length === 1 ? '' : 's'} en esta vista`;
    if (!items.length) {
      tbody.innerHTML = '<tr><td colspan="8"><p class="empty-state">No hay despachos programados.</p></td></tr>';
      return;
    }
    tbody.innerHTML = items.map((r) => `
      <tr>
        <td class="cell-strong"><a href="reserva.html?id=${r.id}">${r.id}</a></td>
        <td>${r.clienteNombre}</td>
        <td>${r.direccion}</td>
        <td>${r.comuna}</td>
        <td>${formatearFecha(r.fechaDespacho)}</td>
        <td>${r.responsable}</td>
        <td>${badgeHtml(r.estado === 'Preparada' ? 'Pendiente' : (r.estado === 'Despachada' ? 'En ruta' : 'Entregado'))}</td>
        <td>
          ${r.estado === 'Preparada'
            ? `<button class="btn btn-primary btn-sm" data-confirmar="${r.id}">Confirmar despacho</button>`
            : `<a class="btn btn-ghost btn-sm" href="despacho-documento.html?id=${r.id}" target="_blank">Ver hoja</a>`}
        </td>
      </tr>
    `).join('');

    tbody.querySelectorAll('[data-confirmar]').forEach((btn) => {
      btn.addEventListener('click', () => confirmarDespacho(btn.dataset.confirmar));
    });
  }

  async function confirmarDespacho(id) {
    const reserva = reservas.find((r) => r.id === id);
    const ok = await confirmarAccion({
      titulo: 'Confirmar despacho',
      mensaje: `Vas a despachar la reserva ${reserva.id} de "${reserva.clienteNombre}". El stock de sus productos pasará de reservado a arrendado.`,
      textoConfirmar: 'Confirmar despacho',
    });
    if (!ok) return;

    reserva.productos.forEach((linea) => {
      linea.despachado = linea.cantidad;
      const producto = inventario.find((p) => p.codigo === linea.codigo);
      if (producto) {
        const mover = Math.min(linea.cantidad, producto.reservado);
        producto.reservado -= mover;
        producto.arrendado += mover;
      }
    });
    reserva.estado = 'Despachada';
    mostrarToast(`Despacho de ${reserva.id} confirmado. Stock actualizado: reservado → arrendado.`);
    renderizar();
  }
})();
