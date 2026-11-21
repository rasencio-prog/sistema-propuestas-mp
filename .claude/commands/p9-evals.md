---
description: Conjunto de evaluación y métricas de calidad de la IA
---

Lee CLAUDE.md, docs/01 (sección 2.7), docs/05 (épica E7), docs/07 (sección 3), ADR-0005 y la sección 17 del brief. Implementa el arnés de evaluación en backend/evals.

1. Formato de anotación simple para que yo complete a mano (plantilla en Excel por defecto): por licitación, código, líneas de servicio correctas, valores esperados de la ficha (presupuesto, plazos, SLA, garantías, fechas tal como aparecen en la ficha), lista de requisitos excluyentes y qué campos no existen en las bases. Genera una plantilla y una guía de anotación de una página.
2. El arnés debe funcionar desde 5 licitaciones anotadas y crecer hasta 15-20 sin cambiar código; se puede volver a correr solo sobre las nuevas.
3. Script que corra clasificación y análisis sobre el conjunto y calcule:
   - Coincidencia de líneas de servicio (objetivo: 85 %).
   - Recall de requisitos excluyentes (objetivo: 90 %), con coincidencia aproximada de texto.
   - Exactitud de fechas (objetivo: 100 %) y de cada campo de la ficha.
   - Porcentaje de valores con cita verificada.
   - Valores inventados: valor entregado donde la anotación dice "no existe" (objetivo: 0).
   - Costo y tiempo por licitación.
   Con menos de 15 licitaciones, informa los resultados como fracciones (p. ej. 4/5) y márcalos como indicativos.
4. Comparación de proveedores: el mismo conjunto contra las 3 configuraciones de docs/01 sección 2.7 (Claude Opus 5.5, Claude Sonnet 5.5 y el modelo de OpenAI fijado en /p7), con tabla comparativa. Antes de correr, muestra el costo estimado; las corridas cuentan para el tope mensual de IA y se detienen si se alcanza.
5. Informe en docs/11-evaluacion-<fecha>.md con tamaño del conjunto, resultados, los 5 peores errores con su explicación y recomendaciones de ajuste de prompts. Sin texto de las bases reales en el informe.
6. Umbrales configurables; los objetivos de arriba son provisionales hasta que yo los confirme con 15-20 licitaciones.
7. Las bases reales del conjunto no se suben al repo: van en backend/evals/data/ (excluida en .gitignore); solo plantilla y código al repo.

Al terminar: dame la plantilla de anotación, explícame cómo correr la evaluación y detente.
