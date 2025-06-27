import hyperliquid
from config import API_URL
from secret import WALLET_ADDRESS, WALLET_PRIVATE_KEY

class HyperliquidClient:
    def __init__(self):
        self.client = hyperliquid.Exchange(api_url=API_URL)

    def get_account(self):
        # Devuelve el estado de la cuenta pública
        return self.client.get_user_state(WALLET_ADDRESS)

    def get_ohlcv(self, symbol, interval, limit):
        # Devuelve velas OHLCV como lista de dicts
        return self.client.candles(symbol + "USDT", interval, limit)

    def get_order_book(self, symbol):
        return self.client.orderbook(symbol + "USDT")

    def get_price(self, symbol):
        ticker = self.client.ticker(symbol + "USDT")
        # field 'mark' es el precio de referencia
        return {'price': ticker['mark']}

    # --------- TRADING: Envío de órdenes -----------
    def create_order(self, symbol, side, size):
        # El SDK oficial requiere firma para órdenes
        # Aquí te indico cómo implementar la lógica con la API REST firmada
        # Ejemplo de orden de mercado (simplificado)
        order = {
            "symbol": symbol + "USDT",
            "side": side.lower(),  # "buy" o "sell"
            "type": "market",
            "size": size,
            "reduceOnly": False
        }
        # FIRMAR Y ENVIAR ORDEN: debes implementar el proceso de firma según la doc oficial
        # https://github.com/hyperliquid-dex/python-sdk#trading-on-hyperliquid
        # Puedes usar web3 y eth_account para firmar, o la clase Signer del SDK si la añaden.
        # Por ahora, devuelve un dummy para que no rompa tu código:
        return {"status": "simulated", "order": order}
