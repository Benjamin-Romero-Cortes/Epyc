// Comportamiento compartido de las pantallas de preparación y despacho.
document.addEventListener('DOMContentLoaded', () => {
  // Formularios con un solo envío: confirmación opcional y botón en "Guardando..." para evitar dobles clics.
  document.querySelectorAll('form[data-un-envio]').forEach((form) => {
    form.addEventListener('submit', async (e) => {
      if (form.dataset.enviando) { e.preventDefault(); return; }
      const boton = e.submitter;

      if (boton && boton.dataset.confirmar && !form.dataset.confirmado) {
        e.preventDefault();
        const opciones = { titulo: boton.textContent.trim(), mensaje: boton.dataset.confirmar, textoConfirmar: boton.textContent.trim() };
        const ok = typeof confirmarAccion === 'function' ? await confirmarAccion(opciones) : window.confirm(opciones.mensaje);
        if (!ok) return;
        form.dataset.confirmado = '1';
        form.requestSubmit(boton);
        return;
      }

      form.dataset.enviando = '1';
      // Ej.: "Enviar por WhatsApp" abre el chat con el mensaje listo y, a la vez, registra el envío.
      if (form.dataset.abrirUrl) window.open(form.dataset.abrirUrl, '_blank', 'noopener');
      // Un botón deshabilitado no envía su valor: se copia a un campo oculto.
      if (boton && boton.name) {
        const oculto = document.createElement('input');
        oculto.type = 'hidden';
        oculto.name = boton.name;
        oculto.value = boton.value;
        form.append(oculto);
      }
      form.querySelectorAll('button[type="submit"], button:not([type])').forEach((b) => { b.disabled = true; });
      if (boton && boton.dataset.textoCargando) {
        boton.classList.add('is-loading');
        boton.textContent = boton.dataset.textoCargando;
      }
    });
  });

  iniciarDevolucion();

  // Hoja de preparación: faltantes en vivo y botón Finalizar solo con todo completo y guardado.
  const tabla = document.getElementById('tabla-preparacion');
  const finalizar = document.getElementById('btn-finalizar');
  if (!tabla || !finalizar) return;

  const filas = [...tabla.querySelectorAll('tr[data-fila]')];
  const hint = document.getElementById('prep-hint');
  const textoHint = hint ? hint.textContent : '';
  const valoresIniciales = filas.map((f) => f.querySelector('input[type="number"]').value);
  const obsIniciales = [...document.querySelectorAll('#form-preparacion .qty-obs, #prep-observaciones')].map((c) => c.value);

  function actualizar() {
    let requeridas = 0;
    let preparadas = 0;
    let completas = true;
    let validas = true;

    filas.forEach((fila) => {
      const input = fila.querySelector('input[type="number"]');
      const requerido = Number(fila.dataset.requerido);
      const texto = input.value.trim();
      const valor = /^\d+$/.test(texto) ? Number(texto) : NaN;
      const valido = !Number.isNaN(valor) && valor <= requerido;
      input.classList.toggle('is-invalid', !valido);
      validas = validas && valido;

      const faltante = valido ? requerido - valor : requerido;
      fila.querySelector('[data-faltante]').textContent = valido ? faltante : '—';
      fila.classList.toggle('is-complete', valido && faltante === 0);
      fila.classList.toggle('is-missing', !(valido && faltante === 0));
      completas = completas && valido && faltante === 0;
      requeridas += requerido;
      preparadas += valido ? valor : 0;
    });

    const porcentaje = requeridas ? Math.round((preparadas * 100) / requeridas) : 0;
    document.getElementById('prep-total-prep').textContent = preparadas;
    document.getElementById('prep-porcentaje').textContent = `${porcentaje} %`;
    const barra = document.getElementById('prep-barra');
    barra.style.width = `${porcentaje}%`;
    barra.classList.toggle('is-complete', porcentaje === 100);

    const cambiado = filas.some((f, i) => f.querySelector('input[type="number"]').value !== valoresIniciales[i])
      || [...document.querySelectorAll('#form-preparacion .qty-obs, #prep-observaciones')].some((c, i) => c.value !== obsIniciales[i]);

    finalizar.disabled = !completas || cambiado;
    if (hint) {
      if (!validas) hint.textContent = 'Hay cantidades no válidas: deben ser enteros entre 0 y lo reservado.';
      else if (cambiado) hint.textContent = 'Tienes cambios sin guardar. Guarda el avance antes de finalizar.';
      else if (!completas) hint.textContent = textoHint;
      else hint.textContent = 'Todo está completo. Ya puedes finalizar la preparación.';
    }
  }

  tabla.addEventListener('input', actualizar);
  document.getElementById('form-preparacion').addEventListener('input', actualizar);
  tabla.addEventListener('click', (e) => {
    const boton = e.target.closest('[data-completar]');
    if (!boton) return;
    const fila = boton.closest('tr[data-fila]');
    fila.querySelector('input[type="number"]').value = fila.dataset.requerido;
    actualizar();
  });

  actualizar();
});


// Formulario de devolución: pendiente en vivo, error bajo cada fila y resumen antes de confirmar.
function iniciarDevolucion() {
  const tabla = document.getElementById('tabla-devolucion');
  const boton = document.getElementById('btn-devolucion');
  if (!tabla || !boton) return;
  const resumen = document.getElementById('dv-resumen');
  const filas = [...tabla.querySelectorAll('tr[data-fila-dev]')];
  const plural = (n, uno, varios) => `${n} ${n === 1 ? uno : varios}`;

  function actualizar() {
    let buenas = 0;
    let merma = 0;
    let pendiente = 0;
    let validas = true;

    filas.forEach((fila) => {
      const disponible = Number(fila.dataset.pendiente);
      const inputs = [...fila.querySelectorAll('input[type="number"]')];
      const valores = inputs.map((input) => {
        const texto = input.value.trim();
        return /^\d+$/.test(texto) ? Number(texto) : NaN;
      });
      const error = fila.querySelector('[data-error]');
      let mensaje = '';
      inputs.forEach((input, i) => input.classList.toggle('is-invalid', Number.isNaN(valores[i])));

      if (valores.some(Number.isNaN)) {
        mensaje = 'Usa números enteros iguales o mayores que 0.';
      } else {
        // Primera columna: vuelve bien; el resto (una o más columnas): merma.
        const suma = valores.reduce((a, b) => a + b, 0);
        if (suma > disponible) {
          mensaje = `Suman ${suma}, pero solo quedan ${disponible} pendientes.`;
          inputs.forEach((input) => input.classList.add('is-invalid'));
        } else {
          buenas += valores[0];
          merma += suma - valores[0];
          pendiente += disponible - suma;
          fila.querySelector('[data-pendiente-out]').textContent = disponible - suma;
          fila.classList.toggle('is-complete', disponible - suma === 0);
          fila.classList.toggle('is-missing', disponible - suma > 0);
        }
      }
      if (mensaje) {
        fila.querySelector('[data-pendiente-out]').textContent = '—';
        fila.classList.add('is-missing');
        fila.classList.remove('is-complete');
      }
      error.textContent = mensaje;
      validas = validas && !mensaje;
    });

    const texto = `Se recibirán ${plural(buenas, 'unidad', 'unidades')} en buen estado. `
      + `Se registrarán ${plural(merma, 'unidad', 'unidades')} como merma. `
      + `Quedarán ${plural(pendiente, 'unidad pendiente', 'unidades pendientes')}.`;
    // Toda unidad debe quedar definida: vuelve bien o va a merma.
    if (!validas) resumen.textContent = 'Corrige las filas marcadas para continuar.';
    else if (pendiente) resumen.textContent = `Faltan ${plural(pendiente, 'unidad', 'unidades')} por definir: indica si vuelven bien o van a merma.`;
    else resumen.textContent = texto;
    resumen.classList.toggle('is-alerta', validas && pendiente > 0);
    boton.dataset.confirmar = texto + ' La reserva quedará Devuelta.';
    boton.disabled = !validas || pendiente > 0 || buenas + merma === 0;
  }

  tabla.addEventListener('input', actualizar);
  tabla.addEventListener('click', (e) => {
    const todo = e.target.closest('[data-todo]');
    if (!todo) return;
    const fila = todo.closest('tr[data-fila-dev]');
    const [buenas, ...resto] = fila.querySelectorAll('input[type="number"]');
    buenas.value = Number(fila.dataset.pendiente);
    resto.forEach((input) => { input.value = 0; });
    actualizar();
  });
  actualizar();
}
