/**
 * main.js
 * Comportamiento compartido por todas las páginas del sitio:
 * header con sombra al hacer scroll, menú responsive, resaltado
 * del link activo y animaciones de aparición al hacer scroll.
 */
document.addEventListener('DOMContentLoaded', () => {
  initHeaderScroll();
  initMobileNav();
  initActiveNavLink();
  initRevealAnimations();
  initFooterYear();
});

function initHeaderScroll() {
  const header = document.querySelector('.site-header');
  if (!header) return;
  const onScroll = () => {
    header.classList.toggle('is-scrolled', window.scrollY > 12);
  };
  onScroll();
  window.addEventListener('scroll', onScroll, { passive: true });
}

function initMobileNav() {
  const toggle = document.querySelector('.nav-toggle');
  const nav = document.querySelector('.main-nav');
  if (!toggle || !nav) return;

  toggle.addEventListener('click', () => {
    const isOpen = nav.classList.toggle('is-open');
    toggle.classList.toggle('is-open', isOpen);
    toggle.setAttribute('aria-expanded', String(isOpen));
    document.body.style.overflow = isOpen ? 'hidden' : '';
  });

  nav.querySelectorAll('a').forEach((link) => {
    link.addEventListener('click', () => {
      nav.classList.remove('is-open');
      toggle.classList.remove('is-open');
      toggle.setAttribute('aria-expanded', 'false');
      document.body.style.overflow = '';
    });
  });
}

function initActiveNavLink() {
  const current = window.location.pathname.split('/').pop() || 'index.html';
  document.querySelectorAll('.nav-links a').forEach((link) => {
    const href = link.getAttribute('href');
    // Los enlaces con ancla (ej. index.html#como-funciona) apuntan a una
    // sección, no a una página distinta, así que no marcan el nav activo.
    if (!href.includes('#') && href === current) {
      link.classList.add('is-active');
    }
  });
}

function initRevealAnimations() {
  const items = document.querySelectorAll('.reveal');
  if (!items.length) return;

  if (!('IntersectionObserver' in window)) {
    items.forEach((el) => el.classList.add('is-visible'));
    return;
  }

  const observer = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        entry.target.classList.add('is-visible');
        observer.unobserve(entry.target);
      }
    });
  }, { threshold: 0.15 });

  items.forEach((el) => observer.observe(el));
}

function initFooterYear() {
  const el = document.querySelector('[data-year]');
  if (el) el.textContent = new Date().getFullYear();
}
