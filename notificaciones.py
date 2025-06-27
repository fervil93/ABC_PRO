from secret import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID
import requests

def enviar_telegram(mensaje, tipo="info"):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": mensaje,
        "parse_mode": "HTML"
    }
    try:
        requests.post(url, data=data)
    except Exception as e:
        print(f"Error enviando notificación Telegram: {e}")
