"""Cliente HTTP resiliente para las APIs internas de INFOMAR (v2 JSON + Respaldo Legacy MVC)."""

from __future__ import annotations

import base64
import html
import io
import logging
import re
import time
from datetime import date, datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional, Tuple

import openpyxl
import requests
from requests.adapters import HTTPAdapter
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)
from urllib3.util.retry import Retry

from .config import (
    DEFAULT_HEADERS,
    DEPARTAMENTO_POR_LUGAR_ID,
    ENDPOINT_ESPECIES,
    ENDPOINT_ESPECIES_POR_PUERTO,
    ENDPOINT_LUGARES,
    LEGACY_ESPECIES_PUERTO_URL,
    LEGACY_LOGIN_URL,
    LEGACY_PUBLIC_CREDENTIALS,
    MAX_JSON_WINDOW_DAYS,
)
from .models import Especie, Lugar

logger = logging.getLogger(__name__)


class InfomarTransientError(RuntimeError):
    """Error transitorio de red o estado HTTP 5xx/429 susceptible de reintento."""


def split_taxon_name(raw_taxon: str) -> Tuple[str, str, str]:
    """Separa 'Nombre común / Nombre científico' y obtiene el nombre comercial principal."""
    cleaned = " ".join((raw_taxon or "").strip().split())
    if " / " in cleaned:
        comun_part, cientifico_part = cleaned.split(" / ", 1)
    elif "/" in cleaned:
        comun_part, cientifico_part = cleaned.split("/", 1)
    else:
        comun_part, cientifico_part = cleaned, ""

    comun_part = comun_part.strip()
    cientifico_part = cientifico_part.strip()
    principal = extract_primary_common_name(comun_part)
    return comun_part, principal, cientifico_part


def extract_primary_common_name(nombre_comun: str) -> str:
    """Obtiene solo el primer nombre comercial limpio y capitalizado (ej. 'Cabrilla, cagálo...' -> 'Cabrilla')."""
    cleaned = " ".join((nombre_comun or "").strip().split())
    first = cleaned.split(",")[0].strip()
    first = re.sub(r"\s*\([^)]*\)\s*$", "", first).strip() or first
    return (first[0].upper() + first[1:].lower()) if first else cleaned


def chunk_date_range(
    fecha_desde: date,
    fecha_hasta: date,
    max_span_days: int = MAX_JSON_WINDOW_DAYS,
) -> List[Tuple[date, date]]:
    """
    Divide un rango [fecha_desde, fecha_hasta] en sub-ventanas donde (fin - inicio).days <= max_span_days
    para garantizar que INFOMAR responda JSON directo (isExcel=False) conservando HORA_STRING.
    """
    chunks: List[Tuple[date, date]] = []
    cursor = fecha_desde
    while cursor <= fecha_hasta:
        chunk_end = min(cursor + timedelta(days=max_span_days), fecha_hasta)
        chunks.append((cursor, chunk_end))
        cursor = chunk_end + timedelta(days=1)
    return chunks


class InfomarClient:
    """Cliente de producción para los endpoints internos v2 de INFOMAR (IMARPE)."""

    def __init__(
        self,
        timeout_seconds: float = 30.0,
        pool_maxsize: int = 16,
        polite_delay_seconds: float = 0.05,
    ) -> None:
        self.timeout = timeout_seconds
        self.polite_delay = polite_delay_seconds
        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)

        retry_strategy = Retry(
            total=2,
            connect=2,
            read=2,
            status=2,
            backoff_factor=0.4,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset(["GET", "POST"]),
            raise_on_status=False,
        )
        adapter = HTTPAdapter(
            pool_connections=pool_maxsize,
            pool_maxsize=pool_maxsize,
            max_retries=retry_strategy,
        )
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    def close(self) -> None:
        self.session.close()

    def __enter__(self) -> "InfomarClient":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()

    @retry(
        retry=retry_if_exception_type((requests.RequestException, InfomarTransientError)),
        wait=wait_exponential_jitter(initial=0.8, max=10.0),
        stop=stop_after_attempt(4),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    def _post_json(self, url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        if self.polite_delay > 0:
            time.sleep(self.polite_delay)

        resp = self.session.post(url, json=payload, timeout=self.timeout)
        if resp.status_code in (429, 500, 502, 503, 504):
            raise InfomarTransientError(f"HTTP {resp.status_code} desde {url}")
        resp.raise_for_status()

        text = resp.text.strip() if resp.text else ""
        if not text:
            return {"data": [], "isExcel": False}

        try:
            parsed = resp.json()
        except ValueError as exc:
            logger.warning("Respuesta no-JSON inesperada desde %s (len=%d): %s", url, len(text), exc)
            return {"data": [], "isExcel": False}

        if isinstance(parsed, dict):
            return parsed
        if isinstance(parsed, list):
            return {"data": parsed, "isExcel": False}
        return {"data": [], "isExcel": False}

    def fetch_lugares(self) -> List[Lugar]:
        """Descarga el catálogo maestro de los 80 puertos/caletas (COSTA y SELVA)."""
        raw = self._post_json(ENDPOINT_LUGARES, {})
        items = raw.get("data") or []
        lugares: List[Lugar] = []
        for item in items:
            lugar_id = int(item["LUGAR_ID"])
            nombre = " ".join(str(item.get("NOMBRE_LUGAR", "")).strip().split()).upper()
            region = " ".join(str(item.get("REGION", "")).strip().split()).upper()
            departamento = DEPARTAMENTO_POR_LUGAR_ID.get(lugar_id, region or "SIN CLASIFICAR")
            lugares.append(
                Lugar(
                    lugar_id=lugar_id,
                    nombre_lugar=nombre,
                    region=region,
                    departamento=departamento,
                )
            )
        lugares.sort(key=lambda x: (x.region, x.departamento, x.nombre_lugar))
        return lugares

    def fetch_especies(self) -> List[Especie]:
        """Descarga el catálogo maestro de los ~362 taxones comerciales."""
        raw = self._post_json(ENDPOINT_ESPECIES, {})
        items = raw.get("data") or []
        especies: List[Especie] = []
        for item in items:
            taxon_id = int(item["TAXON_ID"])
            raw_name = " ".join(str(item.get("NOMBRE_TAXON", "")).strip().split())
            comun, principal, cientifico = split_taxon_name(raw_name)
            especies.append(
                Especie(
                    taxon_id=taxon_id,
                    nombre_taxon_raw=raw_name,
                    nombre_comun=comun,
                    nombre_comun_principal=principal,
                    nombre_cientifico=cientifico,
                )
            )
        especies.sort(key=lambda x: x.nombre_comun.lower())
        return especies

    @staticmethod
    def _parse_excel_base64(base64_str: str) -> List[Dict[str, Any]]:
        """
        Decodifica de forma segura el reporte XLSX en Base64 si INFOMAR activa isExcel=True.
        Estructura interna verificada:
          Fila 1: ('Departamento', '<DEP>')
          Fila 2: ('Lugar', '<PUERTO>')
          Fila 3: ('Nombre Común', 'Nombre Científico', 'Tamaño', 'Precio', 'Fecha')
          Fila 4+: Datos
        """
        if not base64_str:
            return []
        raw_bytes = base64.b64decode(base64_str)
        wb = openpyxl.load_workbook(io.BytesIO(raw_bytes), read_only=True, data_only=True)
        try:
            ws = wb.active
            rows_out: List[Dict[str, Any]] = []
            header_seen = False
            for row in ws.iter_rows(values_only=True):
                if not row or all(cell is None for cell in row):
                    continue
                first_col = str(row[0] or "").strip()
                if not header_seen:
                    if first_col.lower().startswith("nombre com"):
                        header_seen = True
                    continue
                if len(row) < 5 or row[3] is None:
                    continue
                fecha_val = row[4]
                if isinstance(fecha_val, (datetime, date)):
                    fecha_str = fecha_val.strftime("%d/%m/%Y")
                else:
                    fecha_str = str(fecha_val or "").strip()
                rows_out.append(
                    {
                        "NOMBRE_COMUN": str(row[0] or "").strip(),
                        "NOMBRE_CIENTIFICO": str(row[1] or "").strip(),
                        "TAMANO": str(row[2] or "STANDAR").strip(),
                        "PRECIO": float(row[3]),
                        "FECHA_STRING": fecha_str,
                        "HORA_STRING": "",
                    }
                )
            return rows_out
        finally:
            wb.close()

    def fetch_precios_puerto_rango(
        self,
        lugar_id: int,
        fecha_desde: date,
        fecha_hasta: date,
    ) -> List[Dict[str, Any]]:
        """
        Extrae todos los muestreos de precios en playa/muelle de un puerto en [fecha_desde, fecha_hasta].
        Fragmenta rangos > 7 días automáticamente para priorizar respuestas JSON con HORA_STRING.
        """
        all_rows: List[Dict[str, Any]] = []
        for start_d, end_d in chunk_date_range(fecha_desde, fecha_hasta):
            payload = {
                "taxonId": None,
                "lugarId": lugar_id,
                "fecha": start_d.isoformat(),
                "fecha_hasta": end_d.isoformat(),
            }
            resp = self._post_json(ENDPOINT_ESPECIES_POR_PUERTO, payload)
            if resp.get("isExcel") is True and resp.get("base64"):
                all_rows.extend(self._parse_excel_base64(resp["base64"]))
            else:
                chunk_data = resp.get("data") or []
                if isinstance(chunk_data, list):
                    all_rows.extend(chunk_data)
        return all_rows


class LegacyInfomarClient:
    """
    Cliente de respaldo secundario contra la interfaz ASP.NET MVC (/Acceso/Login -> /Reportes/EspeciesPuerto).
    Solo necesario si el API /v2/api entrara en mantenimiento.
    """

    ROW_REGEX = re.compile(
        r"<tr[^>]*>\s*"
        r"<td[^>]*>(?P<fecha>[^<]+)</td>\s*"
        r"<td[^>]*>(?P<comun>[^<]+)</td>\s*"
        r"<td[^>]*>(?P<cientifico>[^<]*)</td>\s*"
        r"<td[^>]*>(?P<tamano>[^<]*)</td>\s*"
        r"<td[^>]*>(?P<precio>[^<]+)</td>\s*"
        r"<td[^>]*>(?P<hora>[^<]*)</td>\s*"
        r"</tr>",
        re.IGNORECASE | re.DOTALL,
    )

    def __init__(self, timeout_seconds: float = 30.0) -> None:
        self.timeout = timeout_seconds
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": DEFAULT_HEADERS["User-Agent"],
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            }
        )
        self._authenticated = False

    def authenticate(self) -> None:
        resp = self.session.post(
            LEGACY_LOGIN_URL,
            data=LEGACY_PUBLIC_CREDENTIALS,
            timeout=self.timeout,
            allow_redirects=True,
        )
        resp.raise_for_status()
        self._authenticated = True

    def fetch_precios_puerto_rango(
        self,
        lugar_id: int,
        fecha_desde: date,
        fecha_hasta: date,
    ) -> List[Dict[str, Any]]:
        if not self._authenticated:
            self.authenticate()

        params = {
            "LUGAR_ID": lugar_id,
            "fecha": fecha_desde.strftime("%d/%m/%Y"),
            "fecha_hasta": fecha_hasta.strftime("%d/%m/%Y"),
            "print": "1",
        }
        resp = self.session.get(LEGACY_ESPECIES_PUERTO_URL, params=params, timeout=self.timeout)
        resp.raise_for_status()
        rows: List[Dict[str, Any]] = []
        for match in self.ROW_REGEX.finditer(resp.text):
            fecha_txt = html.unescape(match.group("fecha")).strip()
            if not re.match(r"^\d{2}/\d{2}/\d{4}$", fecha_txt):
                continue
            try:
                precio_val = float(html.unescape(match.group("precio")).strip().replace(",", "."))
            except ValueError:
                continue
            rows.append(
                {
                    "FECHA_STRING": fecha_txt,
                    "NOMBRE_COMUN": html.unescape(match.group("comun")).strip(),
                    "NOMBRE_CIENTIFICO": html.unescape(match.group("cientifico")).strip(),
                    "TAMANO": html.unescape(match.group("tamano")).strip() or "STANDAR",
                    "PRECIO": precio_val,
                    "HORA_STRING": html.unescape(match.group("hora")).strip(),
                }
            )
        return rows

    def close(self) -> None:
        self.session.close()
