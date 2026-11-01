document.addEventListener('DOMContentLoaded', () => {
  const form = document.getElementById('clientes-filter-form');
  const searchInput = document.getElementById('cli-search');
  const statusFilter = document.getElementById('cli-estado');
  const resultCount = document.getElementById('cli-result-count');
  const emptyRow = document.getElementById('cli-empty-results');
  const pageSizeSelect = document.getElementById('cli-page-size');
  const pageSummary = document.getElementById('cli-page-summary');
  const pageNumbers = document.getElementById('cli-page-numbers');
  const previousButton = document.getElementById('cli-page-previous');
  const nextButton = document.getElementById('cli-page-next');
  const rows = [...document.querySelectorAll('#cli-tbody tr[data-cliente]')];

  if (!form || !searchInput || !statusFilter || !resultCount || !pageSizeSelect || !pageSummary || !pageNumbers || !previousButton || !nextButton) return;

  let matchingRows = rows;
  let currentPage = 1;

  const normalize = (value) => value
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .trim();

  function renderPage() {
    const pageSize = Number(pageSizeSelect.value) || 5;
    const pageCount = Math.max(1, Math.ceil(matchingRows.length / pageSize));
    currentPage = Math.min(currentPage, pageCount);

    rows.forEach((row) => { row.hidden = true; });
    const firstIndex = (currentPage - 1) * pageSize;
    matchingRows.slice(firstIndex, firstIndex + pageSize).forEach((row) => { row.hidden = false; });

    const firstVisible = matchingRows.length ? firstIndex + 1 : 0;
    const lastVisible = Math.min(firstIndex + pageSize, matchingRows.length);
    pageSummary.textContent = `Mostrando ${firstVisible}–${lastVisible} de ${matchingRows.length} clientes`;
    previousButton.disabled = currentPage === 1;
    nextButton.disabled = currentPage === pageCount;
    pageNumbers.replaceChildren();

    const firstPage = Math.max(1, Math.min(currentPage - 2, pageCount - 4));
    const lastPage = Math.min(pageCount, firstPage + 4);
    for (let page = firstPage; page <= lastPage; page += 1) {
      const button = document.createElement('button');
      button.type = 'button';
      button.dataset.page = String(page);
      button.textContent = String(page);
      if (page === currentPage) {
        button.classList.add('is-current');
        button.setAttribute('aria-current', 'page');
      }
      pageNumbers.append(button);
    }

    document.getElementById('cli-pagination').hidden = rows.length === 0;
    if (emptyRow) emptyRow.hidden = matchingRows.length > 0 || rows.length === 0;
  }

  function applyFilters() {
    const term = normalize(searchInput.value);
    const selectedStatus = statusFilter.value;
    matchingRows = rows.filter((row) => {
      // El RUT se guarda sin puntos ni guion: se compara igual aunque se busque como 12.345.678-9.
      const rutTerm = term.replace(/[.\-\s]/g, '');
      const rowRut = normalize(row.dataset.rut || '').replace(/[.\-\s]/g, '');
      const matchesText = normalize(row.textContent).includes(term)
        || (rutTerm !== '' && rowRut.includes(rutTerm));
      const matchesStatus = !selectedStatus || row.dataset.estado === selectedStatus;
      return matchesText && matchesStatus;
    });

    resultCount.textContent = `${matchingRows.length} cliente${matchingRows.length === 1 ? '' : 's'} encontrado${matchingRows.length === 1 ? '' : 's'}`;
    resultCount.hidden = false;
    currentPage = 1;
    renderPage();
    return matchingRows.length;
  }

  form.addEventListener('submit', (event) => {
    event.preventDefault();
    const visibleCount = applyFilters();
    if (typeof mostrarToast === 'function') {
      mostrarToast(`Búsqueda realizada: ${resultCount.textContent}.`);
    }
  });
  form.addEventListener('reset', () => {
    window.setTimeout(() => {
      const visibleCount = applyFilters();
      if (typeof mostrarToast === 'function') {
        mostrarToast(`Filtros limpiados: se muestran ${visibleCount} cliente${visibleCount === 1 ? '' : 's'}.`);
      }
    }, 0);
  });

  pageSizeSelect.addEventListener('change', () => {
    currentPage = 1;
    renderPage();
  });
  previousButton.addEventListener('click', () => {
    if (currentPage > 1) {
      currentPage -= 1;
      renderPage();
    }
  });
  nextButton.addEventListener('click', () => {
    currentPage += 1;
    renderPage();
  });
  pageNumbers.addEventListener('click', (event) => {
    const button = event.target.closest('button[data-page]');
    if (!button) return;
    currentPage = Number(button.dataset.page);
    renderPage();
  });

  renderPage();
});