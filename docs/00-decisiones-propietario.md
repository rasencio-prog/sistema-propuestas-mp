# Decisiones del propietario

Completa antes de ejecutar `/p1-plan`. Deja **PENDIENTE** en lo que no sepas: el agente lo propondrá con justificación.

| Decisión | Valor |
| --- | --- |
| Empresa usuaria | Databrain SpA — empresa de servicios TI (datos corporativos se cargan en MVP-3) |
| Usuarios iniciales | 1 usuario: Robinson Asencio (administrador). Preparado para crecer a 1-3 usuarios |
| Despliegue | Desarrollo local en mi equipo con Docker. Producción en Supabase (nube): PostgreSQL, pgvector, Storage y Auth |
| Frecuencia del radar | Diaria nocturna |
| Modalidades del MVP | Solo licitaciones (Compra Ágil después) |
| Proveedor de IA | Comparar Anthropic (Opus 5.5 y Sonnet 5.5) contra OpenAI detrás de una capa propia. Tope USD 40/mes configurable, alerta al 80 %. El proveedor no debe usar los datos para entrenar; retención cero se revisa en MVP-3 (ADR-0005) |
| Ejecución del backend | En mi equipo (Windows + Docker) por ahora; servicio de contenedores en la nube a elegir antes de cerrar MVP-2 (ADR-0008) |
| Desarrollo local en | Windows |
| Palabras clave / rubros iniciales | Derivadas de las 5 líneas de servicio del brief (sección 2) |
| Umbrales de aceptación | Provisionales: 85 % clasificación, 90 % requisitos excluyentes, 100 % fechas |
| Conjunto de evaluación | 5 licitaciones anotadas al terminar /p7; luego 15-20 |
| Selección del Excel 1 | Filtros duros: estado Publicada y cierre ≥ 3 días. Entran las 50 de mayor puntaje + todas con puntaje ≥ 40 (configurables) |
| Compuerta 1 | Motivo obligatorio en Descartar; responsable obligatorio en Descargar; Dudoso sin obligatorios |

Respuestas completas a las preguntas de `/p1-plan`: `docs/09-preguntas.md`.