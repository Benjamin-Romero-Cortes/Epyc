// Acordeón de Preguntas Frecuentes.
document.addEventListener('DOMContentLoaded', () => {
  const items = document.querySelectorAll('.faq-item');

  const setOpen = (item, open) => {
    item.classList.toggle('is-open', open);
    const question = item.querySelector('.faq-question');
    if (question) question.setAttribute('aria-expanded', String(open));
    // Se anima hasta la altura real para que abrir y cerrar duren lo mismo.
    const answer = item.querySelector('.faq-answer');
    if (answer) answer.style.maxHeight = open ? `${answer.scrollHeight}px` : '';
  };

  items.forEach((item) => {
    const question = item.querySelector('.faq-question');
    if (!question) return;

    question.addEventListener('click', () => {
      const isOpen = item.classList.contains('is-open');
      items.forEach((other) => {
        if (other !== item) setOpen(other, false);
      });
      setOpen(item, !isOpen);
    });
  });
});
