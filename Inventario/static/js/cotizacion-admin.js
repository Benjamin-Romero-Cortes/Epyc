// Detalle de cotización: catálogo para agregar productos y confirmación de la reserva.
document.addEventListener('DOMContentLoaded', () => {
  const modal = document.getElementById('modal-agregar-articulo');
  const abrirCatalogo = () => {
    modal.hidden = false;
    document.getElementById('catalogo-buscar')?.focus();
  };
  document.getElementById('btn-agregar-articulo')?.addEventListener('click', abrirCatalogo);
  document.querySelectorAll('[data-abrir-catalogo]').forEach((b) => b.addEventListener('click', abrirCatalogo));
  iniciarCatalogo();

  // Menús de la barra de envío ("Otro medio", "No aceptó"): se cierran al hacer clic fuera o con Esc,
  // y solo uno queda abierto a la vez.
  const menus = [...document.querySelectorAll('details.flujo__menu')];
  menus.forEach((menu) => menu.addEventListener('toggle', () => {
    if (menu.open) menus.forEach((otro) => { if (otro !== menu) otro.open = false; });
  }));
  document.addEventListener('click', (e) => {
    menus.forEach((menu) => { if (menu.open && !menu.contains(e.target)) menu.open = false; });
  });
  document.addEventListener('keydown', (e) => {
    if (e.key !== 'Escape') return;
    menus.forEach((menu) => {
      if (!menu.open) return;
      menu.open = false;
      menu.querySelector('summary')?.focus();
    });
  });

  // El estado solo cambia en pantalla después de que el servidor confirma; aquí solo se pide confirmación.
  const formConfirmar = document.getElementById('form-confirmar');
  formConfirmar?.addEventListener('submit', async (e) => {
    if (formConfirmar.dataset.confirmado) return;
    e.preventDefault();
    const opciones = {
      titulo: 'Confirmar reserva',
      mensaje: 'Se volverá a comprobar el stock para las fechas del evento. Si alcanza, la reserva quedará confirmada y retendrá esos artículos.',
      textoConfirmar: 'Confirmar reserva',
    };
    const ok = typeof confirmarAccion === 'function'
      ? await confirmarAccion(opciones)
      : window.confirm(opciones.mensaje);
    if (!ok) return;
    formConfirmar.dataset.confirmado = '1';
    const boton = formConfirmar.querySelector('button[type="submit"]');
    boton.disabled = true;
    boton.textContent = 'Confirmando...';
    formConfirmar.submit();
  });
});

// Catálogo: pestañas por categoría, búsqueda, cantidades y resumen de lo que se va a agregar.
function iniciarCatalogo() {
  const form = document.getElementById('form-catalogo');
  if (!form) return;
  const buscar = document.getElementById('catalogo-buscar');
  const tabs = [...form.querySelectorAll('[data-tab]')];
  const grupos = [...form.querySelectorAll('tbody[data-grupo]')];
  const filas = [...form.querySelectorAll('tr[data-producto]')];
  const resumen = document.getElementById('catalogo-resumen');
  const boton = document.getElementById('catalogo-agregar');
  const vacio = document.getElementById('catalogo-vacio');
  const pesos = new Intl.NumberFormat('es-CL');
  const normalizar = (t) => (t || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().trim();
  // Se abre en la primera categoría.
  let tabActiva = tabs.length ? tabs[0].dataset.tab : '';

  function filtrar() {
    const termino = normalizar(buscar.value);
    let visibles = 0;
    grupos.forEach((grupo) => {
      let enGrupo = 0;
      grupo.querySelectorAll('tr[data-producto]').forEach((fila) => {
        const coincide = !termino
          || normalizar(fila.dataset.nombre).includes(termino)
          || normalizar(fila.dataset.codigo).includes(termino);
        fila.hidden = !coincide;
        if (coincide) enGrupo += 1;
      });
      // Al buscar se mira en todas las categorías; sin búsqueda, solo en la pestaña elegida.
      grupo.hidden = enGrupo === 0 || (!termino && grupo.dataset.grupo !== tabActiva);
      if (!grupo.hidden) visibles += enGrupo;
    });
    vacio.hidden = visibles > 0;
    form.classList.toggle('is-buscando', Boolean(termino));
    tabs.forEach((t) => t.classList.toggle('is-activa', !termino && t.dataset.tab === tabActiva));
  }

  function cantidad(fila) {
    const texto = fila.querySelector('input[name="cantidad"]').value.trim();
    return /^\d+$/.test(texto) ? Number(texto) : (texto ? NaN : 0);
  }

  function actualizar() {
    let productos = 0;
    let unidades = 0;
    let total = 0;
    let validas = true;
    filas.forEach((fila) => {
      const n = cantidad(fila);
      const aviso = fila.querySelector('[data-aviso]');
      const disponible = Number(fila.dataset.disponible);
      fila.classList.toggle('is-elegido', n > 0);
      if (Number.isNaN(n)) {
        aviso.textContent = 'Usa un número entero.';
        validas = false;
        return;
      }
      aviso.textContent = n > disponible ? `Supera lo disponible (${disponible}).` : '';
      if (n > 0) {
        productos += 1;
        unidades += n;
        total += n * Number(fila.dataset.precio);
      }
    });
    resumen.innerHTML = productos
      ? `<strong>${productos}</strong> producto${productos === 1 ? '' : 's'} · ${unidades} unidades · $${pesos.format(total)}`
      : 'Ningún producto seleccionado.';
    boton.disabled = !validas || productos === 0;
    boton.textContent = productos ? `Agregar ${productos} producto${productos === 1 ? '' : 's'}` : 'Agregar productos';
  }

  const lista = form.querySelector('.catalogo__lista');
  tabs.forEach((tab) => tab.addEventListener('click', () => {
    tabActiva = tab.dataset.tab;
    buscar.value = '';
    tabs.forEach((t) => t.setAttribute('aria-selected', t === tab));
    filtrar();
    lista.scrollTop = 0;
  }));
  buscar.addEventListener('input', filtrar);

  form.addEventListener('click', (e) => {
    const fila = e.target.closest('tr[data-producto]');
    if (!fila) return;
    const input = fila.querySelector('input[name="cantidad"]');
    const actual = Number.isNaN(cantidad(fila)) ? 0 : cantidad(fila);
    if (e.target.closest('[data-mas]')) input.value = actual + 1;
    else if (e.target.closest('[data-menos]')) input.value = actual > 1 ? actual - 1 : '';
    else if (e.target.closest('[data-invitados]')) input.value = e.target.closest('[data-invitados]').dataset.invitados;
    else return;
    actualizar();
  });
  form.addEventListener('input', actualizar);
  // Enter en el buscador no envía el formulario.
  buscar.addEventListener('keydown', (e) => { if (e.key === 'Enter') e.preventDefault(); });

  form.addEventListener('submit', () => {
    boton.disabled = true;
    boton.textContent = 'Agregando...';
  });

  filtrar();
  actualizar();
}
