/**
 * reportes.js
 * Calcula las cuatro categorías de reportes (inventario, reservas,
 * clientes e información comercial) a partir de los mismos
 * datos que usa el resto del panel, aplicando el filtro de período
 * seleccionado sobre fechas de evento/creación/registro.
 */
(function () {
  const root = document.getElementById('ri-total');
  if (!root) return;

  const HOY = '2026-08-19';
  let inventario = [], clientes = [], cotizaciones = [], reservas = [];

  const CATEGORIAS_COLOR = [
    { nombre: 'Vajilla', color: '#2a78d6' },
    { nombre: 'Cristalería', color: '#eb6834' },
    { nombre: 'Cubiertos y servicio', color: '#1baf7a' },
    { nombre: 'Mantelería', color: '#eda100' },
    { nombre: 'Mesas y sillas', color: '#e87ba4' },
    { nombre: 'Decoración', color: '#008300' },
    { nombre: 'Equipamiento', color: '#4a3aa7' },
    { nombre: 'Carpas y exteriores', color: '#e34948' },
  ];

  Promise.all([
    obtenerDatos('inventario'), obtenerDatos('clientes'), obtenerDatos('cotizaciones'),
    obtenerDatos('reservas'),
  ]).then(([inv, cli, cot, res]) => {
    inventario = inv; clientes = cli; cotizaciones = cot; reservas = res;
    render();
  }).catch((err) => console.error('Error cargando reportes', err));

  document.getElementById('rep-periodo').addEventListener('change', render);

  function limiteInferior() {
    const periodo = document.getElementById('rep-periodo').value;
    if (periodo === 'mes') return '2026-08-01';
    if (periodo === 'trimestre') return '2026-06-01';
    return '0000-01-01';
  }

  function render() {
    const desde = limiteInferior();
    renderInventario();
    renderReservas(desde);
    renderClientes(desde);
    renderComercial(desde);
  }

  function renderInventario() {
    document.getElementById('ri-total').textContent = inventario.reduce((s, p) => s + p.stockTotal, 0).toLocaleString('es-CL');
    document.getElementById('ri-disponible').textContent = inventario.reduce((s, p) => s + p.disponible, 0).toLocaleString('es-CL');
    document.getElementById('ri-comprometido').textContent = inventario.reduce((s, p) => s + p.reservado + p.arrendado, 0).toLocaleString('es-CL');
    document.getElementById('ri-bajo').textContent = inventario.filter((p) => p.estado === 'Stock bajo').length;

    const ordenado = [...inventario].sort((a, b) => b.arrendado - a.arrendado);
    renderRankingChart('ri-chart-mas', ordenado.slice(0, 5).map((p) => ({ label: p.nombre, value: p.arrendado })), { formatValue: (v) => `${v} uds` });
    renderRankingChart('ri-chart-menos', [...ordenado].reverse().slice(0, 5).map((p) => ({ label: p.nombre, value: p.arrendado })), { formatValue: (v) => `${v} uds` });
  }

  function renderReservas(desde) {
    const enPeriodo = reservas.filter((r) => r.fechaEvento >= desde);
    document.getElementById('rr-total').textContent = enPeriodo.length;
    document.getElementById('rr-proximas').textContent = reservas.filter((r) => r.fechaEvento >= HOY && !['Finalizada', 'Cancelada'].includes(r.estado)).length;
    document.getElementById('rr-finalizadas').textContent = enPeriodo.filter((r) => r.estado === 'Finalizada').length;
    document.getElementById('rr-canceladas').textContent = enPeriodo.filter((r) => r.estado === 'Cancelada').length;
  }

  function renderClientes(desde) {
    document.getElementById('rc-total').textContent = clientes.length;
    document.getElementById('rc-nuevos').textContent = clientes.filter((c) => c.clienteDesde >= desde).length;

    const conteo = {};
    reservas.filter((r) => r.fechaEvento >= desde).forEach((r) => { conteo[r.clienteNombre] = (conteo[r.clienteNombre] || 0) + 1; });
    const ranking = Object.entries(conteo).map(([label, value]) => ({ label, value })).sort((a, b) => b.value - a.value).slice(0, 6);
    renderRankingChart('rc-chart', ranking, { formatValue: (v) => `${v} reserva${v === 1 ? '' : 's'}` });
  }

  function renderComercial(desde) {
    const enPeriodo = cotizaciones.filter((c) => c.fechaCreacion >= desde);
    const cotizado = enPeriodo.reduce((s, c) => s + c.monto, 0);
    const aceptadas = enPeriodo.filter((c) => c.estado === 'Aceptada');
    const rechazadas = enPeriodo.filter((c) => c.estado === 'Rechazada');
    document.getElementById('rn-cotizado').textContent = formatearMoneda(cotizado);
    document.getElementById('rn-aceptadas').textContent = aceptadas.length;
    document.getElementById('rn-rechazadas').textContent = rechazadas.length;
    document.getElementById('rn-ticket').textContent = aceptadas.length ? formatearMoneda(aceptadas.reduce((s, c) => s + c.monto, 0) / aceptadas.length) : '$0';

    const porCategoria = {};
    enPeriodo.forEach((c) => {
      (c.lineas || []).forEach((l) => {
        const producto = inventario.find((p) => p.codigo === l.codigo);
        const cat = producto ? producto.categoria : 'Otros';
        porCategoria[cat] = (porCategoria[cat] || 0) + l.precio * l.cantidad;
      });
    });
    const items = CATEGORIAS_COLOR.map((c) => ({ label: c.nombre, value: porCategoria[c.nombre] || 0, color: c.color }));
    if (porCategoria['Otros']) items.push({ label: 'Otros', value: porCategoria['Otros'], color: '#9c9a94' });
    renderStackedBarChart('rn-chart', items, { formatValue: (v) => formatearMoneda(v) });
  }
})();
