# Timeout para cierre automático de posiciones (en minutos)
TIMEOUT_MINUTES = 99999999999

# Apalancamiento deseado (si Hyperliquid testnet lo permite por API, sino se ignora)
LEVERAGE = 10

# Margen (USDT) que quieres arriesgar por cada operación
MARGIN_PER_TRADE = 40

# Multiplicador ATR para calcular TP
ATR_TP_MULT = 1.2

# Máximo 2% por encima del precio de entrada para TP
MAX_TP_PCT = 0.02

# config.py
from secret import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID
### Notificaciones Telegram ###
NOTIFY_TRADE_OPEN = True      # Notificar cuando abre trade
NOTIFY_TRADE_CLOSE = True     # Notificar cuando cierra trade
NOTIFY_ERRORS = False         # Notificar errores críticos
NOTIFY_DAILY_SUMMARY = False  # Notificar resumen diario de operaciones

### Configuración Hyperliquid Testnet ###
# Endpoint de la API de testnet de Hyperliquid
API_URL = "https://api.hyperliquid-testnet.xyz"
