from hyperliquid import Hyperliquid
from secret import WALLET_ADDRESS, WALLET_PRIVATE_KEY
from config import API_URL

class HyperliquidClient:
    def __init__(self):
        self.client = Hyperliquid(
            api_url=API_URL,
            wallet_private_key=WALLET_PRIVATE_KEY,
            wallet_address=WALLET_ADDRESS
        )

    def get_account(self):
        return self.client.account_state()

    def get_ohlcv(self, symbol, interval, limit):
        # El SDK usa pares tipo "BTCUSDT"
        df = self.client.candles(
            symbol=symbol + "USDT",
            interval=interval,
            limit=limit
        )
        return df

    def get_order_book(self, symbol):
        return self.client.orderbook(symbol + "USDT")

    def get_price(self, symbol):
        ticker = self.client.ticker(symbol + "USDT")
        return {'price': ticker['last']}

    def create_order(self, symbol, side, size):
        # side: 'buy' o 'sell'
        return self.client.market_order(
            symbol=symbol + "USDT",
            side=side,
            size=size
        )
