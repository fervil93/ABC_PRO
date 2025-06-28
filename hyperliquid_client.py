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

    def set_leverage(self, symbol, leverage):
        """
        Configura el apalancamiento para un símbolo específico
        
        Args:
            symbol (str): Símbolo del activo
            leverage (int): Valor del apalancamiento (ej: 5, 10, 20)
            
        Returns:
            dict: Respuesta de la operación o None si hay error
        """
        try:
            # Implementa la llamada a la API de Hyperliquid para configurar el apalancamiento
            print(f"[{symbol}] Configurando apalancamiento a {leverage}x")
            
            # Intento 1: Usar el método específico de la API si existe
            try:
                response = self.exchange.update_leverage(symbol, leverage)
                print(f"[{symbol}] Apalancamiento configurado correctamente: {response}")
                return response
            except AttributeError:
                # Si el método no existe, intentar con el enfoque alternativo
                print(f"[{symbol}] Método update_leverage no disponible, intentando alternativa...")
            
            # Intento 2: Usar un enfoque personalizado si la API lo soporta
            try:
                # Este es un ejemplo hipotético, ajusta según la API real
                response = self.exchange.post(
                    endpoint='/derivative/v3/private/position/leverage/save',
                    data={
                        'symbol': symbol,
                        'leverage': leverage
                    }
                )
                print(f"[{symbol}] Apalancamiento configurado por método alternativo: {response}")
                return response
            except Exception as e:
                print(f"[{symbol}] Error en método alternativo: {e}")
            
            # Si no funciona ninguno de los métodos anteriores, devolver un diccionario vacío
            return {"status": "not_supported", "message": "La configuración de apalancamiento no está soportada por la API"}
            
        except Exception as e:
            print(f"[{symbol}] Error al configurar apalancamiento: {e}")
            return None

    def create_order(self, symbol, side, size, price=None, leverage=None):
        """
        Crea una orden de mercado o límite con apalancamiento personalizado
        
        Args:
            symbol (str): Símbolo del activo
            side (str): 'buy' o 'sell'
            size (float): Tamaño de la posición
            price (float, optional): Precio límite (si es None, se crea una orden de mercado)
            leverage (int, optional): Apalancamiento a utilizar (si es None, se usa el valor por defecto)
            
        Returns:
            dict: Respuesta de la orden
        """
        # Intentar configurar el apalancamiento primero si se especificó
        if leverage is not None:
            try:
                self.set_leverage(symbol, leverage)
                print(f"[{symbol}] Apalancamiento configurado antes de la orden: {leverage}x")
            except Exception as e:
                print(f"[{symbol}] Error al configurar apalancamiento: {e}")
        else:
            # Si no se especificó leverage, usar el valor de config.py
            try:
                default_leverage = config.LEVERAGE
                self.set_leverage(symbol, default_leverage)
                print(f"[{symbol}] Usando apalancamiento predeterminado: {default_leverage}x")
            except Exception as e:
                print(f"[{symbol}] Error al configurar apalancamiento predeterminado: {e}")
        
        # Crear la orden
        is_buy = True if side.lower() == "buy" else False
        
        # Si price es None, crear orden de mercado. De lo contrario, orden límite.
        if price is None:
            print(f"[{symbol}] Creando orden de mercado: {side.upper()} {size}")
            return self.exchange.market_open(symbol, is_buy, size)
        else:
            print(f"[{symbol}] Creando orden límite: {side.upper()} {size} @ {price}")
            return self.exchange.limit_open(symbol, is_buy, size, price)
    
    def cancel_order(self, symbol, order_id):
        """
        Cancela una orden existente
        
        Args:
            symbol (str): Símbolo del activo
            order_id (str): ID de la orden a cancelar
            
        Returns:
            dict: Respuesta de la cancelación
        """
        try:
            return self.exchange.cancel_order(symbol, order_id)
        except Exception as e:
            print(f"Error al cancelar orden para {symbol}: {str(e)}")
            return {"status": "error", "message": str(e)}
