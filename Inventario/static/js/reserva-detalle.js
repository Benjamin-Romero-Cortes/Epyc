/**
 * reserva-detalle.js
 * Ficha completa de una reserva: datos generales, línea de tiempo del
 * proceso, listado de productos (cantidad/preparado/despachado/
 * devuelto) y una herramienta para agregar productos que valida
 * disponibilidad real para la fecha del evento cruzando todas las
 * demás reservas activas de ese mismo día.
 */
(function () {
  const contenedor = document.getElementById('reserva-detalle');
  if (!contenedor) return;

  const id = new URLSearchParams(window.location.search).get('id');
  const FASES = ['Cotización', 'Confirmada', 'Preparación', 'Despacho', 'Devolución', 'Finalizada'];
  const FASE_INDEX = {
    Pendiente: 1, Confirmada: 1,
    'En preparación': 2, Preparada: 3,
    Despachada: 3, 'En arriendo': 4,
    'En devolución': 4, Finalizada: 5,
  };

  let reserva, inventario, reservas, clientes;

  Promise.all([obtenerDatos('reservas'), obtenerDatos('inventario'), obtenerDatos('clientes')])
    .then(([rs, inv, clis]) => {
      reservas = rs; inventario = inv; clientes = clis;
      reserva = reservas.find((r) => r.id === id);
      if (!reserva) {
        contenedor.innerHTML = `<p class="empty-state">No encontramos esta reserva. <a href="reservas.html">Volver a reservas</a>.</p>`;
        return;
      }
      document.title = `${reserva.id} · Panel Entre Platos y Copas`;
      render();
    }).catch((err) => {
      contenedor.innerHTML = '<p class="empty-state">No pudimos cargar la reserva.</p>';
      console.error(err);
    });

  function render() {
    const cliente = clientes.find((c) => c.id === reserva.clienteId);

    contenedor.innerHTML = `
      <div class="page-head">
        <div>
          <span class="eyebrow">${reserva.tipoEvento} · ${formatearFecha(reserva.fechaEvento)}</span>
          <h1>${reserva.id} · ${reserva.clienteNombre}</h1>
          <p>${reserva.direccion}, ${reserva.comuna} · ${reserva.invitados || '—'} invitados · Responsable: ${reserva.responsable}</p>
        </div>
        <div class="page-head-actions">${badgeHtml(reserva.estado)}</div>
      </div>

      <div class="card mb-md">
        ${reserva.estado === 'Cancelada'
          ? '<p class="empty-state">Esta reserva fue cancelada.</p>'
          : `<div class="process-timeline">${renderTimeline()}</div>`}
      </div>

      <div class="section-row" style="grid-template-columns:1fr 1fr;">
        <div class="card">
          <h3 style="font-size:1rem;margin-bottom:0.8rem;">Datos de la reserva</h3>
          <table class="data-table" style="min-width:0;">
            <tbody>
              <tr><td class="cell-muted">Cliente</td><td><a href="cliente.html?id=${reserva.clienteId}">${reserva.clienteNombre}</a></td></tr>
              <tr><td class="cell-muted">Fecha del evento</td><td>${formatearFechaLarga(reserva.fechaEvento)}</td></tr>
              <tr><td class="cell-muted">Fecha de despacho</td><td>${formatearFecha(reserva.fechaDespacho)}</td></tr>
              <tr><td class="cell-muted">Fecha de retiro</td><td>${formatearFecha(reserva.fechaRetiro)}</td></tr>
              <tr><td class="cell-muted">Dirección</td><td>${reserva.direccion}, ${reserva.comuna}</td></tr>
              <tr><td class="cell-muted">Monto</td><td class="cell-strong">${formatearMoneda(reserva.monto)}</td></tr>
              ${reserva.cotizacionId ? `<tr><td class="cell-muted">Cotización de origen</td><td><a href="cotizacion.html?id=${reserva.cotizacionId}">${reserva.cotizacionId}</a></td></tr>` : ''}
            </tbody>
          </table>
        </div>
        <div class="card">
          <h3 style="font-size:1rem;margin-bottom:0.4rem;">Agregar producto y validar disponibilidad</h3>
          <p class="form-hint" style="margin-bottom:0.6rem;">Se valida el stock comprometido por otras reservas para el ${formatearFecha(reserva.fechaEvento)}.</p>
          <div style="display:flex;gap:0.5rem;flex-wrap:wrap;">
            <select class="select-filter" id="disp-producto" style="flex:1;min-width:200px;">
              ${inventario.map((p) => `<option value="${p.codigo}">${p.nombre}</option>`).join('')}
            </select>
            <input type="number" class="select-filter" id="disp-cantidad" min="1" value="10" style="width:100px;">
            <button class="btn btn-outline btn-sm" id="btn-verificar">Verificar y agregar</button>
          </div>
          <div id="disp-resultado" style="margin-top:0.8rem;"></div>
        </div>
      </div>

      <div class="card mt-md">
        <h3 style="font-size:1rem;margin-bottom:0.8rem;">Productos incluidos</h3>
        <div class="table-wrap" style="border:none;">
          <table class="data-table" id="tabla-productos-reserva" style="min-width:0;"></table>
        </div>
      </div>
    `;

    renderTablaProductos();
    document.getElementById('btn-verificar').addEventListener('click', verificarYAgregar);
  }

  function renderTimeline() {
    const actual = reserva.estado === 'Finalizada' ? FASES.length - 1 : (FASE_INDEX[reserva.estado] ?? 0);
    return FASES.map((fase, i) => {
      const done = i < actual || reserva.estado === 'Finalizada';
      const current = i === actual && reserva.estado !== 'Finalizada';
      return `
        ${i > 0 ? `<div class="process-line ${i <= actual ? 'is-done' : ''}"></div>` : ''}
        <div class="process-step ${done ? 'is-done' : ''} ${current ? 'is-current' : ''}">
          <span class="dot">${done ? '✓' : i + 1}</span>
          <span>${fase}</span>
        </div>
      `;
    }).join('');
  }

  function renderTablaProductos() {
    const tabla = document.getElementById('tabla-productos-reserva');
    if (!reserva.productos.length) {
      tabla.innerHTML = '<tr><td class="empty-state">Sin productos agregados todavía.</td></tr>';
      return;
    }
    tabla.innerHTML = `
      <thead><tr><th>Producto</th><th class="cell-num">Cantidad</th><th class="cell-num">Preparado</th><th class="cell-num">Despachado</th><th class="cell-num">Devuelto</th></tr></thead>
      <tbody>
        ${reserva.productos.map((p) => `
          <tr>
            <td>${p.nombre}</td>
            <td class="cell-num">${p.cantidad}</td>
            <td class="cell-num">${p.preparado}</td>
            <td class="cell-num">${p.despachado}</td>
            <td class="cell-num">${p.devuelto}</td>
          </tr>
        `).join('')}
      </tbody>
    `;
  }

  function verificarYAgregar() {
    const codigo = document.getElementById('disp-producto').value;
    const cantidad = Number(document.getElementById('disp-cantidad').value);
    const producto = inventario.find((p) => p.codigo === codigo);
    const resultado = document.getElementById('disp-resultado');
    if (!producto || !cantidad || cantidad <= 0) return;

    const otrasReservas = reservas.filter((r) => r.id !== reserva.id && r.fechaEvento === reserva.fechaEvento && r.estado !== 'Cancelada');
    const comprometido = otrasReservas.reduce((s, r) => {
      const linea = r.productos.find((p) => p.codigo === codigo);
      return s + (linea ? linea.cantidad : 0);
    }, 0);
    const yaEnEstaReserva = (reserva.productos.find((p) => p.codigo === codigo) || {}).cantidad || 0;
    const disponibleParaFecha = producto.stockTotal - comprometido - yaEnEstaReserva;

    if (cantidad > disponibleParaFecha) {
      resultado.innerHTML = `
        <div class="alert-row" style="border-bottom:none;">
          <span class="icon" style="background-color:var(--status-danger-bg);color:var(--status-danger);">⚠</span>
          <div>
            <strong>Stock insuficiente para la fecha seleccionada.</strong>
            <span>Disponible: ${Math.max(0, disponibleParaFecha)} unidades de "${producto.nombre}" (stock total ${producto.stockTotal}, comprometido ${comprometido + yaEnEstaReserva} en otras reservas de ese día).</span>
            ${otrasReservas.filter((r) => r.productos.some((p) => p.codigo === codigo)).length ? `
              <div style="margin-top:0.5rem;font-size:0.8rem;">Reservas que usan este producto ese día:
                ${otrasReservas.filter((r) => r.productos.some((p) => p.codigo === codigo)).map((r) => `<a href="reserva.html?id=${r.id}">${r.id}</a>`).join(', ')}
              </div>` : ''}
          </div>
        </div>`;
      return;
    }

    const existente = reserva.productos.find((p) => p.codigo === codigo);
    if (existente) existente.cantidad += cantidad;
    else reserva.productos.push({ codigo, nombre: producto.nombre, cantidad, preparado: 0, despachado: 0, devuelto: 0 });

    resultado.innerHTML = `
      <div class="alert-row" style="border-bottom:none;">
        <span class="icon" style="background-color:var(--status-success-bg);color:var(--status-success);">✓</span>
        <div><strong>Disponibilidad confirmada.</strong><span>Se agregaron ${cantidad} unidades de "${producto.nombre}" a la reserva. Disponible restante para la fecha: ${disponibleParaFecha - cantidad}.</span></div>
      </div>`;
    renderTablaProductos();
    mostrarToast(`${cantidad} × ${producto.nombre} agregado a ${reserva.id}.`);
  }
})();
