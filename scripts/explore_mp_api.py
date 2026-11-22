"""Script exploratorio (NO es código de producción) para /p2-api.

Objetivo: validar con el ticket real los endpoints públicos de la API de
Mercado Público (api.mercadopublico.cl) antes de diseñar el adaptador
definitivo (ver docs/10-api-validada.md).

Qué hace:
  1. Consulta el listado de licitaciones de un día reciente
     (GET licitaciones.json?fecha=ddmmaaaa).
  2. Si el listado trae ítems con rubro (CodigoCategoria), intenta elegir
     5 códigos de rubro TI (prefijo UNSPSC "43"); si no hay suficientes,
     completa con los primeros códigos disponibles y lo indica en el log.
  3. Para cada código, consulta el detalle (GET licitaciones.json?codigo=...).
  4. Respeta un ritmo configurable entre solicitudes (por defecto 1 cada 2
     segundos, `--ritmo-segundos`) y reintenta con backoff exponencial ante
     HTTP 429/5xx (máx. 3 intentos). Registra cuántas solicitudes consumió.
  5. Guarda cada respuesta cruda en docs/api-samples/*.json, saneada:
     se elimina cualquier aparición del ticket (en URL, cabeceras o en el
     cuerpo) antes de escribir a disco.
  6. Opcionalmente (`--check-ocds`), consulta la API OCDS pública de
     ChileCompra (api.mercadopublico.cl/APISOCDS/OCDS/, sin ticket) para 3
     de los códigos ya muestreados, para ver si entrega documentos.
  7. Escribe docs/api-samples/_run-log.json con tiempos de respuesta,
     códigos HTTP y consumo total, para alimentar docs/10-api-validada.md.

Reglas que respeta (CLAUDE.md):
  - Solo llama a api.mercadopublico.cl (nunca mercadopublico.cl ni
    chilecompra.cl); tampoco descarga ningún documento, solo registra URLs.
  - El ticket se lee solo desde el entorno vía python-dotenv; nunca se
    imprime, loguea ni escribe en los archivos de salida.
  - No automatiza nada sobre el portal ni descarga adjuntos.

Uso:
    python scripts/explore_mp_api.py [--fecha ddmmaaaa] [--max-intentos-fecha N]
                                      [--ritmo-segundos 2.0] [--check-ocds]

Requiere `MP_TICKET` en `.env` (ver `.env.example`).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
import os

BASE_URL = "https://api.mercadopublico.cl/servicios/v1/publico/licitaciones.json"
OCDS_BASE_URL = "https://api.mercadopublico.cl/APISOCDS/OCDS"
REPO_ROOT = Path(__file__).resolve().parent.parent
SAMPLES_DIR = REPO_ROOT / "docs" / "api-samples"
DEFAULT_SECONDS_BETWEEN_REQUESTS = 2.0  # decisión del propietario, ADR-0010
TI_CATEGORY_PREFIX = "43"  # UNSPSC segmento "Information Technology..."
SAMPLE_SIZE = 5
MAX_RETRIES_ON_429_5XX = 3


class ApiCallRecord:
    def __init__(self, label: str, url_sanitized: str) -> None:
        self.label = label
        self.url_sanitized = url_sanitized
        self.http_status: int | None = None
        self.duration_ms: float | None = None
        self.error: str | None = None
        self.body_bytes: int | None = None


def sanitize(obj: Any, ticket: str) -> Any:
    """Elimina el ticket real de cualquier string/valor anidado, y oculta
    cualquier clave que se llame (o contenga) 'ticket'."""
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if "ticket" in k.lower():
                out[k] = "<TICKET>"
            else:
                out[k] = sanitize(v, ticket)
        return out
    if isinstance(obj, list):
        return [sanitize(v, ticket) for v in obj]
    if isinstance(obj, str):
        if ticket and ticket in obj:
            return obj.replace(ticket, "<TICKET>")
        return obj
    return obj


def mask_url(url: str, ticket: str) -> str:
    masked = url.replace(ticket, "<TICKET>") if ticket else url
    # por si el ticket viniera url-encoded o con mayúsculas distintas
    masked = re.sub(r"(ticket=)[^&]+", r"\1<TICKET>", masked, flags=re.IGNORECASE)
    return masked


def _get_json(url: str, label: str) -> tuple[ApiCallRecord, Any]:
    record = ApiCallRecord(label, url)
    start = time.monotonic()
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read()
            record.http_status = resp.status
            record.body_bytes = len(raw)
            data = json.loads(raw.decode("utf-8"))
    except urllib.error.HTTPError as e:
        record.http_status = e.code
        record.error = f"HTTPError: {e.reason}"
        try:
            data = json.loads(e.read().decode("utf-8"))
        except Exception:
            data = None
    except urllib.error.URLError as e:
        record.error = f"URLError: {e.reason}"
        data = None
    except json.JSONDecodeError as e:
        record.error = f"JSONDecodeError: {e}"
        data = None
    finally:
        record.duration_ms = round((time.monotonic() - start) * 1000, 1)
    return record, data


def call_api(
    params: dict[str, str], ticket: str, label: str, max_retries: int = MAX_RETRIES_ON_429_5XX
) -> tuple[ApiCallRecord, Any]:
    """Llama a la API ticket-gated con reintentos y backoff exponencial ante
    429/5xx (ADR-0010): 2s, 4s, 8s antes de cada reintento."""
    query = dict(params)
    query["ticket"] = ticket
    url = f"{BASE_URL}?{urllib.parse.urlencode(query)}"
    masked_url = mask_url(url, ticket)

    attempt = 0
    while True:
        record, data = _get_json(url, label)
        record.url_sanitized = masked_url
        attempt += 1
        retryable = record.http_status == 429 or (record.http_status is not None and record.http_status >= 500)
        if not retryable or attempt > max_retries:
            return record, data
        wait_s = 2 ** attempt  # 4, 8, 16...
        print(f"    reintento {attempt}/{max_retries} para {label} tras status={record.http_status}; espero {wait_s}s")
        time.sleep(wait_s)


def pick_ti_codes(listado: list[dict[str, Any]], n: int) -> tuple[list[str], str]:
    """Busca códigos cuyo listado de ítems tenga CodigoCategoria con
    prefijo TI. Devuelve (códigos, nota) — la nota explica el criterio
    realmente usado, para que docs/10-api-validada.md no invente nada."""
    ti_codes: list[str] = []
    other_codes: list[str] = []

    for lic in listado:
        codigo = lic.get("CodigoExterno")
        if not codigo:
            continue
        items = (lic.get("Items") or {}).get("Listado") or []
        is_ti = any(
            str(item.get("CodigoCategoria", "")).startswith(TI_CATEGORY_PREFIX)
            for item in items
            if isinstance(item, dict)
        )
        if is_ti:
            ti_codes.append(codigo)
        else:
            other_codes.append(codigo)

    if len(ti_codes) >= n:
        return ti_codes[:n], (
            f"5 códigos con al menos un ítem de rubro TI (CodigoCategoria que empieza "
            f"con '{TI_CATEGORY_PREFIX}') encontrados en el listado."
        )

    faltan = n - len(ti_codes)
    combinados = ti_codes + other_codes[:faltan]
    if ti_codes:
        nota = (
            f"Solo {len(ti_codes)} código(s) de rubro TI en el listado de este día; "
            f"se completó con {faltan} código(s) de otro rubro (el listado del día no tenía más TI)."
        )
    else:
        nota = (
            "El listado no trajo información de rubro por ítem (o no había TI ese día); "
            "se tomaron los primeros códigos disponibles del listado, sin filtro de rubro."
        )
    return combinados[:n], nota


def check_ocds(codes: list[str], ritmo_segundos: float) -> list[dict[str, Any]]:
    """Consulta la API OCDS pública (sin ticket) para ver si entrega
    documentos de licitación. No descarga nada de mercadopublico.cl: solo
    registra lo que la API OCDS misma devuelva (incluidas URLs, si trae)."""
    results = []
    routes = ["tender", "record"]
    for i, codigo in enumerate(codes):
        for route in routes:
            if i > 0 or route != routes[0]:
                time.sleep(ritmo_segundos)
            url = f"{OCDS_BASE_URL}/{route}/{urllib.parse.quote(codigo)}"
            record, data = _get_json(url, f"ocds_{route}_{codigo}")
            print(f"  OCDS {route} {codigo}: status={record.http_status} body={data}")
            results.append(
                {
                    "codigo": codigo,
                    "ruta": route,
                    "url": url,
                    "http_status": record.http_status,
                    "duration_ms": record.duration_ms,
                    "respuesta": data,
                    "error": record.error,
                }
            )
    out_path = SAMPLES_DIR / "ocds_check.json"
    out_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Resultado de la verificación OCDS guardado en {out_path}")
    return results


def find_listing_with_data(
    ticket: str, start_date: date, max_attempts: int, ritmo_segundos: float
) -> tuple[ApiCallRecord, list[dict[str, Any]], date]:
    """Intenta el listado del día `start_date`; si viene vacío, retrocede
    día a día hasta `max_attempts` veces (p. ej. fines de semana)."""
    d = start_date
    last_record = None
    for attempt in range(max_attempts):
        fecha_str = d.strftime("%d%m%Y")
        record, data = call_api({"fecha": fecha_str}, ticket, f"listado_fecha_{fecha_str}")
        last_record = record
        yield record, data, d
        if data and int((data.get("Listado") and len(data["Listado"])) or 0) > 0:
            return
        d = d - timedelta(days=1)
        if attempt < max_attempts - 1:
            time.sleep(ritmo_segundos)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fecha",
        help="Fecha a consultar primero, formato ddmmaaaa. Por defecto: ayer.",
        default=None,
    )
    parser.add_argument(
        "--max-intentos-fecha",
        type=int,
        default=5,
        help="Si el día no trae licitaciones, cuántos días hacia atrás probar (default 5).",
    )
    parser.add_argument(
        "--ritmo-segundos",
        type=float,
        default=DEFAULT_SECONDS_BETWEEN_REQUESTS,
        help=f"Segundos mínimos entre solicitudes (default {DEFAULT_SECONDS_BETWEEN_REQUESTS}, ADR-0010).",
    )
    parser.add_argument(
        "--check-ocds",
        action="store_true",
        help="Además, consulta la API OCDS pública (sin ticket) para 3 de los códigos ya muestreados.",
    )
    args = parser.parse_args()
    ritmo_segundos = args.ritmo_segundos

    load_dotenv(REPO_ROOT / ".env")
    ticket = os.environ.get("MP_TICKET")
    if not ticket:
        print("ERROR: no se encontró MP_TICKET en el entorno (.env). Revisa .env.example.", file=sys.stderr)
        return 1

    if args.fecha:
        start_date = date(
            int(args.fecha[4:8]), int(args.fecha[2:4]), int(args.fecha[0:2])
        )
    else:
        start_date = date.today() - timedelta(days=1)

    SAMPLES_DIR.mkdir(parents=True, exist_ok=True)

    calls: list[ApiCallRecord] = []
    listado: list[dict[str, Any]] = []
    used_date: date | None = None

    print(f"Buscando un día con licitaciones publicadas, empezando en {start_date.isoformat()}...")
    for record, data, d in find_listing_with_data(ticket, start_date, args.max_intentos_fecha, ritmo_segundos):
        calls.append(record)
        print(
            f"  listado {d.isoformat()}: status={record.http_status} "
            f"duracion_ms={record.duration_ms} error={record.error}"
        )
        if data:
            listado = data.get("Listado") or []
            used_date = d
        if listado:
            break

    if not listado:
        print("No se encontró ningún día con licitaciones en el rango probado.", file=sys.stderr)
        _write_run_log(calls, ticket, extra={"listado_encontrado": False})
        return 1

    sample_listado = sanitize({"Listado": listado}, ticket)
    listado_path = SAMPLES_DIR / f"listado_{used_date.strftime('%Y-%m-%d')}.json"
    listado_path.write_text(
        json.dumps(sample_listado, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Listado guardado en {listado_path} ({len(listado)} licitaciones).")

    codes, nota_seleccion = pick_ti_codes(listado, SAMPLE_SIZE)
    print(f"Códigos elegidos para detalle: {codes}")
    print(f"Nota de selección: {nota_seleccion}")

    detail_summaries = []
    for codigo in codes:
        time.sleep(ritmo_segundos)
        record, data = call_api({"codigo": codigo}, ticket, f"detalle_{codigo}")
        calls.append(record)
        print(
            f"  detalle {codigo}: status={record.http_status} "
            f"duracion_ms={record.duration_ms} error={record.error}"
        )
        if data:
            sanitized = sanitize(data, ticket)
            safe_name = re.sub(r"[^A-Za-z0-9_-]", "_", codigo)
            detail_path = SAMPLES_DIR / f"detalle_{safe_name}.json"
            detail_path.write_text(
                json.dumps(sanitized, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            detail_summaries.append({"codigo": codigo, "archivo": detail_path.name})

    _write_run_log(
        calls,
        ticket,
        extra={
            "listado_encontrado": True,
            "fecha_usada": used_date.isoformat(),
            "licitaciones_en_listado": len(listado),
            "codigos_detalle": codes,
            "nota_seleccion_codigos": nota_seleccion,
            "detalles_guardados": detail_summaries,
        },
    )

    if args.check_ocds:
        muestra_ocds = codes[:3]
        print(f"\nVerificando API OCDS (sin ticket) para: {muestra_ocds}")
        check_ocds(muestra_ocds, ritmo_segundos)

    total = len(calls)
    print(f"\nTotal de solicitudes consumidas (API con ticket): {total}")
    print(f"Muestras guardadas en {SAMPLES_DIR}")
    return 0


def _write_run_log(calls: list[ApiCallRecord], ticket: str, extra: dict[str, Any]) -> None:
    log = {
        "total_requests": len(calls),
        "calls": [
            {
                "label": c.label,
                "url": c.url_sanitized,
                "http_status": c.http_status,
                "duration_ms": c.duration_ms,
                "body_bytes": c.body_bytes,
                "error": c.error,
            }
            for c in calls
        ],
        **extra,
    }
    (SAMPLES_DIR / "_run-log.json").write_text(
        json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    raise SystemExit(main())
