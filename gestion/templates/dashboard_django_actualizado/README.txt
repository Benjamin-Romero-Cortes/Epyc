ACTUALIZACIÓN DEL DASHBOARD (inicio.html)

Incluye:
- inicio.html: dashboard conectado a Django/PostgreSQL.
- gestionIndex_para_views.py.txt: función gestionIndex() para copiar a views.py.
- views.py: si estaba disponible el views.py generado anteriormente, se incluye ya actualizado.

El dashboard ahora obtiene:
- reservas activas;
- reservas de los próximos 7 días;
- stock total y trabajable;
- cotizaciones pendientes;
- monto cotizado del mes;
- próximos eventos;
- alertas de inventario;
- entregas de hoy;
- retiros de hoy;
- preparaciones pendientes;
- devoluciones pendientes;
- registros de merma;
- productos más arrendados;
- categorías más solicitadas;
- clientes con más reservas;
- ingresos de los últimos meses.

La tarjeta "En mantención" queda en 0 porque el modelo actual no tiene una tabla/campo
específico de mantención. Cuando se agregue, se conecta fácilmente.

También se eliminaron del dashboard los antiguos data/*.js y dashboard.js que cargaban datos simulados.
