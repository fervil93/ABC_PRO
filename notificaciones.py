import requests
from secret import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID

def enviar_telegram(mensaje, tipo="info"):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    iconos = {
        "info": "ℹ️",
        "error": "❗️",
        "open": "🟢",
        "close": "🔴",
        "daily": "📊"
    }
    icono = iconos.get(tipo, "")
    try:
        requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": f"{icono} {mensaje}"})
    except Exception as e:
        print(f"Error enviando mensaje Telegram: {e}")
