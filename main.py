import time
import pandas as pd
import numpy as np
import math
import json
import os
import logging
from datetime import datetime, timedelta

from config import (
    TIMEOUT_MINUTES, LEVERAGE, MARGIN_PER_TRADE, ATR_TP_MULT, MAX_TP_PCT,
    # Nuevos parámetros para DCA
    DCA_ENABLED, DCA_MAX_LOSS_PCT, DCA_MAX_ENTRIES, DCA_SIZE_MULTIPLIER, 
    DCA_MIN_TIME_BETWEEN, DCA_MAX_TOTAL_SIZE_MULT
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

# Nueva función para crear cliente con reintentos
def crear_cliente_con_reintentos(tiempo_espera=10):
    intentos = 0
    
    print("Iniciando conexión con Hyperliquid...")
    
    while True:  # Bucle infinito para reintentar siempre
        try:
            # Crear el cliente Hyperliquid
            cliente = HyperliquidClient()
            
            # Verificar que funciona con una llamada simple
            # Usamos get_price("BTC") en lugar de get_meta()
            info = cliente.get_price("BTC")
            print(f"Conexión con Hyperliquid establecida correctamente después de {intentos} intentos.")
            
            # Si llegamos aquí, el cliente se creó correctamente
            return cliente
        
        except Exception as e:
            intentos += 1
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            print(f"[{timestamp}] Error al conectar con Hyperliquid (intento {intentos}): {e}")
            print(f"Esperando {tiempo_espera} segundos antes de reintentar...")
            time.sleep(tiempo_espera)
            
            # Mostrar un mensaje cada 6 intentos (cada minuto con espera de 10 seg)
            if intentos % 6 == 0:
                print(f"[{timestamp}] Continuando intentos de conexión con Hyperliquid... ({intentos} intentos hasta ahora)")

client = crear_cliente_con_reintentos(tiempo_espera=10)  # Reintenta cada 10 segundos indefinidamente

ATR_SL_MULT = 1.0
# MIN_POTENTIAL_PROFIT eliminado

SPREAD_MAX_PCT_POR_SIMBOLO = {
    "BTC": 1.0, "ETH": 1.0, "BNB": 1.0, "SOL": 1.5, "XRP": 2.0, "ADA": 1.5,
    "AVAX": 1.5, "LINK": 1.5, "MATIC": 1.5
}
MULTIPLICADOR_VOL_POR_SIMBOLO = {
    "BTC": 1.5, "ETH": 1.5, "BNB": 1.5, "SOL": 1.2, "XRP": 1.2,
    "ADA": 1.2, "AVAX": 1.2, "LINK": 1.2, "MATIC": 1.2
}
BREAKOUT_ATR_MULT_POR_SIMBOLO = {
    "BTC": 0.15, "ETH": 0.15, "BNB": 0.15, "SOL": 0.1, "XRP": 0.1,
    "ADA": 0.1, "AVAX": 0.1, "LINK": 0.1, "MATIC": 0.1
}

# Definir la precisión para cada símbolo según las reglas de Hyperliquid
PRECISION_POR_SIMBOLO = {
    "BTC": 3,  # 0.001 BTC
    "ETH": 2,  # 0.01 ETH
    "BNB": 2,  # 0.01 BNB
    "SOL": 1,  # 0.1 SOL
    "XRP": 0,  # 1 XRP
    "ADA": 0,  # 1 ADA
    "AVAX": 1, # 0.1 AVAX
    "LINK": 1, # 0.1 LINK
    "MATIC": 0 # 1 MATIC
}

ATR_LEVELS_FILE = "trade_levels_atr.json"
TP_ORDERS_FILE = "tp_orders.json"
PNL_HISTORY_FILE = "pnl_history.csv"  # Cambiado a CSV para mejor compatibilidad con pandas
COOLDOWN_MINUTES = 5  # Reducido de 15 a 5 minutos
SPREAD_MAX_PCT = 1
MAX_RETRIES = 3
RETRY_SLEEP = 5  # Aumentado de 2 a 5 segundos
VOLATILITY_WINDOW = 10
VOLATILITY_UMBRAL = 0.015
REEVALUACION_SIMBOLOS_HORAS = 1  # Reducido de 6 horas a 1 hora
DEBUG = False  # Controla el verbose
VERIFICACION_CIERRE_INTENTOS = 3  # Número de intentos para verificar cierre
VERIFICACION_CIERRE_ESPERA = 3  # Segundos entre verificaciones

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

def evaluar_dca(posiciones):
    """Evalúa posiciones en negativo para aplicar estrategia DCA"""
    if not DCA_ENABLED:
        return
        
    niveles_atr = cargar_niveles_atr()
    tp_orders = cargar_ordenes_tp()
    
    for pos in posiciones:
        try:
            symbol = pos['asset']
            position_float = float(pos['position'])
            direccion = "BUY" if position_float > 0 else "SELL"
            entry_price = float(pos['entryPrice'])
            pnl = float(pos.get('unrealizedPnl', 0))
            
            # Obtener información de la posición
            precio_actual = obtener_precio_hyperliquid(symbol)
            if precio_actual is None:
                continue
                
            # Verificar si ya tiene entradas DCA
            dca_info = niveles_atr.get(symbol, {}).get("dca_info", {})
            num_dca = dca_info.get("num_entradas", 0)
            
            # Si ya alcanzó el máximo de entradas DCA, saltar
            if num_dca >= DCA_MAX_ENTRIES:
                continue
                
            # Verificar tiempo desde la última entrada DCA
            ultima_dca = dca_info.get("ultima_entrada")
            if ultima_dca:
                tiempo_desde_ultima = datetime.now() - datetime.fromisoformat(ultima_dca)
                if tiempo_desde_ultima.total_seconds() < DCA_MIN_TIME_BETWEEN * 60:
                    # No ha pasado suficiente tiempo entre entradas DCA
                    continue
            
            # Calcular pérdida porcentual
            if direccion == "BUY":  # LONG
                loss_pct = (precio_actual - entry_price) / entry_price
            else:  # SHORT
                loss_pct = (entry_price - precio_actual) / entry_price
                
            # NUEVO: Calcular umbral de pérdida progresivo
            # Aumenta en 5% adicional por cada DCA ya realizado
            umbral_loss_pct = DCA_MAX_LOSS_PCT + (num_dca * 0.05)
            
            # Imprimir diagnóstico
            print(f"[{symbol}] Evaluando DCA: Pérdida {loss_pct*100:.2f}%, Umbral actual: {umbral_loss_pct*100:.2f}%")
                
            # Verificar si cumple condiciones para DCA con umbral progresivo
            if loss_pct <= -umbral_loss_pct:
                print(f"[{symbol}] ¡Condición DCA activada! Pérdida {loss_pct*100:.2f}% excede umbral {umbral_loss_pct*100:.2f}%")
                ejecutar_dca(symbol, direccion, pos, precio_actual, niveles_atr)
        
        except Exception as e:
            print(f"Error evaluando DCA para {pos.get('asset', 'desconocido')}: {e}")
            logging.error(f"Error evaluando DCA: {e}", exc_info=True)

def ejecutar_dca(symbol, direccion, pos, precio_actual, niveles_atr):
    """Ejecuta una entrada DCA y recalcula el TP"""
    try:
        # Obtener datos de la posición actual
        position_size = abs(float(pos['position']))
        entry_price = float(pos['entryPrice'])
        
        # Calcular tamaño para la entrada DCA - Mismo tamaño que la original
        dca_size = position_size * DCA_SIZE_MULTIPLIER
        
        # Verificar tamaño total acumulado
        dca_info = niveles_atr.get(symbol, {}).get("dca_info", {})
        total_actual = position_size
        if "total_size" in dca_info:
            total_actual = dca_info["total_size"]
        
        # El límite es tan alto que nunca se alcanzará en la práctica
        if (total_actual + dca_size) > (position_size * DCA_MAX_TOTAL_SIZE_MULT):
            print(f"[{symbol}] Advertencia: Se alcanzó límite de tamaño máximo")
            # Pero no limitamos el tamaño, seguimos con el valor original
        
        # Obtener ATR actual para recalcular TP
        datos = obtener_datos_historicos(symbol)
        if datos is None:
            print(f"[{symbol}] No se pudo obtener datos para recalcular ATR")
            return False
            
        # Calcular ATR
        atr = calcular_atr(datos).iloc[-1]
        
        # Ejecutar orden DCA
        side = "buy" if direccion == "BUY" else "sell"
        orden = client.create_order(
            symbol=symbol,
            side=side,
            size=dca_size,
            leverage=LEVERAGE
        )
        
        if not orden:
            print(f"[{symbol}] Error ejecutando DCA")
            return False
            
        # Recalcular precio promedio y nuevo TP
        precio_promedio_anterior = dca_info.get("precio_promedio", entry_price)
        total_size = total_actual + dca_size
        
        # Cálculo ponderado del nuevo precio promedio
        if "total_size" in dca_info:
            # Si ya tenemos un precio promedio anterior
            precio_promedio = ((precio_promedio_anterior * total_actual) + (precio_actual * dca_size)) / total_size
        else:
            # Primera entrada DCA
            precio_promedio = ((entry_price * position_size) + (precio_actual * dca_size)) / total_size
        
        # Calcular nuevo TP
        nuevo_tp = calcular_tp_atr(precio_promedio, atr, direccion)
        
        # Actualizar información DCA
        num_dca = dca_info.get("num_entradas", 0) + 1
        
        niveles_atr[symbol] = {
            "tp_fijo": nuevo_tp,
            "dca_info": {
                "num_entradas": num_dca,
                "ultima_entrada": datetime.now().isoformat(),
                "precio_promedio": precio_promedio,
                "total_size": total_size,
                "entradas": dca_info.get("entradas", []) + [
                    {"precio": precio_actual, "tamano": dca_size, "fecha": datetime.now().isoformat()}
                ]
            }
        }
        guardar_niveles_atr(niveles_atr)
        
        # Cancelar orden TP antigua si existe
        tp_orders = cargar_ordenes_tp()
        if symbol in tp_orders and "order_id" in tp_orders[symbol] and tp_orders[symbol]["order_id"]:
            try:
                client.cancel_order(symbol=symbol, order_id=tp_orders[symbol]["order_id"])
                print(f"[{symbol}] Orden TP anterior cancelada")
            except Exception as e:
                print(f"[{symbol}] Error cancelando orden TP antigua: {e}")
        
        # Crear nueva orden TP
        tp_side = "sell" if direccion == "BUY" else "buy"
        tp_orden = crear_orden_tp_hyperliquid(symbol, tp_side, total_size, nuevo_tp)
        
        # Actualizar registro de órdenes TP
        if tp_orden:
            if symbol in tp_orders:
                tiempo_apertura = tp_orders[symbol].get("tiempo_apertura", datetime.now().isoformat())
            else:
                tiempo_apertura = datetime.now().isoformat()
                
            tp_orders[symbol] = {
                "order_id": tp_orden.get("order_id", ""),
                "price": nuevo_tp,
                "size": total_size,
                "side": tp_side,
                "created_at": datetime.now().isoformat(),
                "tiempo_apertura": tiempo_apertura
            }
            guardar_ordenes_tp(tp_orders)
        
        # Registrar en historial
        try:
            # Asegurarse de que el archivo existe y tiene encabezados
            if not os.path.exists("dca_history.csv"):
                with open("dca_history.csv", "w") as f:
                    f.write("timestamp,symbol,direccion,entry_original,precio_dca,tamano_dca,precio_promedio,nuevo_tp,num_dca\n")
                    
            # Añadir la nueva entrada DCA
            with open("dca_history.csv", "a") as f:
                f.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')},{symbol},{direccion},{entry_price},{precio_actual},{dca_size},{precio_promedio},{nuevo_tp},{num_dca}\n")
        except Exception as e:
            print(f"Error guardando historial DCA: {e}")
        
        # Notificar
        mejora_porcentual = abs((precio_promedio - entry_price) / entry_price) * 100
        
        enviar_telegram(
            f"🔄 DCA #{num_dca} aplicado en {symbol} {direccion}\n"
            f"Entrada original: {position_size} @ {entry_price:.4f}\n"
            f"Entrada DCA: {dca_size} @ {precio_actual:.4f}\n"
            f"Nuevo precio promedio: {precio_promedio:.4f} (mejora {mejora_porcentual:.2f}%)\n"
            f"Nuevo TP: {nuevo_tp:.4f}",
            tipo="dca"
        )
        
        return True
        
    except Exception as e:
        print(f"[{symbol}] Error ejecutando DCA: {e}")
        logging.error(f"Error ejecutando DCA para {symbol}: {e}", exc_info=True)
        return False

def obtener_simbolos_disponibles():
    """Obtiene la lista de símbolos disponibles en Hyperliquid ordenados por capitalización"""
    # Lista ampliada de los 20 pares con mayor capitalización en Hyperliquid
    todos_simbolos = [
        'BTC', 'ETH', 'SOL', 'BNB', 'XRP', 'ADA', 'AVAX', 'LINK', 'MATIC'
    ]
    
    print("Verificando disponibilidad de símbolos en Hyperliquid...")
    
    simbolos_disponibles = []
    simbolos_solo_precio = []  # Nueva lista para símbolos con precio pero sin datos históricos
    
    for symbol in todos_simbolos:
        try:
            # Intenta obtener precio actual para verificar disponibilidad
            precio = client.get_price(symbol)
            if precio and precio.get('mid'):
                # Verificar además que podemos obtener datos históricos
                df = client.get_ohlcv(symbol, '1m', 10)  # Solo probamos con 10 velas
                if df is not None and len(df) > 0:
                    simbolos_disponibles.append(symbol)
                    print(f"✅ {symbol} disponible completo - Precio: {precio.get('mid')}")
                else:
                    # Ya no añadiremos estos símbolos a la lista principal
                    simbolos_solo_precio.append(symbol)
                    print(f"⚠️ {symbol} tiene precio ({precio.get('mid')}) pero no datos históricos - NO SE USARÁ")
            else:
                print(f"❌ {symbol} no disponible o sin liquidez")
        except Exception as e:
            print(f"❌ Error verificando {symbol}: {str(e)}")
    
    # Ya no agregamos los símbolos que solo tienen precio
    print(f"Total de símbolos disponibles con datos históricos completos: {len(simbolos_disponibles)}")
    if simbolos_solo_precio:
        print(f"Símbolos descartados (solo tienen precio): {', '.join(simbolos_solo_precio)}")
    
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

# Función nueva para guardar historial de PnL real
def guardar_historial_pnl(symbol, direccion, entry_price, exit_price, tp_price, pnl_real, 
                         tiempo_abierto=None, razon_cierre="normal"):
    """Guarda el historial de PnL para análisis posterior en formato CSV"""
    try:
        # Asegurarse de que el archivo existe con encabezados
        if not os.path.exists(PNL_HISTORY_FILE):
            with open(PNL_HISTORY_FILE, "w") as f:
                f.write("timestamp,symbol,direccion,precio_entrada,precio_salida,tp,pnl_real,tiempo_abierto,razon_cierre\n")
        
        # Tiempo actual
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Si no se proporciona tiempo abierto, será N/A
        tiempo_abierto = tiempo_abierto if tiempo_abierto else "N/A"
        
        # Guardar en CSV (asegurarse de que haya un salto de línea al final)
        with open(PNL_HISTORY_FILE, "a") as f:
            f.write(f"{timestamp},{symbol},{direccion},{entry_price},{exit_price},{tp_price or 0},{pnl_real},{tiempo_abierto},{razon_cierre}\n")  # Asegúrate de que termina con \n
        
        print(f"[HISTORIAL] Trade {symbol} {direccion} guardado. PnL: {pnl_real}")
            
    except Exception as e:
        print(f"Error al guardar historial de PnL: {e}")
        logging.error(f"Error al guardar historial de PnL: {e}", exc_info=True)

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
        # Importamos pandas aquí para asegurar que está disponible
        import pandas as pd
        
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
    # Si no tenemos datos históricos, no podemos aplicar la estrategia
    if df is None or len(df) < 30:  # Necesitamos al menos 30 velas para los cálculos (EMA30)
        return None, "No hay suficientes datos históricos para este símbolo", None, None
        
    # Aquí comienza el código original de la estrategia de microestructura
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
        razon = f"ATR actual ({atr_actual:.6f}) < 0.5*ATR20 media ({0.5*atr_media_actual:.6f})."
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
        # Eliminado completamente el código de potential profit
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
        # La API de Hyperliquid necesita ser llamada de manera diferente para órdenes límite
        precision = PRECISION_POR_SIMBOLO.get(symbol, 0)
        price_rounded = round(price, precision + 2)  # Más precisión para el precio
        
        # Para debugging
        print(f"[{symbol}] Creando orden TP: {side} {quantity} @ {price_rounded}")
        
        # Implementamos la lógica para crear una orden límite usando la API disponible
        is_buy = side.lower() == "buy"
        
        # Intento 1: Usar create_order pero sin el parámetro 'type'
        try:
            orden = client.create_order(
                symbol=symbol,
                side=side,
                size=quantity,
                price=price_rounded
                # Eliminado el parámetro 'type="limit"'
            )
            
            if orden and "status" in orden:
                print(f"[{symbol}] Orden TP creada exitosamente: {orden}")
                return orden
            else:
                print(f"[{symbol}] Error al crear orden TP: respuesta sin status")
                logging.error(f"Error al crear orden TP para {symbol}: {orden}")
                
        except Exception as e:
            print(f"[{symbol}] Error al crear orden TP con método principal: {e}")
        
        # Intento 2: Usar exchange.limit_open si está disponible
        try:
            orden = client.exchange.limit_open(symbol, is_buy, quantity, price_rounded)
            if orden and "status" in orden:
                print(f"[{symbol}] Orden TP creada exitosamente (método alternativo): {orden}")
                return orden
        except Exception as e2:
            print(f"[{symbol}] Error en método alternativo de TP: {e2}")
            
        # Si llegamos aquí, es que fallaron todas las opciones anteriores
        # Creamos un TP en modo manual (solo para seguimiento)
        print(f"[{symbol}] Usando modo de TP manual como fallback")
        return {"status": "manual_tp", "tp_price": price_rounded}
    except Exception as e:
        print(f"[{symbol}] Error general al crear orden TP: {e}")
        logging.error(f"Error general al crear orden TP para {symbol}: {e}", exc_info=True)
        return {"status": "manual_tp", "tp_price": price}

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
        # Ejecutar la orden principal (market) - MODIFICACIÓN para aplicar apalancamiento
        try:
            # Aplicar explícitamente el apalancamiento configurado
            orden_principal = client.create_order(
                symbol=symbol,
                side=side,
                size=quantity,
                leverage=LEVERAGE  # Añadimos el parámetro leverage explícitamente
            )
        except TypeError as e:
            # Si falla, intentar con un método alternativo
            print(f"[{symbol}] Error con create_order estándar: {e}")
            try:
                # Intentar usando exchange.market_open si está disponible y aplicar apalancamiento
                is_buy = side.lower() == "buy"
                # Intentamos configurar el leverage primero si la API lo permite
                try:
                    client.set_leverage(symbol=symbol, leverage=LEVERAGE)
                except Exception as e_lev:
                    print(f"[{symbol}] Error configurando leverage: {e_lev}")
                
                orden_principal = client.exchange.market_open(symbol, is_buy, quantity)
            except Exception as e2:
                print(f"[{symbol}] Error con método alternativo: {e2}")
                enviar_telegram(f"⚠️ Error al ejecutar orden para {symbol}: {e2}", tipo="error")
                return None, None
        
        if not orden_principal or "status" not in orden_principal:
            enviar_telegram(f"⚠️ Error al ejecutar orden para {symbol}", tipo="error")
            return None, None
            
        print(f"[{symbol}] Orden principal ejecutada: {orden_principal}")
        
        # Registrar tiempo de apertura del trade
        tiempo_apertura = datetime.now()
        
        # Si se especifica precio TP, crear una orden límite para el TP
        orden_tp = None
        if tp_price is not None:
            # Esperar un breve momento para asegurar que la orden principal se procesó
            time.sleep(0.5)
            
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
                        "created_at": datetime.now().isoformat(),
                        "tiempo_apertura": tiempo_apertura.isoformat()  # Guardar tiempo de apertura
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
                    if "order_id" in order_info and order_info["order_id"]:
                        # Solo intentar cancelar si hay un ID de orden
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

def verificar_posicion_cerrada(symbol):
    """
    Verifica si una posición específica ha sido cerrada
    """
    try:
        # Obtener todas las posiciones actuales
        posiciones = obtener_posiciones_hyperliquid()
        
        # Verificar si el símbolo aparece en alguna posición
        for pos in posiciones:
            if pos.get('asset', '').upper() == symbol.upper():
                position_size = float(pos.get('position', 0))
                if abs(position_size) > 0.0001:  # Si hay tamaño significativo
                    return False
        
        # Si llegamos aquí, no se encontró el símbolo en ninguna posición con tamaño significativo
        return True
    except Exception as e:
        print(f"Error verificando si la posición está cerrada para {symbol}: {e}")
        logging.error(f"Error verificando si la posición está cerrada para {symbol}: {e}", exc_info=True)
        # En caso de error, asumimos que no podemos confirmar que esté cerrada
        return False

def obtener_posicion_actual(symbol):
    """
    Obtiene el tamaño actual de una posición específica
    """
    try:
        posiciones = obtener_posiciones_hyperliquid()
        for pos in posiciones:
            if pos.get('asset', '').upper() == symbol.upper():
                return float(pos.get('position', 0))
        return 0.0  # Si no se encuentra, devolver cero
    except Exception as e:
        print(f"Error obteniendo posición actual para {symbol}: {e}")
        return None

def cerrar_posicion(symbol, positionAmt):
    """
    Cierra una posición usando parámetros compatibles con la API de Hyperliquid
    Con verificación mejorada y manejo de errores
    """
    try:
        pnl_real = None
        tiempo_abierto = "N/A"
        tiempo_apertura = None

        try:
            # Verificar si tenemos información de tiempo de apertura en las órdenes TP
            tp_orders = cargar_ordenes_tp()
            if symbol in tp_orders and "tiempo_apertura" in tp_orders[symbol]:
                try:
                    tiempo_apertura = datetime.fromisoformat(tp_orders[symbol]["tiempo_apertura"])
                    tiempo_abierto = str(datetime.now() - tiempo_apertura).split('.')[0]  # Formato HH:MM:SS
                    print(f"[{symbol}] Tiempo abierto calculado: {tiempo_abierto}")
                except Exception as e:
                    print(f"[{symbol}] Error calculando tiempo abierto: {e}")
        except Exception as e:
            print(f"[{symbol}] Error obteniendo tiempo de apertura: {e}")

        # Obtener PnL real antes de intentar cerrar
        try:
            posiciones = obtener_posiciones_hyperliquid()
            for pos in posiciones:
                if pos.get('asset', '').upper() == symbol.upper():
                    pnl_real = float(pos.get('unrealizedPnl', 0))
                    entryPrice = float(pos.get('entryPrice', 0))
                    break
            else:
                entryPrice = 0
        except Exception as e:
            print(f"[{symbol}] Error obteniendo PnL real: {e}")
            entryPrice = 0

        # Cancelar órdenes TP pendientes
        tp_orders = cargar_ordenes_tp()
        if symbol in tp_orders and "order_id" in tp_orders[symbol] and tp_orders[symbol]["order_id"]:
            try:
                client.cancel_order(symbol=symbol, order_id=tp_orders[symbol]["order_id"])
                print(f"[{symbol}] Orden TP cancelada antes de cerrar posición")
                del tp_orders[symbol]
                guardar_ordenes_tp(tp_orders)
            except Exception as e:
                print(f"[{symbol}] Error cancelando orden TP: {e}")

        # Determinar dirección y cantidad
        position_float = float(positionAmt)
        quantity = abs(position_float)
        side = "sell" if position_float > 0 else "buy"
        direccion = "BUY" if position_float > 0 else "SELL"

        print(f"[{symbol}] Cerrando posición: {side.upper()} {quantity} (posición original: {position_float})")

        # MÉTODO 1: Usar create_order simple
        try:
            order = client.create_order(
                symbol=symbol,
                side=side,
                size=quantity
            )
            if order:
                print(f"[{symbol}] Orden de cierre enviada exitosamente: {order}")
                time.sleep(3)  # Esperar para que se procese

                # Verificar si realmente se cerró
                if verificar_posicion_cerrada(symbol):
                    # Activar cooldown tras cierre exitoso
                    last_trade_time = datetime.now()
                    print(f"[{symbol}] Cooldown activado tras cierre exitoso")
                    print(f"[{symbol}] ✓ Posición cerrada exitosamente (método 1)")
                    precio_actual = obtener_precio_hyperliquid(symbol) or entryPrice
                    tp = None  # Puedes ajustar este valor si tienes el TP usado
                    # NO guardar historial aquí - Se guardará en evaluar_cierre_operacion_hyperliquid
                    if pnl_real is not None:
                        return order, True, pnl_real
                    else:
                        return order, True
                else:
                    print(f"[{symbol}] Posición sigue abierta en intento 1: {quantity}")
        except Exception as e1:
            print(f"[{symbol}] Error en método 1: {e1}")

        # MÉTODO 2: Intentar con exchange.market_close si está disponible
        try:
            is_buy = side.lower() == "buy"
            order = client.exchange.market_close(symbol, is_buy, quantity)
            if order:
                print(f"[{symbol}] Orden de cierre enviada (método 2): {order}")
                time.sleep(3)
                if verificar_posicion_cerrada(symbol):
                    # Activar cooldown tras cierre exitoso
                    last_trade_time = datetime.now()
                    print(f"[{symbol}] Cooldown activado tras cierre exitoso")
                    print(f"[{symbol}] ✓ Posición cerrada exitosamente (método 2)")
                    precio_actual = obtener_precio_hyperliquid(symbol) or entryPrice
                    tp = None
                    # NO guardar historial aquí - Se guardará en evaluar_cierre_operacion_hyperliquid
                    if pnl_real is not None:
                        return order, True, pnl_real
                    else:
                        return order, True
                else:
                    print(f"[{symbol}] Posición sigue abierta después de método 2")
        except Exception as e2:
            print(f"[{symbol}] Error en método 2: {e2}")

        # MÉTODO 3: Intentar cerrando por lotes pequeños
        try:
            print(f"[{symbol}] Intentando cerrar en lotes pequeños...")
            is_buy = side.lower() == "buy"
            parte = quantity / 5.0
            for i in range(5):
                try:
                    cantidad_parte = parte
                    if i == 4:  # Último lote, asegurar que cierre todo
                        posicion_actual = obtener_posicion_actual(symbol)
                        if posicion_actual is not None and abs(posicion_actual) > 0.0001:
                            cantidad_parte = abs(posicion_actual)
                        else:
                            break
                    print(f"[{symbol}] Cerrando lote {i+1}/5: {cantidad_parte}")
                    order = client.exchange.market_close(symbol, is_buy, cantidad_parte)
                    print(f"[{symbol}] Respuesta lote {i+1}: {order}")
                    time.sleep(1.5)
                except Exception as e:
                    print(f"[{symbol}] Error en lote {i+1}: {e}")

            if verificar_posicion_cerrada(symbol):
                # Activar cooldown tras cierre exitoso
                last_trade_time = datetime.now()
                print(f"[{symbol}] Cooldown activado tras cierre exitoso")
                print(f"[{symbol}] ✓ Posición cerrada exitosamente (método 3 - lotes)")
                precio_actual = obtener_precio_hyperliquid(symbol) or entryPrice
                tp = None
                # NO guardar historial aquí - Se guardará en evaluar_cierre_operacion_hyperliquid
                order_info = {"status": "ok", "method": "batch_close"}
                if pnl_real is not None:
                    return order_info, True, pnl_real
                else:
                    return order_info, True
        except Exception as e3:
            print(f"[{symbol}] Error en método 3: {e3}")

        # Si llegamos aquí, todos los métodos fallaron
        print(f"[{symbol}] ❌ No se pudo cerrar la posición tras múltiples intentos")
        enviar_telegram(f"⚠️ No se pudo cerrar la posición para {symbol} tras múltiples intentos. Cierre manualmente.", tipo="error")
        if pnl_real is not None:
            return None, False, pnl_real
        else:
            return None, False

    except Exception as e:
        logging.error(f"Error al cerrar posición para {symbol}: {e}", exc_info=True)
        enviar_telegram(f"⚠️ Error al cerrar posición para {symbol}: {e}", tipo="error")
        return None, False

def evaluar_cierre_operacion_hyperliquid(pos, precio_actual, niveles_atr):
    """
    Evalúa si una posición debe cerrarse manualmente (como respaldo si el TP del exchange falla)
    Con mejor manejo de errores y verificación, además de PnL real
    """
    try:
        global last_trade_time
        entryPrice = float(pos['entryPrice'])
        positionAmt = float(pos['position'])
        qty = abs(positionAmt)
        symbol = pos['asset']
        direccion = "BUY" if positionAmt > 0 else "SELL"
        
        # Obtener el PnL real de la posición antes del cierre
        pnl_real = float(pos.get('unrealizedPnl', 0))

        # Verificar si hay un TP establecido en el archivo
        niveles = niveles_atr.get(symbol)
        if niveles and "tp_fijo" in niveles:
            tp = niveles["tp_fijo"]
        else:
            # Activar cooldown tras cierre exitoso
            last_trade_time = datetime.now()
            print(f"[{symbol}] Cooldown activado tras cierre exitoso")
            # Si no hay TP guardado, no hay criterio para cerrar manualmente
            return False

        # Verificar si el precio ha alcanzado el TP y cerrar manualmente (respaldo)
        if (direccion == "BUY" and precio_actual >= tp) or (direccion == "SELL" and precio_actual <= tp):
            print(f"[{symbol}] TP alcanzado, intentando cerrar posición. Entry: {entryPrice}, Actual: {precio_actual}, TP: {tp}")
            
            # No eliminar el TP hasta confirmar cierre exitoso
            resultado_cierre = cerrar_posicion(symbol, positionAmt)
            
            # Verificar si tenemos 2 o 3 elementos en la respuesta
            if len(resultado_cierre) == 3:
                order, cierre_confirmado, pnl_real_final = resultado_cierre
            else:
                order, cierre_confirmado = resultado_cierre
                pnl_real_final = pnl_real  # Usar el PnL obtenido antes del cierre
            
            if order:
                if not cierre_confirmado:
                    print(f"[{symbol}] ⚠️ ADVERTENCIA CRÍTICA: Se envió orden de cierre pero la posición sigue abierta")
                    enviar_telegram(f"⚠️ ADVERTENCIA CRÍTICA: Se envió orden de cierre para {symbol} pero la posición sigue abierta. VERIFIQUE Y CIERRE MANUALMENTE.", tipo="error")
                    
                    # NO REGISTRAR COMO CERRADA para que el bot siga intentando cerrarla
                    return False
                
                # Si llegamos aquí, el cierre está confirmado
                icono_cerrado = "🟢" if pnl_real_final >= 0 else "🔴"
                
                # Usar el PnL real obtenido de la API
                enviar_telegram(
                    f"{icono_cerrado} Trade CERRADO (respaldo): {symbol} {direccion}\n"
                    f"Entry: {entryPrice:.4f}\n"
                    f"Close: {precio_actual:.4f}\n"
                    f"TP: {tp:.4f}\n"
                    f"PnL real: {pnl_real_final:.4f} USDT",
                    tipo="close"
                )
                
                # Guardar el historial para análisis posterior
                tp_orders = cargar_ordenes_tp()
                tiempo_abierto = "N/A"
                if symbol in tp_orders and "tiempo_apertura" in tp_orders[symbol]:
                    try:
                        tiempo_apertura = datetime.fromisoformat(tp_orders[symbol]["tiempo_apertura"])
                        tiempo_abierto = str(datetime.now() - tiempo_apertura).split('.')[0]
                    except Exception as e:
                        print(f"[{symbol}] Error calculando tiempo abierto en cierre TP: {e}")
                
                # AQUÍ ES DONDE SE DEBE GUARDAR EL HISTORIAL
                guardar_historial_pnl(
                    symbol, direccion, 
                    entryPrice,
                    precio_actual, 
                    tp,
                    pnl_real_final,
                    tiempo_abierto,
                    "tp_alcanzado"
                )
                # Actualizar resumen diario
                resumen_diario["trades_cerrados"] += 1
                resumen_diario["pnl_total"] += pnl_real_final
                
                # Eliminar el TP del archivo SOLO SI el cierre está confirmado
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

def cerrar_posiciones_huerfanas():
    """
    Identifica y cierra posiciones 'huérfanas' que no tienen un TP registrado
    """
    try:
        global last_trade_time
        global last_trade_time
        # Obtener posiciones actuales y niveles ATR/TP
        posiciones = obtener_posiciones_hyperliquid()
        niveles_atr = cargar_niveles_atr()
        
        # Verificar cada posición para ver si tiene niveles TP asociados
        for pos in posiciones:
            symbol = pos['asset']
            
            # Si esta posición no tiene un nivel TP registrado
            if symbol not in niveles_atr:
                print(f"[{symbol}] Posición huérfana detectada (sin TP registrado)")
                
                # Decidir si cerrarla automáticamente
                positionAmt = float(pos['position'])
                entryPrice = float(pos['entryPrice'])
                unrealizedPnl = float(pos.get('unrealizedPnl', 0))
                
                # Por seguridad, solo cerramos posiciones huérfanas con PnL positivo
                if unrealizedPnl > 0:
                    print(f"[{symbol}] Cerrando posición huérfana con PnL positivo: {unrealizedPnl}")
                    resultado_cierre = cerrar_posicion(symbol, positionAmt)
                    
                    # Verificar si tenemos el PnL real en la respuesta
                    if len(resultado_cierre) == 3:
                        order, cierre_confirmado, pnl_real_final = resultado_cierre
                    else:
                        order, cierre_confirmado = resultado_cierre
                        pnl_real_final = unrealizedPnl  # Usar el PnL obtenido antes del cierre
                    
                    if order and cierre_confirmado:
                        # Activar cooldown tras cierre exitoso de posición huérfana
                        last_trade_time = datetime.now()
                        print(f"[{symbol}] Cooldown activado tras cierre de posición huérfana")
                        precio_actual = obtener_precio_hyperliquid(symbol)
                        if precio_actual is None:
                            precio_actual = entryPrice  # Fallback
                        
                        direccion = "BUY" if positionAmt > 0 else "SELL"
                        
                        # Guardar el historial para análisis posterior
                        tp_orders = cargar_ordenes_tp()
                        tiempo_abierto = "N/A"
                        if symbol in tp_orders and "tiempo_apertura" in tp_orders[symbol]:
                            try:
                                tiempo_apertura = datetime.fromisoformat(tp_orders[symbol]["tiempo_apertura"])
                                tiempo_abierto = str(datetime.now() - tiempo_apertura).split('.')[0]
                            except Exception as e:
                                print(f"[{symbol}] Error calculando tiempo abierto en cierre huérfana: {e}")
                        
                        guardar_historial_pnl(symbol, direccion, entryPrice, precio_actual, None, pnl_real_final, tiempo_abierto, "huerfana")

                        enviar_telegram(
                            f"🟡 Trade HUÉRFANO CERRADO: {symbol} {direccion}\n"
                            f"Entry: {entryPrice:.4f}\n"
                            f"Close: {precio_actual:.4f}\n"
                            f"PnL real: {pnl_real_final:.4f} USDT",
                            tipo="close"
                        )
                else:
                    print(f"[{symbol}] Posición huérfana con PnL negativo: {unrealizedPnl}, no se cierra automáticamente")
                    
    except Exception as e:
        print(f"Error verificando posiciones huérfanas: {e}")
        logging.error(f"Error verificando posiciones huérfanas: {e}", exc_info=True)

last_trade_time = None

if __name__ == "__main__":
    try:
        # Primero verificamos los símbolos disponibles
        simbolos = obtener_simbolos_disponibles()
        
        if not simbolos:
            enviar_telegram("⚠️ No se encontraron símbolos disponibles para operar. El bot se detendrá.", tipo="error")
            exit(1)
        
        # Ahora enviamos un solo mensaje de inicio con toda la información
        enviar_telegram(f"🚀 Bot arrancado correctamente y en ejecución.\n\n🔍 Símbolos disponibles para operar ({len(simbolos)}/{20}): {', '.join(simbolos)}", tipo="info")
            
        intervalo_segundos = 10  # Aumentado a 10 segundos para reducir carga en API
        tiempo_inicio = datetime.now()
        ultima_reevaluacion = datetime.now()
        ultimo_chequeo_huerfanas = datetime.now()

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
            # NUEVO: Evaluar posiciones para DCA
            evaluar_dca(posiciones)
            
            # Verificar posiciones huérfanas (sin TP registrado) cada hora
            now = datetime.now()
            if (now - ultimo_chequeo_huerfanas).total_seconds() > 3600:  # 3600 segundos = 1 hora
                print("Verificando posiciones huérfanas...")
                cerrar_posiciones_huerfanas()
                ultimo_chequeo_huerfanas = now
            
            # --- Espera cooldown tras un trade abierto ---
            if last_trade_time and (now - last_trade_time) < timedelta(minutes=COOLDOWN_MINUTES):
                restante = timedelta(minutes=COOLDOWN_MINUTES) - (now - last_trade_time)
                print(f"En cooldown tras última operación. Esperando {restante} antes de poder abrir otro trade.")
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

            print(f"\nEsperando {intervalo_segundos} segundos antes de la próxima evaluación...")
            time.sleep(intervalo_segundos)
    except Exception as e:
        logging.error(f"Error crítico en el bucle principal: {e}", exc_info=True)
        enviar_telegram(f"❗️ Error crítico en el bucle principal: {e}", tipo="error")
