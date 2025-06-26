import requests
from config import API_URL
from secret import WALLET_ADDRESS

class HyperliquidClient:
    def __init__(self):
        self.api_url = API_URL
        self.wallet_address = WALLET_ADDRESS

    def get_account(self):
        endpoint = f"{self.api_url}/info"
        params = {"user": self.wallet_address}
        response = requests.get(endpoint, params=params, timeout=10)
        return response.json()

    def get_markets(self):
        endpoint = f"{self.api_url}/info"
        params = {"type": "markets"}
        response = requests.get(endpoint, params=params, timeout=10)
        return response.json()

    def get_price(self, symbol):
        endpoint = f"{self.api_url}/info"
        params = {"symbol": symbol}
        response = requests.get(endpoint, params=params, timeout=10)
        return response.json()
    
    def get_order_book(self, symbol, limit=5):
        endpoint = f"{self.api_url}/orderbook"
        params = {"symbol": symbol, "limit": limit}
        response = requests.get(endpoint, params=params, timeout=10)
        return response.json()

    def get_ohlcv(self, symbol, interval='1m', limit=100):
        endpoint = f"{self.api_url}/ohlcv"
        params = {"symbol": symbol, "interval": interval, "limit": limit}
        response = requests.get(endpoint, params=params, timeout=10)
        if response.status_code != 200:
            return None
        data = response.json()
        if not data or 'data' not in data:
            return None
        # Formatear a DataFrame
        import pandas as pd
        ohlcv = data['data']
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['open'] = df['open'].astype(float)
        df['high'] = df['high'].astype(float)
        df['low'] = df['low'].astype(float)
        df['close'] = df['close'].astype(float)
        df['volume'] = df['volume'].astype(float)
        return df

    def create_order(self, symbol, side, size, price=None):
        # Para operar en mainnet se requiere firma, en testnet se puede simular.
        order = {
            "symbol": symbol,
            "side": side,      # "buy" o "sell"
            "size": size,      # cantidad del contrato
            "wallet": self.wallet_address,
            "testnet": True
        }
        if price is not None:
            order["price"] = price
        endpoint = f"{self.api_url}/order"
        response = requests.post(endpoint, json=order, timeout=10)
        return response.json()
