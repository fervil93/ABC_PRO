from hyperliquid import Client
from secret import WALLET_ADDRESS, WALLET_PRIVATE_KEY
from config import API_URL

client = Client(
    base_url=API_URL,
    wallet_address=WALLET_ADDRESS,
    wallet_private_key=WALLET_PRIVATE_KEY
)

print(client.account_state())
