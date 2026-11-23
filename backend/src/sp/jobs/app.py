"""App de Procrastinate (cola sobre Postgres, ADR-0001). Sin tareas todavia: el radar, el analisis
IA y la generacion de Excel se agregan en sus propias etapas (/p4 en adelante). Esta Etapa 1 solo
deja el worker arrancando y conectado, para validar la instalacion del esquema (docs/03, ADR-0014).
"""

from __future__ import annotations

from procrastinate import App, PsycopgConnector

from sp.core.settings import get_settings

app = App(connector=PsycopgConnector(conninfo=get_settings().psycopg_conninfo))
