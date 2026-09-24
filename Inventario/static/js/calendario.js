/**
 * calendario.js
 * Calendario de eventos/entregas/retiros con vistas mensual, semanal y
 * diaria, construidas a partir de las fechas de cada reserva
 * (fechaEvento, fechaDespacho, fechaRetiro).
 */
(function () {
  const contenido = document.getElementById('cal-contenido');
  if (!contenido) return;

  const MESES = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'];
  const DOW = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom'];

  let reservas = [];
  let eventos = [];
  let vista = 'mes';
  let fechaRef = new Date('2026-08-19T00:00:00');

  obtenerDatos('reservas').then((data) => {
    reservas = data;
    eventos = construirEventos(reservas);
    render();
  }).catch((err) => {
    contenido.innerHTML = '<p class="empty-state">No pudimos cargar el calendario.</p>';
    console.error(err);
  });

  function construirEventos(reservas) {
    const lista = [];
    reservas.forEach((r) => {
      if (r.estado === 'Cancelada') return;
      lista.push({ fecha: r.fechaEvento, tipo: 'evento', reserva: r });
      lista.push({ fecha: r.fechaDespacho, tipo: 'entrega', reserva: r });
      lista.push({ fecha: r.fechaRetiro, tipo: 'retiro', reserva: r });
    });
    return lista;
  }

  function iso(d) { return d.toISOString().slice(0, 10); }

  document.querySelectorAll('.view-toggle button').forEach((btn) => {
    btn.addEventListener('click', () => {
      vista = btn.dataset.vista;
      document.querySelectorAll('.view-toggle button').forEach((b) => b.classList.toggle('is-active', b === btn));
      render();
    });
  });
  document.getElementById('cal-hoy').addEventListener('click', () => { fechaRef = new Date('2026-08-19T00:00:00'); render(); });
  document.getElementById('cal-prev').addEventListener('click', () => { mover(-1); });
  document.getElementById('cal-next').addEventListener('click', () => { mover(1); });

  function mover(dir) {
    const d = new Date(fechaRef);
    if (vista === 'mes') d.setMonth(d.getMonth() + dir);
    else if (vista === 'semana') d.setDate(d.getDate() + dir * 7);
    else d.setDate(d.getDate() + dir);
    fechaRef = d;
    render();
  }

  function eventosDe(fechaIso) {
    return eventos.filter((e) => e.fecha === fechaIso);
  }

  function render() {
    if (vista === 'mes') renderMes();
    else if (vista === 'semana') renderSemana();
    else renderDia();
  }

  function renderMes() {
    document.getElementById('cal-titulo').textContent = `${MESES[fechaRef.getMonth()]} ${fechaRef.getFullYear()}`;
    const primerDia = new Date(fechaRef.getFullYear(), fechaRef.getMonth(), 1);
    const offset = (primerDia.getDay() + 6) % 7; // lunes=0
    const inicio = new Date(primerDia);
    inicio.setDate(inicio.getDate() - offset);

    let celdas = '';
    for (let i = 0; i < 42; i++) {
      const d = new Date(inicio);
      d.setDate(d.getDate() + i);
      const fechaIso = iso(d);
      const fueraDeMes = d.getMonth() !== fechaRef.getMonth();
      const esHoy = fechaIso === '2026-08-19';
      const evs = eventosDe(fechaIso);

      celdas += `
        <div class="cal-cell ${fueraDeMes ? 'is-outside' : ''} ${esHoy ? 'is-today' : ''}">
          <span class="cal-daynum">${d.getDate()}</span>
          ${evs.slice(0, 3).map((e) => `<a href="reserva.html?id=${e.reserva.id}" class="cal-event cal-event--${e.tipo}" title="${e.reserva.clienteNombre}">${e.reserva.clienteNombre}</a>`).join('')}
          ${evs.length > 3 ? `<span class="cal-event" style="opacity:0.6;">+${evs.length - 3} más</span>` : ''}
        </div>
      `;
    }

    contenido.innerHTML = `
      <div class="cal-grid">
        ${DOW.map((d) => `<div class="cal-dow">${d}</div>`).join('')}
        ${celdas}
      </div>
    `;
  }

  function renderSemana() {
    const offset = (fechaRef.getDay() + 6) % 7;
    const inicio = new Date(fechaRef);
    inicio.setDate(inicio.getDate() - offset);
    const fin = new Date(inicio);
    fin.setDate(fin.getDate() + 6);
    document.getElementById('cal-titulo').textContent = `Semana del ${inicio.getDate()} al ${fin.getDate()} de ${MESES[fin.getMonth()]}`;

    let dias = '';
    for (let i = 0; i < 7; i++) {
      const d = new Date(inicio);
      d.setDate(d.getDate() + i);
      const fechaIso = iso(d);
      const evs = eventosDe(fechaIso);
      dias += `
        <div class="card" style="flex:1;min-width:160px;">
          <strong style="display:block;margin-bottom:0.5rem;">${DOW[i]} ${d.getDate()}</strong>
          ${evs.length ? evs.map((e) => `<a href="reserva.html?id=${e.reserva.id}" class="cal-event cal-event--${e.tipo}" style="margin-bottom:0.3rem;">${e.reserva.clienteNombre}</a>`).join('') : '<span class="cell-muted" style="font-size:0.8rem;">Sin eventos</span>'}
        </div>
      `;
    }
    contenido.innerHTML = `<div style="display:flex;gap:0.6rem;flex-wrap:wrap;">${dias}</div>`;
  }

  function renderDia() {
    const fechaIso = iso(fechaRef);
    document.getElementById('cal-titulo').textContent = `${fechaRef.getDate()} de ${MESES[fechaRef.getMonth()]} de ${fechaRef.getFullYear()}`;
    const evs = eventosDe(fechaIso);
    contenido.innerHTML = `
      <div class="card agenda-list">
        ${evs.length ? evs.map((e) => `
          <a href="reserva.html?id=${e.reserva.id}" class="list-row">
            <span class="cal-event cal-event--${e.tipo}" style="width:90px;text-align:center;flex-shrink:0;">${e.tipo}</span>
            <div class="list-row-body">
              <strong>${e.reserva.id} · ${e.reserva.clienteNombre}</strong>
              <span>${e.reserva.tipoEvento} · ${e.reserva.comuna}</span>
            </div>
            ${badgeHtml(e.reserva.estado)}
          </a>
        `).join('') : '<p class="empty-state">Sin eventos programados este día.</p>'}
      </div>
    `;
  }
})();
