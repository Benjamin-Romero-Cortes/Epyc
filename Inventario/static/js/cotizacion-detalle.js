/**
 * cotizacion-detalle.js
 * Documento de la cotización (formato imprimible) más la barra de
 * acciones: editar, descargar, enviar, compartir, aceptar y convertir
 * en reserva. "Descargar" usa la función de impresión del navegador
 * (Guardar como PDF), ya que no hay backend para generar el archivo.
 */
(function () {
  const contenedor = document.getElementById('cotizacion-detalle');
  if (!contenedor) return;

  const id = new URLSearchParams(window.location.search).get('id');

  cargarCotizaciones().then((cotizaciones) => {
    const cot = cotizaciones.find((c) => c.id === id);
    if (!cot) {
      contenedor.innerHTML = `<p class="empty-state">No encontramos esta cotización. <a href="cotizaciones.html">Volver a cotizaciones</a>.</p>`;
      return;
    }
    document.title = `${cot.id} · Panel Entre Platos y Copas`;
    Promise.all([obtenerDatos('clientes'), obtenerDatos('reservas')]).then(([clientes, reservas]) => {
      const cliente = clientes.find((c) => c.id === cot.clienteId);
      renderAcciones(cot, reservas);
      renderDocumento(cot, cliente);
    });
  }).catch((err) => {
    contenedor.innerHTML = '<p class="empty-state">No pudimos cargar la cotización.</p>';
    console.error(err);
  });

  /** Las cotizaciones recién creadas en el modal viajan por sessionStorage
   *  (viven solo en memoria); si existen, tienen prioridad sobre los datos base. */
  function cargarCotizaciones() {
    const temp = sessionStorage.getItem('epyc_admin_cotizaciones_temp');
    if (temp) return Promise.resolve(JSON.parse(temp));
    return obtenerDatos('cotizaciones');
  }

  function fechaValidoHasta(fechaCreacion) {
    const d = new Date(fechaCreacion + 'T00:00:00');
    d.setDate(d.getDate() + 10);
    return d.toISOString().slice(0, 10);
  }

  function renderAcciones(cot, reservas) {
    const wrap = document.getElementById('doc-actions');
    const tieneReserva = reservas.some((r) => r.cotizacionId === cot.id);
    const botones = [
      { label: '✎ Editar', cls: 'btn-outline', accion: 'editar' },
      { label: '⬇ Descargar documento', cls: 'btn-outline', accion: 'descargar' },
      { label: '✉ Enviar por correo', cls: 'btn-outline', accion: 'enviar' },
      { label: '↗ Compartir', cls: 'btn-outline', accion: 'compartir' },
    ];
    if (!['Aceptada', 'Rechazada'].includes(cot.estado)) {
      botones.push({ label: '✓ Aceptar cotización', cls: 'btn-primary', accion: 'aceptar' });
    }
    if (cot.estado === 'Aceptada' && !tieneReserva) {
      botones.push({ label: '→ Convertir en reserva', cls: 'btn-accent', accion: 'convertir' });
    }
    if (tieneReserva) {
      const r = reservas.find((rr) => rr.cotizacionId === cot.id);
      botones.push({ label: `Ver reserva ${r.id} →`, cls: 'btn-ghost', accion: 'ver-reserva', reservaId: r.id });
    }

    wrap.innerHTML = botones.map((b) => `<button class="btn ${b.cls} btn-sm" data-accion="${b.accion}" ${b.reservaId ? `data-reserva="${b.reservaId}"` : ''}>${b.label}</button>`).join('');

    wrap.querySelectorAll('[data-accion]').forEach((btn) => {
      btn.addEventListener('click', () => manejarAccion(btn.dataset.accion, cot, btn.dataset.reserva));
    });
  }

  async function manejarAccion(accion, cot, reservaId) {
    if (accion === 'descargar') { window.print(); return; }
    if (accion === 'enviar') { mostrarToast(`Cotización ${cot.id} enviada por correo (simulado).`); return; }
    if (accion === 'compartir') {
      if (navigator.share) { navigator.share({ title: cot.id, url: window.location.href }).catch(() => {}); }
      else mostrarToast('Enlace de la cotización copiado (simulado).');
      return;
    }
    if (accion === 'editar') { window.location.href = `cotizaciones.html?editar=${cot.id}`; return; }
    if (accion === 'ver-reserva') { window.location.href = `reserva.html?id=${reservaId}`; return; }

    if (accion === 'aceptar') {
      const ok = await confirmarAccion({ titulo: 'Aceptar cotización', mensaje: `¿Confirmas que "${cot.clienteNombre}" aceptó la cotización ${cot.id}?`, textoConfirmar: 'Aceptar cotización' });
      if (!ok) return;
      cot.estado = 'Aceptada';
      mostrarToast(`Cotización ${cot.id} marcada como aceptada.`);
      location.reload();
    }

    if (accion === 'convertir') {
      const ok = await confirmarAccion({ titulo: 'Convertir en reserva', mensaje: `Se creará una nueva reserva a partir de la cotización ${cot.id} para "${cot.clienteNombre}".`, textoConfirmar: 'Crear reserva' });
      if (!ok) return;
      mostrarToast(`Reserva creada a partir de ${cot.id} (simulado).`);
    }
  }

  function renderDocumento(cot, cliente) {
    const subtotal = cot.subtotal != null ? cot.subtotal : (cot.lineas || []).reduce((s, l) => s + l.precio * l.cantidad, 0);
    const iva = cot.iva != null ? cot.iva : Math.round((subtotal + (cot.transporte || 0) - (cot.descuento || 0)) * 0.19);
    const garantia = cot.garantia || 0;
    const total = (cot.monto || 0) + garantia;

    contenedor.innerHTML = `
      <div class="doc-viewer-toolbar no-print">Vista previa del documento · ${cot.id}</div>
      <div class="doc-page">
        <div class="doc-head">
          <div>
            <h2>Entre Platos y Copas</h2>
            <span class="tagline">Arriendo para eventos</span>
          </div>
          <div class="doc-meta">
            <span class="label">Cotización</span>
            <strong>${cot.id}</strong>
            ${badgeHtml(cot.estado)}
          </div>
        </div>

        <div class="doc-grid">
          <div>
            <div class="label">Cliente</div>
            <strong style="display:block;font-size:1rem;">${cot.clienteNombre}</strong>
            ${cliente ? `${cliente.rut} · ${cliente.correo}<br>${cliente.telefono}` : ''}
          </div>
          <div style="text-align:right;">
            <div class="label">Emisión</div>
            <strong style="display:block;">${formatearFechaLarga(cot.fechaCreacion)}</strong>
            <div class="label" style="margin-top:0.5rem;">Válida hasta</div>
            <strong style="display:block;">${formatearFechaLarga(fechaValidoHasta(cot.fechaCreacion))}</strong>
          </div>
        </div>

        <div class="doc-event-box">
          <div>
            <div class="label">Evento</div>
            <strong style="display:block;font-size:1.02rem;">${cot.tipoEvento}${cot.invitados ? ` · ${cot.invitados} invitados` : ''}</strong>
            <span>${formatearFechaLarga(cot.fechaEvento)}${cot.horario ? `, ${cot.horario}` : ''}</span>
          </div>
          <div style="text-align:right;">
            <strong style="display:block;">${cot.venue || cot.comuna || 'Por confirmar'}</strong>
            ${cot.direccion && cot.direccion !== cot.venue ? `<span>${cot.direccion}</span>` : (cot.venue && cot.comuna ? `<span>${cot.comuna}</span>` : '')}
          </div>
        </div>

        <table class="doc-table">
          <thead><tr><th>Descripción</th><th class="num">Cant.</th><th class="num">Unitario</th><th class="num">Total</th></tr></thead>
          <tbody>
            ${(cot.lineas || []).map((l) => `
              <tr>
                <td>${l.nombre}<span class="item-note">Arriendo por evento</span></td>
                <td class="num">${l.cantidad}</td>
                <td class="num">${formatearMoneda(l.precio)}</td>
                <td class="num cell-strong">${formatearMoneda(l.precio * l.cantidad)}</td>
              </tr>
            `).join('')}
            ${cot.transporte ? `
              <tr>
                <td>Despacho y retiro</td>
                <td class="num">1</td>
                <td class="num">${formatearMoneda(cot.transporte)}</td>
                <td class="num cell-strong">${formatearMoneda(cot.transporte)}</td>
              </tr>` : ''}
          </tbody>
        </table>

        <div class="doc-totals">
          <div class="line"><span>Subtotal</span><span>${formatearMoneda(subtotal + (cot.transporte || 0))}</span></div>
          <div class="line"><span>Descuento</span><span>-${formatearMoneda(cot.descuento || 0)}</span></div>
          <div class="line"><span>IVA (19%)</span><span>${formatearMoneda(iva)}</span></div>
          ${garantia ? `<div class="line"><span>Garantía reembolsable</span><span>${formatearMoneda(garantia)}</span></div>` : ''}
          <div class="line total"><span>TOTAL</span><span>${formatearMoneda(total)}</span></div>
        </div>

        ${garantia ? `<p style="text-align:right;font-size:0.8rem;opacity:0.7;margin-top:0.4rem;">Incluye garantía reembolsable de ${formatearMoneda(garantia)}, devuelta tras la revisión post-evento.</p>` : ''}

        <div class="doc-notes">
          ${cot.observaciones ? `<p class="label">Notas</p><p>${cot.observaciones}</p>` : ''}
          <p class="label">Condiciones</p>
          <ol>
            <li>La cotización mantiene sus valores hasta la fecha de vigencia indicada.</li>
            <li>La reserva se confirma con la aceptación y el abono acordado.</li>
            <li>Pérdidas o daños se valorizan según el costo de reposición vigente.</li>
          </ol>
        </div>

        <div class="doc-footer">
          <span>Entre Platos y Copas · Arriendo de implementos para eventos</span>
          <span>Página 1 de 1</span>
        </div>
      </div>
    `;
  }
})();
