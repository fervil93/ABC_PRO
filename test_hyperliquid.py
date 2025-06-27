from hyperliquid import Client

client = Client(api_url="https://api.hyperliquid-testnet.xyz")
print(client.ticker("BTCUSDT"))
