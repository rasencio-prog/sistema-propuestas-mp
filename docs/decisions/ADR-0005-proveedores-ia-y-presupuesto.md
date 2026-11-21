# ADR-0005 · Capa LLMProvider propia, proveedores a comparar y presupuesto de IA

- Estado: Aceptada
- Fecha: 21-11-2026

## Contexto
El proveedor de IA estaba pendiente; el brief pide elegirlo con el conjunto de evaluación y detrás de una capa de
abstracción. Las bases de licitación son documentos públicos.

## Decisión
- Interfaz propia y delgada `LLMProvider` (sin LiteLLM ni LangChain) que devuelve objetos Pydantic validados y registra
  tokens, costo y latencia. SDK oficiales `anthropic` y `openai`.
- Configuraciones a comparar en `/p9`: **Claude Opus 5.5**, **Claude Sonnet 5.5** y el modelo vigente de **OpenAI**
  (ID y precio se fijan en `/p7` desde la documentación oficial).
- **Presupuesto**: tope mensual configurable por organización, valor inicial **USD 40**, **alerta al 80 %** (auditoría,
  aviso en "Lotes y ejecuciones", log). Al 100 % los análisis nuevos quedan `blocked_budget` hasta el mes siguiente o
  hasta que un administrador suba el tope (auditado). Mes calendario en hora de Chile; las corridas del eval cuentan.
- **Datos**: requisito de que el proveedor **no use los datos para entrenar** (se verifica y documenta en `/p7`).
  No se exige retención cero en MVP-1/2; se revisa en MVP-3 junto con CV y datos de la empresa.
- Citas verificadas por el backend; puntaje y semáforo calculados por el backend.

## Consecuencias
- Se puede cambiar de proveedor o modelo sin tocar el dominio.
- Hace falta mantener 2 cuentas API durante la comparación.
- El tope puede detener análisis a fin de mes; el administrador puede ampliarlo.
