"""
convenios.py — Catálogo único de convenios institucionales.

Fuente de datos compartida entre el Dashboard DRAC (estadísticas/mapa) y el
Generador de Reportes (selección de convenio). Mantener aquí evita duplicar la lista.
"""

CONVENIOS_DATA = [
    {"N": 1,  "numero": "SCE-UTM-CM-NAC-2024-09",       "contraparte": "UNIVERSIDAD TÉCNICA DE MANABÍ",                        "tipo": "CONVENIO MARCO",              "fecha": "10/12/2024", "canton": "Portoviejo",          "provincia": "Manabí",       "lat": -1.0543, "lon": -80.4543},
    {"N": 2,  "numero": "SCE-CCP-CM-NAC-2024-08",       "contraparte": "CÁMARA DE LA CONSTRUCCIÓN DE PORTOVIEJO",              "tipo": "CONVENIO MARCO",              "fecha": "20/12/2024", "canton": "Portoviejo",          "provincia": "Manabí",       "lat": -1.0543, "lon": -80.4543},
    {"N": 3,  "numero": "SCE-CEG-CM-NAC-2024-10",       "contraparte": "COLEGIO DE ECONOMISTAS DEL GUAYAS",                    "tipo": "CONVENIO MARCO",              "fecha": "23/12/2024", "canton": "Guayaquil",           "provincia": "Guayas",       "lat": -2.1894, "lon": -79.8891},
    {"N": 4,  "numero": "SCE-GADMG-CM-NAC-2025-001",    "contraparte": "GAD MUNICIPAL DE GUALACEO",                            "tipo": "CONVENIO MARCO",              "fecha": "22/01/2025", "canton": "Gualaceo",            "provincia": "Azuay",        "lat": -2.8897, "lon": -78.7833},
    {"N": 5,  "numero": "SCE-UC-CCI-NAC-2025-001",      "contraparte": "UNIVERSIDAD CATÓLICA DE CUENCA",                       "tipo": "COOPERACIÓN INTERINSTITUCIONAL", "fecha": "23/01/2025", "canton": "Cuenca",           "provincia": "Azuay",        "lat": -2.9001, "lon": -79.0059},
    {"N": 6,  "numero": "SCE-UPSE-CM-NAC-2025-002",     "contraparte": "UNIVERSIDAD PENÍNSULA DE SANTA ELENA",                 "tipo": "CONVENIO MARCO",              "fecha": "24/01/2025", "canton": "La Libertad",         "provincia": "Santa Elena",  "lat": -2.2333, "lon": -80.9167},
    {"N": 7,  "numero": "SCE-UG-CM-NAC-2025-003",       "contraparte": "UNIVERSIDAD DE GUAYAQUIL",                             "tipo": "CONVENIO MARCO",              "fecha": "27/01/2025", "canton": "Guayaquil",           "provincia": "Guayas",       "lat": -2.1894, "lon": -79.8891},
    {"N": 8,  "numero": "SCE-UTEG-CM-NAC-2025-004",     "contraparte": "UNIVERSIDAD TECNOLÓGICA EMPRESARIAL DE GUAYAQUIL",     "tipo": "CONVENIO MARCO",              "fecha": "27/01/2025", "canton": "Guayaquil",           "provincia": "Guayas",       "lat": -2.1894, "lon": -79.8891},
    {"N": 9,  "numero": "SCE-UPSC-CM-NAC-2025-005",     "contraparte": "UNIVERSIDAD POLITÉCNICA SALESIANA SEDE CUENCA",        "tipo": "CONVENIO MARCO",              "fecha": "14/02/2025", "canton": "Cuenca",              "provincia": "Azuay",        "lat": -2.9001, "lon": -79.0059},
    {"N": 10, "numero": "SCE-CCCUENCA-CM-NAC-2025-008", "contraparte": "CÁMARA DE COMERCIO DE CUENCA",                         "tipo": "CONVENIO MARCO",              "fecha": "26/03/2025", "canton": "Cuenca",              "provincia": "Azuay",        "lat": -2.9001, "lon": -79.0059},
    {"N": 11, "numero": "SCE-CAPIA-CM-NAC-2025-009",    "contraparte": "CÁMARA DE LA PEQUEÑA INDUSTRIA DEL AZUAY",             "tipo": "CONVENIO MARCO",              "fecha": "27/03/2025", "canton": "Cuenca",              "provincia": "Azuay",        "lat": -2.9001, "lon": -79.0059},
    {"N": 12, "numero": "SCE-FAPM-CM-NAC-2025-15",      "contraparte": "FEDERACIÓN ARTESANOS PROFESIONALES DEL CANTÓN MANTA",  "tipo": "CONVENIO MARCO",              "fecha": "18/08/2025", "canton": "Manta",               "provincia": "Manabí",       "lat": -0.9677, "lon": -80.7089},
    {"N": 13, "numero": "SCE-UETHOG-CM-NAC-2025-16",    "contraparte": "U. E. PARTICULAR TENIENTE HUGO ORTIZ",                 "tipo": "CONVENIO MARCO",              "fecha": "18/08/2025", "canton": "Portoviejo",          "provincia": "Manabí",       "lat": -1.0543, "lon": -80.4543},
    {"N": 14, "numero": "SCE-UNESUM-CM-NAC-2025-17",    "contraparte": "UNIVERSIDAD ESTATAL DEL SUR DE MANABÍ",                "tipo": "CONVENIO MARCO",              "fecha": "12/09/2025", "canton": "Jipijapa",            "provincia": "Manabí",       "lat": -1.3464, "lon": -80.5785},
    {"N": 15, "numero": "SCE-UTPL-CM-NAC-2025-19",      "contraparte": "UNIVERSIDAD TÉCNICA PARTICULAR DE LOJA",               "tipo": "CONVENIO MARCO",              "fecha": "25/09/2025", "canton": "Loja",                "provincia": "Loja",         "lat": -3.9931, "lon": -79.2042},
    {"N": 16, "numero": "SCE-ELECGALAPAGOS-CM-NAC-2025-20", "contraparte": "EMPRESA ELÉCTRICA GALÁPAGOS",                      "tipo": "CONVENIO MARCO",              "fecha": "02/10/2025", "canton": "San Cristóbal",       "provincia": "Galápagos",    "lat": -0.9167, "lon": -89.6167},
    {"N": 17, "numero": "UPSE-P-081-12-2025-C",          "contraparte": "UNIVERSIDAD PENÍNSULA DE SANTA ELENA",                "tipo": "CONVENIO ESPECÍFICO",         "fecha": "11/11/2025", "canton": "La Libertad",         "provincia": "Santa Elena",  "lat": -2.2333, "lon": -80.9167},
    {"N": 18, "numero": "SCE-ESPAM-CM-NAC-2025-23",      "contraparte": "E. S. POLITÉCNICA AGROPECUARIA DE MANABÍ",            "tipo": "CONVENIO MARCO",              "fecha": "12/11/2025", "canton": "Bolívar (Calceta)",   "provincia": "Manabí",       "lat": -0.8268, "lon": -80.1780},
    {"N": 19, "numero": "SCE-ULEAM-CM-NAC-2025-22",      "contraparte": "UNIVERSIDAD LAICA ELOY ALFARO DE MANABÍ",             "tipo": "CONVENIO MARCO",              "fecha": "13/11/2025", "canton": "Manta",               "provincia": "Manabí",       "lat": -0.9677, "lon": -80.7089},
    {"N": 20, "numero": "SCE-UNEMI-CMNAC-2026-01",       "contraparte": "UNIVERSIDAD ESTATAL DE MILAGRO",                      "tipo": "CONVENIO MARCO",              "fecha": "20/02/2026", "canton": "Milagro",             "provincia": "Guayas",       "lat": -2.1340, "lon": -79.5872},
]

# Derivados útiles para formularios
NUMEROS_CONVENIO: list[str] = [c["numero"] for c in CONVENIOS_DATA]
CONVENIO_CONTRAPARTE: dict[str, str] = {c["numero"]: c["contraparte"] for c in CONVENIOS_DATA}

# Selección por contraparte → número(s) de convenio (una contraparte puede tener varios)
CONTRAPARTES: list[str] = sorted({c["contraparte"] for c in CONVENIOS_DATA})
CONTRAPARTE_NUMEROS: dict[str, list[str]] = {}
for _c in CONVENIOS_DATA:
    CONTRAPARTE_NUMEROS.setdefault(_c["contraparte"], []).append(_c["numero"])
