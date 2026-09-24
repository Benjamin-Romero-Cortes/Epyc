/**
 * producto.js
 * Ficha de producto: información general, resumen visual de stock,
 * historial de movimientos y acciones de inventario (ingreso, ajuste).
 * Todas las acciones se simulan en memoria: actualizan los números en
 * pantalla y agregan una fila al historial, pero se pierden al recargar
 * (no hay backend todavía).
 */
(function () {
  const contenedor = document.getElementById('producto-detalle');
  if (!contenedor) return;

  const codigo = new URLSearchParams(window.location.search).get('codigo');
  let producto = null;
  let movimientos = [];

  Promise.all([obtenerDatos('inventario'), obtenerDatos('movimientos')]).then(([inventario, movs]) => {
    producto = inventario.find((p) => p.codigo === codigo);
    movimientos = movs.filter((m) => m.productoCodigo === codigo);
    if (!producto) {
      contenedor.innerHTML = '<p class="empty-state">No encontramos este producto. <a href="inventario.html">Volver a inventario</a>.</p>';
      return;
    }
    document.title = `${producto.nombre} · Panel Entre Platos y Copas`;
    render();
  }).catch((err) => {
    contenedor.innerHTML = '<p class="empty-state">No pudimos cargar el producto.</p>';
    console.error(err);
  });

  const STOCK_COLORS = {
    disponible: 'var(--status-success)', reservado: 'var(--status-warning)',
    arrendado: 'var(--status-info)', merma: 'var(--status-danger)',
  };

  function render() {
    const p = producto;
    contenedor.innerHTML = `
      <div class="page-head">
        <div>
          <span class="eyebrow">${p.categoria}</span>
          <h1>${p.nombre}</h1>
        </div>
        <div class="page-head-actions">${badgeHtml(p.estado)}</div>
      </div>

      <div class="section-row" style="grid-template-columns:0.9fr 1.4fr;">
        <div class="stack">
          <div class="card" style="padding:0;overflow:hidden;">
            <img src="${p.imagen}" alt="${p.nombre}" style="width:100%;aspect-ratio:1/1;object-fit:cover;">
          </div>
          <div class="card">
            <h3 style="font-size:1rem;margin-bottom:0.8rem;">Datos del producto</h3>
            <table class="data-table" style="min-width:0;">
              <tbody>
                <tr><td class="cell-muted">Descripción</td><td>${p.descripcion || '—'}</td></tr>
                <tr><td class="cell-muted">Dimensiones</td><td>${p.dimensiones || '—'}</td></tr>
                <tr><td class="cell-muted">Material</td><td>${p.material || '—'}</td></tr>
                <tr><td class="cell-muted">Capacidad</td><td>${p.capacidad || '—'}</td></tr>
                <tr><td class="cell-muted">Color</td><td>${p.color || '—'}</td></tr>
                <tr><td class="cell-muted">Precio de arriendo</td><td class="cell-strong">${formatearMoneda(p.precioArriendo)}</td></tr>
                <tr><td class="cell-muted">Valor de reposición</td><td>${formatearMoneda(p.valorReposicion)}</td></tr>
                <tr><td class="cell-muted">Stock mínimo recomendado</td><td>${p.stockMinimo} unidades</td></tr>
              </tbody>
            </table>
          </div>
        </div>

        <div class="stack">
          <div class="card">
            <h3 style="font-size:1rem;margin-bottom:0.2rem;">Resumen de stock</h3>
            <p class="cell-muted" style="margin-bottom:0.9rem;">Stock total: <strong style="color:var(--color-black);">${p.stockTotal.toLocaleString('es-CL')}</strong> unidades</p>
            <div style="display:flex;height:16px;border-radius:999px;overflow:hidden;margin-bottom:0.9rem;">
              ${['disponible', 'reservado', 'arrendado', 'merma'].map((k) => `
                <div style="width:${(p[k] / p.stockTotal) * 100}%;background-color:${STOCK_COLORS[k]};" title="${k}: ${p[k]}"></div>
              `).join('')}
            </div>
            <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(110px,1fr));gap:0.8rem;">
              ${[
                ['Disponible', p.disponible, 'disponible'],
                ['Reservado', p.reservado, 'reservado'],
                ['Arrendado', p.arrendado, 'arrendado'],
                ['Merma', p.merma, 'merma'],
              ].map(([label, val, key]) => `
                <div>
                  <div style="display:flex;align-items:center;gap:0.4rem;font-size:0.78rem;opacity:0.7;">
                    <span style="width:8px;height:8px;border-radius:50%;background-color:${STOCK_COLORS[key]};display:inline-block;"></span>${label}
                  </div>
                  <div style="font-family:var(--font-display);font-size:1.4rem;" id="stock-${key}">${val.toLocaleString('es-CL')}</div>
                </div>
              `).join('')}
            </div>
          </div>

          <div class="card">
            <h3 style="font-size:1rem;margin-bottom:0.8rem;">Acciones de inventario</h3>
            <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:0.6rem;">
              <button class="btn btn-outline btn-sm" data-accion="ingreso">+ Ingresar nuevo stock</button>
              <button class="btn btn-outline btn-sm" data-accion="ajuste">Ajuste de inventario</button>
            </div>
          </div>

          <div class="card">
            <h3 style="font-size:1rem;margin-bottom:0.8rem;">Historial de movimientos</h3>
            <div class="table-wrap" style="border:none;">
              <table class="data-table" id="tabla-movimientos" style="min-width:0;"></table>
            </div>
          </div>
        </div>
      </div>
    `;

    renderMovimientos();
    contenedor.querySelectorAll('[data-accion]').forEach((btn) => {
      btn.addEventListener('click', () => ejecutarAccion(btn.dataset.accion));
    });
  }

  function renderMovimientos() {
    const tabla = document.getElementById('tabla-movimientos');
    if (!movimientos.length) {
      tabla.innerHTML = '<tr><td class="empty-state">Sin movimientos registrados.</td></tr>';
      return;
    }
    const ordenados = [...movimientos].sort((a, b) => b.fecha.localeCompare(a.fecha));
    tabla.innerHTML = `
      <thead><tr><th>Fecha</th><th>Movimiento</th><th class="cell-num">Cantidad</th><th>Reserva</th><th>Responsable</th></tr></thead>
      <tbody>
        ${ordenados.map((m) => `
          <tr>
            <td>${formatearFecha(m.fecha)}</td>
            <td>${m.tipo}</td>
            <td class="cell-num">${m.cantidad > 0 ? '+' : ''}${m.cantidad}</td>
            <td>${m.reservaId ? `<a href="reserva.html?id=${m.reservaId}">${m.reservaId}</a>` : '—'}</td>
            <td>${m.responsable}</td>
          </tr>
        `).join('')}
      </tbody>
    `;
  }

  const ACCION_LABELS = { ingreso: 'Ingresar nuevo stock', ajuste: 'Ajuste de inventario' };

  function ejecutarAccion(accion) {
    const cantidadStr = window.prompt(`${ACCION_LABELS[accion]}\n\nCantidad de unidades:`, '5');
    const cantidad = Number(cantidadStr);
    if (!cantidad || cantidad <= 0) return;

    const p = producto;
    let tipoMov = ACCION_LABELS[accion];
    let cantidadMov = cantidad;

    if (accion === 'ingreso') {
      p.stockTotal += cantidad; p.disponible += cantidad; tipoMov = 'Ingreso';
    } else if (accion === 'ajuste') {
      p.disponible = Math.max(0, p.disponible - cantidad); tipoMov = 'Ajuste'; cantidadMov = -cantidad;
    }

    p.estado = p.disponible < p.stockMinimo ? 'Stock bajo' : (p.merma / p.stockTotal > 0.03 ? 'Revisar mermas' : 'Activo');
    movimientos.unshift({
      id: Date.now(), productoCodigo: p.codigo, fecha: '2026-08-19',
      tipo: tipoMov, cantidad: cantidadMov, reservaId: null, responsable: 'Helen Cortés',
    });

    mostrarToast(`${ACCION_LABELS[accion]} registrado para "${p.nombre}".`);
    render();
  }
})();
