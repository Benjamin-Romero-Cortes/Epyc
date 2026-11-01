// Pide confirmación antes de enviar cualquier formulario de eliminación de cliente
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('form[data-confirm-delete]').forEach((form) => {
    form.addEventListener('submit', async (e) => {
      if (form.dataset.confirmado) return;
      e.preventDefault();

      const nombre = form.dataset.confirmDelete.trim() || 'este cliente';
      const opciones = {
        titulo: 'Eliminar cliente',
        mensaje: `¿Seguro que quieres eliminar a ${nombre}? Esta acción no se puede deshacer.`,
        textoConfirmar: 'Eliminar',
        peligroso: true,
      };

      const ok = typeof confirmarAccion === 'function'
        ? await confirmarAccion(opciones)
        : window.confirm(opciones.mensaje);

      if (ok) {
        form.dataset.confirmado = '1';
        form.submit();
      }
    });
  });

  const btnNuevo = document.getElementById('btn-nuevo-cliente');
  const modalNuevo = document.getElementById('modal-nuevo-cliente');
  if (btnNuevo && modalNuevo) {
    btnNuevo.addEventListener('click', () => {
      modalNuevo.hidden = false;
      const primerCampo = modalNuevo.querySelector('input[name="nombre"]');
      if (primerCampo) primerCampo.focus();
    });
  }

  const btnEditar = document.getElementById('btn-editar-cliente');
  const modalEditar = document.getElementById('modal-editar-cliente');
  if (btnEditar && modalEditar) {
    btnEditar.addEventListener('click', () => { modalEditar.hidden = false; });
    // Desde el listado se llega con ?editar=1 para abrir la edición directo.
    if (new URLSearchParams(window.location.search).has('editar')) {
      modalEditar.hidden = false;
    }
  }
});
