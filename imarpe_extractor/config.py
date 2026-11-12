"""Configuración central, endpoints reales descubiertos en INFOMAR y enriquecimiento geográfico."""

from datetime import datetime, timedelta, timezone
from typing import Dict

# Zona horaria oficial del Perú (UTC-5, sin horario de verano)
PERU_TZ = timezone(timedelta(hours=-5), name="PET")

BASE_URL = "https://infomar.imarpe.gob.pe"

# Endpoints API Moderna (Vue.js v2 - Sin autenticación ni CSRF)
ENDPOINT_LUGARES = f"{BASE_URL}/v2/api/lugares"
ENDPOINT_ESPECIES = f"{BASE_URL}/v2/api/especies"
ENDPOINT_ESPECIES_POR_PUERTO = f"{BASE_URL}/v2/api/especies-por-puertos"
ENDPOINT_ESPECIE_PUERTO = f"{BASE_URL}/v2/api/especie-puerto"
ENDPOINT_ESPECIES_LITORAL = f"{BASE_URL}/v2/api/especies-litoral"

# Endpoints Interfaz Legacy ASP.NET MVC (Respaldo secundario con cookie .ASPXAUTH)
LEGACY_LOGIN_URL = f"{BASE_URL}/Acceso/Login"
LEGACY_ESPECIES_PUERTO_URL = f"{BASE_URL}/Reportes/EspeciesPuerto"
LEGACY_PUBLIC_CREDENTIALS = {
    "Login": "invitado",
    "Password": "invitado",
    "PasswordVisita": "310404",
}

# Umbral exacto verificado empíricamente:
# Cuando (fecha_hasta - fecha).days <= 7, /v2/api/especies-por-puertos devuelve JSON directo
# (isExcel=False) incluyendo HORA_STRING. Para >= 8 días devuelve un XLSX en Base64 (isExcel=True).
MAX_JSON_WINDOW_DAYS = 7

DEFAULT_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/json;charset=UTF-8",
    "Origin": BASE_URL,
    "Referer": f"{BASE_URL}/newHome/especies",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
}

# Diccionario oficial de Departamentos del Perú para los 80 lugares de INFOMAR (Costa y Selva)
DEPARTAMENTO_POR_LUGAR_ID: Dict[int, str] = {
    # TUMBES
    1: "TUMBES",       # PUERTO PIZARRO
    2: "TUMBES",       # ACAPULCO
    3: "TUMBES",       # CANCAS
    63: "TUMBES",      # LA CRUZ
    64: "TUMBES",      # GRAU
    65: "TUMBES",      # ZORRITOS
    # PIURA
    4: "PIURA",        # MANCORA
    5: "PIURA",        # LOS ORGANOS
    6: "PIURA",        # EL ÑURO
    7: "PIURA",        # CABO BLANCO
    8: "PIURA",        # TALARA
    9: "PIURA",        # ISLILLA
    10: "PIURA",       # PAITA
    11: "PIURA",       # YACILA
    12: "PIURA",       # CONSTANTE
    13: "PIURA",       # PARACHIQUE
    14: "PIURA",       # PUERTO RICO
    70: "PIURA",       # MATACABALLO
    74: "PIURA",       # LAS DELICIAS (Bahía de Sechura)
    # LAMBAYEQUE
    15: "LAMBAYEQUE",  # SAN JOSE
    16: "LAMBAYEQUE",  # PIMENTEL
    17: "LAMBAYEQUE",  # SANTA ROSA
    71: "LAMBAYEQUE",  # PUERTO ETEN
    # LA LIBERTAD
    18: "LA LIBERTAD", # PACASMAYO
    19: "LA LIBERTAD", # MALABRIGO
    21: "LA LIBERTAD", # SALAVERRY
    85: "LA LIBERTAD", # CHERREPE
    86: "LA LIBERTAD", # PUERTO/CALETA MORIN
    # ANCASH
    22: "ANCASH",      # CHIMBOTE
    23: "ANCASH",      # LOS CHIMUS
    24: "ANCASH",      # SAMANCO
    25: "ANCASH",      # CULEBRAS
    51: "ANCASH",      # HUARMEY
    55: "ANCASH",      # CASMA
    73: "ANCASH",      # EL DORADO
    # LIMA / CALLAO
    26: "LIMA",        # CARQUIN
    27: "LIMA",        # HUACHO
    28: "LIMA",        # CHANCAY
    29: "LIMA",        # ANCON
    30: "CALLAO",      # CALLAO (Provincia Constitucional; en reportes internos LIMA/CALLAO)
    31: "LIMA",        # CHORRILLOS
    32: "LIMA",        # PUCUSANA
    33: "LIMA",        # CERRO AZUL
    52: "LIMA",        # SUPE
    53: "LIMA",        # VEGUETA
    # ICA
    34: "ICA",         # TAMBO DE MORA
    35: "ICA",         # SAN ANDRES
    36: "ICA",         # EL CHACO
    37: "ICA",         # LAGUNILLAS
    38: "ICA",         # LAGUNA GRANDE
    39: "ICA",         # RANCHERIO
    40: "ICA",         # SAN JUAN DE MARCONA
    81: "ICA",         # LA PUNTILLA
    # AREQUIPA
    41: "AREQUIPA",    # LOMAS
    42: "AREQUIPA",    # CHALA
    43: "AREQUIPA",    # ATICO
    44: "AREQUIPA",    # LA PLANCHADA
    45: "AREQUIPA",    # QUILCA
    46: "AREQUIPA",    # MATARANI
    102: "AREQUIPA",   # ISLAY
    137: "AREQUIPA",   # CAMANA
    # MOQUEGUA
    47: "MOQUEGUA",    # ILO
    # TACNA
    49: "TACNA",       # MORRO SAMA
    100: "TACNA",      # LOS PALOS
    101: "TACNA",      # PUERTO VIEJO
    # LORETO (SELVA)
    138: "LORETO",     # PUNCHANA
    139: "LORETO",     # BELEN
    140: "LORETO",     # CABALLOCOCHA
    141: "LORETO",     # REQUENA
    142: "LORETO",     # YURIMAGUAS
    143: "LORETO",     # CONTAMANA
    # UCAYALI (SELVA)
    144: "UCAYALI",    # 07 DE JUNIO (Pucallpa)
    147: "UCAYALI",    # AGUAYTIA
    148: "UCAYALI",    # IPARIA
    149: "UCAYALI",    # BOLOGNESI
    150: "UCAYALI",    # YARINACOCHA
    151: "UCAYALI",    # ATALAYA
    152: "UCAYALI",    # PURUS
    # MADRE DE DIOS (SELVA)
    145: "MADRE DE DIOS",  # IBERIA
    146: "MADRE DE DIOS",  # PUERTO MALDONADO
}


def now_peru() -> datetime:
    """Devuelve la fecha y hora actual exacta en hora oficial del Perú (UTC-5)."""
    return datetime.now(PERU_TZ)
