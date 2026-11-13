# Generador de Precios en Playa - INFOMAR (IMARPE Perú)

Extractor automatizado nacional de **precios en playa/muelle y especies por puerto** conectado directamente a los endpoints internos de **INFOMAR (IMARPE)**.

- **Nube (GitHub Actions - 6 corridas diarias UTC-5):** `00:05`, `06:30`, `08:35`, `11:30`, `14:30` y `18:00` hora Perú (extrae datos o recalcula automáticamente etiquetas `"Hoy"` / `"Ayer"` / `"DD/MM"` al cambiar el día).
- **Nodo Perú (Windows Task Scheduler):** `08:35`, `10:00`, `11:30`, `14:30`, `18:00` + `AtLogOn` / `StartWhenAvailable` con sincronización `git pull --rebase` + `git push`.

---

## URL Pública Directa para App Android
```text
https://raw.githubusercontent.com/achayna/Generador-precios/main/output/precios_app_movil.json
```

---

## Estructura de `output/precios_app_movil.json`

Las etiquetas de vigencia **nunca confunden la hora de revisión del script con la fecha real del muestreo**:

```json
{
  "estado_actualizacion": "Actualizado hasta ayer 12",
  "estado_actualizacion_con_hora": "Actualizado hasta ayer 12 (16:00)",
  "actualizado_peru": "Actualizado hasta ayer 12",
  "ultima_fecha_datos": "12/11/2026",
  "ultima_hora_datos": "16:00",
  "ultima_revision_sistema": "13/11/2026 06:48",
  "actualizado_iso": "2026-11-13T06:48:00-05:00",
  "ventana_dias": 7,
  "total_puertos": 65,
  "puertos_con_datos": 42,
  "total_filas_precios": 710,
  "puertos": {
    "MATARANI": {
      "nombre_puerto": "MATARANI",
      "departamento": "AREQUIPA",
      "region": "COSTA",
      "ultima_fecha_muestreo": "12/11/2026",
      "ultima_hora_muestreo": "16:00",
      "estado_puerto": "Actualizado hasta ayer 12",
      "estado_puerto_con_hora": "Actualizado hasta ayer 12 (16:00)",
      "precios": [
        {
          "especie_mostrar": "Perico",
          "especie_corta": "Perico",
          "nombre_cientifico": "Coryphaena hippurus",
          "sinonimos_busqueda": "Perico, dorado",
          "talla": "STANDAR",
          "precio": 15.0,
          "precio_mostrar": "S/ 15.00",
          "hora": "08:48",
          "fecha": "11/11/2026",
          "hora_mostrar": "11/11 08:48"
        }
      ]
    }
  }
}
```
