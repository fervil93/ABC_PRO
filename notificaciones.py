import requests
from config import (TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, 
                    NOTIFY_TRADE_OPEN, NOTIFY_TRADE_CLOSE, 
                    NOTIFY_ERRORS, NOTIFY_DAILY_SUMMARY)

def enviar_telegram(mensaje, tipo="info"):
    if tipo == "open" and not NOTIFY_TRADE_OPEN:
        return
    if tipo == "close" and not NOTIFY_TRADE_CLOSE:
        return
    if tipo == "error" and not NOTIFY_ERRORS:
        return
    if tipo == "daily" and not NOTIFY_DAILY_SUMMARY:
        return
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    params = {"chat_id": TELEGRAM_CHAT_ID, "text": mensaje}
    try:
        requests.get(url, params=params, timeout=10)
    except Exception as e:
        print(f"Error enviando mensaje a Telegram: {e}")
