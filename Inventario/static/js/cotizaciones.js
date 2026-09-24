/**
 * cotizaciones.js
 * Listado de cotizaciones y modal "Crear nueva cotización". La creación
 * se simula en memoria: arma un nuevo registro con las líneas de
 * producto y el resumen calculado, lo agrega al listado y abre el
 * documento de la cotización recién generada.
 */
(function () {
  const tbody = document.getElementById('cot-tbody');
  if (!tbody) return;

  let cotizaciones = [];
  let clientes = [];
  let inventario = [];
  let termino = '';
  let estadoFiltro = '';
  let responsableFiltro = '';
  let lineas = [];

  Promise.all([obtenerDatos('cotizaciones'), obtenerDatos('clientes'), obtenerDatos('inventario')])
    .then(([c, cli, inv]) => {
      cotizaciones = c;
      clientes = cli;
      inventario = inv;
      construirFiltroResponsables();
      poblarSelectsModal();
      renderizar();
      if (new URLSearchParams(window.location.search).get('nueva')) abrirModalNueva();
    }).catch((err) => {
      tbody.innerHTML = '<tr><td colspan="8" class="empty-state">No pudimos cargar las cotizaciones.</td></tr>';
      console.error(err);
    });

  function construirFiltroResponsables() {
    const select = document.getElementById('cot-responsable');
    [...new Set(cotizaciones.map((c) => c.responsable))].forEach((r) => {
      const opt = document.createElement('option');
      opt.value = r; opt.textContent = r;
      select.appendChild(opt);
    });
  }

  function filtradas() {
    return cotizaciones.filter((c) => {
      const t = !termino || c.id.toLowerCase().includes(termino) || c.clienteNombre.toLowerCase().includes(termino);
      const e = !estadoFiltro || c.estado === estadoFiltro;
      const r = !responsableFiltro || c.responsable === responsableFiltro;
      return t && e && r;
    }).sort((a, b) => b.fechaCreacion.localeCompare(a.fechaCreacion));
  }

  function renderizar() {
    const lista = filtradas();
    document.getElementById('cot-result-count').textContent = `${lista.length} cotización${lista.length === 1 ? '' : 'es'} encontrada${lista.length === 1 ? '' : 's'}`;
    if (!lista.length) {
      tbody.innerHTML = '<tr><td colspan="8"><p class="empty-state">No encontramos cotizaciones con ese criterio.</p></td></tr>';
      return;
    }
    tbody.innerHTML = lista.map((c) => `
      <tr>
        <td>
          <a href="cotizacion.html?id=${c.id}" class="cell-strong">${c.id}</a>
          ${c.origen === 'web' ? '<br><span class="tag-origin">Solicitud web</span>' : ''}
        </td>
        <td>${c.clienteNombre}</td>
        <td>${c.tipoEvento}</td>
        <td>${formatearFecha(c.fechaEvento)}</td>
        <td class="cell-num">${formatearMoneda(c.monto)}</td>
        <td>${badgeHtml(c.estado)}</td>
        <td>${c.responsable}</td>
        <td><div class="table-actions"><a href="cotizacion.html?id=${c.id}" class="icon-btn" title="Ver">👁</a></div></td>
      </tr>
    `).join('');
  }

  document.getElementById('cot-search').addEventListener('input', (e) => { termino = e.target.value.trim().toLowerCase(); renderizar(); });
  document.getElementById('cot-estado').addEventListener('change', (e) => { estadoFiltro = e.target.value; renderizar(); });
  document.getElementById('cot-responsable').addEventListener('change', (e) => { responsableFiltro = e.target.value; renderizar(); });

  // ---------- Modal: nueva cotización ----------
  const modal = document.getElementById('modal-nueva-cotizacion');
  const form = document.getElementById('form-nueva-cotizacion');

  function poblarSelectsModal() {
    const cliSel = document.getElementById('nq-cliente');
    cliSel.innerHTML = clientes.map((c) => `<option value="${c.id}">${c.nombre}</option>`).join('');
  }

  function abrirModalNueva() {
    lineas = [];
    form.reset();
    document.getElementById('nq-producto-opciones').hidden = true;
    renderLineas();
    abrirModal(modal);
  }
  document.getElementById('btn-nueva-cotizacion').addEventListener('click', abrirModalNueva);

  // ---------- Buscador de producto ----------
  const prodBuscar = document.getElementById('nq-producto-buscar');
  const prodOculto = document.getElementById('nq-producto');
  const prodOpciones = document.getElementById('nq-producto-opciones');

  function mostrarOpcionesProducto(lista) {
    if (!lista.length) {
      prodOpciones.innerHTML = '<div style="padding:0.65rem 0.9rem;font-size:0.85rem;opacity:0.6;">Sin productos que coincidan.</div>';
      prodOpciones.hidden = false;
      return;
    }
    prodOpciones.innerHTML = lista.map((p) => `
      <div class="producto-opcion" data-codigo="${p.codigo}" style="padding:0.55rem 0.9rem;font-size:0.86rem;cursor:pointer;display:flex;justify-content:space-between;gap:0.6rem;border-top:1px solid var(--color-gray-light);">
        <span>${p.nombre}</span><span style="opacity:0.6;flex-shrink:0;">${formatearMoneda(p.precioArriendo)}</span>
      </div>
    `).join('');
    prodOpciones.hidden = false;
    prodOpciones.querySelectorAll('[data-codigo]').forEach((el) => {
      el.addEventListener('click', () => seleccionarProducto(el.dataset.codigo));
      el.addEventListener('mouseenter', () => { el.style.backgroundColor = 'var(--color-beige-soft)'; });
      el.addEventListener('mouseleave', () => { el.style.backgroundColor = ''; });
    });
  }

  function seleccionarProducto(codigo) {
    const producto = inventario.find((p) => p.codigo === codigo);
    if (!producto) return;
    prodOculto.value = codigo;
    prodBuscar.value = `${producto.nombre} · ${formatearMoneda(producto.precioArriendo)}`;
    prodOpciones.hidden = true;
  }

  prodBuscar.addEventListener('input', () => {
    prodOculto.value = '';
    const term = prodBuscar.value.trim().toLowerCase();
    if (!term) { prodOpciones.hidden = true; return; }
    mostrarOpcionesProducto(inventario.filter((p) => p.nombre.toLowerCase().includes(term)).slice(0, 12));
  });
  prodBuscar.addEventListener('focus', () => {
    const term = prodBuscar.value.trim().toLowerCase();
    if (term && !prodOculto.value) mostrarOpcionesProducto(inventario.filter((p) => p.nombre.toLowerCase().includes(term)).slice(0, 12));
  });
  document.addEventListener('click', (e) => {
    if (!prodOpciones.contains(e.target) && e.target !== prodBuscar) prodOpciones.hidden = true;
  });

  document.getElementById('btn-agregar-linea').addEventListener('click', () => {
    const codigo = prodOculto.value;
    const cantidad = Number(document.getElementById('nq-cantidad').value);
    const producto = inventario.find((p) => p.codigo === codigo);
    if (!producto || !cantidad || cantidad <= 0) { mostrarToast('Busca y selecciona un producto de la lista.'); return; }

    const existente = lineas.find((l) => l.codigo === codigo);
    if (existente) existente.cantidad += cantidad;
    else lineas.push({ codigo, nombre: producto.nombre, precio: producto.precioArriendo, cantidad });
    prodBuscar.value = '';
    prodOculto.value = '';
    renderLineas();
  });

  function renderLineas() {
    const wrap = document.getElementById('lineas-lista');
    document.getElementById('lineas-hint').hidden = lineas.length > 0;
    wrap.innerHTML = lineas.map((l, i) => `
      <div class="line-item">
        <span>${l.nombre}</span>
        <span>${l.cantidad} uds</span>
        <span>${formatearMoneda(l.precio)}</span>
        <span class="cell-strong">${formatearMoneda(l.precio * l.cantidad)}</span>
        <button type="button" class="remove-line" data-quitar="${i}">✕</button>
      </div>
    `).join('');
    wrap.querySelectorAll('[data-quitar]').forEach((btn) => {
      btn.addEventListener('click', () => { lineas.splice(Number(btn.dataset.quitar), 1); renderLineas(); calcularResumen(); });
    });
    calcularResumen();
  }

  function calcularResumen() {
    const subtotalProductos = lineas.reduce((s, l) => s + l.precio * l.cantidad, 0);
    const descuento = Number(document.getElementById('nq-descuento').value) || 0;
    const transporte = Number(document.getElementById('nq-transporte').value) || 0;
    const neto = Math.max(0, subtotalProductos + transporte - descuento);
    const iva = Math.round(neto * 0.19);
    const total = neto + iva;
    document.getElementById('rs-subtotal').textContent = formatearMoneda(subtotalProductos);
    document.getElementById('rs-iva').textContent = formatearMoneda(iva);
    document.getElementById('rs-total').textContent = formatearMoneda(total);
    return { subtotalProductos, descuento, transporte, iva, total };
  }
  ['nq-descuento', 'nq-transporte'].forEach((id) => document.getElementById(id).addEventListener('input', calcularResumen));

  function nuevoId() {
    const nums = cotizaciones.map((c) => Number(c.id.split('-').pop())).filter((n) => !isNaN(n));
    const siguiente = Math.max(0, ...nums) + 1;
    return `COT-2026-${String(siguiente).padStart(3, '0')}`;
  }

  function crearCotizacion(estado) {
    const clienteId = document.getElementById('nq-cliente').value;
    const cliente = clientes.find((c) => c.id === clienteId);
    if (!cliente) return null;
    const resumen = calcularResumen();
    const nueva = {
      id: nuevoId(),
      clienteId, clienteNombre: cliente.nombre,
      tipoEvento: 'Evento',
      fechaEvento: document.getElementById('nq-fecha').value || '2026-09-01',
      fechaCreacion: '2026-08-19',
      monto: resumen.total,
      estado, responsable: 'Helen Cortés', origen: 'interno',
      comuna: document.getElementById('nq-comuna').value.trim(),
      invitados: document.getElementById('nq-invitados').value,
      observaciones: document.getElementById('nq-observaciones').value.trim(),
      descuento: resumen.descuento, transporte: resumen.transporte,
      garantia: Number(document.getElementById('nq-garantia').value) || 0,
      lineas: lineas.map((l) => ({ ...l })),
    };
    cotizaciones.unshift(nueva);
    return nueva;
  }

  document.getElementById('btn-guardar-borrador').addEventListener('click', () => {
    if (!lineas.length) { mostrarToast('Agrega al menos un producto antes de guardar.'); return; }
    const nueva = crearCotizacion('Borrador');
    if (!nueva) return;
    mostrarToast(`Borrador ${nueva.id} guardado.`);
    cerrarModal(modal);
    renderizar();
  });

  form.addEventListener('submit', (e) => {
    e.preventDefault();
    if (!lineas.length) { mostrarToast('Agrega al menos un producto antes de generar la cotización.'); return; }
    const nueva = crearCotizacion('Pendiente');
    if (!nueva) return;
    sessionStorage.setItem('epyc_admin_cotizaciones_temp', JSON.stringify(cotizaciones));
    window.location.href = `cotizacion.html?id=${nueva.id}`;
  });
})();
