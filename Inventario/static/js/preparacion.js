/**
 * preparacion.js
 * Lista de reservas pendientes de preparar, cada una como una orden de
 * preparación desplegable con checklist por producto, barra de
 * progreso y acciones. Marcar productos como preparados actualiza en
 * memoria reserva.productos[].preparado y el estado de la reserva
 * (Confirmada -> En preparación -> Preparada) cuando corresponde.
 */
(function () {
  const lista = document.getElementById('prep-lista');
  if (!lista) return;

  let reservas = [];

  obtenerDatos('reservas').then((data) => {
    reservas = data;
    renderizar();
  }).catch((err) => {
    lista.innerHTML = '<p class="empty-state">No pudimos cargar las órdenes de preparación.</p>';
    console.error(err);
  });

  function pendientes() {
    return reservas
      .filter((r) => ['Confirmada', 'En preparación', 'Preparada'].includes(r.estado))
      .sort((a, b) => a.fechaDespacho.localeCompare(b.fechaDespacho));
  }

  function progreso(r) {
    const total = r.productos.reduce((s, p) => s + p.cantidad, 0);
    const preparado = r.productos.reduce((s, p) => s + p.preparado, 0);
    return { total, preparado, pct: total ? Math.round((preparado / total) * 100) : 0 };
  }

  function renderizar() {
    const items = pendientes();
    if (!items.length) {
      lista.innerHTML = '<p class="empty-state">No hay pedidos pendientes de preparar. Buen trabajo.</p>';
      return;
    }

    lista.innerHTML = items.map((r, idx) => {
      const prog = progreso(r);
      return `
        <div class="card">
          <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:1rem;cursor:pointer;" data-toggle="${r.id}">
            <div>
              <span class="cell-muted" style="font-size:0.78rem;">Despacho: ${formatearFecha(r.fechaDespacho)} · ${r.comuna}</span>
              <h3 style="font-size:1.15rem;margin-top:0.2rem;">${r.id} · ${r.clienteNombre}</h3>
              <span class="cell-muted">${r.tipoEvento} · ${r.direccion} · ${r.productos.length} producto${r.productos.length === 1 ? '' : 's'}</span>
            </div>
            <div style="text-align:right;flex-shrink:0;">
              ${badgeHtml(r.estado)}
              <div style="margin-top:0.4rem;font-size:0.8rem;opacity:0.7;">${prog.preparado} de ${prog.total} unidades</div>
            </div>
          </div>
          <div class="progress-bar-track" style="margin-top:0.8rem;">
            <div class="progress-bar-fill" style="width:${prog.pct}%;"></div>
          </div>

          <div id="panel-${r.id}" ${idx === 0 ? '' : 'hidden'} style="margin-top:1rem;">
            <div class="check-list">
              ${r.productos.map((p, i) => `
                <label class="check-row ${p.preparado >= p.cantidad ? 'is-checked' : ''}">
                  <input type="checkbox" data-reserva="${r.id}" data-idx="${i}" ${p.preparado >= p.cantidad ? 'checked' : ''}>
                  <span class="name">${p.cantidad} × ${p.nombre}</span>
                  <span class="qty">${p.preparado}/${p.cantidad}</span>
                </label>
              `).join('')}
            </div>
            <div class="modal-actions" style="border-top:none;padding-top:0.8rem;">
              <a class="btn btn-ghost btn-sm" href="preparacion-documento.html?id=${r.id}" target="_blank">🖨 Generar hoja de preparación</a>
              <a class="btn btn-ghost btn-sm" href="despacho-documento.html?id=${r.id}" target="_blank">🖨 Generar hoja de despacho</a>
              <span class="spacer"></span>
              <button class="btn btn-primary btn-sm" data-completo="${r.id}" ${prog.preparado >= prog.total ? '' : 'disabled'}>Marcar pedido completo</button>
            </div>
          </div>
        </div>
      `;
    }).join('');

    lista.querySelectorAll('[data-toggle]').forEach((el) => {
      el.addEventListener('click', () => {
        const panel = document.getElementById(`panel-${el.dataset.toggle}`);
        panel.hidden = !panel.hidden;
      });
    });

    lista.querySelectorAll('input[type="checkbox"][data-reserva]').forEach((cb) => {
      cb.addEventListener('click', (e) => e.stopPropagation());
      cb.addEventListener('change', () => {
        const reserva = reservas.find((r) => r.id === cb.dataset.reserva);
        const producto = reserva.productos[Number(cb.dataset.idx)];
        producto.preparado = cb.checked ? producto.cantidad : 0;
        if (reserva.estado === 'Confirmada') reserva.estado = 'En preparación';
        const prog = progreso(reserva);
        if (prog.preparado >= prog.total) reserva.estado = 'Preparada';
        renderizar();
      });
    });

    lista.querySelectorAll('[data-completo]').forEach((btn) => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const reserva = reservas.find((r) => r.id === btn.dataset.completo);
        reserva.productos.forEach((p) => { p.preparado = p.cantidad; });
        reserva.estado = 'Preparada';
        mostrarToast(`${reserva.id} marcada como preparada.`);
        renderizar();
      });
    });
  }
})();
