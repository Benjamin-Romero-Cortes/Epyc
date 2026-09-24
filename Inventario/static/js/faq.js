/**
 * faq.js
 * Acordeón de Preguntas Frecuentes. Cada pregunta abre su propia
 * respuesta sin cerrar las demás, permitiendo comparar varias a la vez.
 */
document.addEventListener('DOMContentLoaded', () => {
  const items = document.querySelectorAll('.faq-item');

  items.forEach((item) => {
    const question = item.querySelector('.faq-question');
    if (!question) return;

    question.addEventListener('click', () => {
      const isOpen = item.classList.contains('is-open');
      item.classList.toggle('is-open', !isOpen);
      question.setAttribute('aria-expanded', String(!isOpen));
    });
  });
});
