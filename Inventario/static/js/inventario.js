/**
 * inventario.js
 *
 * Inventario renderizado por Django/PostgreSQL.
 * Este archivo controla:
 * - búsqueda por nombre
 * - filtro por categoría
 * - filtro por estado
 * - filtro rápido de stock bajo
 * - contador de resultados
 * - apertura/cierre del modal
 * - carga de datos al editar
 */

(function () {

    const tbody = document.getElementById('inv-tbody');

    if (!tbody) return;


    // =========================
    // ELEMENTOS PRINCIPALES
    // =========================

    const filas = Array.from(
        tbody.querySelectorAll('tr[data-producto]')
    );

    const searchInput =
        document.getElementById('inv-search');

    const categoriaSelect =
        document.getElementById('inv-categoria');

    const estadoSelect =
        document.getElementById('inv-estado');

    const chipBajo =
        document.getElementById('inv-chip-bajo');

    const resultCount =
        document.getElementById('inv-result-count');


    // =========================
    // MODAL
    // =========================

    const modal =
        document.getElementById('modal-nuevo-producto');

    const btnNuevo =
        document.getElementById('btn-nuevo-producto');

    const form =
        document.getElementById('form-nuevo-producto');

    let editandoCodigo = null;


    // =========================
    // VARIABLES DE FILTRO
    // =========================

    let termino = '';
    let categoria = '';
    let estado = '';
    let soloBajo = false;


    // =========================
    // NORMALIZAR TEXTO
    // =========================

    function normalizar(texto) {

        return (texto || '')
            .toLowerCase()
            .normalize('NFD')
            .replace(/[\u0300-\u036f]/g, '')
            .trim();

    }


    // =========================
    // CONSTRUIR CATEGORÍAS
    // =========================

    function construirFiltroCategorias() {

        if (!categoriaSelect) return;


        const categorias = [
            ...new Set(
                filas
                    .map((fila) => fila.dataset.categoria)
                    .filter(Boolean)
            )
        ].sort((a, b) =>
            a.localeCompare(b, 'es')
        );


        categorias.forEach((nombre) => {

            const option =
                document.createElement('option');

            option.value = nombre;
            option.textContent = nombre;

            categoriaSelect.appendChild(option);

        });

    }


    // =========================
    // FILTROS DESDE URL
    // =========================

    function aplicarFiltrosDesdeURL() {

        const params =
            new URLSearchParams(
                window.location.search
            );


        const estadoURL =
            params.get('estado');

        if (
            estadoURL &&
            estadoSelect
        ) {

            estado = estadoURL;

            estadoSelect.value =
                estadoURL;

        }


        const categoriaURL =
            params.get('categoria');

        if (
            categoriaURL &&
            categoriaSelect
        ) {

            categoria =
                categoriaURL;

            categoriaSelect.value =
                categoriaURL;

        }

    }


    // =========================
    // RENDERIZAR FILTROS
    // =========================

    function renderizar() {

        let visibles = 0;


        filas.forEach((fila) => {

            const nombreFila =
                normalizar(
                    fila.dataset.nombre
                );

            const categoriaFila =
                fila.dataset.categoria || '';

            const estadoFila =
                fila.dataset.estado || '';


            const coincideTexto =
                !termino ||
                nombreFila.includes(
                    normalizar(termino)
                );


            const coincideCategoria =
                !categoria ||
                categoriaFila === categoria;


            const coincideEstado =
                !estado ||
                estadoFila === estado;


            const coincideBajo =
                !soloBajo ||
                estadoFila === 'Stock bajo';


            const visible =
                coincideTexto &&
                coincideCategoria &&
                coincideEstado &&
                coincideBajo;


            fila.hidden = !visible;


            if (visible) {
                visibles++;
            }

        });


        // =========================
        // CONTADOR
        // =========================

        if (resultCount) {

            resultCount.textContent =
                `${visibles} producto` +
                `${visibles === 1 ? '' : 's'} ` +
                `encontrado` +
                `${visibles === 1 ? '' : 's'}`;

        }


        // =========================
        // ESTADO VACÍO
        // =========================

        let filaVacia =
            tbody.querySelector(
                '.js-empty-row'
            );


        if (visibles === 0) {

            if (!filaVacia) {

                filaVacia =
                    document.createElement('tr');

                filaVacia.className =
                    'js-empty-row';

                filaVacia.innerHTML = `
                    <td colspan="6">
                        <p class="empty-state">
                            No encontramos productos
                            con ese criterio.
                        </p>
                    </td>
                `;

                tbody.appendChild(
                    filaVacia
                );

            }

            filaVacia.hidden = false;


        } else if (filaVacia) {

            filaVacia.hidden = true;

        }

    }


    // =========================
    // BÚSQUEDA
    // =========================

    if (searchInput) {

        searchInput.addEventListener(
            'input',
            (e) => {

                termino =
                    e.target.value;

                renderizar();

            }
        );

    }


    // =========================
    // FILTRO CATEGORÍA
    // =========================

    if (categoriaSelect) {

        categoriaSelect.addEventListener(
            'change',
            (e) => {

                categoria =
                    e.target.value;

                renderizar();

            }
        );

    }


    // =========================
    // FILTRO ESTADO
    // =========================

    if (estadoSelect) {

        estadoSelect.addEventListener(
            'change',
            (e) => {

                estado =
                    e.target.value;

                renderizar();

            }
        );

    }


    // =========================
    // SOLO STOCK BAJO
    // =========================

    if (chipBajo) {

        chipBajo.addEventListener(
            'click',
            () => {

                soloBajo =
                    !soloBajo;

                chipBajo.classList.toggle(
                    'is-active',
                    soloBajo
                );

                renderizar();

            }
        );

    }


    // =========================
    // NUEVO PRODUCTO
    // =========================

    if (
        btnNuevo &&
        modal
    ) {

        btnNuevo.addEventListener(
            'click',
            () => {

                editandoCodigo = null;


                if (form) {
                    form.reset();
                }


                const tituloModal =
                    modal.querySelector('h2');


                if (tituloModal) {

                    tituloModal.textContent =
                        'Nuevo producto';

                }


                if (
                    typeof abrirModal ===
                    'function'
                ) {

                    abrirModal(modal);

                } else {

                    modal.hidden = false;

                }

            }
        );

    }


    // =========================
    // BOTONES EDITAR
    // =========================

    document
        .querySelectorAll('[data-editar]')
        .forEach((btn) => {

            btn.addEventListener(
                'click',
                () => {

                    const codigo =
                        btn.dataset.editar;

                    abrirEdicion(
                        codigo
                    );

                }
            );

        });


    // =========================
    // ABRIR EDICIÓN
    // =========================

    function abrirEdicion(codigo) {

        if (!modal) return;


        const fila =
            filas.find(
                (fila) =>
                    fila.dataset.codigo ===
                    codigo
            );


        if (!fila) {

            console.error(
                'No se encontró el producto:',
                codigo
            );

            return;

        }


        editandoCodigo =
            codigo;


        // =========================
        // TÍTULO
        // =========================

        const tituloModal =
            modal.querySelector('h2');


        if (tituloModal) {

            tituloModal.textContent =
                'Editar producto';

        }


        // =========================
        // NOMBRE
        // =========================

        const inputNombre =
            document.getElementById(
                'np-nombre'
            );


        if (inputNombre) {

            inputNombre.value =
                fila.dataset.nombre || '';

        }


        // =========================
        // CATEGORÍA
        // =========================

        const inputCategoria =
            document.getElementById(
                'np-categoria'
            );


        if (inputCategoria) {

            inputCategoria.value =
                fila.dataset.categoria || '';

        }


        // =========================
        // STOCK TOTAL
        // =========================

        const inputStock =
            document.getElementById(
                'np-stock'
            );


        if (inputStock) {

            inputStock.value =
                fila.dataset.stockTotal || 0;

        }


        // =========================
        // STOCK TRABAJABLE
        // =========================

        const inputDisponible =
            document.getElementById(
                'np-disponible'
            );


        if (inputDisponible) {

            inputDisponible.value =
                fila.dataset.stockTrabajable || 0;

        }


        // =========================
        // PRECIO
        // =========================

        const inputPrecio =
            document.getElementById(
                'np-precio'
            );


        if (inputPrecio) {

            inputPrecio.value =
                fila.dataset.precio || 0;

        }


        // =========================
        // VALOR REPOSICIÓN
        // =========================

        const inputReposicion =
            document.getElementById(
                'np-reposicion'
            );


        if (inputReposicion) {

            inputReposicion.value =
                fila.dataset.reposicion || 0;

        }


        // =========================
        // ABRIR MODAL
        // =========================

        if (
            typeof abrirModal ===
            'function'
        ) {

            abrirModal(modal);

        } else {

            modal.hidden = false;

        }

    }


    // =========================
    // CERRAR MODALES
    // =========================

    document
        .querySelectorAll(
            '[data-close-modal]'
        )
        .forEach((btn) => {

            btn.addEventListener(
                'click',
                () => {

                    const overlay =
                        btn.closest(
                            '.modal-overlay'
                        );


                    if (!overlay) return;


                    if (
                        typeof cerrarModal ===
                        'function'
                    ) {

                        cerrarModal(
                            overlay
                        );

                    } else {

                        overlay.hidden =
                            true;

                    }

                }
            );

        });


    // =========================
    // CERRAR AL HACER CLICK
    // FUERA DEL MODAL
    // =========================

    if (modal) {

        modal.addEventListener(
            'click',
            (e) => {

                if (
                    e.target === modal
                ) {

                    if (
                        typeof cerrarModal ===
                        'function'
                    ) {

                        cerrarModal(
                            modal
                        );

                    } else {

                        modal.hidden =
                            true;

                    }

                }

            }
        );

    }


    // =========================
    // ESC PARA CERRAR
    // =========================

    document.addEventListener(
        'keydown',
        (e) => {

            if (
                e.key === 'Escape' &&
                modal &&
                !modal.hidden
            ) {

                if (
                    typeof cerrarModal ===
                    'function'
                ) {

                    cerrarModal(modal);

                } else {

                    modal.hidden = true;

                }

            }

        }
    );


    // =========================
// GUARDAR PRODUCTO
// =========================

if (form) {

    form.addEventListener(
        'submit',
        async (e) => {

            e.preventDefault();


            const nombre =
                document.getElementById(
                    'np-nombre'
                ).value.trim();


            const categoria =
                document.getElementById(
                    'np-categoria'
                ).value;


            const stockTotal =
                Number(
                    document.getElementById(
                        'np-stock'
                    ).value
                );


            const stockTrabajable =
                Number(
                    document.getElementById(
                        'np-disponible'
                    ).value
                );


            const precioArriendo =
                Number(
                    document.getElementById(
                        'np-precio'
                    ).value
                );


            // =========================
            // VALIDACIÓN CLIENTE
            // =========================

            if (!nombre) {

                alert(
                    'Debes ingresar un nombre.'
                );

                return;
            }


            if (
                stockTrabajable >
                stockTotal
            ) {

                alert(
                    'El stock trabajable no puede ' +
                    'ser mayor que el stock total.'
                );

                return;
            }


            const datos = {

                codigo:
                    editandoCodigo,

                nombre:
                    nombre,

                categoria:
                    categoria,

                stock_total:
                    stockTotal,

                stock_trabajable:
                    stockTrabajable,

                precio_arriendo:
                    precioArriendo

            };


            // =========================
            // CSRF
            // =========================

            const csrfInput =
                form.querySelector(
                    '[name=csrfmiddlewaretoken]'
                );


            if (!csrfInput) {

                console.error(
                    'No se encontró el token CSRF.'
                );

                return;
            }


            const csrfToken =
                csrfInput.value;


            // =========================
            // BOTÓN GUARDAR
            // =========================

            const botonGuardar =
                form.querySelector(
                    'button[type="submit"]'
                );


            if (botonGuardar) {

                botonGuardar.disabled =
                    true;

                botonGuardar.textContent =
                    'Guardando...';

            }


            try {

                const respuesta =
                    await fetch(
                        form.action,
                        {

                            method: 'POST',

                            headers: {

                                'Content-Type':
                                    'application/json',

                                'X-CSRFToken':
                                    csrfToken

                            },

                            body:
                                JSON.stringify(
                                    datos
                                )

                        }
                    );


                const resultado =
                    await respuesta.json();


                if (!respuesta.ok) {

                    throw new Error(
                        resultado.error ||
                        'No se pudo guardar el producto.'
                    );

                }


                // =========================
                // ÉXITO
                // =========================

                if (
                    typeof mostrarToast ===
                    'function'
                ) {

                    mostrarToast(
                        resultado.mensaje
                    );

                } else {

                    alert(
                        resultado.mensaje
                    );

                }


                if (
                    typeof cerrarModal ===
                    'function'
                ) {

                    cerrarModal(
                        modal
                    );

                } else {

                    modal.hidden =
                        true;

                }


                /*
                 * Recargamos porque Django
                 * obtiene nuevamente los
                 * productos desde PostgreSQL.
                 */

                window.location.reload();


            } catch (error) {

                console.error(
                    error
                );


                alert(
                    error.message
                );


            } finally {

                if (botonGuardar) {

                    botonGuardar.disabled =
                        false;

                    botonGuardar.textContent =
                        'Guardar producto';

                }

            }

        }
    );

}


    // =========================
    // INICIALIZACIÓN
    // =========================

    construirFiltroCategorias();

    aplicarFiltrosDesdeURL();

    renderizar();

})();