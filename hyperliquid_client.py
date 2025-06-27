# hyperliquid_client.py
from hyperliquid.exchange import Exchange
from hyperliquid.info import Info
from eth_account import Account
from secret import WALLET_PRIVATE_KEY, WALLET_ADDRESS
import config

class HyperliquidClient:
    def __init__(self):
        # Crear wallet desde la clave privada
        self.wallet = Account.from_key(WALLET_PRIVATE_KEY)
        
        # Instancias para operar y consultar utilizando la API_URL de config.py
        self.info = Info(config.API_URL)  # Para consultas
        self.exchange = Exchange(self.wallet, config.API_URL)  # Para trading
        
    def get_account(self):
        # Devuelve el estado de la cuenta
        return self.info.user_state(WALLET_ADDRESS)

    def get_ohlcv(self, symbol, interval, limit):
        # Para obtener datos OHLCV necesitaremos adaptar la implementación
        # El SDK actual usa candles_snapshot con timestamps
        import time
        
        # Calcular timestamps (en milisegundos)
        end_time = int(time.time() * 1000)
        # Calcula el tiempo de inicio basado en el intervalo y límite
        # Esto es una aproximación - ajusta según sea necesario
        interval_seconds = {
            "1m": 60, "5m": 300, "15m": 900, "30m": 1800,
            "1h": 3600, "4h": 14400, "1d": 86400
        }
        seconds = interval_seconds.get(interval, 60) * limit
        start_time = end_time - (seconds * 1000)
        
        return self.info.candles_snapshot(symbol, interval, start_time, end_time)

    def get_order_book(self, symbol):
        return self.info.l2_snapshot(symbol)

    def get_price(self, symbol):
        ob = self.info.l2_snapshot(symbol)
        
        # Adaptar a la estructura actual del l2_snapshot
        best_ask = float(ob["levels"][0][0]["px"]) if ob["levels"][0] else None
        best_bid = float(ob["levels"][1][0]["px"]) if len(ob["levels"]) > 1 and ob["levels"][1] else None
        mid = (best_ask + best_bid) / 2 if best_ask and best_bid else None
        return {"best_bid": best_bid, "best_ask": best_ask, "mid": mid}

    def create_order(self, symbol, side, size):
        # side: "buy" o "sell"
        is_buy = True if side.lower() == "buy" else False
        
        # Usando market_open para órdenes de mercado
        return self.exchange.market_open(symbol, is_buy, size)
    
    def set_leverage(self, symbol, leverage=None):
        # Configurar apalancamiento según config.LEVERAGE si no se especifica
        if leverage is None:
            leverage = config.LEVERAGE
        
        # Actualizar leverage usando el método correcto de la API
        try:
            return self.exchange.update_leverage(leverage, symbol)
        except Exception as e:
            print(f"Error al establecer apalancamiento: {e}")
            return None
