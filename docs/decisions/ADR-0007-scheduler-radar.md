# ADR-0007 · Scheduler horario con guarda "ya corrió hoy" en hora de Chile

- Estado: Aceptada
- Fecha: 21-11-2026

## Contexto
El radar debe correr una vez al día a una hora configurable (preferentemente entre 22:00 y 07:00, según recomienda
ChileCompra) y también a pedido. Chile tiene cambios de horario y el backend corre por ahora en un equipo que puede
estar apagado.

## Decisión
- Una tarea periódica de Procrastinate corre **cada hora**. Encola el radar solo si la hora local
  (`America/Santiago`) ya pasó la hora configurada y no existe una corrida exitosa para la fecha radar de hoy.
- Restricción única parcial en `radar_runs (organization_id, radar_date) WHERE status = 'succeeded'` y bloqueo de
  Procrastinate para no correr dos a la vez.
- Ejecución manual desde la UI (solo administrador) con el mismo trabajo.

## Consecuencias
- Inmune a cambios de horario y a la zona horaria del servidor.
- Si el equipo estuvo apagado a la hora configurada, el radar corre apenas vuelva a estar encendido ese día.
- Granularidad de una hora, suficiente para una corrida diaria.
