/**
 * dashboard.js
 * Arma el Resumen general a partir de los datos demostrativos. La fecha
 * "de hoy" del panel se fija en 2026-08-19 (en vez de la fecha real del
 * sistema) para que las operaciones del día, entregas y retiros calcen
 * de forma realista con las reservas de ejemplo.
 */
(function () {
  const dashboard = document.getElementById('proximos-eventos');
  if (!dashboard) return;

  const HOY = '2026-08-19';

  Promise.all([
    obtenerDatos('inventario'), obtenerDatos('clientes'),
    obtenerDatos('cotizaciones'), obtenerDatos('reservas'), obtenerDatos('mermas'),
  ]).then(([inventario, clientes, cotizaciones, reservas, mermas]) => {
    renderHero(cotizaciones, reservas);
    renderKpis(inventario, cotizaciones, reservas);
    renderOperacionesDelDia(inventario, reservas, mermas);
    renderProximosEventos(reservas);
    renderAlertasInventario(inventario, reservas, HOY);
    renderCharts(inventario, cotizaciones, reservas);
  }).catch((err) => {
    console.error('Error cargando el dashboard', err);
  });

  function renderHero(cotizaciones, reservas) {
    const proximos = reservas.filter((r) => r.fechaEvento >= HOY && !['Finalizada', 'Cancelada'].includes(r.estado)).length;
    const pendientes = cotizaciones.filter((c) => c.estado === 'Pendiente').length;
    document.getElementById('hero-summary').textContent =
      `Tienes ${proximos} eventos próximos y ${pendientes} cotizaciones esperando respuesta.`;
  }

  function renderKpis(inventario, cotizaciones, reservas) {
    const activas = reservas.filter((r) => !['Finalizada', 'Cancelada'].includes(r.estado));
    document.getElementById('kpi-reservas-activas').textContent = activas.length;
    const semana = reservas.filter((r) => r.fechaEvento >= HOY && r.fechaEvento <= '2026-08-26').length;
    document.getElementById('kpi-reservas-delta').textContent = `+${semana} esta semana`;

    const disponible = inventario.reduce((s, p) => s + p.disponible, 0);
    const total = inventario.reduce((s, p) => s + p.stockTotal, 0);
    document.getElementById('kpi-disponibles').textContent = disponible.toLocaleString('es-CL');
    document.getElementById('kpi-disponibles-sub').textContent = `de ${total.toLocaleString('es-CL')} unidades físicas`;

    const pendientes = cotizaciones.filter((c) => c.estado === 'Pendiente');
    const montoPendiente = pendientes.reduce((s, c) => s + c.monto, 0);
    document.getElementById('kpi-cotizaciones-pendientes').textContent = pendientes.length;
    document.getElementById('kpi-cotizaciones-sub').textContent = `${formatearMoneda(montoPendiente)} en evaluación`;

    const montoMes = cotizaciones.filter((c) => c.fechaCreacion.startsWith('2026-08')).reduce((s, c) => s + c.monto, 0);
    document.getElementById('kpi-ingresos').textContent = formatearMoneda(montoMes);
    document.getElementById('kpi-ingresos-sub').textContent = '+12,4% vs mes anterior';
  }

  function renderOperacionesDelDia(inventario, reservas, mermas) {
    const entregas = reservas.filter((r) => r.fechaDespacho === HOY);
    const retiros = reservas.filter((r) => r.fechaRetiro === HOY);
    const porPreparar = reservas.filter((r) => ['Confirmada', 'En preparación'].includes(r.estado));
    const devolucionesPend = reservas.filter((r) => r.estado === 'En devolución');
    const mantencion = inventario.reduce((s, p) => s + p.mantencion, 0);

    document.getElementById('op-entregas').textContent = entregas.length;
    document.getElementById('op-retiros').textContent = retiros.length;
    document.getElementById('op-preparar').textContent = porPreparar.length;
    document.getElementById('op-devoluciones').textContent = devolucionesPend.length;
    document.getElementById('op-mantencion').textContent = mantencion;
    document.getElementById('op-mermas').textContent = mermas.length;
  }

  function renderProximosEventos(reservas) {
    const meses = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'];
    const proximos = reservas
      .filter((r) => r.fechaEvento >= HOY && !['Finalizada', 'Cancelada'].includes(r.estado))
      .sort((a, b) => a.fechaEvento.localeCompare(b.fechaEvento))
      .slice(0, 4);

    const el = document.getElementById('proximos-eventos');
    if (!proximos.length) {
      el.innerHTML = '<p class="empty-state">No hay eventos próximos.</p>';
      return;
    }

    el.innerHTML = proximos.map((r) => {
      const [y, m, d] = r.fechaEvento.split('-');
      return `
        <a href="reserva.html?id=${r.id}" class="list-row" style="text-decoration:none;color:inherit;">
          <div class="list-row-date"><strong>${d}</strong><span>${meses[Number(m) - 1]}</span></div>
          <div class="list-row-body">
            <strong>${r.tipoEvento} · ${r.clienteNombre}</strong>
            <span>${r.comuna} · ${r.invitados} invitados</span>
          </div>
          ${badgeHtml(r.estado)}
        </a>
      `;
    }).join('');
  }

  function renderAlertasInventario(inventario, reservas, hoy) {
    const alertas = [];

    inventario.filter((p) => p.estado === 'Stock bajo').forEach((p) => {
      alertas.push({
        href: `producto.html?codigo=${p.codigo}`, icon: '⚠', variant: 'danger',
        titulo: p.nombre, detalle: `Stock disponible bajo: ${p.disponible} unidades`,
      });
    });
    inventario.filter((p) => p.mantencion > 0).forEach((p) => {
      alertas.push({
        href: `producto.html?codigo=${p.codigo}`, icon: '🧺', variant: 'warning',
        titulo: p.nombre, detalle: `${p.mantencion} unidades en mantención`,
      });
    });
    reservas.filter((r) => r.estado === 'En devolución' && r.fechaRetiro < hoy).forEach((r) => {
      alertas.push({
        href: `reserva.html?id=${r.id}`, icon: '↩', variant: 'danger',
        titulo: r.productos[0] ? r.productos[0].nombre : r.tipoEvento, detalle: `Devolución atrasada · ${r.id}`,
      });
    });

    const el = document.getElementById('alertas-inventario');
    if (!alertas.length) {
      el.innerHTML = '<p class="empty-state">Sin alertas por ahora.</p>';
      return;
    }
    el.innerHTML = alertas.slice(0, 5).map((a) => `
      <a href="${a.href}" class="alert-row" style="text-decoration:none;color:inherit;">
        <span class="icon" style="background-color:var(--status-${a.variant}-bg);color:var(--status-${a.variant});">${a.icon}</span>
        <div>
          <strong>${a.titulo}</strong>
          <span>${a.detalle}</span>
        </div>
      </a>
    `).join('');
  }

  function renderCharts(inventario, cotizaciones, reservas) {
    const montoAgosto = cotizaciones.filter((c) => c.fechaCreacion.startsWith('2026-08')).reduce((s, c) => s + c.monto, 0);
    renderLineChart('chart-ingresos', [
      { label: 'Mar', value: 2100000 }, { label: 'Abr', value: 2800000 },
      { label: 'May', value: 3400000 }, { label: 'Jun', value: 4650000 },
      { label: 'Jul', value: 5200000 }, { label: 'Ago', value: montoAgosto },
    ], { formatValue: (v) => formatearMoneda(v) });

    const categorias = {};
    inventario.forEach((p) => { categorias[p.categoria] = (categorias[p.categoria] || 0) + p.reservado + p.arrendado; });
    const rankingCategorias = Object.entries(categorias)
      .map(([label, value]) => ({ label, value }))
      .sort((a, b) => b.value - a.value)
      .slice(0, 6);
    renderBarListChart('chart-categorias', rankingCategorias, { formatValue: (v) => `${v} uds` });

    const rankingProductos = [...inventario]
      .sort((a, b) => b.arrendado - a.arrendado)
      .slice(0, 6)
      .map((p) => ({ label: p.nombre, value: p.arrendado }));
    renderBarListChart('chart-productos', rankingProductos, { formatValue: (v) => `${v} uds` });

    const clientesCount = {};
    reservas.forEach((r) => { clientesCount[r.clienteNombre] = (clientesCount[r.clienteNombre] || 0) + 1; });
    const rankingClientes = Object.entries(clientesCount)
      .map(([label, value]) => ({ label, value }))
      .sort((a, b) => b.value - a.value)
      .slice(0, 5);
    renderBarListChart('chart-clientes', rankingClientes, { formatValue: (v) => `${v} reservas` });
  }

})();
