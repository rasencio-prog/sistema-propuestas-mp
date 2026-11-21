# ADR-0008 · Producción inicial en el equipo del propietario, lista para un servicio de contenedores

- Estado: Aceptada
- Fecha: 21-11-2026

## Contexto
Supabase aloja base, Storage y Auth, pero no procesos Python permanentes (API y worker). El propietario no quiere
elegir todavía un proveedor de hosting.

## Decisión
- Por ahora la API, el worker y el frontend corren **en el equipo del propietario** (Windows + Docker Desktop), con los
  mismos contenedores que en desarrollo. Base de producción, Storage y Auth en el proyecto Supabase en la nube.
- El radar corre programado a una hora configurable (ADR-0007) y a pedido.
- Todo se diseña para desplegar después en un **servicio de contenedores**: Railway, Render, Fly.io, Cloud Run o Azure
  Container Apps. Requisitos que se cumplen desde `/p3`: imágenes sin estado; configuración solo por variables de
  entorno; archivos en Supabase Storage (no en disco local, salvo la bandeja `intake/`); API y worker como procesos
  separados de la misma imagen; `/health` para el orquestador; logs JSON a la salida estándar.
- **La elección del servicio se decide antes de cerrar MVP-2**, con una nueva ADR.

## Consecuencias
- Costo de hosting cero en MVP-1 y buena parte de MVP-2.
- Si el equipo está apagado, el radar se atrasa hasta que vuelva a encenderse (mitigado por ADR-0007).
- La carpeta vigilada `intake/` funciona mientras el worker corra en el equipo; en la nube la vía será la carga por UI.
- Los secretos de producción viven en el `.env` del equipo hasta la migración; después, en el gestor de variables del
  servicio elegido.
