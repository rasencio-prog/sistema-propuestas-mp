# ADR-0013 · Frontend: React + Vite + TypeScript (SPA) en vez de Next.js

- Estado: Aceptada
- Fecha: 22-11-2026
- Decide: propietario, antes de `/p3-fundaciones`
- Reemplaza: la elección de Next.js de `docs/01` §2.5 (que a su vez ya era un desvío parcial del brief, que sugería
  Next.js App Router)

## Contexto

`docs/01` §2.5 había elegido Next.js (App Router) + TypeScript "para no desviarse del brief", aunque ya se reconocía
que una alternativa sin Node (FastAPI + Jinja2 + HTMX) era más simple para las 4-5 pantallas de este sistema. El
propietario decide ahora, antes de empezar `/p3-fundaciones`, que prefiere **React + Vite + TypeScript** porque:
- La interfaz es interna, de pocas pantallas (login, configuración, lotes y ejecuciones, carga de documentos), sin
  necesidad de renderizado en servidor ni SEO.
- El propietario ya conoce React y Vite, lo que reduce la curva de aprendizaje frente a las particularidades del
  App Router de Next.js (server components, rutas de servidor, etc.), que aquí no aportan nada.
- Menor complejidad: una aplicación de una sola página (SPA) compilada a archivos estáticos es más simple de servir
  y de razonar que un framework con renderizado híbrido.

## Decisión

- **React 18+ con Vite + TypeScript**, como SPA (sin renderizado en servidor).
- **React Router** para la navegación entre pantallas (login, configuración, lotes y ejecuciones, carga de
  documentos), todas dentro de la misma aplicación compilada.
- **`@supabase/supabase-js`** se usa solo para el login (obtener el JWT de Supabase Auth); el resto de la app llama
  siempre a la API propia de FastAPI con ese JWT. No cambia el diseño de seguridad de `docs/01` §2.4 y `docs/02` §5:
  el navegador nunca habla directo con la base, y ahora, al no haber ningún código de servidor en el frontend,
  **toda** la lógica de negocio y autorización vive exclusivamente en FastAPI.
- Tailwind + shadcn/ui se mantienen (compatibles con Vite); no cambia nada de `docs/01` más allá del framework base.
- El build de Vite (`npm run build`) genera archivos estáticos (`frontend/dist/`); no requiere un runtime Node en
  producción. Dónde se sirven esos archivos (el propio backend FastAPI, un hosting estático, o el mismo servicio de
  contenedores que se elija para la API) se decide junto con ADR-0008/ADR-0012, no aquí.
- El backend FastAPI habilita **CORS** explícito para el origen del frontend: `http://localhost:5173` en desarrollo
  (puerto por defecto de Vite), y el origen real de producción cuando se decida dónde se sirve el estático. Esto es
  nuevo respecto del diseño con Next.js, donde frontend y backend podían convivir detrás de un solo dominio con menos
  fricción de CORS.
- Variables de entorno del frontend: prefijo **`VITE_`** en vez de `NEXT_PUBLIC_`, porque Vite solo expone al
  navegador las variables con ese prefijo (ver `.env.example` y `frontend/.env.local`).

## Consecuencias

- **Sin SSR ni SEO**: irrelevante para una herramienta interna detrás de login; si alguna vez hiciera falta (no se
  prevé), sería una nueva ADR.
- **Despliegue como sitio estático**: más simple que Next.js en modo híbrido; no hay que operar un proceso Node en
  producción solo para el frontend.
- **CORS explícito**: hay que configurarlo y probarlo en `/p3-fundaciones` (dev, puerto 5173) y revisarlo cuando se
  decida el hosting de producción; con Next.js detrás del mismo dominio este paso no existía.
- Dependencias que cambian en `docs/01` §2.5: se quita `next`; se agregan `react-router-dom` y `vite` (ya estaban
  `react`, `@supabase/supabase-js`, Tailwind y shadcn/ui).
- Sin impacto en el backend, el modelo de datos, la seguridad (JWT + roles propios) ni ninguna decisión de
  `docs/01` fuera de §2.5, ni en ADR-0001 a ADR-0012.
