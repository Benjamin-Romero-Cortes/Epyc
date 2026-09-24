/**
 * usuarios.js
 * Administración de usuarios internos: listado, alta simulada y
 * activar/desactivar acceso (acción crítica, requiere confirmación).
 */
(function () {
  const tbody = document.getElementById('usr-tbody');
  if (!tbody) return;

  let usuarios = [];

  obtenerDatos('usuarios').then((data) => {
    usuarios = data;
    renderizar();
  }).catch((err) => {
    tbody.innerHTML = '<tr><td colspan="6" class="empty-state">No pudimos cargar los usuarios.</td></tr>';
    console.error(err);
  });

  function renderizar() {
    tbody.innerHTML = usuarios.map((u) => `
      <tr>
        <td>
          <div style="display:flex;align-items:center;gap:0.7rem;">
            <div class="avatar-sm">${iniciales(u.nombre)}</div>
            <span class="cell-strong">${u.nombre}</span>
          </div>
        </td>
        <td>${u.correo}</td>
        <td>${u.rol}</td>
        <td>${u.ultimoAcceso}</td>
        <td>${badgeHtml(u.estado)}</td>
        <td><button class="btn btn-ghost btn-sm" data-toggle="${u.id}">${u.estado === 'Activo' ? 'Desactivar' : 'Activar'}</button></td>
      </tr>
    `).join('');

    tbody.querySelectorAll('[data-toggle]').forEach((btn) => {
      btn.addEventListener('click', () => toggleEstado(Number(btn.dataset.toggle)));
    });
  }

  async function toggleEstado(id) {
    const u = usuarios.find((x) => x.id === id);
    const activando = u.estado !== 'Activo';
    const ok = await confirmarAccion({
      titulo: activando ? 'Activar usuario' : 'Desactivar usuario',
      mensaje: `¿Confirmas ${activando ? 'activar' : 'desactivar'} el acceso de "${u.nombre}" al panel?`,
      textoConfirmar: activando ? 'Activar' : 'Desactivar',
      peligroso: !activando,
    });
    if (!ok) return;
    u.estado = activando ? 'Activo' : 'Inactivo';
    mostrarToast(`Usuario "${u.nombre}" ${activando ? 'activado' : 'desactivado'}.`);
    renderizar();
  }

  const modal = document.getElementById('modal-nuevo-usuario');
  document.getElementById('btn-nuevo-usuario').addEventListener('click', () => abrirModal(modal));
  document.getElementById('form-nuevo-usuario').addEventListener('submit', (e) => {
    e.preventDefault();
    const nombre = document.getElementById('nu-nombre').value.trim();
    usuarios.unshift({
      id: Date.now(),
      nombre,
      correo: document.getElementById('nu-correo').value.trim(),
      rol: document.getElementById('nu-rol').value,
      estado: 'Activo',
      ultimoAcceso: '—',
    });
    mostrarToast(`Usuario "${nombre}" creado.`);
    e.target.reset();
    cerrarModal(modal);
    renderizar();
  });
})();
