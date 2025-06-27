import time
import pandas as pd
import numpy as np
import math
import json
import os
import logging
from datetime import datetime, timedelta

from config import (
    TIMEOUT_MINUTES, LEVERAGE, MARGIN_PER_TRADE, ATR_TP_MULT, MAX_TP_PCT
)
from secret import WALLET_ADDRESS
from notificaciones import enviar_telegram
from hyperliquid_client import HyperliquidClient

logging.basicConfig(
    filename='bot_errors.log',
    level=logging.ERROR,
    format='%(asctime)s %(levelname)s:%(message)s'
)

with open("tiempo_inicio_bot.txt", "w") as f:
    f.write(datetime.now().isoformat())

client = HyperliquidClient()

ATR_SL_MULT = 1.0
MIN_POTENTIAL_PROFIT = 0.5

SPREAD_MAX_PCT_POR_SIMBOLO = {
    "BTC": 1.0, "ETH": 1.0, "BNB": 1.0, "SOL": 1.5, "XRP": 2.0, "ADA": 1.5,
    "DOGE": 1.5, "AVAX": 1.5, "TON": 1.5, "LINK": 1.5,
}
MULTIPLICADOR_VOL_POR_SIMBOLO = {
    "BTC": 1.0, "ETH": 1.0, "BNB": 1.0, "SOL": 0.8, "XRP": 0.8,
    "ADA": 0.8, "DOGE": 0.8, "AVAX": 0.8, "TON": 0.8, "LINK": 0.8,
}
BREAKOUT_ATR_MULT_POR_SIMBOLO = {
    "BTC": 0.1, "ETH": 0.1, "BNB": 0.1, "SOL": 0.05, "XRP": 0.05,
    "ADA": 0.05, "DOGE": 0.05, "AVAX": 0.05, "TON": 0.05, "LINK": 0.05,
}

ATR_LEVELS_FILE = "trade_levels_atr.json"
COOLDOWN_MINUTES = 15
SPREAD_MAX_PCT = 1
MAX_RETRIES = 3
RETRY_SLEEP = 2
VOLATILITY_WINDOW = 10
VOLATILITY_UMBRAL = 0.015

resumen_diario = {
    "trades_abiertos": 0,
    "trades_cerrados": 0,
    "pnl_total": 0.0,
    "ultimo_envio": datetime.now().date()
}

def retry_api_call(func, *args, **kwargs):
    for intento in range(1, MAX_RETRIES + 1):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            msg = f"[INTENTO {intento}/{MAX_RETRIES}] Error en {func.__name__}: {e}"
            print(msg)
            logging.error(msg, exc_info=True)
            if intento == MAX_RETRIES:
                enviar_telegram(f"❗️ Error crítico tras {MAX_RETRIES} intentos en {func.__name__}: {e}", tipo="error")
            else:
                time.sleep(RETRY_SLEEP)
    return None

def cargar_niveles_atr():
    try:
        if os.path.exists(ATR_LEVELS_FILE):
            with open(ATR_LEVELS_FILE, "r") as f:
                return json.load(f)
        else:
            return {}
    except Exception as e:
        logging.error(f"Error cargando niveles ATR: {e}", exc_info=True)
        enviar_telegram(f"⚠️ Error al cargar niveles ATR: {e}", tipo="error")
        return {}

def guardar_niveles_atr(data):
    try:
        with open(ATR_LEVELS_FILE, "w") as f:
            json.dump(data, f)
    except Exception as e:
        logging.error(f"Error guardando niveles ATR: {e}", exc_info=True)
        enviar_telegram(f"⚠️ Error al guardar niveles ATR: {e}", tipo="error")

def ajustar_precision(valor, precision):
    return float(f"{valor:.{precision}f}") if precision > 0 else float(int(valor))

def obtener_posiciones_hyperliquid():
    try:
        account = retry_api_call(client.get_account)
        # La estructura de user_state contiene 'assetPositions'
        if not account or "assetPositions" not in account:
            return []
        posiciones_abiertas = [p for p in account["assetPositions"] if float(p.get('position', 0)) != 0]
        return posiciones_abiertas
    except Exception as e:
        logging.error(f"Error al obtener posiciones Hyperliquid: {e}", exc_info=True)
        enviar_telegram(f"⚠️ Error al obtener posiciones Hyperliquid: {e}", tipo="error")
        return []

def obtener_datos_historicos(symbol, interval='1m', limit=100):
    try:
        df = client.get_ohlcv(symbol, interval, limit)
        if df is None:
            enviar_telegram(f"⚠️ Error al obtener datos históricos para {symbol}.", tipo="error")
            logging.error(f"Error al obtener datos históricos para {symbol}")
            return None
        if isinstance(df, list):
            df = pd.DataFrame(df)
            df.columns = ['timestamp','open','high','low','close','volume']
        return df
    except Exception as e:
        logging.error(f"Error al obtener datos históricos para {symbol}: {e}", exc_info=True)
        enviar_telegram(f"⚠️ Error al obtener datos históricos para {symbol}: {e}", tipo="error")
        return None

def calcular_atr(df, n=14):
    high_low = df['high'] - df['low']
    high_close = abs(df['high'] - df['close'].shift())
    low_close = abs(df['low'] - df['close'].shift())
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = ranges.max(axis=1)
    atr = true_range.rolling(window=n, min_periods=1).mean()
    return atr

def calcular_ema(df, n=30):
    return df['close'].ewm(span=n, adjust=False).mean()

def spread_aceptable(symbol):
    try:
        spread_limit = SPREAD_MAX_PCT_POR_SIMBOLO.get(symbol, SPREAD_MAX_PCT)
        order_book = retry_api_call(client.get_order_book, symbol=symbol)
        if not order_book or not order_book['bids'] or not order_book['asks']:
            enviar_telegram(f"⚠️ No se pudo obtener el order book para {symbol} para evaluar spread.", tipo="error")
            logging.error(f"No se pudo obtener order book para {symbol}")
            return False
        best_bid = float(order_book['bids'][0][0])
        best_ask = float(order_book['asks'][0][0])
        spread = best_ask - best_bid
        spread_pct = spread / ((best_ask + best_bid) / 2)
        if spread_pct > spread_limit / 100:
            print(f"[{symbol}] Spread demasiado alto: {spread_pct*100:.4f}% (límite: {spread_limit}%)")
            return False
        return True
    except Exception as e:
        logging.error(f"Error al evaluar spread aceptable para {symbol}: {e}", exc_info=True)
        enviar_telegram(f"⚠️ Error al evaluar spread para {symbol}: {e}", tipo="error")
        return False

def detectar_volatilidad_extrema(df):
    if len(df) < VOLATILITY_WINDOW + 1:
        return False
    precio_ini = df['close'].iloc[-VOLATILITY_WINDOW-1]
    precio_fin = df['close'].iloc[-1]
    move_pct = abs(precio_fin - precio_ini) / precio_ini
    if move_pct > VOLATILITY_UMBRAL:
        return True
    return False

def aplicar_condiciones_microestructura_v2(df, precio_actual, symbol):
    ventana_vol = 20
    ventana_atr = 14
    ventana_atr_media = 20

    breakout_mult = BREAKOUT_ATR_MULT_POR_SIMBOLO.get(symbol, 0.1)
    vol_mult = MULTIPLICADOR_VOL_POR_SIMBOLO.get(symbol, 1.0)

    df['vol_rolling'] = df['volume'].rolling(ventana_vol).mean()
    df['atr'] = calcular_atr(df, ventana_atr)
    df['atr_media'] = df['atr'].rolling(ventana_atr_media).mean()
    df['ema30'] = calcular_ema(df, 30)
    df['vol_spike'] = df['volume'] > df['vol_rolling'] * vol_mult

    atr_actual = df['atr'].iloc[-1]
    atr_media_actual = df['atr_media'].iloc[-1]
    close_actual = df['close'].iloc[-1]
    ema30_actual = df['ema30'].iloc[-1]
    prev_max = df['high'].iloc[-6:-1].max()
    prev_min = df['low'].iloc[-6:-1].min()

    if atr_actual < 0.7 * atr_media_actual:
        razon = f"ATR actual ({atr_actual:.6f}) < 0.7*ATR20 media ({0.7*atr_media_actual:.6f})."
        return None, razon, None, None

    long_signal = (
        df['vol_spike'].iloc[-1]
        and close_actual > prev_max + breakout_mult * atr_actual
        and close_actual > ema30_actual
    )
    short_signal = (
        df['vol_spike'].iloc[-1]
        and close_actual < prev_min - breakout_mult * atr_actual
        and close_actual < ema30_actual
    )

    if long_signal or short_signal:
        accion = 'BUY' if long_signal else 'SELL'
        razon = f"Señal {'LONG' if long_signal else 'SHORT'}: spike volumen, ruptura real y tendencia {'alcista' if long_signal else 'bajista'} EMA30."
        fee_est = close_actual * 0.001 * 3
        tp = calcular_tp_atr(close_actual, atr_actual, accion)
        potential_profit = abs(tp - close_actual) - fee_est
        if potential_profit < MIN_POTENTIAL_PROFIT:
            return None, f"El potencial de ganancia neta ({potential_profit:.4f}) es insuficiente para operar.", None, None
        return accion, razon, atr_actual, close_actual

    razon = f"No se detecta señal de microestructura (volumen spike: {df['vol_spike'].iloc[-1]})"
    return None, razon, None, None

def calcular_tp_atr(entry_price, atr, direction, fee_rate=0.001):
    max_tp_move = entry_price * MAX_TP_PCT
    if direction == "BUY":
        tp = entry_price + ATR_TP_MULT * atr
        tp = min(tp, entry_price + max_tp_move)
        tp = max(tp, entry_price + max(entry_price * fee_rate * 3, 0.5))
    else:
        tp = entry_price - ATR_TP_MULT * atr
        tp = max(tp, entry_price - max_tp_move)
        tp = min(tp, entry_price - max(entry_price * fee_rate * 3, 0.5))
    return tp

def calcular_cantidad_valida(symbol, monto_usdt):
    try:
        precio_actual = obtener_precio_hyperliquid(symbol)
        if precio_actual is None:
            return None
        cantidad_calculada = monto_usdt / precio_actual
        return cantidad_calculada
    except Exception as e:
        logging.error(f"Error al calcular cantidad válida para {symbol}: {e}", exc_info=True)
        enviar_telegram(f"⚠️ Error al calcular cantidad válida para {symbol}: {e}", tipo="error")
        return None

def tiene_saldo_suficiente(margen):
    try:
        account = retry_api_call(client.get_account)
        if not account or "equity" not in account:
            return False
        usdt_balance = float(account["equity"])
        if usdt_balance >= margen:
            return True
        else:
            print(f"Saldo insuficiente. Disponible: {usdt_balance} USDT, requerido: {margen} USDT")
            enviar_telegram(f"⚠️ Saldo insuficiente. Disponible: {usdt_balance} USDT, requerido: {margen} USDT", tipo="error")
            return False
    except Exception as e:
        logging.error(f"Error verificando saldo suficiente: {e}", exc_info=True)
        enviar_telegram(f"⚠️ Error verificando saldo suficiente: {e}", tipo="error")
        return False

def ejecutar_orden_hyperliquid(symbol, side, quantity):
    try:
        order = retry_api_call(client.create_order, symbol=symbol, side=side.lower(), size=quantity)
        if order and "status" in order:
            print(f"Orden ejecutada: {order}")
            return order
        else:
            enviar_telegram(f"⚠️ Error al ejecutar orden para {symbol} tras {MAX_RETRIES} intentos.", tipo="error")
            logging.error(f"Error al ejecutar orden para {symbol}: {order}")
            return None
    except Exception as e:
        logging.error(f"Error al ejecutar orden para {symbol}: {e}", exc_info=True)
        enviar_telegram(f"⚠️ Error al ejecutar orden para {symbol}: {e}", tipo="error")
        return None

def cerrar_posicion(symbol, positionAmt):
    try:
        side = "sell" if float(positionAmt) > 0 else "buy"
        quantity = abs(float(positionAmt))
        order = retry_api_call(client.create_order, symbol=symbol, side=side, size=quantity)
        if order and "status" in order:
            print(f"Posición cerrada para {symbol}: {order}")
            return order
        else:
            enviar_telegram(f"⚠️ Error al cerrar posición para {symbol} tras {MAX_RETRIES} intentos.", tipo="error")
            logging.error(f"Error al cerrar posición para {symbol}")
            return None
    except Exception as e:
        logging.error(f"Error al cerrar posición para {symbol}: {e}", exc_info=True)
        enviar_telegram(f"⚠️ Error al cerrar posición para {symbol}: {e}", tipo="error")
        return None

def evaluar_cierre_operacion_hyperliquid(pos, precio_actual, niveles_atr):
    try:
        entryPrice = float(pos['entryPrice'])
        positionAmt = float(pos['position'])
        qty = abs(positionAmt)
        symbol = pos['asset']
        direccion = "BUY" if positionAmt > 0 else "SELL"

        niveles = niveles_atr.get(symbol)
        if niveles and "tp_fijo" in niveles:
            tp = niveles["tp_fijo"]
        else:
            print(f"[{symbol}] No se encontró TP fijo guardado, usando cierre tradicional.")
            return False

        if (direccion == "BUY" and precio_actual >= tp) or (direccion == "SELL" and precio_actual <= tp):
            print(f"[{symbol}] Cerrando por Take Profit fijo. Entry: {entryPrice}, Actual: {precio_actual}, TP: {tp}")
            order = cerrar_posicion(symbol, positionAmt)
            time.sleep(2)
            pnl_estimado = ((precio_actual - entryPrice) * positionAmt) if direccion == "BUY" else ((entryPrice - precio_actual) * abs(positionAmt))
            icono_cerrado = "🟢" if pnl_estimado >= 0 else "🔴"
            pnl_texto = f"PnL estimado: {pnl_estimado:.4f}"
            enviar_telegram(
                f"{icono_cerrado} Trade CERRADO: {symbol} {direccion}\n"
                f"Entry: {entryPrice:.4f}\n"
                f"Close: {precio_actual:.4f}\n"
                f"TP: {tp:.4f}\n"
                f"{pnl_texto}",
                tipo="close"
            )
            resumen_diario["trades_cerrados"] += 1
            resumen_diario["pnl_total"] += pnl_estimado
            return True
    except Exception as e:
        print(f"Error en evaluar_cierre_operacion_hyperliquid: {e}")
        logging.error(f"Error en evaluar_cierre_operacion_hyperliquid: {e}", exc_info=True)
        enviar_telegram(f"⚠️ Error en evaluar_cierre_operacion_hyperliquid: {e}", tipo="error")
    return False

def obtener_precio_hyperliquid(symbol):
    try:
        ticker = retry_api_call(client.get_price, symbol=symbol)
        if ticker and 'mid' in ticker:
            return float(ticker['mid'])
        else:
            print(f"[{symbol}] No se encontró la clave 'mid' en el ticker: {ticker}")
            enviar_telegram(f"⚠️ No se encontró la clave 'mid' en el ticker de {symbol}.", tipo="error")
            logging.error(f"No se encontró la clave 'mid' en el ticker de {symbol}: {ticker}")
            return None
    except Exception as e:
        logging.error(f"Error al obtener precio para {symbol}: {e}", exc_info=True)
        enviar_telegram(f"⚠️ Error al obtener precio para {symbol}: {e}", tipo="error")
        return None

if __name__ == "__main__":
    try:
        enviar_telegram("🚀 Bot arrancado correctamente y en ejecución.", tipo="info")

        simbolos = ['BTC', 'ETH', 'BNB', 'SOL', 'XRP', 'ADA', 'DOGE', 'AVAX', 'TON', 'LINK']
        intervalo_segundos = 5
        tiempo_inicio = datetime.now()
        last_trade_time = None

        print("Iniciando bot de scalping microestructura v2 con TP fijo, sin trailing, sin Stop Loss ni cierre por timeout (Hyperliquid Testnet)...")
        print(f"Configuración: Apalancamiento={LEVERAGE}x | Margen por operación={MARGIN_PER_TRADE} USDT")
        print(f"TP: {ATR_TP_MULT}xATR (máx {MAX_TP_PCT*100:.1f}% sobre entrada) | SL: NO")

        while True:
            print(f"\nTiempo Transcurrido: {datetime.now() - tiempo_inicio}")

            posiciones = obtener_posiciones_hyperliquid()
            niveles_atr = cargar_niveles_atr()

            print(f"Posiciones abiertas en Hyperliquid ({len(posiciones)}):")
            for pos in posiciones:
                symbol = pos['asset']
                positionAmt = pos['position']
                entryPrice = pos['entryPrice']
                pnl = pos.get('unrealizedPnl', 0)
                print(f"  {symbol} | Cantidad: {positionAmt} | Precio Entrada: {entryPrice} | PnL No Realizado: {pnl}")

            # --- Evaluación de cierre ---
            for pos in posiciones:
                symbol = pos['asset']
                precio_actual = obtener_precio_hyperliquid(symbol)
                if precio_actual is None:
                    continue
                if evaluar_cierre_operacion_hyperliquid(pos, precio_actual, niveles_atr):
                    if symbol in niveles_atr:
                        del niveles_atr[symbol]
                        guardar_niveles_atr(niveles_atr)

            # --- Espera cooldown tras un trade abierto ---
            now = datetime.now()
            if last_trade_time and (now - last_trade_time) < timedelta(minutes=COOLDOWN_MINUTES):
                restante = timedelta(minutes=COOLDOWN_MINUTES) - (now - last_trade_time)
                print(f"En cooldown tras última apertura. Esperando {restante} antes de poder abrir otro trade.")
                time.sleep(intervalo_segundos)
                continue

            # --- Solo se permite una apertura nueva por ciclo ---
            apertura_realizada = False
            for simbolo in simbolos:
                ya_abierta = any(pos['asset'] == simbolo for pos in posiciones)
                if ya_abierta or apertura_realizada:
                    continue

                print(f"\nEvaluando condiciones microestructura para {simbolo}...")
                datos = obtener_datos_historicos(simbolo)
                if datos is None:
                    continue

                precio_actual = obtener_precio_hyperliquid(simbolo)
                if precio_actual is None:
                    continue

                # --- Detección de alta volatilidad ---
                if detectar_volatilidad_extrema(datos):
                    msg = f"🚨 Alta volatilidad detectada en {simbolo}: se suspende apertura de trades en este ciclo."
                    print(msg)
                    continue

                # --- Filtro de spread ---
                if not spread_aceptable(simbolo):
                    print(f"[{simbolo}] Spread no aceptable. Se descarta trade.")
                    continue

                accion, razon, atr, entry_price = aplicar_condiciones_microestructura_v2(datos, precio_actual, simbolo)

                if accion and atr is not None:
                    if tiene_saldo_suficiente(MARGIN_PER_TRADE):
                        monto_usdt = LEVERAGE * MARGIN_PER_TRADE
                        cantidad_valida = calcular_cantidad_valida(simbolo, monto_usdt)
                        if cantidad_valida:
                            orden = ejecutar_orden_hyperliquid(simbolo, accion, cantidad_valida)
                            if orden:
                                tp = calcular_tp_atr(entry_price, atr, accion)
                                niveles_atr[simbolo] = {"tp_fijo": tp}
                                guardar_niveles_atr(niveles_atr)
                                print(f"[{simbolo}] Trade ejecutado ({accion}) | ATR: {atr:.4f} | TP FIJO: {tp:.4f} | Configuración TP: {ATR_TP_MULT}xATR (máx {MAX_TP_PCT*100:.1f}% sobre entrada)")
                                icono_abierto = "🔵"
                                enviar_telegram(
                                    f"{icono_abierto} Trade ABIERTO: {simbolo} {accion}\n"
                                    f"Precio: {entry_price:.4f}\n"
                                    f"TP FIJO: {tp:.4f}\n"
                                    f"ATR: {atr:.4f}\n"
                                    f"Leverage: {LEVERAGE}x | Margen: {MARGIN_PER_TRADE} USDT",
                                    tipo="open"
                                )
                                resumen_diario["trades_abiertos"] += 1
                                apertura_realizada = True
                                last_trade_time = datetime.now()
                                break
                    else:
                        print("No hay saldo suficiente para operar.")
                else:
                    print(f"[{simbolo}] No se abre trade. Razón: {razon}")

            # Envío resumen diario si corresponde
            if resumen_diario["ultimo_envio"] != datetime.now().date():
                enviar_telegram(
                    f"📊 Resumen diario:\n"
                    f"Trades abiertos: {resumen_diario['trades_abiertos']}\n"
                    f"Trades cerrados: {resumen_diario['trades_cerrados']}\n"
                    f"PnL estimado: {resumen_diario['pnl_total']:.4f} USDT",
                    tipo="daily"
                )
                resumen_diario["trades_abiertos"] = 0
                resumen_diario["trades_cerrados"] = 0
                resumen_diario["pnl_total"] = 0.0
                resumen_diario["ultimo_envio"] = datetime.now().date()

            print(f"\nEsperando {intervalo_segundos} segundos antes de la próxima evaluación...")
            time.sleep(intervalo_segundos)
    except Exception as e:
        logging.error(f"Error crítico en el bucle principal: {e}", exc_info=True)
        enviar_telegram(f"❗️ Error crítico en el bucle principal: {e}", tipo="error")
