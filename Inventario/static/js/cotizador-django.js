document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("quote-form");
  if (!form) return;

  const steps = [...document.querySelectorAll(".wizard-step")];
  const progressSteps = [...document.querySelectorAll(".progress-step")];
  const progressLines = [...document.querySelectorAll(".progress-line")];

  let current = 1;

  // =========================================================
  // SINCRONIZAR ESTADO VISUAL DE TARJETAS
  // =========================================================

  function syncCards() {
    form.querySelectorAll(".option-card, .checkbox-card").forEach((card) => {
      const input = card.querySelector(
        'input[type="radio"], input[type="checkbox"]'
      );

      if (!input) return;

      card.classList.toggle("is-checked", input.checked);
    });
  }

  // =========================================================
  // HACER CLICKEABLE TODA LA TARJETA
  // =========================================================

  form.querySelectorAll(".option-card, .checkbox-card").forEach((card) => {
    const input = card.querySelector(
      'input[type="radio"], input[type="checkbox"]'
    );

    if (!input) return;

    card.addEventListener("click", (e) => {
      // Si el clic fue directamente en el input,
      // dejamos que el navegador lo procese normalmente.
      if (e.target === input) {
        setTimeout(syncCards, 0);
        return;
      }

      if (input.disabled) return;

      if (input.type === "radio") {
        input.checked = true;
      } else {
        input.checked = !input.checked;
      }

      input.dispatchEvent(
        new Event("change", {
          bubbles: true,
        })
      );

      syncCards();
    });

    input.addEventListener("change", syncCards);
  });

  // =========================================================
  // MOSTRAR PASO
  // =========================================================

  function showStep(step) {
    current = step;

    steps.forEach((el) => {
      el.classList.toggle(
        "is-active",
        Number(el.dataset.step) === step
      );
    });

    progressSteps.forEach((el) => {
      const n = Number(el.dataset.step);

      el.classList.toggle("is-active", n === step);
      el.classList.toggle("is-complete", n < step);
      el.classList.toggle("is-done", n < step);
    });

    progressLines.forEach((el) => {
      const completed = Number(el.dataset.after) < step;

      el.classList.toggle("is-complete", completed);
      el.classList.toggle("is-done", completed);
    });

    syncCards();
  }

  // =========================================================
  // MOSTRAR ERROR
  // =========================================================

  function setError(field, message = "") {
    const wrapper = form.querySelector(
      `[data-field="${field}"]`
    );

    if (!wrapper) return;

    const error = wrapper.querySelector(".field-error");

    if (error) {
      error.textContent = message;
    }

    wrapper.classList.toggle(
      "has-error",
      Boolean(message)
    );
  }

  // =========================================================
  // VALIDACIONES
  // =========================================================

  function validateStep(step) {
    let ok = true;

    // ---------------------------------------------------------
    // PASO 1
    // ---------------------------------------------------------

    if (step === 1) {
      const tipo = form.querySelector(
        'input[name="tipoEvento"]:checked'
      );

      const fecha = form.querySelector(
        '[name="fecha"]'
      );

      const invitados = form.querySelector(
        '[name="invitados"]'
      );

      const comuna = form.querySelector(
        '[name="comuna"]'
      );

      const despacho = form.querySelector(
        'input[name="despacho"]:checked'
      );

      setError(
        "tipoEvento",
        tipo
          ? ""
          : "Selecciona un tipo de evento."
      );

      setError(
        "fecha",
        fecha && fecha.value
          ? ""
          : "Selecciona la fecha."
      );

      setError(
        "invitados",
        invitados &&
        Number(invitados.value) > 0
          ? ""
          : "Ingresa la cantidad de invitados."
      );

      setError(
        "comuna",
        comuna &&
        comuna.value.trim()
          ? ""
          : "Ingresa la comuna."
      );

      setError(
        "despacho",
        despacho
          ? ""
          : "Indica si requieres despacho."
      );

      ok = Boolean(
        tipo &&
        fecha &&
        fecha.value &&
        invitados &&
        Number(invitados.value) > 0 &&
        comuna &&
        comuna.value.trim() &&
        despacho
      );
    }

    // ---------------------------------------------------------
    // PASO 3
    // ---------------------------------------------------------

    if (step === 3) {
      const nombre = form.querySelector('[name="nombre"]');
      const rut = form.querySelector('[name="rut"]');
      const telefono = form.querySelector('[name="telefono"]');
      const correo = form.querySelector('[name="correo"]');
      const direccion = form.querySelector('[name="direccion"]');

      const medio = form.querySelector(
        'input[name="medioContacto"]:checked'
      );

      setError(
        "nombre",
        nombre && nombre.value.trim()
          ? ""
          : "Ingresa tu nombre."
      );

      setError(
        "rut",
        rut && rut.value.trim()
          ? ""
          : "Ingresa tu RUT."
      );

      setError(
        "telefono",
        telefono && telefono.value.trim()
          ? ""
          : "Ingresa tu teléfono."
      );

      setError(
        "correo",
        correo &&
        correo.value.trim() &&
        correo.validity.valid
          ? ""
          : "Ingresa un correo válido."
      );

      setError(
        "direccion",
        direccion && direccion.value.trim()
          ? ""
          : "Ingresa tu dirección."
      );

      setError(
        "medioContacto",
        medio
          ? ""
          : "Selecciona un medio de contacto."
      );

      ok = Boolean(
        nombre &&
        nombre.value.trim() &&
        rut &&
        rut.value.trim() &&
        telefono &&
        telefono.value.trim() &&
        correo &&
        correo.value.trim() &&
        correo.validity.valid &&
        direccion &&
        direccion.value.trim() &&
        medio
      );
    }

    return ok;
  }

  // =========================================================
  // BOTÓN SIGUIENTE
  // =========================================================

  form.querySelectorAll("[data-next]").forEach((btn) => {
    btn.addEventListener("click", () => {
      if (validateStep(current)) {
        showStep(
          Math.min(3, current + 1)
        );
      }
    });
  });

  // =========================================================
  // BOTÓN ATRÁS
  // =========================================================

  form.querySelectorAll("[data-back]").forEach((btn) => {
    btn.addEventListener("click", () => {
      showStep(
        Math.max(1, current - 1)
      );
    });
  });

  // =========================================================
  // ENVÍO DEL FORMULARIO
  // =========================================================

  form.addEventListener("submit", (e) => {
    if (!validateStep(3)) {
      e.preventDefault();
      return;
    }

    const submit = document.getElementById(
      "btn-submit-quote"
    );

    if (submit) {
      submit.disabled = true;
      submit.textContent = "Enviando...";
    }

    /*
      IMPORTANTE:
      Aquí NO usamos e.preventDefault().

      El formulario debe enviarse normalmente
      al backend de Django mediante POST.
    */
  });

  // =========================================================
  // INICIO
  // =========================================================

  syncCards();
  showStep(1);
});