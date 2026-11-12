"""Modelos de dominio tipados para catálogos, observaciones y precios vigentes de INFOMAR."""

from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List, Optional


@dataclass(frozen=True)
class Lugar:
    """Puerto, caleta o Desembarcadero Pesquero Artesanal (DPA) registrado en INFOMAR."""

    lugar_id: int
    nombre_lugar: str
    region: str  # "COSTA" | "SELVA"
    departamento: str


@dataclass(frozen=True)
class Especie:
    """Taxón comercial registrado en el catálogo maestro de INFOMAR."""

    taxon_id: int
    nombre_taxon_raw: str
    nombre_comun: str
    nombre_comun_principal: str
    nombre_cientifico: str


@dataclass(frozen=True)
class ObservacionPrecio:
    """Muestreo puntual de precio en playa/muelle por tamaño, fecha y hora."""

    lugar_id: int
    puerto: str
    region: str
    departamento: str
    taxon_id: Optional[int]
    nombre_comun: str
    nombre_comun_principal: str
    nombre_cientifico: str
    tamano: str
    precio_kg: float
    fecha: date
    fecha_iso: str        # YYYY-MM-DD
    fecha_display: str    # DD/MM/YYYY
    hora: str             # HH:MM
    dias_antiguedad: int


@dataclass
class ResumenVigentePuertoEspecie:
    """Último precio vigente consolidado para una especie en un puerto específico."""

    region: str
    departamento: str
    lugar_id: int
    puerto: str
    taxon_id: Optional[int]
    nombre_comun: str
    nombre_comun_principal: str
    nombre_cientifico: str
    precio_promedio_kg: float
    precio_min_kg: float
    precio_max_kg: float
    ultimo_precio_kg: float
    precios_por_tamano: Dict[str, float]
    detalle_tamanos_texto: str
    muestreos_ultimo_dia: int
    fecha_ultimo_registro: date
    fecha_ultimo_registro_iso: str
    fecha_ultimo_registro_display: str
    hora_ultimo_registro: str
    dias_antiguedad: int
    historico_ventana: List[ObservacionPrecio] = field(default_factory=list)


@dataclass(frozen=True)
class ItemPrecioMovil:
    """Fila ultraligera lista para pintar la tabla móvil de 3 columnas (Especie | Precio | Hora)."""

    lugar_id: int
    puerto: str
    region: str
    departamento: str
    especie_mostrar: str       # Columna 1: ej. "Cabrilla (Grande)" o "Bonito"
    especie_corta: str         # Ej. "Cabrilla"
    nombre_cientifico: str     # Ej. "Paralabrax humeralis"
    sinonimos_busqueda: str    # Ej. "Cabrilla, cagálo, bagalo, cabrilla comun"
    talla: str                 # Ej. "GRANDE"
    precio: float              # Ej. 27.0
    precio_mostrar: str        # Columna 2: ej. "S/ 27.00"
    hora: str                  # Ej. "16:00"
    fecha: str                 # Ej. "10/11/2026"
    hora_mostrar: str          # Columna 3: ej. "Hoy 16:00", "Ayer 16:00" o "10/11 16:00"

