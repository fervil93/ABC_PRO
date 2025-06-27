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
MIN_POTENTIAL_PROFIT = 0.45

SPREAD_MAX_PCT_POR_SIMBOLO = {
    "BTC": 1.0, "ETH": 1.0, "BNB": 1.0, "SOL": 1.5, "XRP": 2.0, "ADA": 1.5,
    "DOGE": 1.5, "AVAX": 1.5, "LINK": 1.5, "MATIC": 1.5, "ARB": 1.5, "SUI": 1.5, 
    "PEPE": 2.0, "OP": 1.5, "NEAR": 1.5, "DOT": 1.5, "ATOM": 1.5, "LTC": 1.5, 
    "SHIB": 2.0, "UNI": 1.5
}
MULTIPLICADOR_VOL_POR_SIMBOLO = {
    "BTC": 1.0, "ETH": 1.0, "BNB": 1.0, "SOL": 0.8, "XRP": 0.8,
    "ADA": 0.8, "DOGE": 0.8, "AVAX": 0.8, "LINK": 0.8, "MATIC": 0.8, 
    "ARB": 0.8, "SUI": 0.8, "PEPE": 0.7, "OP": 0.8, "NEAR": 0.8, 
    "DOT": 0.8, "ATOM": 0.8, "LTC": 0.8, "SHIB": 0.7, "UNI": 0.8
}
BREAKOUT_ATR_MULT_POR_SIMBOLO = {
    "BTC": 0.1, "ETH": 0.1, "BNB": 0.1, "SOL": 0.05, "XRP": 0.05,
    "ADA": 0.05, "DOGE": 0.05, "AVAX": 0.05, "LINK": 0.05,
    "MATIC": 0.05, "ARB": 0.05, "SUI": 0.05, "PEPE": 0.05, "OP": 0.05,
    "NEAR": 0.05, "DOT": 0.05, "ATOM": 0.05, "LTC": 0.05, "SHIB": 0.05,
    "UNI": 0.05
}

# Definir la precisión para cada símbolo según las reglas de Hyperliquid
# Para tokens de bajo precio (DOGE, SHIB, etc.) usamos 0 (enteros)
# Para tokens de precio medio (SOL, ARB, etc.) usamos 1 decimal
# Para tokens de alto precio (BTC, ETH) usamos más precisión
PRECISION_POR_SIMBOLO = {
    "BTC": 3,  # 0.001 BTC
    "ETH": 2,  # 0.01 ETH
    "BNB": 2,  # 0.01 BNB
    "SOL": 1,  # 0.1 SOL
    "XRP": 0,  # 1 XRP
    "ADA": 0,  # 1 ADA
    "DOGE": 0, # 1 DOGE
    "AVAX": 1, # 0.1 AVAX
    "LINK": 1, # 0.1 LINK
    "MATIC": 0, # 1 MATIC
    "ARB": 0,  # 1 ARB
    "SUI": 0,  # 1 SUI
    "PEPE": 0, # 1 PEPE
    "OP": 0,   # 1 OP
    "NEAR": 0, # 1 NEAR
    "DOT": 1,  # 0.1 DOT
    "ATOM": 1, # 0.1 ATOM
    "LTC": 2,  # 0.01 LTC
    "SHIB": 0, # 1 SHIB
    "UNI": 1   # 0.1 UNI
}

ATR_LEVELS_FILE = "trade_levels_atr.json"
TP_ORDERS_FILE = "tp_orders.json"
COOLDOWN_MINUTES = 5  # Reducido de 15 a 5 minutos
SPREAD_MAX_PCT = 1
MAX_RETRIES = 3
RETRY_SLEEP = 2
VOLATILITY_WINDOW = 10
VOLATILITY_UMBRAL = 0.015
REEVALUACION_SIMBOLOS_HORAS = 6  # Frecuencia para reevaluar símbolos
DEBUG = False  # Controla el verbose

resumen_diario = {
    "trades_abiertos": 0,
    "trades_cerrados": 0,
    "pnl_total": 0.0,
    "ultimo_envio": datetime.now().date()
}

def debug_print(mensaje, *args):
    """Función para imprimir mensajes de depuración solo si DEBUG está activado"""
    if DEBUG:
        if args:
            print(mensaje, *args)
        else:
            print(mensaje)

def obtener_simbolos_disponibles():
    """Obtiene la lista de símbolos disponibles en Hyperliquid ordenados por capitalización"""
    # Lista ampliada de los 20 pares con mayor capitalización en Hyperliquid
    todos_simbolos = [
        'BTC', 'ETH', 'SOL', 'BNB', 'DOGE', 'ARB', 'MATIC', 'SUI', 'PEPE', 'OP', 
        'XRP', 'AVAX', 'LINK', 'NEAR', 'DOT', 'ADA', 'ATOM', 'LTC', 'SHIB', 'UNI'
    ]
    
    print("Verificando disponibilidad de símbolos en Hyperliquid...")
    
    simbolos_disponibles = []
    for symbol in todos_simbolos:
        try:
            # Intenta obtener precio actual para verificar disponibilidad
            precio = client.get_price(symbol)
            if precio and precio.get('mid'):
                # Verificar además que podemos obtener datos históricos
                df = client.get_ohlcv(symbol, '1m', 10)  # Solo probamos con 10 velas
                if df is not None and len(df) > 0:
                    simbolos_disponibles.append(symbol)
                    print(f"✅ {symbol} disponible - Precio: {precio.get('mid')}")
                else:
                    print(f"❌ {symbol} tiene precio pero no datos históricos")
            else:
                print(f"❌ {symbol} no disponible o sin liquidez")
        except Exception as e:
            print(f"❌ Error verificando {symbol}: {str(e)}")
    
    # Guardar la última vez que verificamos los símbolos
    with open("ultima_verificacion_simbolos.txt", "w") as f:
        f.write(datetime.now().isoformat())
    
    # Guardar la lista de símbolos disponibles en un archivo
    with open("simbolos_disponibles.txt", "w") as f:
        f.write(",".join(simbolos_disponibles))
    
    return simbolos_disponibles

def verificar_posicion_existente(simbolo, posiciones):
    """Verifica si ya existe una posición abierta para el símbolo dado"""
    for pos in posiciones:
        asset = pos.get('asset', '').upper()
        if asset == simbolo.upper():
            return True
    return False

def verificar_tiempo_para_reevaluar():
    """Verifica si es momento de reevaluar los símbolos disponibles"""
    try:
        if os.path.exists("ultima_verificacion_simbolos.txt"):
            with open("ultima_verificacion_simbolos.txt", "r") as f:
                ultima_verificacion = datetime.fromisoformat(f.read().strip())
                tiempo_transcurrido = datetime.now() - ultima_verificacion
                if tiempo_transcurrido > timedelta(hours=REEVALUACION_SIMBOLOS_HORAS):
                    return True
        else:
            return True
    except Exception:
        return True
    return False

def retry_api_call(func, *args, **kwargs):
    for intento in range(1, MAX_RETRIES + 1):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            msg = f"[INTENTO {intento}/{MAX_RETRIES}] Error en {func.__name__}: {e}"
            debug_print(msg)
            logging.error(msg, exc_info=True)
            if intento == MAX_RETRIES:
                # No enviamos notificaciones por errores de datos históricos
                if "get_ohlcv" not in str(func) and "datos históricos" not in str(e):
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

def cargar_ordenes_tp():
    """Carga las órdenes TP pendientes del archivo"""
    try:
        if os.path.exists(TP_ORDERS_FILE):
            with open(TP_ORDERS_FILE, "r") as f:
                return json.load(f)
        else:
            return {}
    except Exception as e:
        logging.error(f"Error cargando órdenes TP: {e}", exc_info=True)
        return {}

def guardar_ordenes_tp(data):
    """Guarda las órdenes TP pendientes al archivo"""
    try:
        with open(TP_ORDERS_FILE, "w") as f:
            json.dump(data, f)
    except Exception as e:
        logging.error(f"Error guardando órdenes TP: {e}", exc_info=True)

def ajustar_precision(valor, precision):
    return float(f"{valor:.{precision}f}") if precision > 0 else float(int(valor))

def obtener_posiciones_hyperliquid():
    """
    Obtiene las posiciones abiertas en Hyperliquid y las formatea para uso del bot.
    Implementación robusta que maneja la estructura específica de la API de Hyperliquid.
    """
    try:
        account = retry_api_call(client.get_account)
        
        # Verificar si tenemos la estructura esperada
        if not account or "assetPositions" not in account:
            print("No se encontró 'assetPositions' en la respuesta de la API")
            return []
        
        # Lista para almacenar posiciones formateadas
        posiciones_abiertas = []
        
        for item in account["assetPositions"]:
            try:
                # Si position está en las claves y es un diccionario, extraer de ahí
                if 'position' in item and isinstance(item['position'], dict):
                    p = item['position']
                else:
                    p = item
                
                # Extraer el símbolo/asset
                symbol = ""
                for key in ['coin', 'asset', 'symbol']:
                    if key in p:
                        symbol = p[key]
                        debug_print(f"Símbolo encontrado en '{key}': {symbol}")
                        break
                
                if not symbol:
                    debug_print("No se pudo encontrar símbolo para la posición")
                    continue
                
                # Extraer el tamaño de la posición
                position_float = None
                if 'szi' in p:
                    try:
                        position_float = float(p['szi'])
                        debug_print(f"[{symbol}] Valor de posición extraído de szi: {position_float}")
                    except (ValueError, TypeError) as e:
                        debug_print(f"[{symbol}] Error convirtiendo szi: {e}")
                
                # Solo procesar posiciones no-cero
                if position_float is None or abs(position_float) < 0.0001:
                    debug_print(f"[{symbol}] Posición nula o demasiado pequeña: {position_float}")
                    continue
                
                # Extraer precio de entrada
                entry_price_float = 0
                if 'entryPx' in p:
                    try:
                        entry_price_float = float(p['entryPx'])
                        debug_print(f"[{symbol}] Precio de entrada extraído de entryPx: {entry_price_float}")
                    except (ValueError, TypeError) as e:
                        debug_print(f"[{symbol}] Error convirtiendo entryPx: {e}")
                
                # Extraer PnL
                unrealized_pnl_float = 0
                if 'unrealizedPnl' in p:
                    try:
                        unrealized_pnl_float = float(p['unrealizedPnl'])
                        debug_print(f"[{symbol}] PnL extraído de unrealizedPnl: {unrealized_pnl_float}")
                    except (ValueError, TypeError) as e:
                        debug_print(f"[{symbol}] Error convirtiendo unrealizedPnl: {e}")
                
                # Crear una posición formateada
                posicion_formateada = {
                    'asset': symbol,
                    'position': position_float,
                    'entryPrice': entry_price_float,
                    'unrealizedPnl': unrealized_pnl_float
                }
                posiciones_abiertas.append(posicion_formateada)
                
            except Exception as e:
                debug_print(f"Error procesando posición: {e}")
                logging.error(f"Error procesando posición: {e}", exc_info=True)
                continue
        
        return posiciones_abiertas
    except Exception as e:
        logging.error(f"Error al obtener posiciones Hyperliquid: {e}", exc_info=True)
        enviar_telegram(f"⚠️ Error al obtener posiciones Hyperliquid: {e}", tipo="error")
        return []

def obtener_datos_historicos(symbol, interval='1m', limit=100):
    try:
        # No enviamos notificaciones por errores de datos históricos
        df = client.get_ohlcv(symbol, interval, limit)
        if df is None:
            # Solo registrar en el log, sin enviar a Telegram
            print(f"Error al obtener datos históricos para {symbol}")
            logging.error(f"Error al obtener datos históricos para {symbol}")
            return None
        if isinstance(df, list):
            df = pd.DataFrame(df)
            df.columns = ['timestamp','open','high','low','close','volume']
        return df
    except Exception as e:
        # Solo registrar en el log, sin enviar a Telegram
        print(f"Error al obtener datos históricos para {symbol}: {e}")
        logging.error(f"Error al obtener datos históricos para {symbol}: {e}", exc_info=True)
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
    """
    Calcula el precio de Take Profit basado en ATR con validación de dirección mejorada.
    """
    max_tp_move = entry_price * MAX_TP_PCT
    
    # Normalizar la dirección para asegurar que solo sea "BUY" o "SELL"
    direction_normalizada = direction.upper().strip()
    if "BUY" in direction_normalizada:
        direction_normalizada = "BUY"
    elif "SELL" in direction_normalizada:
        direction_normalizada = "SELL"
    else:
        # Si no podemos determinar la dirección, usar un valor seguro
        print(f"ERROR: Dirección no reconocida '{direction}'. Se usará 'SELL' por defecto.")
        direction_normalizada = "SELL"
    
    if direction_normalizada == "BUY":
        # Para operaciones LONG
        tp = entry_price + ATR_TP_MULT * atr
        # No permitir que exceda el porcentaje máximo
        tp = min(tp, entry_price * (1 + MAX_TP_PCT))
        # Asegurar ganancia mínima para cubrir comisiones
        tp = max(tp, entry_price * (1 + fee_rate * 3))
    else:
        # Para operaciones SHORT
        tp = entry_price - ATR_TP_MULT * atr
        # No permitir que exceda el porcentaje máximo (en SHORT es precio menor)
        tp = max(tp, entry_price * (1 - MAX_TP_PCT))
        # Asegurar ganancia mínima para cubrir comisiones (pero sin subir sobre el precio de entrada)
        tp = min(tp, entry_price * (1 - fee_rate * 3))
    
    # Validación final para detectar valores desorbitados
    pct_change = abs(tp - entry_price) / entry_price
    if pct_change > MAX_TP_PCT:
        print(f"ADVERTENCIA: TP calculado ({tp:.4f}) excede el límite máximo permitido ({MAX_TP_PCT*100}%)")
        # Corregir el TP para que respete el límite máximo
        if direction_normalizada == "BUY":
            tp = entry_price * (1 + MAX_TP_PCT)
        else:
            tp = entry_price * (1 - MAX_TP_PCT)
    
    return tp

def calcular_cantidad_valida(symbol, monto_usdt):
    """
    Calcula la cantidad válida para una orden en Hyperliquid asegurando
    que cumpla con los requisitos de precisión.
    """
    try:
        precio_actual = obtener_precio_hyperliquid(symbol)
        if precio_actual is None:
            return None
            
        # Obtener la precisión adecuada para este símbolo
        precision = PRECISION_POR_SIMBOLO.get(symbol, 0)
        
        # Calcular la cantidad base
        cantidad_calculada = monto_usdt / precio_actual
        
        # Para los tokens que requieren enteros (DOGE, ARB, etc.)
        if precision == 0:
            cantidad_redondeada = int(cantidad_calculada)
            # Asegurarnos de que la cantidad no sea cero
            if cantidad_redondeada == 0:
                cantidad_redondeada = 1
        else:
            # Para tokens que permiten decimales, redondeamos a la precisión adecuada
            cantidad_redondeada = round(cantidad_calculada, precision)
            # Asegurarnos de que la cantidad no sea cero
            if cantidad_redondeada == 0:
                cantidad_redondeada = 10**(-precision)
        
        # Convertir a float para asegurar compatibilidad con la API
        cantidad_redondeada = float(cantidad_redondeada)
        
        debug_print(f"[{symbol}] Cantidad calculada: {cantidad_calculada}, ajustada a precisión {precision}: {cantidad_redondeada}")
        return cantidad_redondeada
        
    except Exception as e:
        logging.error(f"Error al calcular cantidad válida para {symbol}: {e}", exc_info=True)
        return None

def tiene_saldo_suficiente(margen):
    try:
        account = retry_api_call(client.get_account)
        if not account:
            return False
        
        # Intentar obtener el saldo desde diferentes rutas posibles en la respuesta
        usdt_balance = None
        if "equity" in account:
            usdt_balance = float(account["equity"])
        elif "marginSummary" in account and "accountValue" in account["marginSummary"]:
            usdt_balance = float(account["marginSummary"]["accountValue"])
        
        if usdt_balance is None:
            print("No se pudo extraer el saldo de la cuenta")
            return False
            
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

def crear_orden_tp_hyperliquid(symbol, side, quantity, price):
    """
    Crea una orden límite para Take Profit en Hyperliquid
    
    Args:
        symbol (str): Símbolo del par de trading
        side (str): Dirección de la orden ('buy' o 'sell')
        quantity (float): Cantidad a operar
        price (float): Precio límite para la orden TP
    
    Returns:
        dict: Respuesta de la API o None si hay error
    """
    try:
        # La API de Hyperliquid utiliza create_order con type='limit' para órdenes límite
        precision = PRECISION_POR_SIMBOLO.get(symbol, 0)
        price_rounded = round(price, precision + 2)  # Más precisión para el precio
        
        # Para debugging
        print(f"[{symbol}] Creando orden TP: {side} {quantity} @ {price_rounded}")
        
        orden = retry_api_call(
            client.create_order,
            symbol=symbol,
            side=side.lower(),
            size=quantity,
            type='limit',
            price=price_rounded
        )
        
        if orden and "status" in orden:
            print(f"[{symbol}] Orden TP creada: {orden}")
            return orden
        else:
            print(f"[{symbol}] Error al crear orden TP")
            logging.error(f"Error al crear orden TP para {symbol}: {orden}")
            return None
    except Exception as e:
        print(f"[{symbol}] Error al crear orden TP: {e}")
        logging.error(f"Error al crear orden TP para {symbol}: {e}", exc_info=True)
        return None

def ejecutar_orden_hyperliquid(symbol, side, quantity, tp_price=None):
    """
    Ejecuta una orden de mercado y opcionalmente establece un TP
    
    Args:
        symbol (str): Símbolo del par de trading
        side (str): Dirección de la orden ('buy' o 'sell')
        quantity (float): Cantidad a operar
        tp_price (float, optional): Precio para el Take Profit
    
    Returns:
        dict: Orden principal ejecutada
        dict: Orden TP si se estableció
    """
    try:
        # Ejecutar la orden principal (market)
        orden_principal = retry_api_call(
            client.create_order, 
            symbol=symbol, 
            side=side.lower(), 
            size=quantity,
            type='market'  # Asegurarnos que sea orden de mercado
        )
        
        if not orden_principal or "status" not in orden_principal:
            enviar_telegram(f"⚠️ Error al ejecutar orden para {symbol}", tipo="error")
            return None, None
            
        print(f"[{symbol}] Orden principal ejecutada: {orden_principal}")
        
        # Si se especifica precio TP, crear una orden límite para el TP
        orden_tp = None
        if tp_price is not None:
            # El lado del TP es opuesto a la entrada
            tp_side = "sell" if side.lower() == "buy" else "buy"
            
            # Crear la orden TP
            orden_tp = crear_orden_tp_hyperliquid(symbol, tp_side, quantity, tp_price)
            
            # Guardar el ID de la orden TP para seguimiento
            if orden_tp:
                # Guardar referencia de la orden TP
                try:
                    tp_orders = cargar_ordenes_tp()
                    
                    # Guardar relación entre símbolo y orden TP
                    tp_orders[symbol] = {
                        "order_id": orden_tp.get("order_id", ""),
                        "price": tp_price,
                        "size": quantity,
                        "side": tp_side,
                        "created_at": datetime.now().isoformat()
                    }
                    
                    guardar_ordenes_tp(tp_orders)
                    print(f"[{symbol}] Orden TP guardada en archivo de seguimiento")
                except Exception as e:
                    print(f"[{symbol}] Error guardando referencia de orden TP: {e}")
            
        return orden_principal, orden_tp
    except Exception as e:
        logging.error(f"Error al ejecutar orden con TP para {symbol}: {e}", exc_info=True)
        enviar_telegram(f"⚠️ Error al ejecutar orden con TP para {symbol}: {e}", tipo="error")
        return None, None

def verificar_ordenes_tp_pendientes():
    """
    Verifica si hay órdenes TP pendientes y las sincroniza con las posiciones actuales
    """
    try:
        # Cargar órdenes TP pendientes
        tp_orders = cargar_ordenes_tp()
        
        if not tp_orders:
            return
            
        # Obtener posiciones actuales
        posiciones = obtener_posiciones_hyperliquid()
        simbolos_con_posicion = [pos['asset'] for pos in posiciones]
        
        # Verificar órdenes pendientes
        ordenes_activas = []
        for symbol, order_info in tp_orders.items():
            # Si ya no hay posición para este símbolo, cancelar la orden TP
            if symbol not in simbolos_con_posicion:
                try:
                    if "order_id" in order_info:
                        client.cancel_order(symbol=symbol, order_id=order_info["order_id"])
                        print(f"[{symbol}] Orden TP cancelada - Posición cerrada")
                except Exception as e:
                    print(f"[{symbol}] Error cancelando orden TP: {e}")
            else:
                ordenes_activas.append(symbol)
        
        # Actualizar el archivo de órdenes TP
        tp_orders_actualizadas = {symbol: info for symbol, info in tp_orders.items() 
                                 if symbol in ordenes_activas}
        
        if len(tp_orders) != len(tp_orders_actualizadas):
            guardar_ordenes_tp(tp_orders_actualizadas)
            
    except Exception as e:
        print(f"Error verificando órdenes TP pendientes: {e}")
        logging.error(f"Error verificando órdenes TP pendientes: {e}", exc_info=True)

def cerrar_posicion(symbol, positionAmt):
    """
    Cierra una posición y cancela cualquier orden TP pendiente
    """
    try:
        # Primero cancelar órdenes TP pendientes
        tp_orders = cargar_ordenes_tp()
        
        if symbol in tp_orders and "order_id" in tp_orders[symbol]:
            try:
                client.cancel_order(symbol=symbol, order_id=tp_orders[symbol]["order_id"])
                print(f"[{symbol}] Orden TP cancelada antes de cerrar posición")
                del tp_orders[symbol]
                guardar_ordenes_tp(tp_orders)
            except Exception as e:
                print(f"[{symbol}] Error cancelando orden TP: {e}")
        
        # Ahora cerrar la posición con una orden de mercado
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
    """
    Evalúa si una posición debe cerrarse manualmente (como respaldo si el TP del exchange falla)
    """
    try:
        entryPrice = float(pos['entryPrice'])
        positionAmt = float(pos['position'])
        qty = abs(positionAmt)
        symbol = pos['asset']
        direccion = "BUY" if positionAmt > 0 else "SELL"

        # Verificar si hay un TP establecido en el archivo
        niveles = niveles_atr.get(symbol)
        if niveles and "tp_fijo" in niveles:
            tp = niveles["tp_fijo"]
        else:
            # Si no hay TP guardado, no hay criterio para cerrar manualmente
            return False

        # Verificar si el precio ha alcanzado el TP y cerrar manualmente (respaldo)
        if (direccion == "BUY" and precio_actual >= tp) or (direccion == "SELL" and precio_actual <= tp):
            print(f"[{symbol}] Cerrando como respaldo (TP en exchange no ejecutado). Entry: {entryPrice}, Actual: {precio_actual}, TP: {tp}")
            order = cerrar_posicion(symbol, positionAmt)
            
            if order:
                time.sleep(2)
                pnl_estimado = ((precio_actual - entryPrice) * positionAmt) if direccion == "BUY" else ((entryPrice - precio_actual) * abs(positionAmt))
                icono_cerrado = "🟢" if pnl_estimado >= 0 else "🔴"
                pnl_texto = f"PnL estimado: {pnl_estimado:.4f}"
                enviar_telegram(
                    f"{icono_cerrado} Trade CERRADO (respaldo): {symbol} {direccion}\n"
                    f"Entry: {entryPrice:.4f}\n"
                    f"Close: {precio_actual:.4f}\n"
                    f"TP: {tp:.4f}\n"
                    f"{pnl_texto}",
                    tipo="close"
                )
                resumen_diario["trades_cerrados"] += 1
                resumen_diario["pnl_total"] += pnl_estimado
                
                # Eliminar el TP del archivo
                if symbol in niveles_atr:
                    del niveles_atr[symbol]
                    guardar_niveles_atr(niveles_atr)
                
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
            debug_print(f"[{symbol}] No se encontró la clave 'mid' en el ticker: {ticker}")
            logging.error(f"No se encontró la clave 'mid' en el ticker de {symbol}: {ticker}")
            return None
    except Exception as e:
        logging.error(f"Error al obtener precio para {symbol}: {e}", exc_info=True)
        return None

def abrir_posicion_con_tp(simbolo, accion, entry_price, atr):
    """Abre una posición con Take Profit automático en el exchange"""
    if tiene_saldo_suficiente(MARGIN_PER_TRADE):
        monto_usdt = LEVERAGE * MARGIN_PER_TRADE
        cantidad_valida = calcular_cantidad_valida(simbolo, monto_usdt)
        
        if cantidad_valida:
            # Calcular precio de TP según ATR
            tp = calcular_tp_atr(entry_price, atr, accion)
            
            # Ejecutar la orden con TP incluido
            orden_principal, orden_tp = ejecutar_orden_hyperliquid(simbolo, accion, cantidad_valida, tp)
            
            if orden_principal:
                print(f"[{simbolo}] Trade ejecutado ({accion}) | ATR: {atr:.4f} | TP: {tp:.4f}")
                
                # Guardar niveles solo como respaldo
                niveles_atr = cargar_niveles_atr()
                niveles_atr[simbolo] = {"tp_fijo": tp}
                guardar_niveles_atr(niveles_atr)
                
                # Enviar notificación
                icono_abierto = "🔵"
                tp_msg = f"TP FIJO: {tp:.4f}" if orden_tp else f"TP calculado: {tp:.4f}"
                enviar_telegram(
                    f"{icono_abierto} Trade ABIERTO: {simbolo} {accion}\n"
                    f"Precio: {entry_price:.4f}\n"
                    f"{tp_msg}\n"
                    f"ATR: {atr:.4f}\n"
                    f"Leverage: {LEVERAGE}x | Margen: {MARGIN_PER_TRADE} USDT",
                    tipo="open"
                )
                
                return True
            else:
                print(f"Error al ejecutar orden para {simbolo}")
                return False
        else:
            print(f"No se pudo calcular una cantidad válida para {simbolo}")
            return False
    else:
        print("No hay saldo suficiente para operar.")
        return False

if __name__ == "__main__":
    try:
        # Primero verificamos los símbolos disponibles
        simbolos = obtener_simbolos_disponibles()
        
        if not simbolos:
            enviar_telegram("⚠️ No se encontraron símbolos disponibles para operar. El bot se detendrá.", tipo="error")
            exit(1)
        
        # Ahora enviamos un solo mensaje de inicio con toda la información
        enviar_telegram(f"🚀 Bot arrancado correctamente y en ejecución.\n\n🔍 Símbolos disponibles para operar ({len(simbolos)}/{20}): {', '.join(simbolos)}", tipo="info")
            
        intervalo_segundos = 5
        tiempo_inicio = datetime.now()
        last_trade_time = None
        ultima_reevaluacion = datetime.now()

        print("Iniciando bot de scalping microestructura v2 con TP en exchange (Hyperliquid Testnet)...")
        print(f"Configuración: Apalancamiento={LEVERAGE}x | Margen por operación={MARGIN_PER_TRADE} USDT")
        print(f"TP: {ATR_TP_MULT}xATR (máx {MAX_TP_PCT*100:.1f}% sobre entrada) | SL: NO")

        while True:
            print(f"\nTiempo Transcurrido: {datetime.now() - tiempo_inicio}")
            
            # Añadir esta sección para obtener y registrar el saldo
            try:
                account = retry_api_call(client.get_account)
                if account:
                    # Intentar obtener el saldo desde diferentes rutas posibles en la respuesta
                    saldo_usdt = None
                    if "equity" in account:
                        saldo_usdt = float(account["equity"])
                    elif "marginSummary" in account and "accountValue" in account["marginSummary"]:
                        saldo_usdt = float(account["marginSummary"]["accountValue"])
                    
                    if saldo_usdt is not None:
                        print(f"[SALDO] Saldo actual: {saldo_usdt:.4f} USDT")
                        # Registra en archivo para que el panel lo pueda leer
                        with open("ultimo_saldo.txt", "w") as f:
                            f.write(f"{saldo_usdt}")
                    else:
                        print("❌ No se pudo extraer el saldo.")
            except Exception as e:
                print(f"❌ Error obteniendo saldo: {e}")
            
            # Verificar órdenes TP pendientes
            verificar_ordenes_tp_pendientes()
            
            # Reevaluar los símbolos disponibles periódicamente (pero sin enviar mensajes)
            if verificar_tiempo_para_reevaluar():
                print("Reevaluando símbolos disponibles...")
                simbolos_actualizados = obtener_simbolos_disponibles()
                if simbolos_actualizados:
                    simbolos = simbolos_actualizados
                    print(f"Lista de símbolos actualizada: {simbolos}")

            posiciones = obtener_posiciones_hyperliquid()
            niveles_atr = cargar_niveles_atr()

            # Imprimir símbolos con posiciones abiertas para depuración
            simbolos_abiertos = [pos.get('asset', '').upper() for pos in posiciones]
            print(f"Símbolos con posiciones abiertas: {simbolos_abiertos}")

            print(f"Posiciones abiertas en Hyperliquid ({len(posiciones)}):")
            for pos in posiciones:
                symbol = pos['asset']
                positionAmt = pos['position']
                entryPrice = pos['entryPrice']
                pnl = pos.get('unrealizedPnl', 0)
                print(f"  {symbol} | Cantidad: {positionAmt} | Precio Entrada: {entryPrice} | PnL No Realizado: {pnl}")

            # --- Evaluación de cierre (respaldo local por si falla el TP del exchange) ---
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
                # Usar la nueva función para verificar posiciones existentes
                ya_abierta = verificar_posicion_existente(simbolo, posiciones)
                if ya_abierta:
                    print(f"Ya existe una posición abierta para {simbolo}. Se omite.")
                    continue
                
                if apertura_realizada:
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
                    if abrir_posicion_con_tp(simbolo, accion, entry_price, atr):
                        resumen_diario["trades_abiertos"] += 1
                        apertura_realizada = True
                        last_trade_time = datetime.now()
                        break
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
