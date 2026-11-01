document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("quote-form");
  if (!form) return;

  const steps = [...document.querySelectorAll(".wizard-step")];
  const progressSteps = [...document.querySelectorAll(".progress-step")];
  const progressLines = [...document.querySelectorAll(".progress-line")];
  const errorGlobal = document.getElementById("quote-error");
  const submit = document.getElementById("btn-submit-quote");

  // Paso en el que vive cada campo, para volver a él si el servidor lo rechaza.
  const PASO_DE_CAMPO = {
    tipoEvento: 1, fecha: 1, invitados: 1, comuna: 1, despacho: 1,
    categorias: 2,
    nombre: 3, rut: 3, telefono: 3, correo: 3, medioContacto: 3,
  };

  let current = 1;

  // Fecha mínima: hoy (según la hora local del navegador)
  function hoyISO() {
    const d = new Date();
    const mm = String(d.getMonth() + 1).padStart(2, "0");
    const dd = String(d.getDate()).padStart(2, "0");
    return `${d.getFullYear()}-${mm}-${dd}`;
  }

  const fechaInput = form.querySelector('[name="fecha"]');
  if (fechaInput) fechaInput.min = hoyISO();

  // RUT chileno: normalización y dígito verificador (el servidor lo vuelve a validar).
  function normalizarRut(rut) {
    return (rut || "").replace(/[.\-\s]/g, "").toUpperCase();
  }

  function rutValido(rut) {
    const limpio = normalizarRut(rut);
    if (!/^\d{7,8}[0-9K]$/.test(limpio)) return false;
    let suma = 0;
    let factor = 2;
    for (let i = limpio.length - 2; i >= 0; i -= 1) {
      suma += Number(limpio[i]) * factor;
      factor = factor === 7 ? 2 : factor + 1;
    }
    const resto = 11 - (suma % 11);
    const dv = resto === 11 ? "0" : resto === 10 ? "K" : String(resto);
    return dv === limpio.slice(-1);
  }

  function telefonoValido(telefono) {
    if (!/^[\d\s+()-]+$/.test(telefono)) return false;
    const digitos = telefono.replace(/\D/g, "").length;
    return digitos >= 8 && digitos <= 15;
  }

  // Estado visual de las tarjetas
  function syncCards() {
    form.querySelectorAll(".option-card, .checkbox-card").forEach((card) => {
      const input = card.querySelector('input[type="radio"], input[type="checkbox"]');
      if (input) card.classList.toggle("is-checked", input.checked);
    });
  }

  form.querySelectorAll(".option-card input, .checkbox-card input").forEach((input) => {
    input.addEventListener("change", syncCards);
  });

  // "Aún no estoy seguro/a" es excluyente con las demás categorías.
  const porDefinir = form.querySelector("input[data-por-definir]");
  const categorias = [...form.querySelectorAll('input[name="categorias"]:not([data-por-definir])')];

  if (porDefinir) {
    porDefinir.addEventListener("change", () => {
      if (porDefinir.checked) categorias.forEach((input) => { input.checked = false; });
      syncCards();
    });
    categorias.forEach((input) => {
      input.addEventListener("change", () => {
        if (input.checked) porDefinir.checked = false;
        syncCards();
      });
    });
  }

  // Mostrar paso (los datos de los otros pasos se conservan en el formulario)
  function showStep(step) {
    current = step;
    steps.forEach((el) => el.classList.toggle("is-active", Number(el.dataset.step) === step));
    progressSteps.forEach((el) => {
      const n = Number(el.dataset.step);
      el.classList.toggle("is-active", n === step);
      el.classList.toggle("is-done", n < step);
    });
    progressLines.forEach((el) => el.classList.toggle("is-done", Number(el.dataset.after) < step));
    syncCards();
  }

  function setError(field, message = "") {
    const wrapper = form.querySelector(`[data-field="${field}"]`);
    if (!wrapper) return;
    const error = wrapper.querySelector(".field-error");
    if (error) error.textContent = message;
    wrapper.classList.toggle("has-error", Boolean(message));
  }

  function mostrarErrorGlobal(message = "") {
    if (!errorGlobal) return;
    errorGlobal.textContent = message;
    errorGlobal.hidden = !message;
  }

  const valor = (name) => (form.querySelector(`[name="${name}"]`)?.value || "").trim();
  const marcado = (name) => form.querySelector(`input[name="${name}"]:checked`);

  // Cada validación devuelve un mensaje de error o "" si el campo está bien.
  const REGLAS = {
    1: {
      tipoEvento: () => (marcado("tipoEvento") ? "" : "Selecciona un tipo de evento."),
      fecha: () => {
        const fecha = valor("fecha");
        if (!fecha) return "Selecciona la fecha.";
        return fecha < hoyISO() ? "La fecha no puede ser anterior a hoy." : "";
      },
      invitados: () => {
        const n = Number(valor("invitados"));
        return Number.isInteger(n) && n > 0 ? "" : "Ingresa una cantidad de invitados mayor que cero.";
      },
      comuna: () => (valor("comuna") ? "" : "Ingresa la comuna."),
      despacho: () => (marcado("despacho") ? "" : "Indica si requieres despacho."),
    },
    2: {
      categorias: () => (marcado("categorias") ? "" : 'Selecciona al menos una categoría o "Aún no estoy seguro/a".'),
    },
    3: {
      nombre: () => (valor("nombre") ? "" : "Ingresa tu nombre."),
      rut: () => {
        if (!valor("rut")) return "Ingresa tu RUT.";
        return rutValido(valor("rut")) ? "" : "El RUT no es válido. Revisa el número y el dígito verificador.";
      },
      telefono: () => (!valor("telefono") || telefonoValido(valor("telefono")) ? "" : "Ingresa un teléfono válido o déjalo en blanco."),
      correo: () => {
        const correo = form.querySelector('[name="correo"]');
        return !valor("correo") || correo.validity.valid ? "" : "Ingresa un correo válido o déjalo en blanco.";
      },
    },
  };

  function validateStep(step) {
    let ok = true;
    Object.entries(REGLAS[step] || {}).forEach(([campo, regla]) => {
      const mensaje = regla();
      setError(campo, mensaje);
      if (mensaje) ok = false;
    });
    return ok;
  }

  form.querySelectorAll("[data-next]").forEach((btn) => {
    btn.addEventListener("click", () => {
      if (validateStep(current)) showStep(Math.min(3, current + 1));
    });
  });

  form.querySelectorAll("[data-back]").forEach((btn) => {
    btn.addEventListener("click", () => showStep(Math.max(1, current - 1)));
  });

  function setCargando(cargando) {
    if (!submit) return;
    submit.disabled = cargando;
    submit.classList.toggle("is-loading", cargando);
    submit.querySelector(".btn-text").textContent = cargando ? "Enviando..." : "Solicitar cotización";
  }

  function mostrarConfirmacion(message) {
    const confirmacion = document.getElementById("wizard-confirmation");
    document.getElementById("wizard-progress").hidden = true;
    form.hidden = true;
    mostrarErrorGlobal("");
    if (confirmacion) {
      document.getElementById("wizard-confirmation-text").textContent = message;
      confirmacion.hidden = false;
      confirmacion.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  }

  // Muestra los errores del servidor y vuelve al primer paso que tenga alguno.
  function mostrarErroresServidor(errores) {
    let primerPaso = null;
    Object.entries(errores).forEach(([campo, mensaje]) => {
      setError(campo, mensaje);
      const paso = PASO_DE_CAMPO[campo];
      if (paso && (primerPaso === null || paso < primerPaso)) primerPaso = paso;
    });
    if (primerPaso) showStep(primerPaso);
  }

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (submit?.disabled) return;

    // Revalida todo por si se modificó algo al volver atrás.
    for (const paso of [1, 2, 3]) {
      if (!validateStep(paso)) {
        showStep(paso);
        return;
      }
    }

    mostrarErrorGlobal("");
    setCargando(true);

    try {
      const respuesta = await fetch(form.action, {
        method: "POST",
        body: new FormData(form),
        headers: { "X-Requested-With": "XMLHttpRequest" },
      });
      const datos = await respuesta.json().catch(() => ({}));

      if (respuesta.ok && datos.ok) {
        mostrarConfirmacion(datos.message);
        return;
      }

      mostrarErrorGlobal(datos.message || "No pudimos enviar tu solicitud. Inténtalo nuevamente.");
      if (datos.errors) mostrarErroresServidor(datos.errors);
    } catch {
      mostrarErrorGlobal("No pudimos conectarnos. Revisa tu conexión e inténtalo nuevamente.");
    }
    setCargando(false);
  });

  syncCards();
  showStep(1);
});
