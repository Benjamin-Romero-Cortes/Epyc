/**
 * mermas.js
 * Registro histórico de pérdidas y bajas de inventario, con filtro por
 * categoría (cruzando con inventario.json para conocer la categoría de
 * cada producto).
 */
(function () {
  const tbody = document.getElementById('mer-tbody');
  if (!tbody) return;

  let mermas = [], inventario = [];
  let termino = '', categoria = '';

  Promise.all([obtenerDatos('mermas'), obtenerDatos('inventario')]).then(([m, inv]) => {
    mermas = m; inventario = inv;
    construirFiltroCategorias();
    renderizarKpis();
    renderizar();
  }).catch((err) => {
    tbody.innerHTML = '<tr><td colspan="7" class="empty-state">No pudimos cargar las mermas.</td></tr>';
    console.error(err);
  });

  function categoriaDe(codigo) {
    const p = inventario.find((i) => i.codigo === codigo);
    return p ? p.categoria : '—';
  }

  function construirFiltroCategorias() {
    const select = document.getElementById('mer-categoria');
    const categorias = [...new Set(inventario.map((p) => p.categoria))];
    categorias.forEach((c) => {
      const opt = document.createElement('option');
      opt.value = c; opt.textContent = c;
      select.appendChild(opt);
    });
  }

  function renderizarKpis() {
    document.getElementById('mer-total').textContent = mermas.length;
    document.getElementById('mer-unidades').textContent = mermas.reduce((s, m) => s + m.cantidad, 0);
    document.getElementById('mer-costo').textContent = formatearMoneda(mermas.reduce((s, m) => s + m.valorReposicion, 0));
  }

  function filtradas() {
    return mermas.filter((m) => {
      const t = !termino || m.productoNombre.toLowerCase().includes(termino);
      const ca = !categoria || categoriaDe(m.productoCodigo) === categoria;
      return t && ca;
    }).sort((a, b) => b.fecha.localeCompare(a.fecha));
  }

  function renderizar() {
    const lista = filtradas();
    document.getElementById('mer-result-count').textContent = `${lista.length} registro${lista.length === 1 ? '' : 's'} encontrado${lista.length === 1 ? '' : 's'}`;
    if (!lista.length) {
      tbody.innerHTML = '<tr><td colspan="7"><p class="empty-state">No encontramos registros con ese criterio.</p></td></tr>';
      return;
    }
    tbody.innerHTML = lista.map((m) => `
      <tr>
        <td>${formatearFecha(m.fecha)}</td>
        <td><a href="producto.html?codigo=${m.productoCodigo}" class="cell-strong">${m.productoNombre}</a></td>
        <td>${categoriaDe(m.productoCodigo)}</td>
        <td class="cell-num">${m.cantidad}</td>
        <td>${m.reservaId ? `<a href="reserva.html?id=${m.reservaId}">${m.reservaId}</a>` : '—'}</td>
        <td class="cell-num">${formatearMoneda(m.valorReposicion)}</td>
        <td>${m.responsable}</td>
      </tr>
    `).join('');
  }

  document.getElementById('mer-search').addEventListener('input', (e) => { termino = e.target.value.trim().toLowerCase(); renderizar(); });
  document.getElementById('mer-categoria').addEventListener('change', (e) => { categoria = e.target.value; renderizar(); });

  // ---------- Modal: registrar merma de bodega ----------
  const modal = document.getElementById('modal-nueva-merma');
  const form = document.getElementById('form-nueva-merma');
  const prodBuscar = document.getElementById('nm-producto-buscar');
  const prodOculto = document.getElementById('nm-producto');
  const prodOpciones = document.getElementById('nm-producto-opciones');

  function mostrarOpcionesProducto(lista) {
    if (!lista.length) {
      prodOpciones.innerHTML = '<div style="padding:0.65rem 0.9rem;font-size:0.85rem;opacity:0.6;">Sin productos que coincidan.</div>';
      prodOpciones.hidden = false;
      return;
    }
    prodOpciones.innerHTML = lista.map((p) => `
      <div class="producto-opcion" data-codigo="${p.codigo}" style="padding:0.55rem 0.9rem;font-size:0.86rem;cursor:pointer;display:flex;justify-content:space-between;gap:0.6rem;border-top:1px solid var(--color-gray-light);">
        <span>${p.nombre}</span><span style="opacity:0.6;flex-shrink:0;">${p.categoria}</span>
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
    prodBuscar.value = `${producto.nombre} · ${producto.categoria}`;
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

  document.getElementById('btn-nueva-merma').addEventListener('click', () => {
    form.reset();
    prodOculto.value = '';
    prodOpciones.hidden = true;
    document.getElementById('nm-fecha').value = '2026-08-19';
    document.getElementById('nm-responsable').value = 'Bodega';
    abrirModal(modal);
  });

  form.addEventListener('submit', (e) => {
    e.preventDefault();
    const codigo = prodOculto.value;
    const producto = inventario.find((p) => p.codigo === codigo);
    const cantidad = Number(document.getElementById('nm-cantidad').value);
    if (!producto || !cantidad || cantidad <= 0) { mostrarToast('Busca y selecciona un producto de la lista.'); return; }

    const nueva = {
      id: Math.max(0, ...mermas.map((m) => m.id)) + 1,
      fecha: document.getElementById('nm-fecha').value || '2026-08-19',
      productoCodigo: codigo,
      productoNombre: producto.nombre,
      cantidad,
      reservaId: null,
      valorReposicion: Number(document.getElementById('nm-valor').value) || 0,
      responsable: document.getElementById('nm-responsable').value.trim() || 'Bodega',
    };
    mermas.unshift(nueva);
    renderizarKpis();
    renderizar();
    cerrarModal(modal);
    mostrarToast(`Merma de "${producto.nombre}" registrada.`);
  });
})();
