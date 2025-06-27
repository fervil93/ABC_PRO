# hyperliquid_client.py
from hyperliquid.exchange import Exchange
from hyperliquid.info import Info
from eth_account import Account
import time
from secret import WALLET_PRIVATE_KEY, WALLET_ADDRESS
import config

class HyperliquidClient:
    def __init__(self):
        # Crear wallet desde la clave privada
        self.wallet = Account.from_key(WALLET_PRIVATE_KEY)
        
        # Instancias para operar y consultar utilizando la API_URL de config.py
        self.info = Info(config.API_URL)  # Para consultas
        self.exchange = Exchange(self.wallet, config.API_URL)  # Para trading
        
        # Para mantener compatibilidad con la estructura que usas en tu bot
        # Creamos un atributo "order" que tiene un método "market"
        self.order = self.OrderProxy(self.exchange)
        
    class OrderProxy:
        def __init__(self, exchange):
            self.exchange = exchange
            
        def market(self, symbol, size, is_buy=True):
            """Compatibilidad con la interfaz anterior"""
            return self.exchange.market_open(symbol, is_buy, size)
        
    def get_account(self):
        # Devuelve el estado de la cuenta
        return self.info.user_state(WALLET_ADDRESS)

    def get_ohlcv(self, symbol, interval, limit):
        """
        Obtiene datos OHLCV para un símbolo
        
        Args:
            symbol (str): Símbolo del activo
            interval (str): Intervalo temporal ('1m', '5m', etc.)
            limit (int): Cantidad de velas a obtener
        
        Returns:
            list: Lista de diccionarios con datos OHLCV o None si hay error
        """
        try:
            # Calcular timestamps (en milisegundos)
            end_time = int(time.time() * 1000)
            
            # Mapea los intervalos a segundos
            interval_segundos = {
                "1m": 60, "5m": 300, "15m": 900, "30m": 1800,
                "1h": 3600, "4h": 14400, "1d": 86400
            }
            
            # Calcula el tiempo de inicio basado en el intervalo y límite
            segundos = interval_segundos.get(interval, 60) * limit
            start_time = end_time - (segundos * 1000)
            
            # Obtiene los datos de velas
            candles_data = self.info.candles_snapshot(symbol, interval, start_time, end_time)
            
            # Si no hay datos, devuelve None
            if not candles_data or len(candles_data) == 0:
                print(f"No hay datos OHLCV disponibles para {symbol}")
                return None
                
            # Reformatea la respuesta para mantener la compatibilidad con tu código existente
            formatted_candles = []
            for candle in candles_data:
                formatted_candle = {
                    'timestamp': candle['t'],
                    'open': float(candle['o']),
                    'high': float(candle['h']), 
                    'low': float(candle['l']), 
                    'close': float(candle['c']),
                    'volume': float(candle['v'])
                }
                formatted_candles.append(formatted_candle)
            
            return formatted_candles
            
        except Exception as e:
            print(f"Error al obtener datos OHLCV para {symbol}: {str(e)}")
            return None

    def get_order_book(self, symbol):
        """
        Obtiene el libro de órdenes para un símbolo
        
        Args:
            symbol (str): Símbolo del activo
            
        Returns:
            dict: Libro de órdenes con bids y asks
        """
        try:
            l2_snapshot = self.info.l2_snapshot(symbol)
            
            # Reformatear la respuesta para mantener compatibilidad
            order_book = {
                'bids': [],
                'asks': []
            }
            
            # Los niveles[0] son asks (ventas), niveles[1] son bids (compras)
            if len(l2_snapshot["levels"]) > 0 and l2_snapshot["levels"][0]:
                for order in l2_snapshot["levels"][0]:
                    order_book['asks'].append([order['px'], order['sz']])
                    
            if len(l2_snapshot["levels"]) > 1 and l2_snapshot["levels"][1]:
                for order in l2_snapshot["levels"][1]:
                    order_book['bids'].append([order['px'], order['sz']])
            
            return order_book
        except Exception as e:
            print(f"Error al obtener order book para {symbol}: {str(e)}")
            return {'bids': [], 'asks': []}

    def get_price(self, symbol):
        """
        Obtiene el precio actual de un símbolo
        
        Args:
            symbol (str): Símbolo del activo
            
        Returns:
            dict: Mejor bid, ask y precio medio
        """
        try:
            order_book = self.get_order_book(symbol)
            
            best_ask = float(order_book['asks'][0][0]) if order_book['asks'] else None
            best_bid = float(order_book['bids'][0][0]) if order_book['bids'] else None
            mid = (best_ask + best_bid) / 2 if best_ask and best_bid else None
            
            return {"best_bid": best_bid, "best_ask": best_ask, "mid": mid}
        except Exception as e:
            print(f"Error al obtener precio para {symbol}: {str(e)}")
            return {"best_bid": None, "best_ask": None, "mid": None}

    def create_order(self, symbol, side, size):
        """
        Crea una orden de mercado
        
        Args:
            symbol (str): Símbolo del activo
            side (str): 'buy' o 'sell'
            size (float): Tamaño de la posición
            
        Returns:
            dict: Respuesta de la orden
        """
        is_buy = True if side.lower() == "buy" else False
        return self.exchange.market_open(symbol, is_buy, size)
