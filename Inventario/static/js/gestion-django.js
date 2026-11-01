// Abre los modales del panel desde sus botones y con ?editar=1 en la URL.
document.addEventListener('DOMContentLoaded', () => {
  const MODALES = {
    'btn-nuevo-cliente': 'modal-nuevo-cliente',
    'btn-editar-cliente': 'modal-editar-cliente',
    'btn-nuevo-producto': 'modal-nuevo-producto',
    'btn-editar-producto': 'modal-editar-producto',
    'btn-nueva-cotizacion': 'modal-nueva-cotizacion',
    'btn-nueva-merma': 'modal-nueva-merma',
    'btn-nuevo-usuario': 'modal-nuevo-usuario',
  };

  const abrir = (modal) => {
    modal.hidden = false;
    modal.querySelector('input:not([type=hidden]), select, textarea')?.focus();
  };

  Object.entries(MODALES).forEach(([botonId, modalId]) => {
    const boton = document.getElementById(botonId);
    const modal = document.getElementById(modalId);
    if (boton && modal) boton.addEventListener('click', () => abrir(modal));
  });

  if (new URLSearchParams(window.location.search).has('editar')) {
    const modal = document.getElementById('modal-editar-producto') || document.getElementById('modal-editar-cliente');
    if (modal) abrir(modal);
  }

  // Si el stock trabajable iba igual al total, lo sigue al cambiar el total.
  const total = document.querySelector('[name=stock_total]');
  const trabajable = document.querySelector('[name=stock_trabajable]');
  if (total && trabajable) {
    let anterior = total.value;
    total.addEventListener('input', () => {
      if (trabajable.value === anterior || trabajable.value === '') trabajable.value = total.value;
      anterior = total.value;
    });
  }
});
