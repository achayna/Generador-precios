# Generador de Precios en Playa - INFOMAR (IMARPE Perú)

Extractor automatizado nacional de **precios en playa/muelle y especies por puerto** conectado directamente a los endpoints internos de **INFOMAR (IMARPE)**. Se ejecuta automáticamente **4 veces al día en GitHub Actions** (`08:30`, `11:30`, `14:30` y `18:00` hora Perú `UTC-5`).

---

## Salidas Públicas Auto-Actualizadas (`output/`)

| Archivo | Uso Principal | Descripción |
| :--- | :--- | :--- |
| **`output/precios_app_movil.json`** | **App Android (Tabla 3 Columnas)** | Payload JSON ultraligero indexado por puerto sin tildes (`MATARANI`, `CALLAO`, `PAITA`, `EL NURO`, etc.), con filas listas para pintar: `especie_mostrar`, `precio_mostrar` y `hora_mostrar`. |
| **`output/precios_imarpe_app.json`** | **Backend / Analítica / BI** | Payload completo con estadísticas, rangos mín/máx/promedio e historial diario de la ventana de 7 días. |
| **`output/Precios_Playa_IMARPE_Nacional.xlsx`** | **Reporte Ejecutivo Excel** | Libro Excel profesional con 3 hojas (`Ultimos_Precios_Vigentes`, `Historico_Reciente`, `Catalogo_Puertos_Especies`). |

### URL Directa para Consumo en App Android
```text
https://raw.githubusercontent.com/achayna/Generador-precios/main/output/precios_app_movil.json
```

---

## Estructura de `output/precios_app_movil.json`

```json
{
  "actualizado_peru": "11/11/2026 23:40",
  "actualizado_iso": "2026-11-11T23:40:00-05:00",
  "fecha_extraccion_peru": "11/11/2026",
  "ventana_dias": 7,
  "total_puertos": 65,
  "puertos_con_datos": 42,
  "total_filas_precios": 740,
  "puertos": {
    "MATARANI": {
      "nombre_puerto": "MATARANI",
      "departamento": "AREQUIPA",
      "region": "COSTA",
      "precios": [
        {
          "especie_mostrar": "Cabrilla (Grande)",
          "especie_corta": "Cabrilla",
          "nombre_cientifico": "Paralabrax humeralis",
          "sinonimos_busqueda": "Cabrilla, cagálo, bagalo, cabrilla comun",
          "talla": "GRANDE",
          "precio": 27.0,
          "precio_mostrar": "S/ 27.00",
          "hora": "16:00",
          "fecha": "10/11/2026",
          "hora_mostrar": "Ayer 16:00"
        }
      ]
    }
  }
}
```

---

## Ejecución Manual Local

```bash
pip install -r requirements.txt
python main.py --days 7
```
