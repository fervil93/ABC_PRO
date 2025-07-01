# Timeout para cierre automático de posiciones (en minutos)
TIMEOUT_MINUTES = 99999999999

# Apalancamiento deseado (si Hyperliquid testnet lo permite por API, sino se ignora)
LEVERAGE = 10

# Margen (USDT) que quieres arriesgar por cada operación
MARGIN_PER_TRADE = 100

# Multiplicador ATR para calcular TP
ATR_TP_MULT = 1.2

# Máximo 2% por encima del precio de entrada para TP
MAX_TP_PCT = 0.02

# Endpoint de la API de testnet de Hyperliquid
API_URL = "https://api.hyperliquid-testnet.xyz"

# Configuración DCA
DCA_ENABLED = True
DCA_MAX_LOSS_PCT = 0.05      # Activar DCA cuando la pérdida alcance -5%
DCA_MAX_ENTRIES = 999        # Sin límite práctico de entradas DCA
DCA_SIZE_MULTIPLIER = 1.0    # Mismo tamaño que la entrada original
DCA_MIN_TIME_BETWEEN = 1440  # 24 horas (1440 minutos) entre entradas DCA
DCA_MAX_TOTAL_SIZE_MULT = 999.0  # Sin límite efectivo
