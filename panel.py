import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.ticker import MaxNLocator
import config
from config import TIMEOUT_MINUTES, LEVERAGE, MARGIN_PER_TRADE, ATR_TP_MULT, MAX_TP_PCT
from streamlit_autorefresh import st_autorefresh
import json
import os
import time
from hyperliquid_client import HyperliquidClient

def leer_tiempo_inicio_bot():
    try:
        with open("tiempo_inicio_bot.txt") as f:
            return datetime.fromisoformat(f.read().strip())
    except Exception:
        return None

def leer_niveles_atr():
    if os.path.exists("trade_levels_atr.json"):
        with open("trade_levels_atr.json") as f:
            return json.load(f)
    else:
        return {}

client = HyperliquidClient()

st.set_page_config(
    page_title="Panel de Control - Scalping Bot Microestructura v2 (Hyperliquid)",
    layout="wide",
    initial_sidebar_state="collapsed"
)

def close_single_position(symbol):
    try:
        # Obtener las posiciones actuales
        posiciones = obtener_posiciones_hyperliquid()
        for pos in posiciones:
            if pos['asset'] == symbol and float(pos.get('position', 0)) != 0:
                qty = float(pos['position'])
                # En Hyperliquid, necesitamos invertir la dirección para cerrar
                side = "buy" if qty < 0 else "sell"
                order = client.create_order(symbol=symbol, side=side, size=abs(qty))
                return f"Posición en {symbol} cerrada correctamente."
        return f"No hay posición abierta en {symbol}."
    except Exception as e:
        return f"Error cerrando {symbol}: {e}"

def obtener_posiciones_hyperliquid():
    try:
        account = client.get_account()
        # La estructura de user_state contiene 'assetPositions'
        if not account or "assetPositions" not in account:
            return []
        posiciones_abiertas = [p for p in account["assetPositions"] if float(p.get('position', 0)) != 0]
        return posiciones_abiertas
    except Exception as e:
        st.error(f"Error al obtener posiciones Hyperliquid: {e}")
        return []

def close_all_positions():
    try:
        posiciones = obtener_posiciones_hyperliquid()
        resultados = []
        for pos in posiciones:
            symbol = pos['asset']
            qty = float(pos.get('position', 0))
            if qty == 0:
                continue
            # En Hyperliquid, necesitamos invertir la dirección para cerrar
            side = "buy" if qty < 0 else "sell"
            try:
                order = client.create_order(symbol=symbol, side=side, size=abs(qty))
                resultados.append(f"Posición en {symbol} cerrada correctamente.")
            except Exception as e:
                resultados.append(f"Error cerrando {symbol}: {e}")
        return resultados
    except Exception as e:
        return [f"Error al obtener posiciones: {e}"]

def get_open_positions():
    try:
        posiciones = obtener_posiciones_hyperliquid()
        niveles_atr = leer_niveles_atr()
        rows = []
        
        for p in posiciones:
            symbol = p['asset']
            qty = float(p.get('position', 0))
            entry = float(p.get('entryPrice', 0))
            direction = "long" if qty > 0 else "short"
            pnl = float(p.get('unrealizedPnl', 0))
            
            # Hyperliquid no proporciona timestamp de actualización como Binance,
            # usaremos la hora actual o un timestamp de registro si está disponible
            ts = datetime.now()
            
            # Obtener precio actual
            try:
                precio_ticker = client.get_price(symbol)
                precio_actual = float(precio_ticker.get('mid', 0)) if precio_ticker else 0
            except Exception:
                precio_actual = entry  # Si falla, usamos el precio de entrada
                
            notional = abs(qty) * precio_actual
            
            # TP fijo desde niveles ATR
            tp_fijo = None
            sl_atr = "NO"
            if symbol in niveles_atr:
                tp_fijo = niveles_atr[symbol].get("tp_fijo")
            
            # Hyperliquid proporciona la liquidación en el objeto de posición
            liquidation_price = p.get('liquidationPrice', 0)
            try:
                liquidation_price = float(liquidation_price)
            except Exception:
                liquidation_price = 0.0
            liquidation_str = f"{liquidation_price:.4f}" if liquidation_price > 0 else "NO DISPONIBLE"
            
            # Calcular timeout
            try:
                if TIMEOUT_MINUTES > 525600:
                    hora_timeout = "NO"
                else:
                    hora_timeout = (ts + timedelta(minutes=TIMEOUT_MINUTES)).strftime('%Y-%m-%d %H:%M:%S')
            except OverflowError:
                hora_timeout = "NO"
            
            rows.append({
                "Par": symbol,
                "Dirección": direction,
                "Precio Entrada": entry,
                "Cantidad": abs(qty),
                "Margen usado": notional/LEVERAGE,  # Dividir por leverage para obtener el margen real
                "Timestamp": ts.strftime('%Y-%m-%d %H:%M:%S'),
                "Precio Actual": precio_actual,
                "PnL en vivo": pnl,
                "TP fijo": tp_fijo,
                "SL ATR": sl_atr,
                "Hora Timeout": hora_timeout,
                "Liquidación": liquidation_str,
            })
        
        df = pd.DataFrame(rows)
        return df
    except Exception as e:
        st.error(f"Error obteniendo posiciones: {e}")
        return pd.DataFrame()

def obtener_simbolos_disponibles():
    """Obtiene la lista de símbolos disponibles en Hyperliquid"""
    try:
        # Lista predefinida de símbolos que sabemos que están en Hyperliquid
        simbolos_conocidos = [
            'BTC', 'ETH', 'SOL', 'BNB', 'DOGE', 'ARB', 'SUI', 'OP', 
            'AVAX', 'NEAR', 'ADA', 'ATOM'
        ]
        
        # Intentar verificar disponibilidad de cada símbolo con get_price
        simbolos_disponibles = []
        for symbol in simbolos_conocidos:
            try:
                precio = client.get_price(symbol)
                if precio and precio.get('mid'):
                    simbolos_disponibles.append(symbol)
            except Exception:
                pass
                
        return simbolos_disponibles
    except Exception as e:
        st.error(f"Error obteniendo símbolos disponibles: {e}")
        return []

def get_account_balance():
    try:
        account = client.get_account()
        if account and "equity" in account:
            return float(account["equity"])
        return 0
    except Exception as e:
        st.error(f"Error obteniendo saldo: {e}")
        return 0

# Simulación de historial de trades para el panel
def simular_historial_trades():
    st.warning("El historial de trades es simulado. La API de Hyperliquid no proporciona acceso directo al historial de trades completo.")
    return pd.DataFrame()

balance_inicial = get_account_balance()

# --- AUTORREFRESCO SEGURO ---
st_autorefresh(interval=10000, key="panel_autorefresh")

tiempo_inicio = leer_tiempo_inicio_bot()
if not tiempo_inicio:
    st.warning("No se encontró la hora de inicio del bot (tiempo_inicio_bot.txt).")

tiempo_transcurrido = "00h 00m 00s"
if tiempo_inicio:
    try:
        tiempo_actual = datetime.now()
        tiempo_transcurrido_obj = tiempo_actual - tiempo_inicio
        horas, resto = divmod(tiempo_transcurrido_obj.seconds, 3600)
        minutos, segundos = divmod(resto, 60)
        tiempo_transcurrido = f"{tiempo_transcurrido_obj.days}d {horas}h {minutos}m {segundos}s"
    except Exception as e:
        st.error(f"Error calculando tiempo transcurrido: {e}")

st.markdown(
    f"<p style='text-align: center; font-size: 14px;'>El panel se actualizará automáticamente cada 10 segundos. "
    f"Tiempo Transcurrido: {tiempo_transcurrido}</p>",
    unsafe_allow_html=True
)

# ----------- MEJORA 1: mostrar arriba la configuración de trading -----------
tp_text = f"{ATR_TP_MULT} x ATR (máx {MAX_TP_PCT*100:.1f}% sobre entrada)"
sl_text = "NO"
st.markdown(
    f"<p style='text-align: center; font-size: 14px;'>"
    f"<b>TP:</b> {tp_text} &nbsp; | &nbsp; "
    f"<b>SL:</b> {sl_text} &nbsp; | &nbsp; "
    f"<b>TIMEOUT_MINUTES:</b> {config.TIMEOUT_MINUTES} &nbsp; | &nbsp; "
    f"<b>LEVERAGE:</b> {LEVERAGE}x &nbsp; | &nbsp; "
    f"<b>MARGEN POR TRADE:</b> {MARGIN_PER_TRADE} USDT"
    f"</p>",
    unsafe_allow_html=True
)

# --- SECCIÓN DE BALANCE ACTUAL ---
current_balance = get_account_balance()
st.markdown(f"<h3 style='text-align: center;'>Saldo actual: {current_balance:.4f} USDT</h3>", unsafe_allow_html=True)

# --- SIMULACIÓN DE HISTORIAL DE TRADES ---
st.info("En Hyperliquid, el historial de trades no está disponible directamente a través de la API pública de la forma en que lo está en Binance. Para tener esta funcionalidad, sería necesario registrar los trades en un archivo local cuando ocurren.")

# -------- OPERACIONES ABIERTAS: tabla + botón centrado y compacto --------
st.markdown("<h4 style='text-align: center;'>Operaciones abiertas</h4>", unsafe_allow_html=True)
operaciones_vivas = get_open_positions()

def color_fila_por_antiguedad(row):
    # Suponemos que 'Timestamp' está en formato 'YYYY-MM-DD HH:MM:SS'
    try:
        fecha = pd.to_datetime(row['Timestamp'])
        dias = (datetime.now() - fecha).days
        if dias <= 1:
            color = 'background-color: #d4edda;'  # verde claro
        elif dias < 3:
            color = 'background-color: #fff3cd;'  # amarillo claro
        else:
            color = 'background-color: #f8d7da;'  # rojo claro
    except Exception:
        color = ''
    return [color] * len(row)

if not operaciones_vivas.empty:
    operaciones_vivas_display = operaciones_vivas.copy()
    # Asegúrate de que Timestamp sea datetime
    operaciones_vivas_display['Timestamp'] = pd.to_datetime(operaciones_vivas_display['Timestamp'], errors='coerce')
    float_cols = operaciones_vivas_display.select_dtypes(include='float').columns
    format_dict = {col: "{:.4f}" for col in float_cols}
    if "Liquidación" in operaciones_vivas_display.columns:
        format_dict["Liquidación"] = "{}"
    styled_df = operaciones_vivas_display.style.format(format_dict).apply(color_fila_por_antiguedad, axis=1)
    st.dataframe(styled_df, use_container_width=True, hide_index=True)
    cols = st.columns([4,1,4])
    with cols[1]:
        if st.button("Cerrar todas"):
            resultados = close_all_positions()
            for r in resultados:
                st.success(r)
else:
    st.warning("No hay operaciones abiertas en este momento.")

# Sección para los símbolos disponibles
st.markdown("<h4 style='text-align: center;'>Símbolos disponibles para operar</h4>", unsafe_allow_html=True)

simbolos = obtener_simbolos_disponibles()
if simbolos:
    # Crear una tabla con los símbolos disponibles
    cols = st.columns(4)
    for i, symbol in enumerate(simbolos):
        cols[i % 4].write(f"✅ {symbol}")
else:
    st.warning("No se encontró información sobre símbolos disponibles. Verifica la conexión con Hyperliquid.")
