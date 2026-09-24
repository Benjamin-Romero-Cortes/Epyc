/**
 * admin-datos.js
 * Punto único para obtener los datos demostrativos del panel (inventario,
 * clientes, cotizaciones, reservas, movimientos, mermas, usuarios).
 * Intenta cargar el .json correspondiente (listo para cuando el panel se
 * conecte a una base de datos/API real); si el navegador bloquea esa
 * carga -por ejemplo al abrir el archivo directamente, sin servidor- usa
 * la copia embebida en el archivo -data.js correspondiente como respaldo.
 *
 * Todas las pantallas leen desde aquí para que la información se
 * mantenga consistente entre módulos (ej. la Reserva RES-0152 muestra el
 * mismo cliente y productos en Reservas, Preparación, Despachos, etc.).
 */
const ADMIN_DATA_MAP = {
  inventario: 'INVENTARIO_DATA',
  movimientos: 'MOVIMIENTOS_DATA',
  clientes: 'CLIENTES_DATA',
  cotizaciones: 'COTIZACIONES_DATA',
  reservas: 'RESERVAS_DATA',
  mermas: 'MERMAS_DATA',
  usuarios: 'USUARIOS_DATA',
};

function obtenerDatos(nombre) {
  return fetch(`data/${nombre}.json`)
    .then((res) => {
      if (!res.ok) throw new Error('Respuesta no válida de ' + nombre);
      return res.json();
    })
    .catch(() => {
      const varName = ADMIN_DATA_MAP[nombre];
      if (varName && typeof window[varName] !== 'undefined') return window[varName];
      throw new Error('No se pudieron cargar los datos de ' + nombre);
    });
}

function formatearMoneda(valor) {
  return (valor || 0).toLocaleString('es-CL', { style: 'currency', currency: 'CLP', maximumFractionDigits: 0 });
}

function formatearFecha(iso) {
  if (!iso) return '—';
  const [y, m, d] = iso.split('-');
  return `${d}-${m}-${y}`;
}

function formatearFechaLarga(iso) {
  if (!iso) return '—';
  const meses = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre'];
  const [y, m, d] = iso.split('-').map(Number);
  return `${d} de ${meses[m - 1]} de ${y}`;
}

function iniciales(nombre) {
  return nombre.split(' ').filter(Boolean).slice(0, 2).map((w) => w[0]).join('').toUpperCase();
}

/** Mapea cada estado de negocio a una variante visual de badge. */
const ESTADO_BADGE = {
  // Cotizaciones
  Borrador: 'neutral', Pendiente: 'warning', Enviada: 'info', Aceptada: 'success', Rechazada: 'danger', Vencida: 'danger',
  // Reservas
  Confirmada: 'info', 'En preparación': 'warning', Preparada: 'info', Despachada: 'info',
  'En arriendo': 'success', 'En devolución': 'warning', Finalizada: 'success', Cancelada: 'danger',
  // Inventario / clientes / usuarios
  Activo: 'success', 'Stock bajo': 'danger', 'Revisar mermas': 'warning', Prospecto: 'neutral', Inactivo: 'neutral',
  // Etiquetas visuales de despacho (derivadas del estado de la reserva)
  'En ruta': 'info', Entregado: 'success',
};

function badgeHtml(estado) {
  const variante = ESTADO_BADGE[estado] || 'neutral';
  return `<span class="badge badge--${variante}">${estado}</span>`;
}
