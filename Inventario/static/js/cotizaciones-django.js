document.addEventListener('DOMContentLoaded', () => {
  const form = document.getElementById('cotizaciones-filter-form');
  const searchInput = document.getElementById('cot-search');
  const tbody = document.getElementById('cot-tbody');

  if (!form || !searchInput || !tbody) return;

  const rows = [...tbody.querySelectorAll('tr[data-cotizacion]')];

  const normalize = (value) => (value || '')
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .trim();

  const emptyRow = document.createElement('tr');
  emptyRow.hidden = true;
  emptyRow.innerHTML = '<td colspan="8" class="empty-state">No encontramos cotizaciones con ese criterio.</td>';
  tbody.append(emptyRow);

  function applyFilters() {
    const term = normalize(searchInput.value);
    let visibles = 0;

    rows.forEach((row) => {
      row.hidden = Boolean(term) && !normalize(row.textContent).includes(term);
      if (!row.hidden) visibles += 1;
    });

    emptyRow.hidden = visibles > 0 || rows.length === 0;
    return visibles;
  }

  form.addEventListener('submit', (event) => {
    event.preventDefault();
    const visibles = applyFilters();
    if (typeof mostrarToast === 'function') {
      mostrarToast(`Búsqueda realizada: ${visibles} cotizaci${visibles === 1 ? 'ón' : 'ones'} encontrada${visibles === 1 ? '' : 's'}.`);
    }
  });

  form.addEventListener('reset', () => {
    window.setTimeout(applyFilters, 0);
  });
});
