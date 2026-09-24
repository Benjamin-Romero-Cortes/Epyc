/**
 * devolucion.js
 * Formulario de registro de devolución por producto: recibidas
 * correctamente y perdidas (quebradas, dañadas o que requieren
 * mantención se registran directamente como perdidas). Verifica en
 * vivo que la suma calce con lo despachado, calcula el costo de
 * reposición de las perdidas y, al finalizar, aplica los movimientos
 * simulados al inventario y cierra la reserva.
 */
(function () {
  const contenedor = document.getElementById('devolucion-form');
  if (!contenedor) return;

  const id = new URLSearchParams(window.location.search).get('id');
  const CAMPOS = ['recibidas', 'perdidas'];
  const CAMPO_LABEL = { recibidas: 'Recibidas OK', perdidas: 'Perdidas' };

  let reserva, inventario;

  Promise.all([obtenerDatos('reservas'), obtenerDatos('inventario')]).then(([reservas, inv]) => {
    reserva = reservas.find((r) => r.id === id);
    inventario = inv;
    if (!reserva) {
      contenedor.innerHTML = `<p class="empty-state">No encontramos esta reserva.</p>`;
      return;
    }
    reserva.productos.forEach((p) => {
      p._devolucion = p._devolucion || { recibidas: p.devuelto || p.despachado, perdidas: 0 };
    });
    document.title = `Devolución ${reserva.id} · Panel Entre Platos y Copas`;
    render();
  }).catch((err) => {
    contenedor.innerHTML = '<p class="empty-state">No pudimos cargar la reserva.</p>';
    console.error(err);
  });

  function render() {
    contenedor.innerHTML = `
      <div class="page-head">
        <div>
          <span class="eyebrow">${reserva.clienteNombre} · Retiro ${formatearFecha(reserva.fechaRetiro)}</span>
          <h1>Devolución de ${reserva.id}</h1>
        </div>
        ${badgeHtml(reserva.estado)}
      </div>

      <div class="card">
        <div class="devol-row head">
          <span>Producto</span>${CAMPOS.map((c) => `<span>${CAMPO_LABEL[c]}</span>`).join('')}
        </div>
        <div id="devol-rows"></div>
      </div>

      <div class="section-row" style="grid-template-columns:1fr 1fr;margin-top:var(--space-md);">
        <div class="card">
          <h3 style="font-size:1rem;margin-bottom:0.6rem;">Observaciones</h3>
          <textarea id="devol-observaciones" placeholder="Detalles adicionales de la devolución..." style="width:100%;min-height:100px;padding:0.7rem;border-radius:8px;border:1px solid var(--color-gray-light);"></textarea>
        </div>
        <div class="summary-box">
          <h3>Resumen y reposición</h3>
          <div class="summary-line"><span>Recibidas correctamente</span><span id="sum-recibidas">0</span></div>
          <div class="summary-line"><span>Perdidas</span><span id="sum-perdidas">0</span></div>
          <div class="summary-line total"><span>Total reposición</span><span id="sum-reposicion">$0</span></div>
        </div>
      </div>

      <div class="modal-actions" style="border-top:none;">
        <span class="spacer"></span>
        <a href="reserva.html?id=${reserva.id}" class="btn btn-outline">Cancelar</a>
        <button class="btn btn-primary" id="btn-finalizar">Finalizar reserva</button>
      </div>
    `;

    renderFilas();
    document.getElementById('btn-finalizar').addEventListener('click', finalizar);
  }

  function renderFilas() {
    const wrap = document.getElementById('devol-rows');
    wrap.innerHTML = reserva.productos.map((p, i) => {
      const d = p._devolucion;
      const suma = CAMPOS.reduce((s, c) => s + Number(d[c] || 0), 0);
      const mismatch = suma !== p.despachado;
      return `
        <div class="devol-row ${mismatch ? 'mismatch' : ''}" data-fila="${i}">
          <span>${p.nombre}<br><span class="cell-muted">Despachado: ${p.despachado} ${mismatch ? `· Suma actual: ${suma} ⚠` : '· ✓ Cuadra'}</span></span>
          ${CAMPOS.map((c) => `<input type="number" min="0" data-idx="${i}" data-campo="${c}" value="${d[c]}">`).join('')}
        </div>
      `;
    }).join('');

    wrap.querySelectorAll('input').forEach((input) => {
      input.addEventListener('input', () => {
        const p = reserva.productos[Number(input.dataset.idx)];
        p._devolucion[input.dataset.campo] = Number(input.value) || 0;
        renderFilas();
        actualizarResumen();
      });
    });
    actualizarResumen();
  }

  function actualizarResumen() {
    const totales = { recibidas: 0, perdidas: 0 };
    let reposicion = 0;
    reserva.productos.forEach((p) => {
      const d = p._devolucion;
      const producto = inventario.find((inv) => inv.codigo === p.codigo);
      CAMPOS.forEach((c) => { totales[c] += Number(d[c] || 0); });
      reposicion += Number(d.perdidas || 0) * (producto ? producto.valorReposicion : 0);
    });
    document.getElementById('sum-recibidas').textContent = totales.recibidas;
    document.getElementById('sum-perdidas').textContent = totales.perdidas;
    document.getElementById('sum-reposicion').textContent = formatearMoneda(reposicion);
  }

  async function finalizar() {
    const conProblemas = reserva.productos.filter((p) => {
      const suma = CAMPOS.reduce((s, c) => s + Number(p._devolucion[c] || 0), 0);
      return suma !== p.despachado;
    });
    if (conProblemas.length) {
      mostrarToast(`Revisa ${conProblemas.length} producto(s): la suma no calza con lo despachado.`);
      return;
    }

    const ok = await confirmarAccion({
      titulo: 'Finalizar reserva',
      mensaje: `Se aplicarán los movimientos de inventario y la reserva ${reserva.id} pasará a estado Finalizada. Esta acción no se puede deshacer.`,
      textoConfirmar: 'Finalizar reserva',
      peligroso: true,
    });
    if (!ok) return;

    reserva.productos.forEach((p) => {
      const d = p._devolucion;
      p.devuelto = d.recibidas;
      const producto = inventario.find((inv) => inv.codigo === p.codigo);
      if (producto) {
        producto.arrendado = Math.max(0, producto.arrendado - p.despachado);
        producto.disponible += Number(d.recibidas || 0);
        producto.merma += Number(d.perdidas || 0);
      }
    });
    reserva.estado = 'Finalizada';
    reserva.observacionesDevolucion = document.getElementById('devol-observaciones').value.trim();

    mostrarToast(`Reserva ${reserva.id} finalizada correctamente.`);
    setTimeout(() => { window.location.href = `reserva.html?id=${reserva.id}`; }, 900);
  }
})();
