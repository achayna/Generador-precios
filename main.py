#!/usr/bin/env python3
"""
CLI Principal - Extractor Automatizado Nacional INFOMAR (IMARPE Perú)
Extrae precios en playa/muelle por puerto y especie y genera:
  - Precios_Playa_IMARPE_Nacional.xlsx (3 hojas ejecutivas con formato profesional)
  - precios_imarpe_app.json (JSON jerárquico listo para Android / Supabase / Firebase)
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

from imarpe_extractor.config import now_peru
from imarpe_extractor.exporters import (
    export_to_excel,
    export_to_json,
    export_to_mobile_json,
)
from imarpe_extractor.processor import run_national_extraction


def parse_args() -> argparse.Namespace:
    default_out = Path(__file__).resolve().parent / "output"
    parser = argparse.ArgumentParser(
        description="Extractor automatizado nacional de precios en playa/muelle - INFOMAR IMARPE Perú"
    )
    parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="Ventana de búsqueda hacia atrás en días desde la fecha de corte (por defecto: 7).",
    )
    parser.add_argument(
        "--include-selva",
        action="store_true",
        help="Incluye también los 15 desembarcaderos fluviales de SELVA además de los 65 de COSTA.",
    )
    parser.add_argument(
        "--end-date",
        type=str,
        default=None,
        help="Fecha final YYYY-MM-DD (por defecto: fecha actual en hora oficial del Perú UTC-5).",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=6,
        help="Concurrencia moderada de hilos HTTP (por defecto: 6 para proteger la IP ante IMARPE).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=default_out,
        help=f"Directorio destino para el Excel y JSON (por defecto: {default_out}).",
    )
    parser.add_argument(
        "--use-legacy-fallback",
        action="store_true",
        help="Fuerza el uso del respaldo ASP.NET MVC (/Acceso/Login + /Reportes/EspeciesPuerto).",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Activa logs detallados DEBUG.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logger = logging.getLogger("imarpe_main")

    if args.end_date:
        try:
            fecha_ref = datetime.strptime(args.end_date, "%Y-%m-%d").date()
        except ValueError:
            logger.error("Formato inválido en --end-date '%s'. Use YYYY-MM-DD.", args.end_date)
            return 2
    else:
        fecha_ref = now_peru().date()

    t0 = time.perf_counter()
    result = run_national_extraction(
        dias_ventana=args.days,
        include_selva=args.include_selva,
        fecha_referencia=fecha_ref,
        max_workers=max(1, min(args.workers, 12)),
        use_legacy_fallback=args.use_legacy_fallback,
    )

    out_dir: Path = args.output_dir.resolve()
    excel_path = out_dir / "Precios_Playa_IMARPE_Nacional.xlsx"
    json_path = out_dir / "precios_imarpe_app.json"
    mobile_json_path = out_dir / "precios_app_movil.json"

    logger.info("Generando reporte Excel corporativo en: %s", excel_path)
    export_to_excel(result, excel_path)

    logger.info("Generando payload JSON completo en: %s", json_path)
    export_to_json(result, json_path)

    logger.info("Generando payload JSON ultraligero (3 columnas Android) en: %s", mobile_json_path)
    export_to_mobile_json(result, mobile_json_path)

    elapsed = time.perf_counter() - t0
    logger.info(
        "Extracción completada en %.2fs | Puertos consultados: %d | Con datos: %d | "
        "Precios vigentes (puerto-especie): %d | Filas móvil (talla): %d | Muestreos históricos: %d",
        elapsed,
        len(result.lugares_consultados),
        result.puertos_con_datos,
        len(result.vigentes),
        len(result.items_movil),
        len(result.historico),
    )
    logger.info(
        "Archivos listos -> Excel (%.1f KB): %s | JSON Completo (%.1f KB): %s | JSON Móvil (%.1f KB): %s",
        excel_path.stat().st_size / 1024.0,
        excel_path,
        json_path.stat().st_size / 1024.0,
        json_path,
        mobile_json_path.stat().st_size / 1024.0,
        mobile_json_path,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
