// Gráficos del Resumen.
document.addEventListener('DOMContentLoaded', () => {
  const leer = (id) => {
    const el = document.getElementById(id);
    try { return el ? JSON.parse(el.textContent) : []; } catch { return []; }
  };
  const sinDatos = (id, texto) => {
    const el = document.getElementById(id);
    if (el) el.innerHTML = `<p class="empty-state">${texto}</p>`;
  };

  const pesos = (v) => `$${Math.round(v).toLocaleString('es-CL')}`;
  const pesosCorto = (v) => (v >= 1000000
    ? `$${(v / 1000000).toLocaleString('es-CL', { maximumFractionDigits: 1 })}M`
    : `$${Math.round(v / 1000).toLocaleString('es-CL')}k`);

  const MESES = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic'];

  // Monto reservado por mes (solo datos reales; sin reservas se muestra un aviso)
  const ingresos = leer('data-ingresos').map((i) => {
    const [mes, anio] = String(i.mes).split('/');
    return { label: `${MESES[Number(mes) - 1]} ${String(anio).slice(-2)}`, value: Number(i.total) || 0 };
  });
  if (ingresos.length) {
    renderColumnChart('chart-ingresos', ingresos, { formatValue: pesos, formatAxis: pesosCorto });
  } else {
    sinDatos('chart-ingresos', 'Aún no hay reservas confirmadas.');
  }

  // Productos más arrendados
  const productos = leer('data-productos').map((p) => ({ label: p.nombre, value: Number(p.cantidad) || 0 }));
  if (productos.length) {
    renderRankingChart('chart-productos', productos, { formatValue: (v) => `${v.toLocaleString('es-CL')} u.` });
  } else {
    sinDatos('chart-productos', 'Aún no hay productos en reservas confirmadas.');
  }
});

// Columnas por período con eje Y discreto y tooltip al pasar el mouse.
function renderColumnChart(container, items, { formatValue = (v) => v, formatAxis = formatValue } = {}) {
  const el = typeof container === 'string' ? document.getElementById(container) : container;
  if (!el || !items.length) return;

  const max = Math.max(...items.map((i) => i.value), 1);
  const paso = Math.pow(10, Math.floor(Math.log10(max)));
  const tope = Math.ceil(max / paso) * paso;
  const marcas = [tope, tope / 2, 0];

  el.innerHTML = `
    <div class="col-chart">
      <div class="col-chart-axis">${marcas.map((m) => `<span>${formatAxis(m)}</span>`).join('')}</div>
      <div class="col-chart-plot">
        ${marcas.map((_, i) => `<div class="col-chart-grid" style="top:${(i / (marcas.length - 1)) * 100}%"></div>`).join('')}
        ${items.map((item, i) => `
          <div class="col-chart-col${i === items.length - 1 ? ' is-current' : ''}" tabindex="0"
               aria-label="${item.label}: ${formatValue(item.value)}">
            <div class="col-chart-bar" style="height:${(item.value / tope) * 100}%">
              <div class="col-chart-tip"><strong>${formatValue(item.value)}</strong>${item.label}</div>
            </div>
          </div>
        `).join('')}
      </div>
      <div></div>
      <div class="col-chart-labels">${items.map((i) => `<span>${i.label}</span>`).join('')}</div>
    </div>
  `;
}
