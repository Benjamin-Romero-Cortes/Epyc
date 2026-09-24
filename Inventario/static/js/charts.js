/**
 * charts.js
 * Componentes de gráficos livianos en HTML/CSS/SVG (sin librerías
 * externas) usados en el Dashboard y en Reportes. Cada gráfico es de una
 * sola serie, por lo que se usa un único tono (el acento de marca) en
 * distintas intensidades en vez de una paleta categórica — no hace falta
 * distinguir series por color porque cada barra ya está identificada por
 * su etiqueta.
 */

/** Ranking horizontal: items = [{ label, value, sublabel }] */
function renderBarListChart(container, items, { formatValue = (v) => v } = {}) {
  const el = typeof container === 'string' ? document.getElementById(container) : container;
  if (!el || !items.length) return;
  const max = Math.max(...items.map((i) => i.value), 1);

  el.innerHTML = items.map((item) => `
    <div style="margin-bottom:0.85rem;">
      <div style="display:flex;justify-content:space-between;font-size:0.84rem;margin-bottom:0.3rem;">
        <span style="font-weight:600;">${item.label}</span>
        <span style="opacity:0.7;">${formatValue(item.value)}</span>
      </div>
      <div style="height:9px;border-radius:999px;background-color:var(--color-beige-soft);overflow:hidden;">
        <div style="height:100%;border-radius:999px;background-color:var(--color-accent);width:${(item.value / max) * 100}%;"></div>
      </div>
    </div>
  `).join('');
}

/** Barras verticales por mes: items = [{ label, value }] */
function renderMonthlyBarChart(container, items, { formatValue = (v) => v } = {}) {
  const el = typeof container === 'string' ? document.getElementById(container) : container;
  if (!el || !items.length) return;
  const max = Math.max(...items.map((i) => i.value), 1);

  el.innerHTML = `
    <div style="display:flex;align-items:flex-end;gap:0.6rem;height:150px;">
      ${items.map((item) => `
        <div style="flex:1;display:flex;flex-direction:column;align-items:center;gap:0.4rem;height:100%;justify-content:flex-end;" title="${item.label}: ${formatValue(item.value)}">
          <span style="font-size:0.7rem;opacity:0.65;">${formatValue(item.value)}</span>
          <div style="width:100%;max-width:34px;border-radius:6px 6px 2px 2px;background-color:var(--color-accent);height:${(item.value / max) * 100}%;min-height:4px;"></div>
        </div>
      `).join('')}
    </div>
    <div style="display:flex;gap:0.6rem;margin-top:0.5rem;">
      ${items.map((item) => `<span style="flex:1;text-align:center;font-size:0.7rem;opacity:0.55;">${item.label}</span>`).join('')}
    </div>
  `;
}

/**
 * Ranking horizontal en formato "lollipop": línea fina + marcador circular
 * en vez de una barra sólida. Misma lectura que un ranking de barras pero
 * mucho más liviano a la vista para listas de 5-6 ítems.
 * items = [{ label, value }]
 */
function renderRankingChart(container, items, { formatValue = (v) => v } = {}) {
  const el = typeof container === 'string' ? document.getElementById(container) : container;
  if (!el) return;
  if (!items.length) { el.innerHTML = '<p class="empty-state">Sin datos para este período.</p>'; return; }
  const max = Math.max(...items.map((i) => i.value), 1);

  el.innerHTML = items.map((item) => {
    const pct = Math.max((item.value / max) * 100, 2);
    return `
      <div style="display:flex;align-items:center;gap:0.7rem;margin-bottom:0.75rem;" title="${item.label}: ${formatValue(item.value)}">
        <span style="width:42%;flex-shrink:0;font-size:0.83rem;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${item.label}</span>
        <div style="position:relative;flex:1;height:9px;">
          <div style="position:absolute;top:50%;left:0;right:0;height:1px;background-color:var(--color-gray-light);transform:translateY(-50%);"></div>
          <div style="position:absolute;top:50%;left:0;height:2px;width:${pct}%;background-color:var(--color-accent);border-radius:2px;transform:translateY(-50%);"></div>
          <div style="position:absolute;top:50%;left:${pct}%;width:9px;height:9px;border-radius:50%;background-color:var(--color-accent);box-shadow:0 0 0 2px var(--color-white-warm);transform:translate(-50%,-50%);"></div>
        </div>
        <span style="flex-shrink:0;font-size:0.8rem;font-weight:700;opacity:0.75;min-width:48px;text-align:right;">${formatValue(item.value)}</span>
      </div>
    `;
  }).join('');
}

/**
 * Barra apilada horizontal + leyenda: para datos parte-todo (ej. ingresos
 * por categoría de producto). items = [{ label, value, color }]
 */
function renderStackedBarChart(container, items, { formatValue = (v) => v } = {}) {
  const el = typeof container === 'string' ? document.getElementById(container) : container;
  if (!el) return;
  const total = items.reduce((s, i) => s + i.value, 0);
  if (!total) { el.innerHTML = '<p class="empty-state">Sin datos para este período.</p>'; return; }

  el.innerHTML = `
    <div style="display:flex;width:100%;height:22px;border-radius:8px;overflow:hidden;background-color:var(--color-beige-soft);">
      ${items.map((item) => `
        <div style="flex:${Math.max(item.value, 0)} 0 auto;min-width:3px;background-color:${item.color};border-right:2px solid var(--color-white-warm);" title="${item.label}: ${formatValue(item.value)} · ${Math.round((item.value / total) * 100)}%"></div>
      `).join('')}
    </div>
    <div style="display:flex;flex-wrap:wrap;gap:0.55rem 1.1rem;margin-top:0.9rem;">
      ${items.map((item) => `
        <div style="display:flex;align-items:center;gap:0.4rem;font-size:0.8rem;">
          <span style="width:9px;height:9px;border-radius:50%;background-color:${item.color};flex-shrink:0;"></span>
          <span style="font-weight:600;">${item.label}</span>
          <span style="opacity:0.6;">${formatValue(item.value)} · ${Math.round((item.value / total) * 100)}%</span>
        </div>
      `).join('')}
    </div>
  `;
}

/** Línea de tendencia: items = [{ label, value }] */
function renderLineChart(container, items, { formatValue = (v) => v } = {}) {
  const el = typeof container === 'string' ? document.getElementById(container) : container;
  if (!el || !items.length) return;

  const w = 100, h = 34, pad = 4;
  const max = Math.max(...items.map((i) => i.value));
  const min = Math.min(...items.map((i) => i.value), 0);
  const range = max - min || 1;
  const stepX = (w - pad * 2) / (items.length - 1 || 1);

  const points = items.map((item, i) => {
    const x = pad + i * stepX;
    const y = h - pad - ((item.value - min) / range) * (h - pad * 2);
    return { x, y, item };
  });

  const path = points.map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x.toFixed(2)},${p.y.toFixed(2)}`).join(' ');
  const areaPath = `${path} L${points[points.length - 1].x.toFixed(2)},${h} L${points[0].x.toFixed(2)},${h} Z`;

  el.innerHTML = `
    <svg viewBox="0 0 ${w} ${h}" style="width:100%;height:150px;" preserveAspectRatio="none">
      <path d="${areaPath}" fill="var(--color-accent)" opacity="0.12"></path>
      <path d="${path}" fill="none" stroke="var(--color-accent)" stroke-width="0.8" vector-effect="non-scaling-stroke"></path>
      ${points.map((p) => `<circle cx="${p.x.toFixed(2)}" cy="${p.y.toFixed(2)}" r="1" fill="var(--color-black)"></circle>`).join('')}
    </svg>
    <div style="display:flex;margin-top:0.4rem;">
      ${items.map((item, i) => `
        <span style="flex:1;text-align:center;font-size:0.7rem;${i === items.length - 1 ? 'font-weight:700;color:var(--color-black);' : 'opacity:0.55;'}">
          ${item.label}${i === items.length - 1 ? `<br>${formatValue(item.value)}` : ''}
        </span>
      `).join('')}
    </div>
  `;
}
