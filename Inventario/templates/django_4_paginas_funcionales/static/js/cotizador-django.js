document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("quote-form");
  if (!form) return;

  const steps = [...document.querySelectorAll(".wizard-step")];
  const progressSteps = [...document.querySelectorAll(".progress-step")];
  const progressLines = [...document.querySelectorAll(".progress-line")];
  let current = 1;

  function showStep(step) {
    current = step;
    steps.forEach(el => el.classList.toggle("is-active", Number(el.dataset.step) === step));
    progressSteps.forEach(el => {
      const n = Number(el.dataset.step);
      el.classList.toggle("is-active", n === step);
      el.classList.toggle("is-complete", n < step);
    });
    progressLines.forEach(el => el.classList.toggle("is-complete", Number(el.dataset.after) < step));
  }

  function setError(field, message) {
    const wrapper = form.querySelector(`[data-field="${field}"]`);
    if (!wrapper) return;
    const error = wrapper.querySelector(".field-error");
    if (error) error.textContent = message || "";
  }

  function validateStep(step) {
    let ok = true;

    if (step === 1) {
      const tipo = form.querySelector('input[name="tipoEvento"]:checked');
      const fecha = form.querySelector('[name="fecha"]');
      const invitados = form.querySelector('[name="invitados"]');
      const comuna = form.querySelector('[name="comuna"]');
      const despacho = form.querySelector('input[name="despacho"]:checked');

      setError("tipoEvento", tipo ? "" : "Selecciona un tipo de evento.");
      setError("fecha", fecha.value ? "" : "Selecciona la fecha.");
      setError("invitados", Number(invitados.value) > 0 ? "" : "Ingresa la cantidad de invitados.");
      setError("comuna", comuna.value.trim() ? "" : "Ingresa la comuna.");
      setError("despacho", despacho ? "" : "Indica si requieres despacho.");

      ok = Boolean(tipo && fecha.value && Number(invitados.value) > 0 && comuna.value.trim() && despacho);
    }

    if (step === 3) {
      const nombre = form.querySelector('[name="nombre"]');
      const telefono = form.querySelector('[name="telefono"]');
      const correo = form.querySelector('[name="correo"]');
      const medio = form.querySelector('input[name="medioContacto"]:checked');

      setError("nombre", nombre.value.trim() ? "" : "Ingresa tu nombre.");
      setError("telefono", telefono.value.trim() ? "" : "Ingresa tu teléfono.");
      setError("correo", correo.value.trim() && correo.validity.valid ? "" : "Ingresa un correo válido.");
      setError("medioContacto", medio ? "" : "Selecciona un medio de contacto.");

      ok = Boolean(nombre.value.trim() && telefono.value.trim() && correo.value.trim() && correo.validity.valid && medio);
    }

    return ok;
  }

  form.querySelectorAll("[data-next]").forEach(btn => {
    btn.addEventListener("click", () => {
      if (validateStep(current)) showStep(Math.min(3, current + 1));
    });
  });

  form.querySelectorAll("[data-back]").forEach(btn => {
    btn.addEventListener("click", () => showStep(Math.max(1, current - 1)));
  });

  form.addEventListener("submit", e => {
    if (!validateStep(3)) {
      e.preventDefault();
      return;
    }
    const btn = document.getElementById("btn-submit-quote");
    if (btn) {
      btn.disabled = true;
      btn.textContent = "Enviando...";
    }
  });

  showStep(1);
});