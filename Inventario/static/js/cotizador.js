/**
 * cotizador.js
 * Controla el formulario de cotización en 3 pasos: navegación entre
 * pasos, validaciones básicas y una pantalla de confirmación simulada.
 *
 * IMPORTANTE: en esta etapa no existe backend. `enviarSolicitud()`
 * simula el envío con un pequeño retardo. Cuando exista una API de
 * cotizaciones, esa función es el único lugar que debe cambiar: en
 * vez de simular, debería hacer un fetch POST con el mismo objeto
 * `datosSolicitud` que ya se arma más abajo.
 */
(function () {
  const wizard = document.getElementById('quote-wizard');
  if (!wizard) return;

  const TELEFONO_WHATSAPP = '56942058820';

  let pasoActual = 1;
  const TOTAL_PASOS = 3;
  const estado = {
    tipoEvento: '',
    fecha: '',
    invitados: '',
    comuna: '',
    despacho: '',
    categorias: [],
    nombre: '',
    empresa: '',
    telefono: '',
    correo: '',
    medioContacto: '',
    comentarios: ''
  };

  init();

  function init() {
    document.querySelectorAll('[data-next]').forEach((btn) => {
      btn.addEventListener('click', () => irSiguiente());
    });
    document.querySelectorAll('[data-back]').forEach((btn) => {
      btn.addEventListener('click', () => irAtras());
    });

    document.querySelectorAll('.option-card input, .checkbox-card input').forEach((input) => {
      input.addEventListener('change', () => {
        input.closest('.option-card, .checkbox-card').parentElement
          .querySelectorAll(`.option-card, .checkbox-card`).forEach((card) => {
            const cardInput = card.querySelector('input');
            if (cardInput && cardInput.name === input.name && cardInput.type === 'radio') {
              card.classList.toggle('is-checked', cardInput.checked);
            }
          });
        if (input.type === 'checkbox') {
          input.closest('.checkbox-card').classList.toggle('is-checked', input.checked);
        }
      });
    });

    const form = document.getElementById('quote-form');
    form.addEventListener('submit', (e) => {
      e.preventDefault();
      if (!validarPaso(3)) return;
      enviarSolicitud();
    });

    actualizarProgreso();
  }

  function irSiguiente() {
    if (!validarPaso(pasoActual)) return;
    if (pasoActual < TOTAL_PASOS) {
      pasoActual += 1;
      actualizarProgreso();
    }
  }

  function irAtras() {
    if (pasoActual > 1) {
      pasoActual -= 1;
      actualizarProgreso();
    }
  }

  function actualizarProgreso() {
    document.querySelectorAll('.wizard-step').forEach((step) => {
      step.classList.toggle('is-active', Number(step.dataset.step) === pasoActual);
    });
    document.querySelectorAll('.progress-step').forEach((dot) => {
      const n = Number(dot.dataset.step);
      dot.classList.toggle('is-active', n === pasoActual);
      dot.classList.toggle('is-done', n < pasoActual);
    });
    document.querySelectorAll('.progress-line').forEach((line) => {
      line.classList.toggle('is-done', Number(line.dataset.after) < pasoActual);
    });
    wizard.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  function mostrarError(campoId, mensaje) {
    const field = document.querySelector(`[data-field="${campoId}"]`);
    if (!field) return;
    field.classList.toggle('has-error', Boolean(mensaje));
    const errorEl = field.querySelector('.field-error');
    if (errorEl) errorEl.textContent = mensaje || '';
  }

  function validarPaso(paso) {
    let valido = true;

    if (paso === 1) {
      const tipoEvento = wizard.querySelector('input[name="tipoEvento"]:checked');
      const fecha = document.getElementById('fecha-evento');
      const invitados = document.getElementById('num-invitados');
      const comuna = document.getElementById('comuna');
      const despacho = wizard.querySelector('input[name="despacho"]:checked');

      const errores = {
        tipoEvento: tipoEvento ? '' : 'Selecciona el tipo de evento.',
        fecha: fecha.value ? '' : 'Indica la fecha estimada.',
        invitados: invitados.value && Number(invitados.value) > 0 ? '' : 'Indica la cantidad aproximada de invitados.',
        comuna: comuna.value.trim() ? '' : 'Indica la comuna del evento.',
        despacho: despacho ? '' : 'Indica si necesitas despacho.'
      };
      Object.entries(errores).forEach(([campo, mensaje]) => mostrarError(campo, mensaje));
      valido = Object.values(errores).every((mensaje) => !mensaje);

      if (valido) {
        estado.tipoEvento = tipoEvento.value;
        estado.fecha = fecha.value;
        estado.invitados = invitados.value;
        estado.comuna = comuna.value.trim();
        estado.despacho = despacho.value;
      }
    }

    if (paso === 2) {
      estado.categorias = Array.from(wizard.querySelectorAll('input[name="categorias"]:checked')).map((c) => c.value);
      // Paso opcional: no bloquea el avance aunque no se seleccione nada.
    }

    if (paso === 3) {
      const nombre = document.getElementById('nombre');
      const telefono = document.getElementById('telefono');
      const correo = document.getElementById('correo');
      const medioContacto = wizard.querySelector('input[name="medioContacto"]:checked');
      const correoValido = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(correo.value.trim());

      const errores = {
        nombre: nombre.value.trim() ? '' : 'Cuéntanos tu nombre.',
        telefono: telefono.value.trim() ? '' : 'Indica un teléfono de contacto.',
        correo: correoValido ? '' : 'Ingresa un correo electrónico válido.',
        medioContacto: medioContacto ? '' : 'Indica tu medio de contacto preferido.'
      };
      Object.entries(errores).forEach(([campo, mensaje]) => mostrarError(campo, mensaje));
      valido = Object.values(errores).every((mensaje) => !mensaje);

      if (valido) {
        estado.nombre = nombre.value.trim();
        estado.empresa = document.getElementById('empresa').value.trim();
        estado.telefono = telefono.value.trim();
        estado.correo = correo.value.trim();
        estado.medioContacto = medioContacto.value;
        estado.comentarios = document.getElementById('comentarios').value.trim();
      }
    }

    return valido;
  }

  function enviarSolicitud() {
    const submitBtn = document.getElementById('btn-submit-quote');
    submitBtn.disabled = true;
    submitBtn.textContent = 'Enviando...';

    const datosSolicitud = {
      evento: {
        tipo: estado.tipoEvento,
        fecha: estado.fecha,
        invitados: estado.invitados,
        comuna: estado.comuna,
        despacho: estado.despacho
      },
      categoriasInteres: estado.categorias,
      contacto: {
        nombre: estado.nombre,
        empresa: estado.empresa,
        telefono: estado.telefono,
        correo: estado.correo,
        medioContacto: estado.medioContacto,
        comentarios: estado.comentarios
      },
      fechaSolicitud: new Date().toISOString()
    };

    // Simulación de envío (sin backend). Aquí iría el fetch POST a la API.
    setTimeout(() => {
      console.log('Solicitud de cotización (simulada):', datosSolicitud);
      mostrarConfirmacion(datosSolicitud);
    }, 900);
  }

  function mostrarConfirmacion(datos) {
    document.getElementById('wizard-form-view').hidden = true;
    document.getElementById('wizard-progress').hidden = true;
    const confirmacion = document.getElementById('wizard-confirmation');
    confirmacion.hidden = false;

    const mensaje = `Hola, soy ${datos.contacto.nombre}. Acabo de enviar una solicitud de cotización para un evento tipo "${datos.evento.tipo}" el ${datos.evento.fecha || 'fecha por confirmar'}, aproximadamente ${datos.evento.invitados} invitados en ${datos.evento.comuna}. Me gustaría continuar la conversación por aquí.`;
    const linkWhatsApp = document.getElementById('btn-whatsapp-confirm');
    if (linkWhatsApp) {
      linkWhatsApp.href = `https://wa.me/${TELEFONO_WHATSAPP}?text=${encodeURIComponent(mensaje)}`;
    }

    confirmacion.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }
})();
