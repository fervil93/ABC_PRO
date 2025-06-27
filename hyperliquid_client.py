import hyperliquid
from eth_account import Account
from config import API_URL
from secret import WALLET_ADDRESS, WALLET_PRIVATE_KEY

class HyperliquidClient:
    def __init__(self):
        self.client = hyperliquid.Exchange(api_url=API_URL)
        self.wallet_address = WALLET_ADDRESS
        self.wallet_private_key = WALLET_PRIVATE_KEY

    def get_account(self):
        # Estado público de la cuenta
        return self.client.get_user_state(self.wallet_address)

    def get_ohlcv(self, symbol, interval, limit):
        return self.client.candles(symbol + "USDT", interval, limit)

    def get_order_book(self, symbol):
        return self.client.orderbook(symbol + "USDT")

    def get_price(self, symbol):
        ticker = self.client.ticker(symbol + "USDT")
        return {'price': ticker['mark']}

    def create_order(self, symbol, side, size):
        # Hyperliquid espera size en unidades del activo (no USDT)
        # El side debe ser "buy" o "sell"
        # El SDK requiere firma EIP-712
        # La orden es de tipo mercado (market)
        payload = {
            "coin": symbol + "USDT",
            "is_buy": True if side.lower() == "buy" else False,
            "sz": str(size),
            "limit_px": None,   # Market order
            "reduce_only": False,
        }
        # Firma usando la clave privada
        signed = self.client.prepare_order(
            address=self.wallet_address,
            priv_key=self.wallet_private_key,
            **payload
        )
        # Enviar orden firmada
        resp = self.client.place_order(signed)
        return resp
