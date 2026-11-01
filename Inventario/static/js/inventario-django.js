document.addEventListener('DOMContentLoaded', () => {
  // Pide confirmación antes de eliminar un producto
  document.querySelectorAll('form[data-confirm-delete]').forEach((formEliminar) => {
    formEliminar.addEventListener('submit', async (e) => {
      if (formEliminar.dataset.confirmado) return;
      e.preventDefault();

      const nombre = formEliminar.dataset.confirmDelete.trim() || 'este producto';
      const opciones = {
        titulo: 'Eliminar producto',
        mensaje: `¿Seguro que quieres eliminar ${nombre}? Esta acción no se puede deshacer.`,
        textoConfirmar: 'Eliminar',
        peligroso: true,
      };

      const ok = typeof confirmarAccion === 'function'
        ? await confirmarAccion(opciones)
        : window.confirm(opciones.mensaje);

      if (ok) {
        formEliminar.dataset.confirmado = '1';
        formEliminar.submit();
      }
    });
  });

  const form = document.getElementById('inventario-filter-form');
  const searchInput = document.getElementById('inv-search');
  const categoriaSelect = document.getElementById('inv-categoria');
  const estadoSelect = document.getElementById('inv-estado');
  const chipBajo = document.getElementById('inv-chip-bajo');
  const grupos = [...document.querySelectorAll('[data-grupo]')];
  const tarjetas = [...document.querySelectorAll('[data-ir-categoria]')];
  const sinResultados = document.getElementById('inv-sin-resultados');
  const ayuda = document.getElementById('inv-ayuda-categoria');

  if (!form || !searchInput || !categoriaSelect) return;

  const normalize = (value) => (value || '')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .trim();

  function cumpleEstado(row, estado) {
    if (!estado) return true;
    if (estado === 'ok') return row.dataset.nivel === 'ok';
    if (estado === 'bajo') return ['bajo', 'agotado', 'sin-stock'].includes(row.dataset.nivel);
    if (estado === 'mermas') return Number(row.dataset.mermas) > 0;
    if (estado === 'inactivo') return row.dataset.activo === '0';
    return true;
  }

  // Filtra filas y oculta las categorías que quedan sin productos visibles.
  function applyFilters() {
    const term = normalize(searchInput.value);
    const categoria = categoriaSelect.value;
    const estado = chipBajo && chipBajo.classList.contains('is-active') ? 'bajo' : (estadoSelect ? estadoSelect.value : '');
    let visibles = 0;
    // Los productos solo se listan al elegir una categoría (o al buscar / filtrar por estado).
    const mostrarProductos = Boolean(categoria || term || estado);

    grupos.forEach((grupo) => {
      let enGrupo = 0;
      grupo.querySelectorAll('tr[data-producto]').forEach((row) => {
        const matchesText = !term
          || normalize(row.dataset.nombre).includes(term)
          || normalize(row.dataset.codigo).includes(term);
        const matchesCategoria = !categoria || row.dataset.categoria === categoria;
        row.hidden = !(matchesText && matchesCategoria && cumpleEstado(row, estado));
        if (!row.hidden) enGrupo += 1;
      });
      grupo.hidden = !mostrarProductos || enGrupo === 0;
      const contador = grupo.querySelector('[data-contador]');
      if (contador) contador.textContent = enGrupo;
      // Al buscar, se abren las categorías con resultados.
      if (enGrupo && mostrarProductos) grupo.open = true;
      visibles += enGrupo;
    });

    if (ayuda) ayuda.hidden = mostrarProductos;

    tarjetas.forEach((t) => t.classList.toggle('is-activa', t.dataset.irCategoria === categoria));
    if (sinResultados) sinResultados.hidden = !mostrarProductos || visibles > 0 || grupos.length === 0;
    return visibles;
  }

  form.addEventListener('submit', (event) => {
    event.preventDefault();
    const visibles = applyFilters();
    if (typeof mostrarToast === 'function') {
      mostrarToast(`Búsqueda realizada: ${visibles} producto${visibles === 1 ? '' : 's'} encontrado${visibles === 1 ? '' : 's'}.`);
    }
  });

  form.addEventListener('reset', () => {
    categoriaSelect.value = '';
    if (chipBajo) {
      chipBajo.classList.remove('is-active');
      chipBajo.setAttribute('aria-pressed', 'false');
    }
    window.setTimeout(applyFilters, 0);
  });

  searchInput.addEventListener('input', applyFilters);
  categoriaSelect.addEventListener('change', applyFilters);
  if (estadoSelect) estadoSelect.addEventListener('change', () => {
    if (chipBajo) chipBajo.classList.remove('is-active');
    applyFilters();
  });
  if (chipBajo) chipBajo.addEventListener('click', () => {
    chipBajo.classList.toggle('is-active');
    chipBajo.setAttribute('aria-pressed', chipBajo.classList.contains('is-active'));
    applyFilters();
  });

  // Tarjeta de categoría: filtra por ella (o quita el filtro si ya estaba) y lleva a su sección.
  tarjetas.forEach((tarjeta) => {
    tarjeta.addEventListener('click', () => {
      const nombre = tarjeta.dataset.irCategoria;
      categoriaSelect.value = categoriaSelect.value === nombre ? '' : nombre;
      applyFilters();
      const grupo = grupos.find((g) => g.dataset.grupo === nombre);
      if (grupo && categoriaSelect.value) {
        grupo.open = true;
        grupo.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    });
  });

  const categoriaURL = new URLSearchParams(window.location.search).get('categoria');
  if (categoriaURL) categoriaSelect.value = categoriaURL;

  applyFilters();
});
