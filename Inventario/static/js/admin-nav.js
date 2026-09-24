/**
 * admin-nav.js
 * Comportamiento compartido por todas las pantallas del panel: apertura
 * del menú lateral en pantallas angostas, resaltado del enlace activo,
 * y utilidades reusables de UI (toast de confirmación y diálogo de
 * confirmación para acciones críticas como eliminar, cancelar, etc.).
 */
document.addEventListener('DOMContentLoaded', () => {
  initSidebarToggle();
  initActiveSidebarLink();
  initGenericModalClosers();
  initSidebarInventoryBadge();
});

/** Muestra en el ítem "Inventario" del menú la cantidad de productos con stock bajo. */
function initSidebarInventoryBadge() {
  const badge = document.getElementById('badge-inventario');
  if (!badge || typeof obtenerDatos === 'undefined') return;
  obtenerDatos('inventario').then((inventario) => {
    const count = inventario.filter((p) => p.estado === 'Stock bajo').length;
    if (count > 0) { badge.textContent = count; badge.hidden = false; }
  }).catch(() => {});
}

function initSidebarToggle() {
  const toggle = document.getElementById('sidebar-toggle');
  const sidebar = document.querySelector('.admin-sidebar');
  if (!toggle || !sidebar) return;
  toggle.addEventListener('click', () => sidebar.classList.toggle('is-open'));
  document.addEventListener('click', (e) => {
    if (sidebar.classList.contains('is-open') && !sidebar.contains(e.target) && e.target !== toggle && !toggle.contains(e.target)) {
      sidebar.classList.remove('is-open');
    }
  });
}

function initActiveSidebarLink() {
  const current = window.location.pathname.split('/').pop() || 'index.html';
  document.querySelectorAll('.sidebar-link[href]').forEach((link) => {
    const href = link.getAttribute('href').split('?')[0];
    if (href === current) link.classList.add('is-active');
  });
}

/** Cierra cualquier .modal-overlay al hacer clic en su fondo o en [data-close-modal]. */
function initGenericModalClosers() {
  document.querySelectorAll('.modal-overlay').forEach((overlay) => {
    overlay.addEventListener('click', (e) => {
      if (e.target === overlay) cerrarModal(overlay);
    });
  });
  document.querySelectorAll('[data-close-modal]').forEach((btn) => {
    btn.addEventListener('click', () => cerrarModal(btn.closest('.modal-overlay')));
  });
}

function abrirModal(idOrEl) {
  const el = typeof idOrEl === 'string' ? document.getElementById(idOrEl) : idOrEl;
  if (el) el.hidden = false;
}

function cerrarModal(idOrEl) {
  const el = typeof idOrEl === 'string' ? document.getElementById(idOrEl) : idOrEl;
  if (el) el.hidden = true;
}

/** Muestra un mensaje breve en la esquina inferior derecha. */
function mostrarToast(mensaje) {
  let toast = document.getElementById('admin-toast');
  if (!toast) {
    toast = document.createElement('div');
    toast.id = 'admin-toast';
    toast.className = 'toast';
    toast.innerHTML = '<span class="icon">✓</span><span class="toast-text"></span>';
    document.body.appendChild(toast);
  }
  toast.querySelector('.toast-text').textContent = mensaje;
  toast.classList.add('is-visible');
  clearTimeout(toast._timeout);
  toast._timeout = setTimeout(() => toast.classList.remove('is-visible'), 3200);
}

/**
 * Diálogo de confirmación reusable para acciones críticas (cancelar
 * reserva, eliminar producto, finalizar devolución, etc.). Devuelve una
 * Promise<boolean> con la decisión del usuario.
 */
function confirmarAccion({ titulo, mensaje, textoConfirmar = 'Confirmar', peligroso = false }) {
  return new Promise((resolve) => {
    let overlay = document.getElementById('confirm-overlay');
    if (!overlay) {
      overlay = document.createElement('div');
      overlay.id = 'confirm-overlay';
      overlay.className = 'modal-overlay';
      overlay.hidden = true;
      overlay.innerHTML = `
        <div class="modal-panel confirm-panel">
          <div class="icon-lg">!</div>
          <h2 id="confirm-title"></h2>
          <p id="confirm-message"></p>
          <div class="modal-actions">
            <button class="btn btn-outline" id="confirm-cancel-btn">Cancelar</button>
            <button class="btn btn-primary" id="confirm-ok-btn"></button>
          </div>
        </div>`;
      document.body.appendChild(overlay);
    }

    overlay.querySelector('#confirm-title').textContent = titulo;
    overlay.querySelector('#confirm-message').textContent = mensaje;
    const okBtn = overlay.querySelector('#confirm-ok-btn');
    okBtn.textContent = textoConfirmar;
    okBtn.className = 'btn ' + (peligroso ? 'btn-danger-outline' : 'btn-primary');

    const cleanup = (result) => {
      overlay.hidden = true;
      okBtn.replaceWith(okBtn.cloneNode(true));
      cancelBtn.replaceWith(cancelBtn.cloneNode(true));
      resolve(result);
    };

    let cancelBtn = overlay.querySelector('#confirm-cancel-btn');
    overlay.hidden = false;
    overlay.querySelector('#confirm-ok-btn').addEventListener('click', () => cleanup(true), { once: true });
    overlay.querySelector('#confirm-cancel-btn').addEventListener('click', () => cleanup(false), { once: true });
  });
}
