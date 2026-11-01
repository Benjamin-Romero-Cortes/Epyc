document.addEventListener('DOMContentLoaded', () => {
  const form = document.getElementById('reservas-filter-form');
  const searchInput = document.getElementById('res-search');
  const estadoSelect = document.getElementById('res-estado');
  const tbody = document.getElementById('res-tbody');

  if (!form || !searchInput || !estadoSelect || !tbody) return;

  const rows = [...tbody.querySelectorAll('tr[data-reserva]')];

  const normalize = (value) => (value || '')
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .trim();

  // Las opciones salen de los estados que realmente tienen las reservas.
  const etiquetas = new Map(rows.map((row) => [row.dataset.estado, row.dataset.etiqueta || row.dataset.estado]));
  [...etiquetas].filter(([estado]) => estado)
    .sort((a, b) => a[1].localeCompare(b[1], 'es'))
    .forEach(([estado, etiqueta]) => {
      const option = document.createElement('option');
      option.value = estado;
      option.textContent = etiqueta;
      estadoSelect.append(option);
    });

  const emptyRow = document.createElement('tr');
  emptyRow.hidden = true;
  emptyRow.innerHTML = '<td colspan="8" class="empty-state">No encontramos reservas con ese criterio.</td>';
  tbody.append(emptyRow);

  function applyFilters() {
    const term = normalize(searchInput.value);
    const estado = estadoSelect.value;
    let visibles = 0;

    rows.forEach((row) => {
      const matchesText = !term || normalize(row.textContent).includes(term);
      const matchesEstado = !estado || row.dataset.estado === estado;
      row.hidden = !(matchesText && matchesEstado);
      if (!row.hidden) visibles += 1;
    });

    emptyRow.hidden = visibles > 0 || rows.length === 0;
    return visibles;
  }

  form.addEventListener('submit', (event) => {
    event.preventDefault();
    const visibles = applyFilters();
    if (typeof mostrarToast === 'function') {
      mostrarToast(`Búsqueda realizada: ${visibles} reserva${visibles === 1 ? '' : 's'} encontrada${visibles === 1 ? '' : 's'}.`);
    }
  });

  form.addEventListener('reset', () => {
    window.setTimeout(applyFilters, 0);
  });

  const estadoURL = new URLSearchParams(window.location.search).get('estado');
  if (estadoURL) {
    estadoSelect.value = estadoURL;
    applyFilters();
  }
});
