"""Exportadores de producción: Excel profesional multipágina (openpyxl) y JSON jerárquico (App/Cloud)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table, TableStyleInfo
from openpyxl.worksheet.worksheet import Worksheet

from .config import BASE_URL, now_peru
from .processor import NationalExtractionResult, normalize_port_key

# Paleta institucional inspirada en IMARPE
HEADER_FILL = PatternFill(start_color="0B3C5D", end_color="0B3C5D", fill_type="solid")
SUBHEADER_FILL = PatternFill(start_color="1D65A6", end_color="1D65A6", fill_type="solid")
ZEBRA_FILL = PatternFill(start_color="F4F8FB", end_color="F4F8FB", fill_type="solid")
FRESH_FILL = PatternFill(start_color="E6F4EA", end_color="E6F4EA", fill_type="solid")
RECENT_FILL = PatternFill(start_color="FEF7E0", end_color="FEF7E0", fill_type="solid")
STALE_FILL = PatternFill(start_color="FCE8E6", end_color="FCE8E6", fill_type="solid")

HEADER_FONT = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
REGULAR_FONT = Font(name="Calibri", size=10, color="1F2937")
BOLD_FONT = Font(name="Calibri", size=10, bold=True, color="111827")
ITALIC_FONT = Font(name="Calibri", size=10, italic=True, color="374151")

THIN_GRAY = Side(border_style="thin", color="D1D5DB")
CELL_BORDER = Border(left=THIN_GRAY, right=THIN_GRAY, top=THIN_GRAY, bottom=THIN_GRAY)

CURRENCY_FMT = '"S/ "#,##0.00'
DATE_FMT = "dd/mm/yyyy"


def _auto_adjust_columns(ws: Worksheet, min_width: int = 11, max_width: int = 48) -> None:
    """Ajusta el ancho de cada columna según el contenido real con límites estéticos."""
    for col_idx in range(1, ws.max_column + 1):
        col_letter = get_column_letter(col_idx)
        max_len = 0
        # Muestreamos encabezado + hasta primeras 400 filas para máxima velocidad
        for row_idx in range(1, min(ws.max_row + 1, 402)):
            val = ws.cell(row=row_idx, column=col_idx).value
            if val is None:
                continue
            if hasattr(val, "strftime"):
                text = "10/11/2026"
            elif isinstance(val, float):
                text = f"S/ {val:,.2f}"
            else:
                text = str(val)
            if len(text) > max_len:
                max_len = len(text)
        ws.column_dimensions[col_letter].width = max(min_width, min(max_len + 4, max_width))


def _style_header_row(ws: Worksheet, num_cols: int, fill: PatternFill = HEADER_FILL) -> None:
    ws.row_dimensions[1].height = 28
    for col_idx in range(1, num_cols + 1):
        cell = ws.cell(row=1, column=col_idx)
        cell.fill = fill
        cell.font = HEADER_FONT
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = CELL_BORDER


def export_to_excel(result: NationalExtractionResult, output_path: Path) -> Path:
    """
    Genera el libro Excel corporativo Precios_Playa_IMARPE_Nacional.xlsx con 3 hojas:
      1. Ultimos_Precios_Vigentes
      2. Historico_Reciente
      3. Catalogo_Puertos_Especies
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    wb = openpyxl.Workbook()

    # =========================================================================
    # HOJA 1: Ultimos_Precios_Vigentes
    # =========================================================================
    ws1 = wb.active
    ws1.title = "Ultimos_Precios_Vigentes"
    ws1.views.sheetView[0].showGridLines = True

    headers_1 = [
        "Región",
        "Departamento",
        "ID Puerto",
        "Puerto / DPA",
        "ID Especie",
        "Especie (Nombre Común)",
        "Nombre Científico",
        "Precio Playa Promedio (S/ kg)",
        "Precio Mínimo (S/ kg)",
        "Precio Máximo (S/ kg)",
        "Último Precio Hora (S/ kg)",
        "Detalle por Tamaño",
        "Muestreos Día",
        "Fecha Último Registro",
        "Hora Último Registro",
        "Días de Antigüedad",
    ]
    ws1.append(headers_1)
    _style_header_row(ws1, len(headers_1))
    ws1.freeze_panes = "A2"

    for idx, item in enumerate(result.vigentes, start=2):
        ws1.append(
            [
                item.region,
                item.departamento,
                item.lugar_id,
                item.puerto,
                item.taxon_id if item.taxon_id is not None else "",
                item.nombre_comun,
                item.nombre_cientifico,
                item.precio_promedio_kg,
                item.precio_min_kg,
                item.precio_max_kg,
                item.ultimo_precio_kg,
                item.detalle_tamanos_texto,
                item.muestreos_ultimo_dia,
                item.fecha_ultimo_registro,
                item.hora_ultimo_registro or "-",
                item.dias_antiguedad,
            ]
        )
        is_even = idx % 2 == 0
        for col_idx in range(1, len(headers_1) + 1):
            cell = ws1.cell(row=idx, column=col_idx)
            cell.font = REGULAR_FONT
            cell.border = CELL_BORDER
            if is_even:
                cell.fill = ZEBRA_FILL

            if col_idx in (1, 3, 5, 13, 14, 15, 16):
                cell.alignment = Alignment(horizontal="center", vertical="center")
            elif col_idx in (8, 9, 10, 11):
                cell.number_format = CURRENCY_FMT
                cell.alignment = Alignment(horizontal="right", vertical="center")
                if col_idx == 8:
                    cell.font = BOLD_FONT
            else:
                cell.alignment = Alignment(horizontal="left", vertical="center")

            if col_idx == 4:
                cell.font = BOLD_FONT
            elif col_idx == 7:
                cell.font = ITALIC_FONT
            elif col_idx == 14:
                cell.number_format = DATE_FMT
            elif col_idx == 16:
                if item.dias_antiguedad <= 1:
                    cell.fill = FRESH_FILL
                elif item.dias_antiguedad <= 3:
                    cell.fill = RECENT_FILL
                else:
                    cell.fill = STALE_FILL

    ws1.auto_filter.ref = f"A1:{get_column_letter(len(headers_1))}{max(2, ws1.max_row)}"
    _auto_adjust_columns(ws1)

    # =========================================================================
    # HOJA 2: Historico_Reciente
    # =========================================================================
    ws2 = wb.create_sheet(title="Historico_Reciente")
    headers_2 = [
        "Fecha",
        "Hora",
        "Región",
        "Departamento",
        "ID Puerto",
        "Puerto / DPA",
        "ID Especie",
        "Especie (Nombre Común)",
        "Nombre Científico",
        "Tamaño",
        "Precio Playa (S/ kg)",
        "Unidad",
        "Días de Antigüedad",
    ]
    ws2.append(headers_2)
    _style_header_row(ws2, len(headers_2))
    ws2.freeze_panes = "A2"

    for idx, obs in enumerate(result.historico, start=2):
        ws2.append(
            [
                obs.fecha,
                obs.hora or "-",
                obs.region,
                obs.departamento,
                obs.lugar_id,
                obs.puerto,
                obs.taxon_id if obs.taxon_id is not None else "",
                obs.nombre_comun,
                obs.nombre_cientifico,
                obs.tamano,
                obs.precio_kg,
                "S/ kg",
                obs.dias_antiguedad,
            ]
        )
        is_even = idx % 2 == 0
        for col_idx in range(1, len(headers_2) + 1):
            cell = ws2.cell(row=idx, column=col_idx)
            cell.font = REGULAR_FONT
            cell.border = CELL_BORDER
            if is_even:
                cell.fill = ZEBRA_FILL

            if col_idx == 1:
                cell.number_format = DATE_FMT
                cell.alignment = Alignment(horizontal="center", vertical="center")
            elif col_idx in (2, 3, 5, 7, 10, 12, 13):
                cell.alignment = Alignment(horizontal="center", vertical="center")
            elif col_idx == 11:
                cell.number_format = CURRENCY_FMT
                cell.font = BOLD_FONT
                cell.alignment = Alignment(horizontal="right", vertical="center")
            elif col_idx == 9:
                cell.font = ITALIC_FONT
                cell.alignment = Alignment(horizontal="left", vertical="center")
            else:
                cell.alignment = Alignment(horizontal="left", vertical="center")

    ws2.auto_filter.ref = f"A1:{get_column_letter(len(headers_2))}{max(2, ws2.max_row)}"
    _auto_adjust_columns(ws2)

    # =========================================================================
    # HOJA 3: Catalogo_Puertos_Especies (Diccionario Oficial INFOMAR)
    # =========================================================================
    ws3 = wb.create_sheet(title="Catalogo_Puertos_Especies")
    ws3.freeze_panes = "A2"

    puertos_headers = ["ID Puerto", "Puerto / DPA", "Región", "Departamento"]
    especies_headers = [
        "ID Especie",
        "Nombre Comercial Corto",
        "Nombre Común Completo",
        "Nombre Científico",
        " Etiqueta Original INFOMAR",
    ]

    for c_idx, title in enumerate(puertos_headers, start=1):
        c = ws3.cell(row=1, column=c_idx, value=title)
        c.fill = HEADER_FILL
        c.font = HEADER_FONT
        c.alignment = Alignment(horizontal="center", vertical="center")
        c.border = CELL_BORDER

    for offset, title in enumerate(especies_headers):
        c_idx = 6 + offset  # Columna F en adelante (columna E queda como separador limpio)
        c = ws3.cell(row=1, column=c_idx, value=title.strip())
        c.fill = SUBHEADER_FILL
        c.font = HEADER_FONT
        c.alignment = Alignment(horizontal="center", vertical="center")
        c.border = CELL_BORDER

    ws3.row_dimensions[1].height = 26
    ws3.column_dimensions["E"].width = 4

    lugares_sorted = sorted(result.catalogo_lugares, key=lambda l: l.lugar_id)
    for r_idx, lug in enumerate(lugares_sorted, start=2):
        vals = [lug.lugar_id, lug.nombre_lugar, lug.region, lug.departamento]
        for c_idx, v in enumerate(vals, start=1):
            cell = ws3.cell(row=r_idx, column=c_idx, value=v)
            cell.font = BOLD_FONT if c_idx == 2 else REGULAR_FONT
            cell.border = CELL_BORDER
            cell.alignment = Alignment(
                horizontal="center" if c_idx in (1, 3) else "left",
                vertical="center",
            )

    especies_sorted = sorted(result.catalogo_especies, key=lambda e: e.taxon_id)
    for r_idx, esp in enumerate(especies_sorted, start=2):
        vals = [
            esp.taxon_id,
            esp.nombre_comun_principal,
            esp.nombre_comun,
            esp.nombre_cientifico,
            esp.nombre_taxon_raw,
        ]
        for offset, v in enumerate(vals):
            c_idx = 6 + offset
            cell = ws3.cell(row=r_idx, column=c_idx, value=v)
            cell.font = ITALIC_FONT if offset == 3 else (BOLD_FONT if offset == 1 else REGULAR_FONT)
            cell.border = CELL_BORDER
            cell.alignment = Alignment(
                horizontal="center" if offset == 0 else "left",
                vertical="center",
            )

    if lugares_sorted:
        tab_puertos = Table(
            displayName="CatalogoPuertosINFOMAR",
            ref=f"A1:D{len(lugares_sorted) + 1}",
        )
        tab_puertos.tableStyleInfo = TableStyleInfo(
            name="TableStyleMedium2",
            showFirstColumn=False,
            showLastColumn=False,
            showRowStripes=True,
            showColumnStripes=False,
        )
        ws3.add_table(tab_puertos)

    if especies_sorted:
        tab_especies = Table(
            displayName="CatalogoEspeciesINFOMAR",
            ref=f"F1:J{len(especies_sorted) + 1}",
        )
        tab_especies.tableStyleInfo = TableStyleInfo(
            name="TableStyleMedium9",
            showFirstColumn=False,
            showLastColumn=False,
            showRowStripes=True,
            showColumnStripes=False,
        )
        ws3.add_table(tab_especies)

    _auto_adjust_columns(ws3)
    ws3.column_dimensions["E"].width = 4

    wb.save(output_path)
    return output_path


def export_to_json(result: NationalExtractionResult, output_path: Path) -> Path:
    """
    Genera precios_imarpe_app.json jerárquico por puerto -> especie, optimizado para
    consumo móvil (Android / Kotlin), Supabase, Firebase o PostgreSQL JSONB.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    vigentes_por_puerto: Dict[int, List[Any]] = {}
    for v in result.vigentes:
        vigentes_por_puerto.setdefault(v.lugar_id, []).append(v)

    puertos_payload: List[Dict[str, Any]] = []
    for lug in result.lugares_consultados:
        items = vigentes_por_puerto.get(lug.lugar_id, [])
        ultimo_muestreo_puerto = (
            max(i.fecha_ultimo_registro_iso for i in items) if items else None
        )
        dias_antiguedad_puerto = (
            min(i.dias_antiguedad for i in items) if items else None
        )

        especies_json = [
            {
                "taxon_id": sp.taxon_id,
                "nombre_comun": sp.nombre_comun,
                "nombre_comun_corto": sp.nombre_comun_principal,
                "nombre_cientifico": sp.nombre_cientifico,
                "precio_playa_kg": {
                    "promedio": sp.precio_promedio_kg,
                    "minimo": sp.precio_min_kg,
                    "maximo": sp.precio_max_kg,
                    "ultimo": sp.ultimo_precio_kg,
                },
                "precios_por_tamano": sp.precios_por_tamano,
                "fecha_ultimo_registro": sp.fecha_ultimo_registro_iso,
                "hora_ultimo_registro": sp.hora_ultimo_registro or None,
                "dias_antiguedad": sp.dias_antiguedad,
                "muestreos_ultimo_dia": sp.muestreos_ultimo_dia,
                "historico_reciente": [
                    {
                        "fecha": h.fecha_iso,
                        "hora": h.hora or None,
                        "tamano": h.tamano,
                        "precio_kg": h.precio_kg,
                    }
                    for h in sp.historico_ventana
                ],
            }
            for sp in items
        ]

        puertos_payload.append(
            {
                "lugar_id": lug.lugar_id,
                "puerto": lug.nombre_lugar,
                "region": lug.region,
                "departamento": lug.departamento,
                "tiene_datos_recientes": bool(especies_json),
                "fecha_ultimo_muestreo": ultimo_muestreo_puerto,
                "dias_antiguedad_min": dias_antiguedad_puerto,
                "total_especies_vigentes": len(especies_json),
                "especies": especies_json,
            }
        )

    # Ordenamos puertos con datos recientes primero, luego alfabéticamente por departamento y puerto
    puertos_payload.sort(
        key=lambda p: (
            0 if p["tiene_datos_recientes"] else 1,
            p["region"],
            p["departamento"],
            p["puerto"],
        )
    )

    ts_pe = now_peru()
    ts_utc = datetime.now(timezone.utc)

    payload = {
        "metadata": {
            "sistema_origen": "INFOMAR - Instituto del Mar del Perú (IMARPE)",
            "endpoint_principal": f"{BASE_URL}/v2/api/especies-por-puertos",
            "generado_en_peru": ts_pe.isoformat(timespec="seconds"),
            "generado_en_utc": ts_utc.isoformat(timespec="seconds"),
            "moneda": "PEN",
            "simbolo_moneda": "S/",
            "unidad": "kg",
            "ventana_consulta": {
                "fecha_desde": result.fecha_desde.isoformat(),
                "fecha_hasta": result.fecha_hasta.isoformat(),
                "dias_ventana": result.dias_ventana,
            },
            "regiones_incluidas": result.regiones_incluidas,
            "estadisticas": {
                "puertos_consultados": len(result.lugares_consultados),
                "puertos_con_datos": result.puertos_con_datos,
                "total_especies_vigentes_puerto": len(result.vigentes),
                "total_muestreos_ventana": len(result.historico),
                "catalogo_total_lugares": len(result.catalogo_lugares),
                "catalogo_total_especies": len(result.catalogo_especies),
                "puertos_con_error": result.puertos_fallidos,
            },
        },
        "puertos": puertos_payload,
    }

    with output_path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)

    return output_path


def export_to_mobile_json(result: NationalExtractionResult, output_path: Path) -> Path:
    """
    Genera output/precios_app_movil.json ultraligero pensado específicamente para
    pintar la tabla móvil de 3 columnas en Android (Especie | Precio | Hora) con
    búsqueda instantánea por puerto sin tildes.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    items_por_puerto: Dict[int, List[Any]] = {}
    for item in result.items_movil:
        items_por_puerto.setdefault(item.lugar_id, []).append(item)

    lugares_sorted = sorted(
        result.lugares_consultados,
        key=lambda l: normalize_port_key(l.nombre_lugar),
    )

    puertos_dict: Dict[str, Dict[str, Any]] = {}
    for lug in lugares_sorted:
        port_key = normalize_port_key(lug.nombre_lugar)
        filas = items_por_puerto.get(lug.lugar_id, [])
        puertos_dict[port_key] = {
            "nombre_puerto": lug.nombre_lugar,
            "departamento": lug.departamento,
            "region": lug.region,
            "precios": [
                {
                    "especie_mostrar": f.especie_mostrar,
                    "especie_corta": f.especie_corta,
                    "nombre_cientifico": f.nombre_cientifico,
                    "sinonimos_busqueda": f.sinonimos_busqueda,
                    "talla": f.talla,
                    "precio": f.precio,
                    "precio_mostrar": f.precio_mostrar,
                    "hora": f.hora,
                    "fecha": f.fecha,
                    "hora_mostrar": f.hora_mostrar,
                }
                for f in filas
            ],
        }

    ts_pe = now_peru()
    payload_movil = {
        "actualizado_peru": ts_pe.strftime("%d/%m/%Y %H:%M"),
        "actualizado_iso": ts_pe.isoformat(timespec="seconds"),
        "fecha_extraccion_peru": result.fecha_hasta.strftime("%d/%m/%Y"),
        "ventana_dias": result.dias_ventana,
        "total_puertos": len(lugares_sorted),
        "puertos_con_datos": result.puertos_con_datos,
        "total_filas_precios": len(result.items_movil),
        "puertos": puertos_dict,
    }

    with output_path.open("w", encoding="utf-8") as fh:
        json.dump(payload_movil, fh, ensure_ascii=False, indent=2)

    return output_path

