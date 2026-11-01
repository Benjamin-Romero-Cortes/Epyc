// Comportamiento compartido por todas las pantallas del panel
document.addEventListener('DOMContentLoaded', () => {
  initSidebarIcons();
  initSidebarToggle();
  initActiveSidebarLink();
  initGenericModalClosers();
  initSidebarInventoryBadge();
});

function initSidebarIcons() {
  const icons = {
    'Resumen': '<rect x="3" y="3" width="7" height="7" rx="1.3"/><rect x="14" y="3" width="7" height="7" rx="1.3"/><rect x="3" y="14" width="7" height="7" rx="1.3"/><rect x="14" y="14" width="7" height="7" rx="1.3"/>',
    'Clientes': '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M15.5 3.13a4 4 0 0 1 0 7.75"/>',
    'Inventario': '<path d="M12 3l8 4.5v9L12 21l-8-4.5v-9L12 3z"/><path d="M12 12l8-4.5M12 12v9M12 12L4 7.5"/>',
    'Cotizaciones': '<path d="M14 3H6a1 1 0 0 0-1 1v16a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V8l-5-5z"/><path d="M14 3v5h5M9 13h6M9 17h6"/>',
    'Reservas': '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M16 3v4M8 3v4M3 10h18"/>',
    'Preparación de pedidos': '<rect x="6" y="4" width="12" height="17" rx="2"/><rect x="9" y="2" width="6" height="4" rx="1"/><path d="M9 11h6M9 15h6"/>',
    'Despachos': '<rect x="2" y="7" width="13" height="9"/><path d="M15 10h4l3 3v3h-7z"/><circle cx="6.5" cy="18.5" r="1.6"/><circle cx="17.5" cy="18.5" r="1.6"/>',
    'Devoluciones': '<path d="M3 12a9 9 0 1 1 3 6.7"/><path d="M3 17v-5h5"/>',
    'Mermas': '<path d="M12 3l10 18H2L12 3z"/><path d="M12 10v4M12 17h.01"/>',
    'Calendario': '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M16 3v4M8 3v4M3 10h18"/><rect x="7" y="13.3" width="3" height="3" rx=".5" fill="currentColor" stroke="none"/><rect x="14" y="13.3" width="3" height="3" rx=".5" fill="currentColor" stroke="none"/>',
    'Reportes': '<path d="M4 20V10M12 20V4M20 20v-7"/>',
    'Usuarios': '<path d="M12 2l7 3v6c0 5-3.5 8.5-7 10-3.5-1.5-7-5-7-10V5l7-3z"/><circle cx="12" cy="10" r="2.2"/><path d="M8.7 16a3.6 3.6 0 0 1 6.6 0"/>',
    'Configuración': '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.6 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.6a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>',
    'Ver sitio público': '<path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><path d="M15 3h6v6M10 14L21 3"/>',
    'Cerrar sesión': '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><path d="M16 17l5-5-5-5M21 12H9"/>',
  };
  const iconAttributes = 'viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"';

  document.querySelectorAll('.admin-sidebar .sidebar-link').forEach((link) => {
    const label = link.querySelector('.nav-label')?.textContent.trim();
    const paths = icons[label];
    const icon = link.querySelector('.nav-icon');
    if (paths && icon) icon.innerHTML = `<svg ${iconAttributes}>${paths}</svg>`;
  });
}

// Muestra en el ítem "Inventario" del menú la cantidad de productos con stock bajo.
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
  const normalizePath = (path) => path.replace(/\/+$/, '') || '/';
  const currentPath = normalizePath(window.location.pathname);

  document.querySelectorAll('.sidebar-nav .sidebar-link[href]').forEach((link) => {
    const linkPath = normalizePath(new URL(link.href, window.location.origin).pathname);
    const isActive = currentPath === linkPath || (
      linkPath !== '/gestion' && currentPath.startsWith(`${linkPath}/`)
    );

    link.classList.toggle('is-active', isActive);
    if (isActive) link.setAttribute('aria-current', 'page');
    else link.removeAttribute('aria-current');
  });
}

// Cierra cualquier .modal-overlay al hacer clic en su fondo o en [data-close-modal].
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

// Muestra un mensaje breve en la esquina inferior derecha.
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

// Diálogo de confirmación reusable para acciones críticas
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
