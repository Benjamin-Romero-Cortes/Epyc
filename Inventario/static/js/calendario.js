// Calendario del panel con vistas mes, semana y día al estilo Google Calendar.
document.addEventListener('DOMContentLoaded', () => {
  const contenedor = document.getElementById('cal-contenido');
  const datos = document.getElementById('cal-eventos');
  if (!contenedor || !datos) return;

  const titulo = document.getElementById('cal-titulo');
  const pop = document.getElementById('cal-pop');
  const botonesVista = document.querySelectorAll('[data-vista]');

  const ALTO_HORA = 48;
  const MAX_CHIPS_MES = 3;
  const ETIQUETA_TIPO = { evento: 'Evento', entrega: 'Entrega', retiro: 'Devolución recibida', devolucion: 'Devolución esperada' };
  const svg = (trazo) => `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">${trazo}</svg>`;
  const ICONOS = {
    codigo: svg('<path d="M4 9h16M4 15h16M10 3 8 21M16 3l-2 18"/>'),
    estado: svg('<circle cx="12" cy="12" r="8"/><path d="m8.5 12 2.5 2.5 4.5-5"/>'),
    cliente: svg('<circle cx="12" cy="8" r="4"/><path d="M4 21c1.5-4 4.5-6 8-6s6.5 2 8 6"/>'),
    lugar: svg('<path d="M12 21s-7-6.2-7-12a7 7 0 0 1 14 0c0 5.8-7 12-7 12z"/><circle cx="12" cy="9" r="2.5"/>'),
    personas: svg('<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20c1-3.5 3.5-5 6.5-5s5.5 1.5 6.5 5"/><path d="M16 4.5a3.5 3.5 0 0 1 0 7M18 15c2 .6 3.2 2.3 3.8 5"/>'),
  };

  const aFecha = (iso) => {
    const [a, m, d] = iso.split('-').map(Number);
    return new Date(a, m - 1, d);
  };
  const clave = (f) => `${f.getFullYear()}-${String(f.getMonth() + 1).padStart(2, '0')}-${String(f.getDate()).padStart(2, '0')}`;
  const sumarDias = (f, n) => new Date(f.getFullYear(), f.getMonth(), f.getDate() + n);
  const inicioSemana = (f) => sumarDias(f, -((f.getDay() + 6) % 7)); // semanas de lunes a domingo
  const minutos = (hora) => {
    const [h, m] = hora.split(':').map(Number);
    return h * 60 + m;
  };
  const escapar = (texto) => String(texto ?? '').replace(/[&<>"']/g, (c) => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
  ));
  const fmt = (opciones) => new Intl.DateTimeFormat('es-CL', opciones);
  const fmtMes = fmt({ month: 'long', year: 'numeric' });
  const fmtDiaLargo = fmt({ weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });
  const fmtDiaSemana = fmt({ weekday: 'short' });
  const fmtCorto = fmt({ day: 'numeric', month: 'short' });
  const capitalizar = (t) => t.charAt(0).toUpperCase() + t.slice(1);

  const eventos = JSON.parse(datos.textContent).map((e, i) => ({
    ...e,
    id: i,
    desde: aFecha(e.inicio),
    hasta: aFecha(e.fin),
  }));
  // Con hora y en un solo día se dibuja en la grilla horaria; el resto va en "todo el día".
  const conHora = (e) => Boolean(e.hora_inicio) && e.inicio === e.fin;

  const hoy = new Date();
  const hoyClave = clave(hoy);

  let vista = 'mes';
  try { vista = localStorage.getItem('cal-vista') || 'mes'; } catch (e) { /* sin almacenamiento */ }
  if (!['mes', 'semana', 'dia'].includes(vista)) vista = 'mes';
  let fecha = new Date(hoy.getFullYear(), hoy.getMonth(), hoy.getDate());

  function eventosDelDia(dia) {
    return eventos
      .filter((e) => e.desde <= dia && dia <= e.hasta)
      .sort((a, b) => {
        const ah = conHora(a), bh = conHora(b);
        if (ah !== bh) return ah ? 1 : -1;
        return (a.hora_inicio || '').localeCompare(b.hora_inicio || '') || a.titulo.localeCompare(b.titulo);
      });
  }

  const TEXTO_ABRIR = { evento: 'Abrir', entrega: 'Ver despacho', retiro: 'Ver devolución', devolucion: 'Registrar o ver devolución' };

  function claseChip(e) {
    return `tipo-${e.tipo}${e.tentativo ? ' is-tentativo' : ''}${e.atrasado ? ' is-atrasado' : ''}`;
  }

  function chip(e) {
    const hora = conHora(e);
    return `<button type="button" class="gcal-chip ${claseChip(e)}${hora ? ' gcal-chip--timed' : ''}" data-evento="${e.id}" title="${escapar(e.titulo)}">`
      + `${hora ? `<span class="t">${e.hora_inicio}</span>` : ''}${escapar(e.titulo)}</button>`;
  }

  // VISTA MES
  function renderMes() {
    const primero = new Date(fecha.getFullYear(), fecha.getMonth(), 1);
    const ultimo = new Date(fecha.getFullYear(), fecha.getMonth() + 1, 0);
    const desde = inicioSemana(primero);
    const semanas = Math.ceil((ultimo - desde) / 86400000 / 7 + 1 / 7);

    let html = '<div class="gcal-month">';
    for (let i = 0; i < 7; i += 1) {
      html += `<div class="gcal-dow">${fmtDiaSemana.format(sumarDias(desde, i)).replace('.', '')}</div>`;
    }
    for (let i = 0; i < semanas * 7; i += 1) {
      const dia = sumarDias(desde, i);
      const delDia = eventosDelDia(dia);
      const visibles = delDia.length > MAX_CHIPS_MES ? delDia.slice(0, MAX_CHIPS_MES - 1) : delDia;
      const clases = ['gcal-day'];
      if (dia.getMonth() !== fecha.getMonth()) clases.push('is-outside');
      if (clave(dia) === hoyClave) clases.push('is-today');
      html += `<div class="${clases.join(' ')}">`
        + `<button type="button" class="gcal-num" data-ir-dia="${clave(dia)}" aria-label="${escapar(fmtDiaLargo.format(dia))}">${dia.getDate()}</button>`
        + visibles.map(chip).join('')
        + (delDia.length > visibles.length
          ? `<button type="button" class="gcal-more" data-ir-dia="${clave(dia)}">${delDia.length - visibles.length} más</button>`
          : '')
        + '</div>';
    }
    contenedor.innerHTML = `${html}</div>`;
    titulo.textContent = capitalizar(fmtMes.format(fecha));
  }

  // VISTAS SEMANA Y DÍA
  // Reparte en columnas los eventos que se superponen, como hace Google Calendar.
  function distribuir(lista) {
    const items = lista.map((e) => {
      const ini = minutos(e.hora_inicio);
      const fin = e.hora_fin && minutos(e.hora_fin) > ini ? minutos(e.hora_fin) : ini + 60;
      return { e, ini, fin: Math.max(fin, ini + 30) };
    }).sort((a, b) => a.ini - b.ini || b.fin - a.fin);

    const grupos = [];
    let grupo = [];
    let finGrupo = -1;
    items.forEach((it) => {
      if (it.ini >= finGrupo && grupo.length) { grupos.push(grupo); grupo = []; }
      grupo.push(it);
      finGrupo = Math.max(finGrupo, it.fin);
    });
    if (grupo.length) grupos.push(grupo);

    grupos.forEach((g) => {
      const columnas = [];
      g.forEach((it) => {
        let col = columnas.findIndex((finCol) => finCol <= it.ini);
        if (col === -1) { col = columnas.length; columnas.push(0); }
        columnas[col] = it.fin;
        it.col = col;
      });
      g.forEach((it) => { it.cols = columnas.length; });
    });
    return items;
  }

  function renderGrilla(dias) {
    const cols = dias.length;
    let cabecera = `<div class="gcal-week" style="--cols:${cols}"><div></div>`;
    let todoElDia = '<div class="gcal-allday-label">Todo el día</div>';
    let columnas = '';

    dias.forEach((dia) => {
      const esHoy = clave(dia) === hoyClave;
      const delDia = eventosDelDia(dia);
      cabecera += `<div class="gcal-colhead${esHoy ? ' is-today' : ''}">`
        + `<div class="dow">${fmtDiaSemana.format(dia).replace('.', '')}</div>`
        + `<button type="button" class="gcal-bignum" data-ir-dia="${clave(dia)}">${dia.getDate()}</button></div>`;
      todoElDia += `<div class="gcal-allday">${delDia.filter((e) => !conHora(e)).map(chip).join('')}</div>`;

      const bloques = distribuir(delDia.filter(conHora)).map((it) => {
        const ancho = 100 / it.cols;
        const alto = Math.max(((it.fin - it.ini) / 60) * ALTO_HORA - 2, 20);
        const rango = it.e.hora_fin ? `${it.e.hora_inicio} – ${it.e.hora_fin}` : it.e.hora_inicio;
        return `<button type="button" class="gcal-timed ${claseChip(it.e)}" data-evento="${it.e.id}"`
          + ` style="top:${(it.ini / 60) * ALTO_HORA}px;height:${alto}px;left:calc(${it.col * ancho}% + 2px);width:calc(${ancho}% - 6px)">`
          + `<strong>${escapar(it.e.titulo)}</strong>${alto > 30 ? `<span>${rango}</span>` : ''}</button>`;
      }).join('');
      const ahora = esHoy
        ? `<div class="gcal-now" style="top:${((hoy.getHours() * 60 + hoy.getMinutes()) / 60) * ALTO_HORA}px"></div>`
        : '';
      columnas += `<div class="gcal-col">${bloques}${ahora}</div>`;
    });

    let horas = '<div class="gcal-hours">';
    for (let h = 0; h < 24; h += 1) horas += `<div>${String(h).padStart(2, '0')}:00</div>`;
    horas += '</div>';

    contenedor.innerHTML = `<div class="gcal-head">${cabecera}${todoElDia}</div></div>`
      + `<div class="gcal-scroll"><div class="gcal-week" style="--cols:${cols}">${horas}${columnas}</div></div>`;

    // Como Google: abre la grilla a las 8:00 o en el primer evento con hora si es antes.
    const primeraHora = Math.min(8, ...dias.flatMap((d) => eventosDelDia(d).filter(conHora).map((e) => Math.floor(minutos(e.hora_inicio) / 60))));
    contenedor.querySelector('.gcal-scroll').scrollTop = Math.max(0, primeraHora - 0.5) * ALTO_HORA;
  }

  function renderSemana() {
    const lunes = inicioSemana(fecha);
    const domingo = sumarDias(lunes, 6);
    renderGrilla(Array.from({ length: 7 }, (_, i) => sumarDias(lunes, i)));
    titulo.textContent = lunes.getMonth() === domingo.getMonth()
      ? `${lunes.getDate()} – ${domingo.getDate()} de ${fmtMes.format(domingo)}`
      : `${fmtCorto.format(lunes)} – ${fmtCorto.format(domingo)} ${domingo.getFullYear()}`;
  }

  function renderDia() {
    renderGrilla([fecha]);
    titulo.textContent = capitalizar(fmtDiaLargo.format(fecha));
  }

  function render() {
    cerrarPop();
    botonesVista.forEach((b) => b.classList.toggle('is-active', b.dataset.vista === vista));
    if (vista === 'mes') renderMes();
    else if (vista === 'semana') renderSemana();
    else renderDia();
  }

  function cambiarVista(nueva) {
    vista = nueva;
    try { localStorage.setItem('cal-vista', vista); } catch (e) { /* sin almacenamiento */ }
    render();
  }

  function mover(sentido) {
    if (vista === 'mes') fecha = new Date(fecha.getFullYear(), fecha.getMonth() + sentido, 1);
    else fecha = sumarDias(fecha, sentido * (vista === 'semana' ? 7 : 1));
    render();
  }

  // VENTANA DE DETALLE
  function textoCuando(e) {
    let texto = e.inicio === e.fin
      ? capitalizar(fmtDiaLargo.format(e.desde))
      : `${capitalizar(fmtDiaLargo.format(e.desde))} – ${fmtDiaLargo.format(e.hasta)}`;
    if (e.hora_inicio) texto += ` · ${e.hora_inicio}${e.hora_fin ? ` – ${e.hora_fin}` : ''}`;
    return texto;
  }

  function abrirPop(e, origen) {
    const filas = [
      [ICONOS.codigo, `${escapar(e.codigo)} · ${escapar(ETIQUETA_TIPO[e.tipo])}`],
      [ICONOS.estado, escapar(e.estado) + (e.tentativo ? ' (sin confirmar)' : '')],
      [ICONOS.cliente, escapar(e.cliente)],
    ];
    if (e.lugar) filas.push([ICONOS.lugar, escapar(e.lugar)]);
    if (e.personas) filas.push([ICONOS.personas, `${e.personas} invitados`]);

    pop.className = `gcal-pop tipo-${e.tipo}`;
    pop.innerHTML = '<button type="button" class="gcal-pop-close" aria-label="Cerrar">✕</button>'
      + `<div class="gcal-pop-head"><i></i><div><h3>${escapar(e.titulo)}</h3><div class="when">${escapar(textoCuando(e))}</div></div></div>`
      + `<dl>${filas.map(([icono, valor]) => `<dt aria-hidden="true">${icono}</dt><dd>${valor}</dd>`).join('')}</dl>`
      + `<div class="gcal-pop-actions"><a class="btn btn-primary btn-sm" href="${escapar(e.url)}">${TEXTO_ABRIR[e.tipo] || 'Abrir'}${e.tipo === 'evento' ? (e.tentativo ? ' cotización' : ' reserva') : ''}</a></div>`;
    pop.hidden = false;

    const r = origen.getBoundingClientRect();
    const ancho = pop.offsetWidth;
    const alto = pop.offsetHeight;
    // A la derecha del evento, si no cabe a la izquierda, y si el evento es muy ancho, centrada sobre él.
    let left = r.right + 8;
    if (left + ancho > window.innerWidth - 12) {
      left = r.left - ancho - 8 >= 12 ? r.left - ancho - 8 : r.left + r.width / 2 - ancho / 2;
    }
    left = Math.min(Math.max(12, left), window.innerWidth - ancho - 12);
    const top = Math.min(Math.max(12, r.top), window.innerHeight - alto - 12);
    pop.style.left = `${left}px`;
    pop.style.top = `${top}px`;
    pop.querySelector('.gcal-pop-close').focus();
  }

  function cerrarPop() {
    if (pop) pop.hidden = true;
  }

  // EVENTOS DE INTERFAZ
  contenedor.addEventListener('click', (ev) => {
    const evento = ev.target.closest('[data-evento]');
    if (evento) {
      ev.stopPropagation();
      abrirPop(eventos[Number(evento.dataset.evento)], evento);
      return;
    }
    const irDia = ev.target.closest('[data-ir-dia]');
    if (irDia) {
      fecha = aFecha(irDia.dataset.irDia);
      cambiarVista('dia');
    }
  });

  pop.addEventListener('click', (ev) => {
    if (ev.target.closest('.gcal-pop-close')) cerrarPop();
    ev.stopPropagation();
  });
  document.addEventListener('click', cerrarPop);
  window.addEventListener('resize', cerrarPop);
  contenedor.addEventListener('scroll', cerrarPop, true);

  botonesVista.forEach((b) => b.addEventListener('click', () => cambiarVista(b.dataset.vista)));
  document.getElementById('cal-prev').addEventListener('click', () => mover(-1));
  document.getElementById('cal-next').addEventListener('click', () => mover(1));
  document.getElementById('cal-hoy').addEventListener('click', () => {
    fecha = new Date(hoy.getFullYear(), hoy.getMonth(), hoy.getDate());
    render();
  });

  // Atajos de teclado de Google Calendar: m/s/d cambian de vista, t vuelve a hoy, flechas mueven.
  document.addEventListener('keydown', (ev) => {
    if (ev.key === 'Escape') { cerrarPop(); return; }
    if (ev.ctrlKey || ev.metaKey || ev.altKey || ev.target.closest('input, textarea, select, [contenteditable]')) return;
    const acciones = {
      m: () => cambiarVista('mes'),
      s: () => cambiarVista('semana'),
      w: () => cambiarVista('semana'),
      d: () => cambiarVista('dia'),
      t: () => document.getElementById('cal-hoy').click(),
      ArrowLeft: () => mover(-1),
      ArrowRight: () => mover(1),
    };
    if (acciones[ev.key]) { ev.preventDefault(); acciones[ev.key](); }
  });

  render();
});
