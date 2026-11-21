---
description: Conjunto de evaluación y métricas de calidad de la IA
---

Lee CLAUDE.md, docs/07 y la sección 17 del brief. Implementa el arnés de evaluación en backend/evals.

1. Formato de anotación simple para que yo complete a mano: un Excel o YAML por licitación con código, líneas de servicio correctas, valores esperados de la ficha (presupuesto, plazos, SLA, garantías, fechas) y lista de requisitos excluyentes. Genera una plantilla y una guía de anotación de una página.
2. Script que corra clasificación y análisis sobre el conjunto y calcule:
   - Coincidencia de líneas de servicio (objetivo: 85 %).
   - Recall de requisitos excluyentes (objetivo: 90 %), con coincidencia aproximada de texto.
   - Exactitud de fechas (objetivo: 100 %) y de cada campo de la ficha.
   - Porcentaje de valores con cita verificada.
   - Valores inventados: valor entregado donde la anotación dice "no existe" (objetivo: 0).
   - Costo y tiempo por licitación.
3. Comparación de proveedores: el mismo conjunto contra 2 configuraciones de proveedor/modelo (las de docs/01), con tabla comparativa.
4. Informe en docs/11-evaluacion-<fecha>.md con resultados, los 5 peores errores con su explicación y recomendaciones de ajuste de prompts.
5. Umbrales configurables; los objetivos de arriba son provisionales hasta que yo los confirme.
6. Las bases reales del conjunto no se suben al repo: van en backend/evals/data/ (excluida en .gitignore); solo plantilla y código al repo.

Al terminar: dame la plantilla de anotación, explícame cómo correr la evaluación y detente.
