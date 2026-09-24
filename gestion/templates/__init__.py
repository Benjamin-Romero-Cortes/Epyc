{% load static %}
<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Resumen general · Panel Entre Platos y Copas</title>
<link rel="icon" href="{% static 'images/logo.jpg' %}">
<link rel="stylesheet" href="{% static 'css/admin.css' %}">
</head>
<body>

<div class="admin-shell">

  <aside class="admin-sidebar" id="admin-sidebar">
    <div class="sidebar-brand">
      <a href="{% url 'index' %}"><img src="{% static 'images/logo2.jpg' %}" alt="Entre Platos y Copas"></a>
    </div>
    <nav class="sidebar-nav">
      <a href="{% url 'index' %}" class="sidebar-link"><span class="nav-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="7" rx="1.3"/><rect x="14" y="3" width="7" height="7" rx="1.3"/><rect x="3" y="14" width="7" height="7" rx="1.3"/><rect x="14" y="14" width="7" height="7" rx="1.3"/></svg></span><span class="nav-label">Resumen</span></a>

      <span class="sidebar-group-label">Operación</span>
      <a href="clientes.html" class="sidebar-link"><span class="nav-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M15.5 3.13a4 4 0 0 1 0 7.75"/></svg></span><span class="nav-label">Clientes</span></a>
      <a href="{% url 'gestion_inventario' %}" class="sidebar-link"><span class="nav-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3l8 4.5v9L12 21l-8-4.5v-9L12 3z"/><path d="M12 12l8-4.5M12 12v9M12 12L4 7.5"/></svg></span><span class="nav-label">Inventario</span><span class="badge-count" id="badge-inventario" hidden>0</span></a>
      <a href="cotizaciones.html" class="sidebar-link"><span class="nav-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M14 3H6a1 1 0 0 0-1 1v16a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V8l-5-5z"/><path d="M14 3v5h5"/><path d="M9 13h6M9 17h6"/></svg></span><span class="nav-label">Cotizaciones</span></a>
      <a href="reservas.html" class="sidebar-link"><span class="nav-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M16 3v4M8 3v4M3 10h18"/></svg></span><span class="nav-label">Reservas</span></a>
      <a href="preparacion.html" class="sidebar-link"><span class="nav-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><rect x="6" y="4" width="12" height="17" rx="2"/><rect x="9" y="2" width="6" height="4" rx="1"/><path d="M9 11h6M9 15h6"/></svg></span><span class="nav-label">Preparación de pedidos</span></a>
      <a href="despachos.html" class="sidebar-link"><span class="nav-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="7" width="13" height="9"/><path d="M15 10h4l3 3v3h-7z"/><circle cx="6.5" cy="18.5" r="1.6"/><circle cx="17.5" cy="18.5" r="1.6"/></svg></span><span class="nav-label">Despachos</span></a>
      <a href="devoluciones.html" class="sidebar-link"><span class="nav-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12a9 9 0 1 1 3 6.7"/><path d="M3 17v-5h5"/></svg></span><span class="nav-label">Devoluciones</span></a>
      <a href="mermas.html" class="sidebar-link"><span class="nav-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3l10 18H2L12 3z"/><path d="M12 10v4M12 17h.01"/></svg></span><span class="nav-label">Mermas</span></a>
      <a href="calendario.html" class="sidebar-link"><span class="nav-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M16 3v4M8 3v4M3 10h18"/><rect x="7" y="13.3" width="3" height="3" rx="0.5" fill="currentColor" stroke="none"/><rect x="14" y="13.3" width="3" height="3" rx="0.5" fill="currentColor" stroke="none"/></svg></span><span class="nav-label">Calendario</span></a>

      <span class="sidebar-group-label">Análisis</span>
      <a href="reportes.html" class="sidebar-link"><span class="nav-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M4 20V10M12 20V4M20 20v-7"/></svg></span><span class="nav-label">Reportes</span></a>

      <span class="sidebar-group-label">Sistema</span>
      <a href="usuarios.html" class="sidebar-link"><span class="nav-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2l7 3v6c0 5-3.5 8.5-7 10-3.5-1.5-7-5-7-10V5l7-3z"/><circle cx="12" cy="10" r="2.2"/><path d="M8.7 16a3.6 3.6 0 0 1 6.6 0"/></svg></span><span class="nav-label">Usuarios</span></a>
      <a href="configuracion.html" class="sidebar-link"><span class="nav-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.6 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.6a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg></span><span class="nav-label">Configuración</span></a>
    </nav>
    <div class="sidebar-footer">
      <a href="{% url 'inicio' %}" class="sidebar-link" target="_blank" rel="noopener"><span class="nav-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><path d="M15 3h6v6"/><path d="M10 14L21 3"/></svg></span><span class="nav-label">Ver sitio público</span></a>
      <a href="login.html" class="sidebar-link"><span class="nav-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><path d="M16 17l5-5-5-5"/><path d="M21 12H9"/></svg></span><span class="nav-label">Cerrar sesión</span></a>
    </div>
  </aside>

  <div class="admin-main">
    <header class="admin-topbar">
      <div style="display:flex;align-items:center;gap:1rem;">
        <button class="nav-toggle-admin" id="sidebar-toggle" aria-label="Abrir menú">☰</button>
        <div class="topbar-title">
          <span class="eyebrow" id="topbar-date">Lunes, 17 de agosto</span>
          <h1>Resumen general</h1>
        </div>
      </div>
      <div class="topbar-search">
        <span class="icon">🔍</span>
        <input type="search" id="global-search" placeholder="Buscar productos, clientes, cotizaciones, reservas...">
      </div>
      <div class="topbar-actions">
        <button class="icon-btn" aria-label="Notificaciones"><span class="dot"></span>🔔</button>
        <div class="topbar-user">
          <div class="user-avatar">HC</div>
          <div class="user-info"><strong>Helen Cortés</strong><span>Administradora</span></div>
        </div>
      </div>
    </header>

    <main class="admin-content">

      <div class="hero-banner">
        <div>
          <span class="eyebrow" style="display:block;font-size:0.72rem;letter-spacing:0.12em;text-transform:uppercase;font-weight:700;">Panel de hoy</span>
          <h2>Todo bajo control, Helen.</h2>
          <p id="hero-summary">Cargando resumen del día...</p>
        </div>
        <a href="cotizaciones.html?nueva=1" class="btn btn-accent">+ Nueva cotización</a>
      </div>

      <div class="kpi-grid">
        <div class="kpi-card">
          <div class="kpi-top">
            <span class="kpi-label">Reservas activas</span>
          </div>
          <div class="kpi-value" id="kpi-reservas-activas">—</div>
          <span class="kpi-delta is-positive" id="kpi-reservas-delta"></span>
        </div>
        <div class="kpi-card">
          <div class="kpi-top">
            <span class="kpi-label">Artículos disponibles</span>
          </div>
          <div class="kpi-value" id="kpi-disponibles">—</div>
          <span class="kpi-delta" id="kpi-disponibles-sub"></span>
        </div>
        <div class="kpi-card">
          <div class="kpi-top">
            <span class="kpi-label">Cotizaciones pendientes</span>
          </div>
          <div class="kpi-value" id="kpi-cotizaciones-pendientes">—</div>
          <span class="kpi-delta" id="kpi-cotizaciones-sub"></span>
        </div>
        <div class="kpi-card">
          <div class="kpi-top">
            <span class="kpi-label">Monto cotizado del mes</span>
          </div>
          <div class="kpi-value" id="kpi-ingresos" style="font-size:1.6rem;">—</div>
          <span class="kpi-delta is-positive" id="kpi-ingresos-sub"></span>
        </div>
      </div>

      <div class="section-row">
        <div class="card">
          <div class="card-head">
            <div>
              <span class="eyebrow">Agenda</span>
              <h2>Próximos eventos</h2>
            </div>
            <a href="reservas.html" class="link">Ver todos →</a>
          </div>
          <div id="proximos-eventos"></div>
        </div>

        <div class="card">
          <div class="card-head">
            <div>
              <span class="eyebrow">Atención</span>
              <h2>Alertas de inventario</h2>
            </div>
          </div>
          <div id="alertas-inventario"></div>
          <a href="inventario.html?estado=Stock+bajo" class="link" style="display:block;margin-top:0.8rem;">Revisar inventario →</a>
        </div>
      </div>

      <div class="kpi-grid" style="grid-template-columns:repeat(auto-fit,minmax(160px,1fr));">
        <div class="kpi-card">
          <span class="kpi-label">Entregas hoy</span>
          <div class="kpi-value" id="op-entregas" style="font-size:1.6rem;">—</div>
        </div>
        <div class="kpi-card">
          <span class="kpi-label">Retiros hoy</span>
          <div class="kpi-value" id="op-retiros" style="font-size:1.6rem;">—</div>
        </div>
        <div class="kpi-card">
          <span class="kpi-label">Pendientes de preparar</span>
          <div class="kpi-value" id="op-preparar" style="font-size:1.6rem;">—</div>
        </div>
        <div class="kpi-card">
          <span class="kpi-label">Devoluciones pendientes</span>
          <div class="kpi-value" id="op-devoluciones" style="font-size:1.6rem;">—</div>
        </div>
        <div class="kpi-card">
          <span class="kpi-label">En mantención</span>
          <div class="kpi-value" id="op-mantencion" style="font-size:1.6rem;">—</div>
        </div>
        <div class="kpi-card">
          <span class="kpi-label">Registros de merma</span>
          <div class="kpi-value" id="op-mermas" style="font-size:1.6rem;">—</div>
        </div>
      </div>

      <div class="section-row">
        <div class="card">
          <div class="card-head">
            <div><span class="eyebrow">Tendencia</span><h2>Arriendos y evolución de ingresos</h2></div>
          </div>
          <div id="chart-ingresos"></div>
        </div>
        <div class="card">
          <div class="card-head">
            <div><span class="eyebrow">Ranking</span><h2>Categorías más solicitadas</h2></div>
          </div>
          <div id="chart-categorias"></div>
        </div>
      </div>

      <div class="section-row">
        <div class="card">
          <div class="card-head">
            <div><span class="eyebrow">Ranking</span><h2>Productos más arrendados</h2></div>
          </div>
          <div id="chart-productos"></div>
        </div>
        <div class="card">
          <div class="card-head">
            <div><span class="eyebrow">Fidelización</span><h2>Clientes con más reservas</h2></div>
          </div>
          <div id="chart-clientes"></div>
        </div>
      </div>

    </main>
  </div>
</div>

<script src="{% static 'data/inventario-data.js' %}"></script>
<script src="{% static 'data/movimientos-data.js' %}"></script>
<script src="{% static 'data/clientes-data.js' %}"></script>
<script src="{% static 'data/cotizaciones-data.js' %}"></script>
<script src="{% static 'data/reservas-data.js' %}"></script>
<script src="{% static 'data/mermas-data.js' %}"></script>
<script src="{% static 'data/usuarios-data.js' %}"></script>
<script src="{% static 'js/admin-datos.js' %}"></script>
<script src="{% static 'js/admin-nav.js' %}"></script>
<script src="{% static 'js/admin-search.js' %}"></script>
<script src="{% static 'js/charts.js' %}"></script>
<script src="{% static 'js/dashboard.js' %}"></script>
</body>
</html>
