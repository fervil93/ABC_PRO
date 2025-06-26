import requests
from config import API_URL, WALLET_ADDRESS

class HyperliquidClient:
    def __init__(self):
        self.api_url = API_URL
        self.wallet_address = WALLET_ADDRESS

    def get_account(self):
        endpoint = f"{self.api_url}/info"
        params = {"user": self.wallet_address}
        response = requests.get(endpoint, params=params)
        return response.json()

    def get_markets(self):
        endpoint = f"{self.api_url}/info"
        params = {"type": "markets"}
        response = requests.get(endpoint, params=params)
        return response.json()

    def get_price(self, symbol):
        endpoint = f"{self.api_url}/info"
        params = {"symbol": symbol}
        response = requests.get(endpoint, params=params)
        return response.json()

    def create_order(self, symbol, side, size, price=None):
        # NOTA: Para operar en mainnet debes firmar la orden, en testnet se puede simular.
        order = {
            "symbol": symbol,
            "side": side,      # "buy" o "sell"
            "size": size,      # cantidad del contrato
            "price": price,    # puede ser None para market
            "wallet": self.wallet_address,
            "testnet": True
        }
        endpoint = f"{self.api_url}/order"
        response = requests.post(endpoint, json=order)
        return response.json()