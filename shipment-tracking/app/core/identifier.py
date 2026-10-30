import re
from typing import Dict, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select

# Default in-memory mappings (fallback when database is offline or not passed)
AIRLINE_PREFIX_MAP: Dict[str, Dict[str, str]] = {
    "160": {
        "carrier_code": "CX",
        "name": "Cathay Pacific Cargo",
        "primary_provider": "cathay_cargo",
        "fallback_providers": "generic_air",
    },
    "618": {
        "carrier_code": "SQ",
        "name": "Singapore Airlines Cargo",
        "primary_provider": "singapore_airlines",
        "fallback_providers": "generic_air",
    },
    "020": {
        "carrier_code": "LH",
        "name": "Lufthansa Cargo",
        "primary_provider": "lufthansa_cargo",
        "fallback_providers": "generic_air",
    },
    "131": {
        "carrier_code": "JL",
        "name": "Japan Airlines Cargo",
        "primary_provider": "jal_cargo",
        "fallback_providers": "generic_air",
    },
    "1331": {
        "carrier_code": "JL",
        "name": "Japan Airlines Cargo",
        "primary_provider": "jal_cargo",
        "fallback_providers": "generic_air",
    },
    "016": {
        "carrier_code": "UA",
        "name": "United Cargo",
        "primary_provider": "generic_air",
        "fallback_providers": "",
    },
    "006": {
        "carrier_code": "DL",
        "name": "Delta Cargo",
        "primary_provider": "generic_air",
        "fallback_providers": "",
    },
    "074": {
        "carrier_code": "KL",
        "name": "KLM Cargo",
        "primary_provider": "generic_air",
        "fallback_providers": "",
    },
    "312": {
        "carrier_code": "6E",
        "name": "IndiGo Cargo",
        "primary_provider": "indigo_cargo",
        "fallback_providers": "generic_air",
    },
    "098": {
        "carrier_code": "AI",
        "name": "Air India Cargo",
        "primary_provider": "air_india_cargo",
        "fallback_providers": "generic_air",
    },
    "603": {
        "carrier_code": "UL",
        "name": "SriLankan Cargo",
        "primary_provider": "srilankan_cargo",
        "fallback_providers": "generic_air",
    },
    "141": {
        "carrier_code": "FZ",
        "name": "FlyDubai Cargo",
        "primary_provider": "flydubai_cargo",
        "fallback_providers": "generic_air",
    },
    "235": {
        "carrier_code": "TK",
        "name": "Turkish Cargo",
        "primary_provider": "turkish_cargo",
        "fallback_providers": "generic_air",
    },
    "672": {
        "carrier_code": "BI",
        "name": "Royal Brunei Airlines Cargo",
        "primary_provider": "royal_brunei_cargo",
        "fallback_providers": "generic_air",
    },
    "406": {
        "carrier_code": "5X",
        "name": "UPS Air Cargo",
        "primary_provider": "ups_air_cargo",
        "fallback_providers": "generic_air",
    },
    "198": {
        "carrier_code": "AFCOM",
        "name": "Afcom Cargo",
        "primary_provider": "afcom_cargo",
        "fallback_providers": "generic_air",
    },
    "071": {
        "carrier_code": "ET",
        "name": "Ethiopian Airlines Cargo",
        "primary_provider": "ethiopian_cargo",
        "fallback_providers": "generic_air",
    },
    "217": {
        "carrier_code": "TG",
        "name": "Thai Cargo",
        "primary_provider": "thai_cargo",
        "fallback_providers": "generic_air",
    },
    "157": {
        "carrier_code": "QR",
        "name": "Qatar Airways Cargo",
        "primary_provider": "qatar_cargo",
        "fallback_providers": "generic_air",
    },
    "615": {
        "carrier_code": "DHL",
        "name": "DHL Aviation Cargo",
        "primary_provider": "dhl_aviation_cargo",
        "fallback_providers": "generic_air",
    },
    "936": {
        "carrier_code": "D0",
        "name": "DHL Air",
        "primary_provider": "dhl_aviation_cargo",
        "fallback_providers": "generic_air",
    },
    "932": {
        "carrier_code": "VS",
        "name": "Virgin Atlantic Cargo",
        "primary_provider": "virgin_atlantic_cargo",
        "fallback_providers": "generic_air",
    },
    "607": {
        "carrier_code": "EY",
        "name": "Etihad Cargo",
        "primary_provider": "etihad_cargo",
        "fallback_providers": "generic_air",
    },
    "229": {
        "carrier_code": "KU",
        "name": "Kuwait Airways Cargo",
        "primary_provider": "kuwait_airways",
        "fallback_providers": "generic_air",
    },
    "807": {
        "carrier_code": "AK",
        "name": "AirAsia Cargo",
        "primary_provider": "air_asia",
        "fallback_providers": "generic_air",
    },
    "555": {
        "carrier_code": "SU",
        "name": "Aeroflot Cargo",
        "primary_provider": "aeroflot_cargo",
        "fallback_providers": "generic_air",
    },
    "577": {
        "carrier_code": "AD",
        "name": "Azul Cargo",
        "primary_provider": "azul_cargo",
        "fallback_providers": "generic_air",
    },
    "501": {
        "carrier_code": "7L",
        "name": "Silk Way West Airlines",
        "primary_provider": "silk_way_west_cargo",
        "fallback_providers": "generic_air",
    },
    "125": {
        "carrier_code": "BA",
        "name": "IAG Cargo",
        "primary_provider": "iag_cargo",
        "fallback_providers": "generic_air",
    },
    "072": {
        "carrier_code": "GF",
        "name": "Gulf Air",
        "primary_provider": "champ_cargo",
        "fallback_providers": "generic_air",
    },
    "232": {
        "carrier_code": "MH",
        "name": "Malaysia Airlines",
        "primary_provider": "maskargo",
        "fallback_providers": "generic_air",
    },
    "176": {
        "carrier_code": "EK",
        "name": "Emirates SkyCargo",
        "primary_provider": "emirates_skycargo",
        "fallback_providers": "generic_air",
    },
}

SEA_CONTAINER_PREFIX_MAP: Dict[str, Dict[str, str]] = {
    "AAAU": {"carrier_code": "AAAU", "name": "CLIFFLINE SHIPPING INDIA PVT LTD", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "AAMU": {"carrier_code": "AAMU", "name": "Shipping Line", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "AKLU": {"carrier_code": "AKKON", "name": "Akkon Lines", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "AMCU": {"carrier_code": "CMA_CGM", "name": "CMA CGM", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "ANNU": {"carrier_code": "CMA_CGM", "name": "CMA CGM (ANL)", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "APHU": {"carrier_code": "CMA_CGM", "name": "CMA CGM (APL)", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "APLU": {"carrier_code": "CMA_CGM", "name": "CMA CGM (APL)", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "APZU": {"carrier_code": "CMA_CGM", "name": "CMA CGM (APL)", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "ARKU": {"carrier_code": "ARKAS", "name": "Arkas Line", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "ASLU": {"carrier_code": "ASLU", "name": "CORDELIA CONTAINER SHIPPING LINE", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "AXIU": {"carrier_code": "AXIU", "name": "MEDITERRANEAN SHIPPING COMPANY", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "BAXU": {"carrier_code": "BAXU", "name": "FREIGHT CONNECTION INDIA PVT. LTD.", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "BEAU": {"carrier_code": "BEACON", "name": "Beacon Intermodal", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "BHCU": {"carrier_code": "BHCU", "name": "Shipping Line", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "BLJU": {"carrier_code": "BLJU", "name": "Unifeeder / DP World", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "BMOU": {"carrier_code": "BEACON", "name": "Beacon Intermodal", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "BOMU": {"carrier_code": "BOMU", "name": "Shipping Line", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "BOTU": {"carrier_code": "BOTU", "name": "Shipping Line", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "BSIU": {"carrier_code": "BSIU", "name": "Unifeeder / DP World", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "BSTU": {"carrier_code": "BSTU", "name": "Shipping Line", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "BSVU": {"carrier_code": "BSVU", "name": "THE SHIPPING CORPORATION OF INDIA", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "BURU": {"carrier_code": "BORCHARD", "name": "Borchard Lines", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "BWLU": {"carrier_code": "BWLU", "name": "ABRAO SHIPPING SERVICES LLC", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "BXAU": {"carrier_code": "BXAU", "name": "CU LINES[THAILAND]", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "CAAU": {"carrier_code": "CAAU", "name": "CAI International (MSC)", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "CAGU": {"carrier_code": "CMA_CGM", "name": "CMA CGM", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "CAIU": {"carrier_code": "CAI", "name": "CAI International", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "CAJU": {"carrier_code": "CAJU", "name": "OCEAN NETWORK EXPRESS (ONE)", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "CARU": {"carrier_code": "CARU", "name": "MEDITERRANEAN SHIPPING COMPANY", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "CAXU": {"carrier_code": "CAI", "name": "CAI International", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "CBHU": {"carrier_code": "COSCO", "name": "COSCO", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "CCLU": {"carrier_code": "COSCO", "name": "COSCO", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "CCRU": {"carrier_code": "CC_CONTAIN", "name": "C&C Container", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "CCTU": {"carrier_code": "COSCO", "name": "COSCO", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "CGHU": {"carrier_code": "CMA_CGM", "name": "CMA CGM", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "CGMU": {"carrier_code": "CMA_CGM", "name": "CMA CGM", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "CHSU": {"carrier_code": "CUL", "name": "China United Lines", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "CICU": {"carrier_code": "CICU", "name": "SMART MARINE SERVICES PVT LTD", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "CIPU": {"carrier_code": "CIPU", "name": "ANL", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "CKEU": {"carrier_code": "CKEU", "name": "Shipping Line", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "CKLU": {"carrier_code": "CKLU", "name": "CEEKAY SHIPPING SERVICES", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "CLHU": {"carrier_code": "CLHU", "name": "JAK MARITIME AND LOGISTICS INDIA PVT LTD", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "CLNU": {"carrier_code": "CLNU", "name": "SMART MARINE SERVICES PVT LTD", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "CLSU": {"carrier_code": "CLSU", "name": "CARAVEL", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "CMAU": {"carrier_code": "CMA_CGM", "name": "CMA CGM", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "CNNU": {"carrier_code": "SWIRE", "name": "Swire Shipping", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "CORU": {"carrier_code": "CORU", "name": "MEDITERRANEAN SHIPPING COMPANY", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "COSU": {"carrier_code": "COSCO", "name": "COSCO", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "CRSU": {"carrier_code": "CRONOS", "name": "Cronos Containers", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "CRTU": {"carrier_code": "CRTU", "name": "CEEKAY SHIPPING SERVICES", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "CRXU": {"carrier_code": "CRRC", "name": "China Railway CRRC", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "CSGU": {"carrier_code": "CSGU", "name": "COSCO Shipping", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "CSLU": {"carrier_code": "COSCO", "name": "COSCO (CSCL)", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "CSNU": {"carrier_code": "COSCO", "name": "COSCO (CSCL)", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "CSOU": {"carrier_code": "CSOU", "name": "COSCO Shipping", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "CSQU": {"carrier_code": "COSCO", "name": "COSCO", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "CSRU": {"carrier_code": "CSRU", "name": "COSCO Shipping", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "CULU": {"carrier_code": "CULU", "name": "CU Lines", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "CXDU": {"carrier_code": "CMA_CGM", "name": "CMA CGM", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "CXOU": {"carrier_code": "CXOU", "name": "MEDITERRANEAN SHIPPING COMPANY", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "CXRU": {"carrier_code": "COSCO", "name": "COSCO", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "CXTU": {"carrier_code": "CXTU", "name": "Shipping Line", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "CZZU": {"carrier_code": "CZZU", "name": "ZIM CONTAINER SERVICE", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "DAHU": {"carrier_code": "DAHU", "name": "DAHNAY LOGISTICS PRIVATE LIMITED", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "DAYU": {"carrier_code": "HAPAG_LLOY", "name": "Hapag-Lloyd", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "DFOU": {"carrier_code": "DFOU", "name": "COSCO", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "DFSU": {"carrier_code": "DONG_FANG", "name": "Dong Fang Container", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "DNAU": {"carrier_code": "CMA_CGM", "name": "CMA CGM (Delmas)", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "DOLU": {"carrier_code": "DOLU", "name": "RADIANT MARITIME INDIA PVT LTD", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "DPWU": {"carrier_code": "DPWU", "name": "Unifeeder / DP World", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "DRYU": {"carrier_code": "DRYU", "name": "UNIFEEDER AGENCIES INDIA PRIVATE LIMITED", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "DTEU": {"carrier_code": "DONG_FANG", "name": "Dong Fang Container", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "ECMU": {"carrier_code": "CMA_CGM", "name": "CMA CGM", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "ECNU": {"carrier_code": "ECNU", "name": "VISTAR SHIPPING LLC", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "EGHU": {"carrier_code": "EVERGREEN", "name": "Evergreen", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "EGSU": {"carrier_code": "EVERGREEN", "name": "Evergreen", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "EIAU": {"carrier_code": "EIAU", "name": "Evergreen Line", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "EISU": {"carrier_code": "EVERGREEN", "name": "Evergreen", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "EITU": {"carrier_code": "EVERGREEN", "name": "Evergreen", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "EMCU": {"carrier_code": "EVERGREEN", "name": "Evergreen", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "EOLU": {"carrier_code": "EOLU", "name": "Shipping Line", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "ESDU": {"carrier_code": "ESDU", "name": "Emirates Shipping Line", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "ESGU": {"carrier_code": "ESGU", "name": "Emirates Shipping Line", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "ESLU": {"carrier_code": "ESLU", "name": "Emirates Shipping Line", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "EXFU": {"carrier_code": "EXFU", "name": "KMTC MIDDLE EAST SHIPPING LLC", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "EXXU": {"carrier_code": "EXXU", "name": "Shipping Line", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "FANU": {"carrier_code": "FESCO", "name": "Fesco", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "FBIU": {"carrier_code": "FBIU", "name": "MEDITERRANEAN SHIPPING COMPANY", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "FBLU": {"carrier_code": "FBLU", "name": "ORIENT OVERSEAS CONTIANER LINE LTD", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "FCGU": {"carrier_code": "FCGU", "name": "MEDITERRANEAN SHIPPING COMPANY", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "FCIU": {"carrier_code": "FLORENS", "name": "Florens Container", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "FDCU": {"carrier_code": "FDCU", "name": "OCEAN NETWORK EXPRESS (ONE)", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "FESU": {"carrier_code": "FESCO", "name": "Fesco Transport", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "FFAU": {"carrier_code": "FLORENS", "name": "Florens Container", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "FLNU": {"carrier_code": "FLNU", "name": "Shipping Line", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "FLOU": {"carrier_code": "FLORENS", "name": "Florens Container", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "FSCU": {"carrier_code": "FLORENS", "name": "Florens Container", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "FTAU": {"carrier_code": "FTAU", "name": "COSCO", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "FTBU": {"carrier_code": "FTBU", "name": "DIAMOND SHIPPING", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "FYCU": {"carrier_code": "FYCU", "name": "UNIFEEDER AGENCIES INDIA PRIVATE LIMITED", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "GAOU": {"carrier_code": "GAOU", "name": "GATX / Seaco (MSC)", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "GATU": {"carrier_code": "GATX", "name": "GATX", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "GCNU": {"carrier_code": "GCNU", "name": "ATLANTIC CONTAINER LINE", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "GCXU": {"carrier_code": "GCXU", "name": "Maersk Line", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "GESU": {"carrier_code": "GE_SEACO", "name": "GE SeaCo", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "GHMU": {"carrier_code": "GHMU", "name": "NAVIO SHIPPING PVT LTD", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "GLDU": {"carrier_code": "GLDU", "name": "Gold Container (Cape Ocean)", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "GMCU": {"carrier_code": "GRIMALDI", "name": "Grimaldi Lines", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "GRMU": {"carrier_code": "GRMU", "name": "GOODRICH CONTAINER LINES", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "GVCU": {"carrier_code": "GVCU", "name": "TURKON LINE", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "HAEU": {"carrier_code": "HEUNG_A", "name": "Heung-A Shipping", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "HALU": {"carrier_code": "HEUNG_A", "name": "Heung-A Shipping", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "HAMU": {"carrier_code": "HAMU", "name": "Hapag-Lloyd", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "HASU": {"carrier_code": "MSK", "name": "Maersk Line", "primary_provider": "maersk", "fallback_providers": "track_trace,ldb_container,generic_ocean"},
    "HDMU": {"carrier_code": "HMM", "name": "HMM", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "HHXU": {"carrier_code": "HHXU", "name": "Shipping Line", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "HJCU": {"carrier_code": "HANJIN", "name": "Hanjin (Legacy)", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "HJSU": {"carrier_code": "HAIJING", "name": "Haijing Shipping", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "HLBU": {"carrier_code": "HAPAG_LLOY", "name": "Hapag-Lloyd", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "HLCU": {"carrier_code": "HAPAG_LLOY", "name": "Hapag-Lloyd", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "HLHU": {"carrier_code": "HLHU", "name": "Hapag-Lloyd", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "HLXU": {"carrier_code": "HAPAG_LLOY", "name": "Hapag-Lloyd", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "HMCU": {"carrier_code": "HMM", "name": "HMM", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "HMJU": {"carrier_code": "HMJU", "name": "HMM (Hyundai Merchant Marine)", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "HMMU": {"carrier_code": "HMM", "name": "HMM", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "HOYU": {"carrier_code": "HOYU", "name": "Shipping Line", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "HPCU": {"carrier_code": "HPCU", "name": "MEDITERRANEAN SHIPPING COMPANY", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "HSXU": {"carrier_code": "HSXU", "name": "TURKON LINE", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "IAAU": {"carrier_code": "INTERASIA", "name": "Interasia Lines", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "IALU": {"carrier_code": "IALU", "name": "IAL (Indo-Asia Lines)", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "INBU": {"carrier_code": "ICL", "name": "Independent Container Line", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "INLU": {"carrier_code": "INLU", "name": "Shipping Line", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "IPXU": {"carrier_code": "INTERASIA", "name": "Interasia Lines", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "IRSU": {"carrier_code": "IRISL", "name": "IRISL Group", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "JFSU": {"carrier_code": "JFSU", "name": "LCL SHIPPING AND FORWARDING LLC", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "JHSU": {"carrier_code": "JHSU", "name": "Shipping Line", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "JTMU": {"carrier_code": "JTMU", "name": "Textainer (MSC)", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "JXJU": {"carrier_code": "JXJU", "name": "Ocean Network Express (ONE)", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "KKFU": {"carrier_code": "ONE", "name": "Ocean Network Express (ONE)", "primary_provider": "one_line", "fallback_providers": "ldb_container,generic_ocean"},
    "KKTU": {"carrier_code": "KKTU", "name": "Ocean Network Express (ONE)", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "KMCU": {"carrier_code": "KMTC", "name": "KMTC", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "KMTC": {"carrier_code": "KMTC", "name": "KMTC (Korea Marine Transport)", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "KMTU": {"carrier_code": "KMTC", "name": "KMTC", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "KOCU": {"carrier_code": "KOCU", "name": "HMM (Hyundai Merchant Marine)", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "KSBU": {"carrier_code": "KSBU", "name": "Shipping Line", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "LEGU": {"carrier_code": "LEGU", "name": "Unifeeder / DP World", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "LLTU": {"carrier_code": "LLTU", "name": "RADIANT MARITIME INDIA PVT LTD", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "LMCU": {"carrier_code": "LMCU", "name": "Ignazio Messina & C.", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "LOHU": {"carrier_code": "LOHU", "name": "Shipping Line", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "LOJU": {"carrier_code": "LOJU", "name": "Shipping Line", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "LOMU": {"carrier_code": "LOMU", "name": "Shipping Line", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "LOUJ": {"carrier_code": "LOUJ", "name": "Shipping Line", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "LSCU": {"carrier_code": "LOGIN", "name": "Log-In Logistica", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "LYGU": {"carrier_code": "LYGU", "name": "Evergreen Line", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "MAEU": {"carrier_code": "MSK", "name": "Maersk", "primary_provider": "maersk", "fallback_providers": "track_trace,ldb_container,generic_ocean"},
    "MAGU": {"carrier_code": "MAGU", "name": "CMA-CGM SHIPPING AGENCIES INDIA LTD", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "MANU": {"carrier_code": "MATSON", "name": "Matson", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "MATU": {"carrier_code": "MATSON", "name": "Matson", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "MAXU": {"carrier_code": "MAXU", "name": "RADIANT MARITIME INDIA PVT LTD", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "MBIU": {"carrier_code": "MBIU", "name": "Shipping Line", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "MCAU": {"carrier_code": "MCAU", "name": "Maersk Line", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "MEDU": {"carrier_code": "MSC", "name": "Mediterranean Shipping Company", "primary_provider": "msc", "fallback_providers": "generic_ocean"},
    "MERU": {"carrier_code": "MERU", "name": "PIL (Pacific International Lines)", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "MHMR": {"carrier_code": "MHMR", "name": "GREENWICH MERIDIAN LOGISTICS INDIA PVT LTD", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "MIEU": {"carrier_code": "MIEU", "name": "Shipping Line", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "MJRU": {"carrier_code": "MJRU", "name": "RADIANT MARITIME INDIA PVT LTD", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "MMAU": {"carrier_code": "MMAU", "name": "Shipping Line", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "MNBU": {"carrier_code": "MNBU", "name": "Maersk Line", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "MOAU": {"carrier_code": "ONE", "name": "Ocean Network Express (ONE)", "primary_provider": "one_line", "fallback_providers": "ldb_container,generic_ocean"},
    "MOLU": {"carrier_code": "ONE", "name": "Ocean Network Express (ONE)", "primary_provider": "one_line", "fallback_providers": "ldb_container,generic_ocean"},
    "MOTU": {"carrier_code": "MOTU", "name": "Ocean Network Express (ONE)", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "MRFU": {"carrier_code": "MRFU", "name": "Shipping Line", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "MRKU": {"carrier_code": "MSK", "name": "Maersk", "primary_provider": "maersk", "fallback_providers": "track_trace,ldb_container,generic_ocean"},
    "MRSU": {"carrier_code": "MSK", "name": "Maersk Line", "primary_provider": "maersk", "fallback_providers": "track_trace,ldb_container,generic_ocean"},
    "MRSV": {"carrier_code": "MSK", "name": "Maersk", "primary_provider": "maersk", "fallback_providers": "track_trace,ldb_container,generic_ocean"},
    "MSBU": {"carrier_code": "MSBU", "name": "Mediterranean Shipping Company (MSC)", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "MSCU": {"carrier_code": "MSC", "name": "Mediterranean Shipping Company", "primary_provider": "msc", "fallback_providers": "generic_ocean"},
    "MSDU": {"carrier_code": "MSC", "name": "Mediterranean Shipping Company", "primary_provider": "msc", "fallback_providers": "generic_ocean"},
    "MSGU": {"carrier_code": "MSGU", "name": "Mediterranean Shipping Company (MSC)", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "MSKU": {"carrier_code": "MSK", "name": "Maersk", "primary_provider": "maersk", "fallback_providers": "track_trace,ldb_container,generic_ocean"},
    "MSMU": {"carrier_code": "MSC", "name": "Mediterranean Shipping Company", "primary_provider": "msc", "fallback_providers": "generic_ocean"},
    "MSNU": {"carrier_code": "MSC", "name": "Mediterranean Shipping Company", "primary_provider": "msc", "fallback_providers": "generic_ocean"},
    "MSWU": {"carrier_code": "MSC", "name": "Mediterranean Shipping Company", "primary_provider": "msc", "fallback_providers": "generic_ocean"},
    "MTMU": {"carrier_code": "MTMU", "name": "Shipping Line", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "MVIU": {"carrier_code": "MSK", "name": "Maersk", "primary_provider": "maersk", "fallback_providers": "track_trace,ldb_container,generic_ocean"},
    "MWCU": {"carrier_code": "MSK", "name": "MCC Transport (Maersk)", "primary_provider": "maersk", "fallback_providers": "track_trace,ldb_container,generic_ocean"},
    "MXCU": {"carrier_code": "MXCU", "name": "SEASTAR GLOBAL SHIPPING AND LOGISTICS LLP", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "MZWU": {"carrier_code": "MZWU", "name": "SMART MARINE SERVICES PVT LTD", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "NIDU": {"carrier_code": "NIDU", "name": "Shipping Line", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "NLLU": {"carrier_code": "NLLU", "name": "RADIANT MARITIME INDIA PVT LTD", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "NSLU": {"carrier_code": "NSCSA", "name": "Bahri (NSCSA)", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "NVOU": {"carrier_code": "NVOU", "name": "Shipping Line", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "NYKU": {"carrier_code": "ONE", "name": "Ocean Network Express (ONE)", "primary_provider": "one_line", "fallback_providers": "ldb_container,generic_ocean"},
    "NYSU": {"carrier_code": "NAMSUNG", "name": "Namsung Shipping", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "OCGU": {"carrier_code": "OCGU", "name": "Evergreen Line", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "OLUJ": {"carrier_code": "OLUJ", "name": "Shipping Line", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "ONEU": {"carrier_code": "ONE", "name": "Ocean Network Express (ONE)", "primary_provider": "one_line", "fallback_providers": "ldb_container,generic_ocean"},
    "ONEY": {"carrier_code": "ONE", "name": "Ocean Network Express (ONE)", "primary_provider": "one_line", "fallback_providers": "ldb_container,generic_ocean"},
    "ONLU": {"carrier_code": "ONLU", "name": "Asyad Line", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "OOCU": {"carrier_code": "OOCL", "name": "OOCL", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "OOLU": {"carrier_code": "OOCL", "name": "OOCL", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "OTPU": {"carrier_code": "OTPU", "name": "Textainer (MSC / Wan Hai)", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "PALU": {"carrier_code": "PIL", "name": "PIL", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "PCIU": {"carrier_code": "PIL", "name": "PIL", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "PCVU": {"carrier_code": "PCVU", "name": "Shipping Line", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "PFCU": {"carrier_code": "PFL", "name": "Pacific Forum Line", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "PIDU": {"carrier_code": "PIDU", "name": "PIL (Pacific International Lines)", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "PILU": {"carrier_code": "PIL", "name": "PIL", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "PLGU": {"carrier_code": "PLGU", "name": "Textainer (MSC)", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "POLU": {"carrier_code": "POLU", "name": "Shipping Line", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "PONU": {"carrier_code": "MSK", "name": "Maersk", "primary_provider": "maersk", "fallback_providers": "track_trace,ldb_container,generic_ocean"},
    "PRGU": {"carrier_code": "PRGU", "name": "SEA MARINE LOGISTICS PVT. LTD.", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "PRKU": {"carrier_code": "PERKINS", "name": "Perkins Shipping", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "PRSU": {"carrier_code": "PRSU", "name": "GLOBELINKWW INDIA PVT LTD", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "PSBU": {"carrier_code": "PSBU", "name": "Shipping Line", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "QNLU": {"carrier_code": "QNLU", "name": "Shipping Line", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "REGU": {"carrier_code": "RCL", "name": "Regional Container Lines", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "RFCU": {"carrier_code": "RFCU", "name": "OOCL", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "RFSU": {"carrier_code": "RFSU", "name": "Ocean Network Express (ONE)", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "RLTU": {"carrier_code": "RLTU", "name": "Shipping Line", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "SAFU": {"carrier_code": "MSK", "name": "Safmarine (Maersk)", "primary_provider": "maersk", "fallback_providers": "track_trace,ldb_container,generic_ocean"},
    "SCMU": {"carrier_code": "SEACASTLE", "name": "SeaCastle", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "SCZU": {"carrier_code": "SEACUBE", "name": "SeaCube Container", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "SEAU": {"carrier_code": "MSK", "name": "Maersk (Sealand)", "primary_provider": "maersk", "fallback_providers": "track_trace,ldb_container,generic_ocean"},
    "SEGU": {"carrier_code": "SEACASTLE", "name": "SeaCastle", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "SEKU": {"carrier_code": "SEKU", "name": "CMA CGM", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "SELU": {"carrier_code": "SELU", "name": "FREESEAS CONTAINER SHIPPING LLC", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "SGRU": {"carrier_code": "SGRU", "name": "Shipping Line", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "SIFU": {"carrier_code": "SIFU", "name": "Shipping Line", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "SIKU": {"carrier_code": "SINOKOR", "name": "Sinokor", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "SIMU": {"carrier_code": "SIMU", "name": "Shipping Line", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "SITU": {"carrier_code": "SITC", "name": "SITC", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "SKHU": {"carrier_code": "SKHU", "name": "Sinokor Merchant Marine", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "SKIU": {"carrier_code": "SKIU", "name": "CMA-CGM SHIPPING AGENCIES INDIA LTD", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "SKLU": {"carrier_code": "SINOKOR", "name": "Sinokor", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "SLPU": {"carrier_code": "SLPU", "name": "COSCO Shipping", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "SLSU": {"carrier_code": "SLSU", "name": "TS Lines", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "SLZU": {"carrier_code": "SLZU", "name": "Shipping Line", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "SMLM": {"carrier_code": "SM_LINE", "name": "SM Line", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "SMLU": {"carrier_code": "SM_LINE", "name": "SM Line", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "SNBU": {"carrier_code": "SEACASTLE", "name": "SeaCastle", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "SNCU": {"carrier_code": "SNCU", "name": "Shipping Line", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "SNRU": {"carrier_code": "SNRU", "name": "Samudera Shipping Line", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "SNTU": {"carrier_code": "SNTU", "name": "Shipping Line", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "SPPU": {"carrier_code": "SPPU", "name": "Shipping Corporation of India (SCI)", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "SRMU": {"carrier_code": "SRMU", "name": "Ocean Network Express (ONE)", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "SRXU": {"carrier_code": "SEACUBE", "name": "SeaCube Container", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "STBU": {"carrier_code": "STBU", "name": "Seacube Container (MSC)", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "STCU": {"carrier_code": "SITC", "name": "SITC", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "SUDU": {"carrier_code": "MSK", "name": "Maersk Line", "primary_provider": "maersk", "fallback_providers": "track_trace,ldb_container,generic_ocean"},
    "SUZU": {"carrier_code": "SUZU", "name": "NAVIO SHIPPING PVT LTD", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "SWGU": {"carrier_code": "SWIRE", "name": "Swire Shipping", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "SZLU": {"carrier_code": "SZLU", "name": "Seaco Global (MSC / IAL)", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "TCKU": {"carrier_code": "TCKU", "name": "Textainer (Maersk / MSC)", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "TCLU": {"carrier_code": "TRITON", "name": "Triton Container", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "TCMU": {"carrier_code": "TCMU", "name": "Shipping Line", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "TCNU": {"carrier_code": "TCNU", "name": "Textainer (MSC / ONE)", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "TDRU": {"carrier_code": "TDRU", "name": "Textainer (Cape Ocean / Cliffline)", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "TEMU": {"carrier_code": "TEXTAINER", "name": "Textainer", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "TEXU": {"carrier_code": "TEXTAINER", "name": "Textainer", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "TGBU": {"carrier_code": "TGBU", "name": "Textainer (MSC / CMA)", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "TGCU": {"carrier_code": "TARROS", "name": "Tarros Group", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "TGHU": {"carrier_code": "TRITON", "name": "Triton Container", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "TIDU": {"carrier_code": "TIDU", "name": "LCL SHIPPING AND FORWARDING LLC", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "TIFU": {"carrier_code": "TIFU", "name": "Textainer (MSC)", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "TIIU": {"carrier_code": "TIIU", "name": "Textainer (MSC / CMA)", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "TLHU": {"carrier_code": "TLHU", "name": "Shipping Line", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "TLLU": {"carrier_code": "ONE", "name": "Ocean Network Express (ONE)", "primary_provider": "one_line", "fallback_providers": "ldb_container,generic_ocean"},
    "TLNU": {"carrier_code": "TLNU", "name": "Shipping Line", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "TLXU": {"carrier_code": "TLXU", "name": "Shipping Line", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "TOLU": {"carrier_code": "TOLU", "name": "RADIANT MARITIME INDIA PVT LTD", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "TRHU": {"carrier_code": "TRITON", "name": "Triton Container", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "TRIU": {"carrier_code": "TRITON", "name": "Triton Container", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "TRKU": {"carrier_code": "TRKU", "name": "Turkon Line", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "TRLU": {"carrier_code": "TRLU", "name": "DIAMOND SHIPPING", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "TSLU": {"carrier_code": "TS_LINES", "name": "TS Lines", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "TSSU": {"carrier_code": "TS_LINES", "name": "TS Lines", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "TTAU": {"carrier_code": "TEXTAINER", "name": "Textainer", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "TTNU": {"carrier_code": "TRITON", "name": "Triton Container", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "TWCU": {"carrier_code": "TWCU", "name": "Shipping Line", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "TXGU": {"carrier_code": "TXGU", "name": "Textainer (MSC / Hapag)", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "UACU": {"carrier_code": "HAPAG_LLOY", "name": "Hapag-Lloyd (UASC)", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "UAEU": {"carrier_code": "UAEU", "name": "Hapag-Lloyd (UASC)", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "UESU": {"carrier_code": "UES", "name": "UES International", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "UETU": {"carrier_code": "UNIFEEDER", "name": "Unifeeder", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "UFCU": {"carrier_code": "UNIFEEDER", "name": "Unifeeder", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "UNIU": {"carrier_code": "UNIU", "name": "BAYLINES", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "UNSU": {"carrier_code": "UNSU", "name": "Shipping Line", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "UTCU": {"carrier_code": "UTCU", "name": "Shipping Line", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "VMLU": {"carrier_code": "VMLU", "name": "Goodrich Maritime", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "VSBU": {"carrier_code": "VSBU", "name": "Textainer (Diamond Shipping)", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "WBPU": {"carrier_code": "WBPU", "name": "Unifeeder / DP World", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "WEDU": {"carrier_code": "WEDU", "name": "NVOCEAN AGENCY PRIVATE LIMITED", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "WFHU": {"carrier_code": "WAN_HAI", "name": "Wan Hai", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "WHLU": {"carrier_code": "WAN_HAI", "name": "Wan Hai", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "WHSU": {"carrier_code": "WAN_HAI", "name": "Wan Hai", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "WIKU": {"carrier_code": "WIKU", "name": "Shipping Line", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "WNGU": {"carrier_code": "WNGU", "name": "NAVIO SHIPPING PVT LTD", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "WSCU": {"carrier_code": "WSCU", "name": "SEASTAR GLOBAL SHIPPING AND LOGISTICS LLP", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "XHCU": {"carrier_code": "XHCU", "name": "Textainer (MSC)", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "XINU": {"carrier_code": "XPRESS", "name": "X-Press Feeders", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "XPFU": {"carrier_code": "XPRESS", "name": "X-Press Feeders", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "XXIU": {"carrier_code": "XXIU", "name": "Asyad Line", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "YMJU": {"carrier_code": "YANG-MING", "name": "Yang Ming", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "YMLU": {"carrier_code": "YANG-MING", "name": "Yang Ming", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "YMMU": {"carrier_code": "YANG-MING", "name": "Yang Ming", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "ZCSU": {"carrier_code": "ZIM", "name": "ZIM", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "ZIMU": {"carrier_code": "ZIM", "name": "ZIM", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "ZSTU": {"carrier_code": "ZIM", "name": "ZIM", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "ZTSU": {"carrier_code": "ZTSU", "name": "NAVIO SHIPPING PVT LTD", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
    "ZXJU": {"carrier_code": "ZXJU", "name": "Shipping Line", "primary_provider": "containertracking_net", "fallback_providers": "generic_ocean"},
}


LIVE_SUPPORTED_AIR_PROVIDERS = {
    "cathay_cargo",
    "singapore_airlines",
    "jal_cargo",
    "indigo_cargo",
    "air_india_cargo",
    "srilankan_cargo",
    "flydubai_cargo",
    "turkish_cargo",
    "lufthansa_cargo",
    "royal_brunei_cargo",
    "ups_air_cargo",
    "ethiopian_cargo",
    "thai_cargo",
    "qatar_cargo",
    "dhl_aviation_cargo",
    "etihad_cargo",
    "kuwait_airways",
    "air_asia",
    "azul_cargo",
    "aeroflot_cargo",
    "afcom_cargo",
    "silk_way_west_cargo",
    "iag_cargo",
    "champ_cargo",
    "maskargo",
    "virgin_atlantic_cargo",
    "emirates_skycargo",
}
LIVE_SUPPORTED_SEA_PROVIDERS = {
    "msc",
    "ldb_container",
    "one_line",
    "maersk",
    "track_trace",
    "containertracking_net",
    "generic_ocean",
}


class IdentificationResult:
    def __init__(
        self,
        mode: str,
        clean_tracking_number: str,
        carrier_code: str,
        carrier_name: str,
        prefix: str,
        serial_number: str,
        primary_provider: str,
        fallback_providers: list[str],
        is_valid_format: bool = True,
        is_supported: bool = True,
        relatable_message: Optional[str] = None,
    ):
        self.mode = mode
        self.clean_tracking_number = clean_tracking_number
        self.carrier_code = carrier_code
        self.carrier_name = carrier_name
        self.prefix = prefix
        self.serial_number = serial_number
        self.primary_provider = primary_provider
        self.fallback_providers = fallback_providers
        self.is_valid_format = is_valid_format
        self.is_supported = is_supported
        self.relatable_message = relatable_message

    def to_dict(self):
        return {
            "mode": self.mode,
            "clean_tracking_number": self.clean_tracking_number,
            "carrier_code": self.carrier_code,
            "carrier_name": self.carrier_name,
            "prefix": self.prefix,
            "serial_number": self.serial_number,
            "primary_provider": self.primary_provider,
            "fallback_providers": self.fallback_providers,
            "is_valid_format": self.is_valid_format,
            "is_supported": self.is_supported,
            "relatable_message": self.relatable_message,
        }


def _lookup_db_carrier(db: Optional[Session], prefix: str, mode: str):
    """Query MySQL carriers table for custom carrier provider rules."""
    if not db:
        return None
    try:
        from app.db.models import Carrier
        stmt = select(Carrier).where(
            (Carrier.prefix == prefix)
            | (Carrier.code == prefix)
            | Carrier.prefix.like(f"%{prefix}%"),
            Carrier.mode == mode,
        )
        return db.execute(stmt).scalars().first()
    except Exception:
        return None


def parse_and_identify(
    raw_query: str,
    explicit_mode: Optional[str] = None,
    db: Optional[Session] = None,
    carrier_code_override: Optional[str] = None,
) -> IdentificationResult:
    cleaned = raw_query.strip().upper()
    digits_only = re.sub(r"\D", "", cleaned)

    # Normalize 1331 alias to 131 (standard JAL prefix)
    if digits_only.startswith("1331") and len(digits_only) == 12:
        digits_only = "131" + digits_only[4:]
    if cleaned.startswith("1331-"):
        cleaned = "131-" + cleaned[5:]

    # 0. Ocean Network Express (ONE) identification (containers, bookings, or carrier code override)
    is_one_carrier = (
        (carrier_code_override and carrier_code_override.strip().upper() in ("ONE", "ONEY"))
        or cleaned.startswith("ONEY")
        or cleaned.startswith("ONEU")
        or (cleaned.startswith("BLRG") and len(cleaned) >= 8)
    )
    if is_one_carrier:
        prefix = "ONEU" if cleaned.startswith("ONEU") else "ONEY"
        serial = cleaned[4:] if (cleaned.startswith("ONEU") or cleaned.startswith("ONEY")) else cleaned
        return IdentificationResult(
            mode="SEA",
            clean_tracking_number=cleaned,
            carrier_code="ONE",
            carrier_name="Ocean Network Express (ONE)",
            prefix=prefix,
            serial_number=serial,
            primary_provider="one_line",
            fallback_providers=["ldb_container", "generic_ocean"],
            is_valid_format=True,
            is_supported=True,
            relatable_message=None,
        )

    # 1. SEA Container detection: Standard ISO 6346 container (4 alpha + 6 or 7 digits, e.g. MSMU6484830, AKLU1234567)
    clean_alphanumeric = re.sub(r"[^A-Z0-9]", "", cleaned)
    container_match = re.match(r"^([A-Z]{4})(\d{6,7})$", clean_alphanumeric)
    if container_match or (explicit_mode == "SEA" and len(clean_alphanumeric) >= 7):
        if container_match:
            prefix = container_match.group(1)
            serial = container_match.group(2)
            cleaned = clean_alphanumeric
        else:
            prefix = clean_alphanumeric[:4]
            serial = clean_alphanumeric[4:]
            cleaned = clean_alphanumeric

        # Check DB first
        db_carrier = _lookup_db_carrier(db, prefix, "SEA")
        if db_carrier:
            fallbacks = [
                p.strip()
                for p in (db_carrier.fallback_providers or "").split(",")
                if p.strip()
            ]
            primary_p = db_carrier.primary_provider
            carrier_code = db_carrier.code
            carrier_name = db_carrier.name
        else:
            carrier_info = SEA_CONTAINER_PREFIX_MAP.get(
                prefix,
                {
                    "carrier_code": f"SEA_{prefix}",
                    "name": f"Shipping Line ({prefix})",
                    "primary_provider": "containertracking_net",
                    "fallback_providers": "generic_ocean",
                },
            )
            fallbacks = [
                p.strip()
                for p in carrier_info["fallback_providers"].split(",")
                if p.strip()
            ]
            primary_p = carrier_info["primary_provider"]
            carrier_code = carrier_info["carrier_code"]
            carrier_name = carrier_info["name"]

        is_supported = primary_p in LIVE_SUPPORTED_SEA_PROVIDERS
        relatable_msg = (
            None
            if is_supported
            else f"Shipping line not supported: Container prefix '{prefix}' ({carrier_name}) is currently not supported for live tracking."
        )

        return IdentificationResult(
            mode="SEA",
            clean_tracking_number=f"{prefix}{serial}",
            carrier_code=carrier_code,
            carrier_name=carrier_name,
            prefix=prefix,
            serial_number=serial,
            primary_provider=primary_p,
            fallback_providers=fallbacks,
            is_valid_format=True,
            is_supported=is_supported,
            relatable_message=relatable_msg,
        )

    # 2. AIR Waybill detection: Standard 11-digit AWB (3 prefix + 8 serial)
    if (explicit_mode is None and len(digits_only) == 11) or (explicit_mode == "AIR" and len(digits_only) >= 8):
        prefix = digits_only[:3]
        serial = digits_only[3:]

        # Check DB first
        db_carrier = _lookup_db_carrier(db, prefix, "AIR")
        if db_carrier:
            fallbacks = [
                p.strip()
                for p in (db_carrier.fallback_providers or "").split(",")
                if p.strip()
            ]
            primary_p = db_carrier.primary_provider
            carrier_code = db_carrier.code
            carrier_name = db_carrier.name
        else:
            carrier_info = AIRLINE_PREFIX_MAP.get(
                prefix,
                {
                    "carrier_code": f"AIR_{prefix}",
                    "name": f"Airline Prefix {prefix}",
                    "primary_provider": "generic_air",
                    "fallback_providers": "",
                },
            )
            fallbacks = [
                p.strip()
                for p in carrier_info["fallback_providers"].split(",")
                if p.strip()
            ]
            primary_p = carrier_info["primary_provider"]
            carrier_code = carrier_info["carrier_code"]
            carrier_name = carrier_info["name"]

        is_supported = primary_p in LIVE_SUPPORTED_AIR_PROVIDERS
        relatable_msg = (
            None
            if is_supported
            else f"Airline not supported: Prefix '{prefix}' ({carrier_name}) is currently not supported for live tracking."
        )

        return IdentificationResult(
            mode="AIR",
            clean_tracking_number=f"{prefix}-{serial}",
            carrier_code=carrier_code,
            carrier_name=carrier_name,
            prefix=prefix,
            serial_number=serial,
            primary_provider=primary_p,
            fallback_providers=fallbacks,
            is_valid_format=True,
            is_supported=is_supported,
            relatable_message=relatable_msg,
        )

    # 3. Invalid tracking number format
    detected_mode = "SEA" if re.search(r"[A-Z]{2,}", cleaned) else "AIR"
    return IdentificationResult(
        mode=detected_mode,
        clean_tracking_number=cleaned,
        carrier_code="UNKNOWN",
        carrier_name="Unknown Carrier",
        prefix="",
        serial_number=cleaned,
        primary_provider="none",
        fallback_providers=[],
        is_valid_format=False,
        is_supported=False,
        relatable_message=f"Invalid tracking number format: '{raw_query}'. Expected an 11-digit Air Waybill (e.g. 160-15246221) or standard Sea Container number (e.g. MSMU6484830).",
    )
