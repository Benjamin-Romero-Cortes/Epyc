/**
 * productos.js
 *
 * El catálogo ya viene renderizado desde Django/PostgreSQL.
 * Este archivo controla:
 * - búsqueda
 * - filtro por categoría
 * - contador de resultados
 * - mensaje cuando no hay resultados
 */

(function () {
    const grid = document.getElementById('product-grid');

    // Si no estamos en el catálogo, salir.
    if (!grid) return;

    const searchInput = document.getElementById('product-search');
    const chipsContainer = document.getElementById('filter-chips');
    const resultCount = document.getElementById('result-count');
    const emptyState = document.getElementById('empty-state');

    const productos = document.querySelectorAll('.product-card');

    let categoriaActiva = 'todas';
    let terminoBusqueda = '';

    function normalizarTexto(texto) {
        return (texto || '')
            .toLowerCase()
            .normalize('NFD')
            .replace(/[\u0300-\u036f]/g, '')
            .trim();
    }

    function actualizarContador(cantidad) {
        if (!resultCount) return;

        resultCount.textContent =
            cantidad === 1
                ? '1 producto encontrado'
                : `${cantidad} productos encontrados`;
    }

    function actualizarEstadoVacio(cantidad) {
        if (!emptyState) return;

        emptyState.hidden = cantidad !== 0;
    }

    function renderizar() {
        let visibles = 0;

        productos.forEach((producto) => {
            const categoria = producto.dataset.categoria;

            const nombre = normalizarTexto(
                producto.dataset.nombre
            );

            const descripcion = normalizarTexto(
                producto.dataset.descripcion
            );

            const material = normalizarTexto(
                producto.dataset.material
            );

            const color = normalizarTexto(
                producto.dataset.color
            );

            const busqueda = normalizarTexto(
                terminoBusqueda
            );

            const coincideCategoria =
                categoriaActiva === 'todas' ||
                categoria === categoriaActiva;

            const coincideBusqueda =
                busqueda === '' ||
                nombre.includes(busqueda) ||
                descripcion.includes(busqueda) ||
                material.includes(busqueda) ||
                color.includes(busqueda);

            if (coincideCategoria && coincideBusqueda) {
                producto.style.display = '';
                visibles++;
            } else {
                producto.style.display = 'none';
            }
        });

        actualizarContador(visibles);
        actualizarEstadoVacio(visibles);
    }

    // ==========================
    // FILTROS POR CATEGORÍA
    // ==========================

    if (chipsContainer) {
        const chips = chipsContainer.querySelectorAll('.chip');

        chips.forEach((chip) => {
            chip.addEventListener('click', () => {
                categoriaActiva = chip.dataset.categoria;

                chips.forEach((c) =>
                    c.classList.remove('is-active')
                );

                chip.classList.add('is-active');

                renderizar();
            });
        });
    }

    // ==========================
    // BARRA DE BÚSQUEDA
    // ==========================

    if (searchInput) {
        searchInput.addEventListener('input', () => {
            terminoBusqueda = searchInput.value;
            renderizar();
        });
    }

    // Render inicial
    renderizar();
})();