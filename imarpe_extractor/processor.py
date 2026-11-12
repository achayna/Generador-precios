"""Motor de barrido nacional concurrente, cruce taxonómico y cálculo de Último Precio Vigente."""

from __future__ import annotations

import logging
import re
import unicodedata
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from statistics import mean
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .client import InfomarClient, LegacyInfomarClient, extract_primary_common_name
from .models import (
    Especie,
    ItemPrecioMovil,
    Lugar,
    ObservacionPrecio,
    ResumenVigentePuertoEspecie,
)

logger = logging.getLogger(__name__)

SIZE_ORDER = {"PEQUEÑO": 1, "PEQUENO": 1, "CHICO": 1, "MEDIANO": 2, "GRANDE": 3, "STANDAR": 4, "ESTANDAR": 4}
DOTNET_DATE_RE = re.compile(r"/Date\((\d+)\)/")


def _norm_text(val: str) -> str:
    return " ".join((val or "").strip().lower().split())


def normalize_port_key(val: str) -> str:
    """Clave normalizada en mayúsculas sin tildes ni diacríticos (ej. 'EL ÑURO' -> 'EL NURO', 'ANCÓN' -> 'ANCON')."""
    nfkd = unicodedata.normalize("NFKD", (val or "").strip())
    ascii_only = "".join(ch for ch in nfkd if not unicodedata.combining(ch))
    return " ".join(ascii_only.upper().split())


def format_especie_mostrar(especie_corta: str, talla: str) -> str:
    """Arma 'Cabrilla (Grande)' si la talla no es STANDAR, o solo 'Cabrilla' si es STANDAR."""
    t_up = (talla or "").strip().upper()
    if not t_up or t_up in ("STANDAR", "ESTANDAR", "ESTÁNDAR"):
        return especie_corta
    t_pretty = t_up[0].upper() + t_up[1:].lower()
    return f"{especie_corta} ({t_pretty})"


def format_hora_mostrar(obs_date: date, hora: str, fecha_corte_peru: date) -> str:
    """Formatea Columna 3: 'Hoy 16:00', 'Ayer 16:00' o '10/11 16:00'."""
    diff = (fecha_corte_peru - obs_date).days
    h = (hora or "").strip()
    if diff == 0:
        prefix = "Hoy"
    elif diff == 1:
        prefix = "Ayer"
    else:
        prefix = obs_date.strftime("%d/%m")
    return f"{prefix} {h}".strip() if h else prefix


class TaxonMatcher:
    """Enlaza registros de precios (Nombre Común + Científico) con su TAXON_ID maestro."""

    def __init__(self, especies: Iterable[Especie]) -> None:
        self.by_pair: Dict[Tuple[str, str], int] = {}
        self.by_comun: Dict[str, int] = {}
        sci_counts: Dict[str, List[int]] = defaultdict(list)

        for esp in especies:
            nc = _norm_text(esp.nombre_comun)
            ns = _norm_text(esp.nombre_cientifico)
            if nc or ns:
                self.by_pair[(nc, ns)] = esp.taxon_id
            if nc and nc not in self.by_comun:
                self.by_comun[nc] = esp.taxon_id
            if ns:
                sci_counts[ns].append(esp.taxon_id)

        self.by_unique_sci: Dict[str, int] = {
            ns: ids[0] for ns, ids in sci_counts.items() if len(ids) == 1
        }

    def resolve(self, nombre_comun: str, nombre_cientifico: str) -> Optional[int]:
        nc = _norm_text(nombre_comun)
        ns = _norm_text(nombre_cientifico)
        if (nc, ns) in self.by_pair:
            return self.by_pair[(nc, ns)]
        if nc in self.by_comun:
            return self.by_comun[nc]
        if ns in self.by_unique_sci:
            return self.by_unique_sci[ns]
        return None


def parse_infomar_date(raw_row: Dict[str, Any]) -> Optional[date]:
    """Convierte FECHA_STRING ('DD/MM/YYYY' o 'YYYY-MM-DD') o FECHA ('/Date(ms)/') a datetime.date."""
    f_str = str(raw_row.get("FECHA_STRING") or "").strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        if f_str:
            try:
                return datetime.strptime(f_str, fmt).date()
            except ValueError:
                pass

    f_epoch = str(raw_row.get("FECHA") or "").strip()
    m = DOTNET_DATE_RE.search(f_epoch)
    if m:
        ts_sec = int(m.group(1)) / 1000.0
        # Los timestamps .NET de IMARPE están anclados a medianoche hora Perú (UTC-5)
        dt = datetime.fromtimestamp(ts_sec, tz=datetime.now().astimezone().tzinfo)
        return dt.date()
    return None


@dataclass
class NationalExtractionResult:
    """Resultado consolidado del barrido nacional."""

    fecha_desde: date
    fecha_hasta: date
    dias_ventana: int
    regiones_incluidas: List[str]
    catalogo_lugares: List[Lugar]
    catalogo_especies: List[Especie]
    lugares_consultados: List[Lugar]
    puertos_con_datos: int
    puertos_fallidos: List[str]
    vigentes: List[ResumenVigentePuertoEspecie]
    historico: List[ObservacionPrecio]
    items_movil: List[ItemPrecioMovil]


def run_national_extraction(
    dias_ventana: int = 7,
    include_selva: bool = False,
    fecha_referencia: Optional[date] = None,
    max_workers: int = 6,
    use_legacy_fallback: bool = False,
    timeout_seconds: float = 30.0,
) -> NationalExtractionResult:
    """
    Ejecuta el barrido nacional completo contra INFOMAR:
      1. Descarga catálogos oficiales de Puertos (80) y Especies (~362).
      2. Filtra puertos objetivo (COSTA por defecto, + SELVA si include_selva=True).
      3. Consulta concurrentemente la ventana [fecha_hasta - (dias_ventana - 1), fecha_hasta]
         o últimos N días calendario hasta hoy.
      4. Construye Histórico Reciente y Último Precio Vigente por Puerto y Especie.
    """
    if dias_ventana < 1:
        raise ValueError("dias_ventana debe ser >= 1")

    fecha_hasta = fecha_referencia or date.today()
    # Ventana de últimos N días (ej. N=7 -> desde hoy-7 hasta hoy inclusive, cubriendo rezagos de carga)
    fecha_desde = fecha_hasta - timedelta(days=dias_ventana)

    with InfomarClient(timeout_seconds=timeout_seconds, pool_maxsize=max(12, max_workers * 2)) as client:
        logger.info("Descargando catálogos maestros de INFOMAR (/v2/api/lugares y /v2/api/especies)...")
        catalogo_lugares = client.fetch_lugares()
        catalogo_especies = client.fetch_especies()
        matcher = TaxonMatcher(catalogo_especies)

        regiones_objetivo = ["COSTA", "SELVA"] if include_selva else ["COSTA"]
        regiones_set = set(regiones_objetivo)
        lugares_objetivo = [l for l in catalogo_lugares if l.region in regiones_set]

        logger.info(
            "Iniciando barrido de %d puertos (%s) en ventana [%s .. %s] con %d hilos...",
            len(lugares_objetivo),
            ", ".join(regiones_objetivo),
            fecha_desde.isoformat(),
            fecha_hasta.isoformat(),
            max_workers,
        )

        raw_by_lugar: Dict[int, List[Dict[str, Any]]] = {}
        puertos_fallidos: List[str] = []

        if not use_legacy_fallback:
            def _fetch_one(lugar: Lugar) -> Tuple[Lugar, List[Dict[str, Any]]]:
                rows = client.fetch_precios_puerto_rango(lugar.lugar_id, fecha_desde, fecha_hasta)
                return lugar, rows

            with ThreadPoolExecutor(max_workers=max_workers) as pool:
                futures = {pool.submit(_fetch_one, lug): lug for lug in lugares_objetivo}
                for idx, fut in enumerate(as_completed(futures), start=1):
                    lug = futures[fut]
                    try:
                        _, rows = fut.result()
                        raw_by_lugar[lug.lugar_id] = rows
                        if rows:
                            logger.info(
                                "[%d/%d] %s (%s): %d muestreos obtenidos",
                                idx,
                                len(lugares_objetivo),
                                lug.nombre_lugar,
                                lug.departamento,
                                len(rows),
                            )
                        else:
                            logger.debug("[%d/%d] %s: sin registros en la ventana", idx, len(lugares_objetivo), lug.nombre_lugar)
                    except Exception as exc:
                        logger.error("Error extrayendo puerto %s (ID=%d): %s", lug.nombre_lugar, lug.lugar_id, exc)
                        puertos_fallidos.append(f"{lug.nombre_lugar} (ID {lug.lugar_id})")
                        raw_by_lugar[lug.lugar_id] = []
        else:
            logger.info("Usando modo respaldo Legacy ASP.NET MVC (/Acceso/Login -> /Reportes/EspeciesPuerto)...")
            legacy = LegacyInfomarClient(timeout_seconds=timeout_seconds)
            try:
                legacy.authenticate()
                for idx, lug in enumerate(lugares_objetivo, start=1):
                    try:
                        rows = legacy.fetch_precios_puerto_rango(lug.lugar_id, fecha_desde, fecha_hasta)
                        raw_by_lugar[lug.lugar_id] = rows
                        if rows:
                            logger.info("[%d/%d] %s: %d muestreos (legacy)", idx, len(lugares_objetivo), lug.nombre_lugar, len(rows))
                    except Exception as exc:
                        logger.error("Error legacy en puerto %s: %s", lug.nombre_lugar, exc)
                        puertos_fallidos.append(f"{lug.nombre_lugar} (ID {lug.lugar_id})")
                        raw_by_lugar[lug.lugar_id] = []
            finally:
                legacy.close()

    # Normalización y desduplicación de observaciones
    lugares_map = {l.lugar_id: l for l in lugares_objetivo}
    historico: List[ObservacionPrecio] = []
    seen_keys = set()
    puertos_con_datos = 0

    for lugar_id, rows in raw_by_lugar.items():
        lugar = lugares_map[lugar_id]
        port_obs_count = 0
        for row in rows:
            obs_date = parse_infomar_date(row)
            if obs_date is None:
                continue
            raw_precio = row.get("PRECIO")
            if raw_precio is None:
                continue
            try:
                precio_val = round(float(raw_precio), 2)
            except (TypeError, ValueError):
                continue
            if precio_val <= 0:
                continue

            nombre_comun = " ".join(str(row.get("NOMBRE_COMUN") or "").strip().split())
            nombre_cientifico = " ".join(str(row.get("NOMBRE_CIENTIFICO") or "").strip().split())
            if not nombre_comun and not nombre_cientifico:
                continue

            principal = extract_primary_common_name(nombre_comun or nombre_cientifico)
            tamano = " ".join(str(row.get("TAMANO") or "STANDAR").strip().split()).upper() or "STANDAR"
            hora = str(row.get("HORA_STRING") or "").strip()
            taxon_id = matcher.resolve(nombre_comun, nombre_cientifico)
            antiguedad = max(0, (fecha_hasta - obs_date).days)

            dedup_key = (
                lugar_id,
                _norm_text(nombre_comun),
                _norm_text(nombre_cientifico),
                tamano,
                precio_val,
                obs_date,
                hora,
            )
            if dedup_key in seen_keys:
                continue
            seen_keys.add(dedup_key)

            historico.append(
                ObservacionPrecio(
                    lugar_id=lugar_id,
                    puerto=lugar.nombre_lugar,
                    region=lugar.region,
                    departamento=lugar.departamento,
                    taxon_id=taxon_id,
                    nombre_comun=nombre_comun,
                    nombre_comun_principal=principal,
                    nombre_cientifico=nombre_cientifico,
                    tamano=tamano,
                    precio_kg=precio_val,
                    fecha=obs_date,
                    fecha_iso=obs_date.isoformat(),
                    fecha_display=obs_date.strftime("%d/%m/%Y"),
                    hora=hora,
                    dias_antiguedad=antiguedad,
                )
            )
            port_obs_count += 1

        if port_obs_count > 0:
            puertos_con_datos += 1

    # Ordenar histórico: más reciente primero, luego Región -> Departamento -> Puerto -> Especie
    historico.sort(
        key=lambda o: (
            -o.fecha.toordinal(),
            o.region,
            o.departamento,
            o.puerto,
            o.nombre_comun.lower(),
            SIZE_ORDER.get(o.tamano, 99),
            o.hora,
        )
    )

    # Consolidación: "Último Precio Vigente por Puerto y Especie"
    grouped: Dict[Tuple[int, str], List[ObservacionPrecio]] = defaultdict(list)
    for obs in historico:
        sp_key = f"id:{obs.taxon_id}" if obs.taxon_id is not None else f"txt:{_norm_text(obs.nombre_comun)}|{_norm_text(obs.nombre_cientifico)}"
        grouped[(obs.lugar_id, sp_key)].append(obs)

    vigentes: List[ResumenVigentePuertoEspecie] = []
    items_movil: List[ItemPrecioMovil] = []

    for (_, _), obs_list in grouped.items():
        # Ordenamos historial de esa especie en ese puerto (más reciente primero)
        obs_sorted_desc = sorted(
            obs_list,
            key=lambda x: (x.fecha, x.hora or "00:00", SIZE_ORDER.get(x.tamano, 99)),
            reverse=True,
        )
        max_fecha = obs_sorted_desc[0].fecha
        latest_day_obs = [o for o in obs_list if o.fecha == max_fecha]

        # Última observación cronológica del último día registrado
        latest_day_chrono = sorted(
            latest_day_obs,
            key=lambda x: (x.hora or "00:00", SIZE_ORDER.get(x.tamano, 99)),
        )
        last_sample = latest_day_chrono[-1]

        prices = [o.precio_kg for o in latest_day_obs]
        by_size_obs: Dict[str, List[ObservacionPrecio]] = defaultdict(list)
        for o in latest_day_obs:
            by_size_obs[o.tamano].append(o)

        ordered_sizes = sorted(by_size_obs.keys(), key=lambda s: (SIZE_ORDER.get(s, 99), s))
        precios_por_tamano = {
            sz: round(mean(o.precio_kg for o in by_size_obs[sz]), 2) for sz in ordered_sizes
        }
        detalle_texto = " | ".join(f"{sz}: S/ {precios_por_tamano[sz]:.2f}" for sz in ordered_sizes)

        # Filas móviles de 3 columnas: una fila limpia por talla vigente en la fecha más reciente
        for sz in ordered_sizes:
            sz_chrono = sorted(by_size_obs[sz], key=lambda x: x.hora or "00:00")
            last_sz_obs = sz_chrono[-1]
            same_hour_prices = [x.precio_kg for x in sz_chrono if x.hora == last_sz_obs.hora]
            precio_sz = round(mean(same_hour_prices), 2)
            especie_corta = last_sz_obs.nombre_comun_principal

            items_movil.append(
                ItemPrecioMovil(
                    lugar_id=last_sz_obs.lugar_id,
                    puerto=last_sz_obs.puerto,
                    region=last_sz_obs.region,
                    departamento=last_sz_obs.departamento,
                    especie_mostrar=format_especie_mostrar(especie_corta, sz),
                    especie_corta=especie_corta,
                    nombre_cientifico=last_sz_obs.nombre_cientifico,
                    sinonimos_busqueda=last_sz_obs.nombre_comun,
                    talla=sz,
                    precio=precio_sz,
                    precio_mostrar=f"S/ {precio_sz:.2f}",
                    hora=last_sz_obs.hora,
                    fecha=last_sz_obs.fecha_display,
                    hora_mostrar=format_hora_mostrar(last_sz_obs.fecha, last_sz_obs.hora, fecha_hasta),
                )
            )

        vigentes.append(
            ResumenVigentePuertoEspecie(
                region=last_sample.region,
                departamento=last_sample.departamento,
                lugar_id=last_sample.lugar_id,
                puerto=last_sample.puerto,
                taxon_id=last_sample.taxon_id,
                nombre_comun=last_sample.nombre_comun,
                nombre_comun_principal=last_sample.nombre_comun_principal,
                nombre_cientifico=last_sample.nombre_cientifico,
                precio_promedio_kg=round(mean(prices), 2),
                precio_min_kg=round(min(prices), 2),
                precio_max_kg=round(max(prices), 2),
                ultimo_precio_kg=last_sample.precio_kg,
                precios_por_tamano=precios_por_tamano,
                detalle_tamanos_texto=detalle_texto,
                muestreos_ultimo_dia=len(latest_day_obs),
                fecha_ultimo_registro=max_fecha,
                fecha_ultimo_registro_iso=max_fecha.isoformat(),
                fecha_ultimo_registro_display=max_fecha.strftime("%d/%m/%Y"),
                hora_ultimo_registro=last_sample.hora,
                dias_antiguedad=last_sample.dias_antiguedad,
                historico_ventana=obs_sorted_desc,
            )
        )

    vigentes.sort(
        key=lambda v: (
            v.region,
            v.departamento,
            v.puerto,
            v.nombre_comun_principal.lower(),
            v.nombre_comun.lower(),
        )
    )

    items_movil.sort(
        key=lambda m: (
            normalize_port_key(m.puerto),
            normalize_port_key(m.especie_corta),
            SIZE_ORDER.get(m.talla, 99),
            m.especie_mostrar.lower(),
        )
    )

    return NationalExtractionResult(
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        dias_ventana=dias_ventana,
        regiones_incluidas=regiones_objetivo,
        catalogo_lugares=catalogo_lugares,
        catalogo_especies=catalogo_especies,
        lugares_consultados=lugares_objetivo,
        puertos_con_datos=puertos_con_datos,
        puertos_fallidos=puertos_fallidos,
        vigentes=vigentes,
        historico=historico,
        items_movil=items_movil,
    )
