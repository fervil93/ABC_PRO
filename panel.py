import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import config
from config import TIMEOUT_MINUTES, LEVERAGE, MARGIN_PER_TRADE, ATR_TP_MULT, MAX_TP_PCT
from streamlit_autorefresh import st_autorefresh
import json
import os
import time
from hyperliquid_client import HyperliquidClient

# Configuración de estilo personalizado
st.markdown("""
    <style>
    .big-metric {
        font-size: 26px;
        font-weight: bold;
        color: #1E88E5;
    }
    .metric-label {
        font-size: 14px;
        color: #555;
    }
    .metric-card {
        background-color: #f8f9fa;
        border-radius: 10px;
        padding: 15px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        text-align: center;
    }
    .profit {
        color: #4CAF50;
    }
    .loss {
        color: #F44336;
    }
    .header-decoration {
        background: linear-gradient(to right, #1E88E5, #5DADE2);
        padding: 5px 10px;
        border-radius: 5px;
        color: white;
        text-align: center;
        margin-bottom: 10px;
    }
    </style>
""", unsafe_allow_html=True)

# Cache para reducir llamadas API
cache = {
    "last_balance_check": datetime.now() - timedelta(minutes=5),
    "balance": 0,
    "last_positions_check": datetime.now() - timedelta(minutes=5),
    "positions": [],
    "api_errors": 0,
    "max_consecutive_errors": 3
}

def leer_tiempo_inicio_bot():
    try:
        with open("tiempo_inicio_bot.txt") as f:
            return datetime.fromisoformat(f.read().strip())
    except Exception:
        return None

def leer_niveles_atr():
    try:
        if os.path.exists("trade_levels_atr.json"):
            with open("trade_levels_atr.json") as f:
                return json.load(f)
        else:
            return {}
    except Exception as e:
        st.error(f"Error leyendo niveles ATR: {e}")
        return {}

def leer_simbolos_disponibles_desde_archivo():
    try:
        if os.path.exists("simbolos_disponibles.txt"):
            with open("simbolos_disponibles.txt", "r") as f:
                contenido = f.read().strip()
                simbolos = [s.strip() for s in contenido.split(',')]
                return simbolos
    except Exception:
        pass
    return None

# Crear cliente con manejo de errores
@st.cache_resource
def get_client():
    return HyperliquidClient()

client = get_client()

st.set_page_config(
    page_title="Monitor Trading - Hyperliquid",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Función con retry y backoff para llamadas API
def api_call_with_retry(func, *args, max_retries=3, **kwargs):
    retries = 0
    while retries < max_retries:
        try:
            return func(*args, **kwargs)
        except Exception as e:
            retries += 1
            if retries == max_retries:
                cache["api_errors"] += 1
                if cache["api_errors"] > cache["max_consecutive_errors"]:
                    st.error(f"Demasiados errores consecutivos de API: {e}")
                return None
            # Espera exponencial entre reintentos
            time.sleep(2 ** retries)
    return None

def close_single_position(symbol):
    try:
        posiciones = obtener_posiciones_hyperliquid(forzar=True)
        for pos in posiciones:
            if pos['asset'] == symbol and float(pos.get('position', 0)) != 0:
                qty = float(pos['position'])
                side = "buy" if qty < 0 else "sell"
                order = api_call_with_retry(client.create_order, symbol=symbol, side=side, size=abs(qty))
                return f"Posición en {symbol} cerrada correctamente."
        return f"No hay posición abierta en {symbol}."
    except Exception as e:
        return f"Error cerrando {symbol}: {e}"

def obtener_posiciones_hyperliquid(forzar=False):
    # Usar cache para reducir llamadas API
    if not forzar and (datetime.now() - cache["last_positions_check"]).total_seconds() < 20:
        return cache["positions"]
    
    try:
        account = api_call_with_retry(client.get_account)
        if not account or "assetPositions" not in account:
            return []
        posiciones_abiertas = [p for p in account["assetPositions"] if float(p.get('position', 0)) != 0]
        
        cache["last_positions_check"] = datetime.now()
        cache["positions"] = posiciones_abiertas
        cache["api_errors"] = 0  # Reset error counter on success
        
        return posiciones_abiertas
    except Exception as e:
        st.error(f"Error al obtener posiciones: {e}")
        return []

def close_all_positions():
    try:
        posiciones = obtener_posiciones_hyperliquid(forzar=True)
        resultados = []
        for pos in posiciones:
            symbol = pos['asset']
            qty = float(pos.get('position', 0))
            if qty == 0:
                continue
            side = "buy" if qty < 0 else "sell"
            try:
                order = api_call_with_retry(client.create_order, symbol=symbol, side=side, size=abs(qty))
                resultados.append(f"Posición en {symbol} cerrada correctamente.")
            except Exception as e:
                resultados.append(f"Error cerrando {symbol}: {e}")
        return resultados
    except Exception as e:
        return [f"Error al obtener posiciones: {e}"]

def get_open_positions():
    posiciones = obtener_posiciones_hyperliquid()
    niveles_atr = leer_niveles_atr()
    rows = []
    
    for p in posiciones:
        symbol = p['asset']
        qty = float(p.get('position', 0))
        entry = float(p.get('entryPrice', 0))
        direction = "LONG" if qty > 0 else "SHORT"
        pnl = float(p.get('unrealizedPnl', 0))
        
        ts = datetime.now()
        
        try:
            precio_ticker = api_call_with_retry(client.get_price, symbol=symbol)
            precio_actual = float(precio_ticker.get('mid', 0)) if precio_ticker else 0
        except Exception:
            precio_actual = entry
            
        notional = abs(qty) * precio_actual
        
        # Calcular % de beneficio/pérdida
        if direction == "LONG":
            pct_change = (precio_actual - entry) / entry * 100
        else:
            pct_change = (entry - precio_actual) / entry * 100
        
        tp_fijo = None
        sl_atr = "NO"
        if symbol in niveles_atr:
            tp_fijo = niveles_atr[symbol].get("tp_fijo")
        
        liquidation_price = p.get('liquidationPrice', 0)
        try:
            liquidation_price = float(liquidation_price)
        except Exception:
            liquidation_price = 0.0
        
        if TIMEOUT_MINUTES > 525600:
            hora_timeout = "NO"
        else:
            hora_timeout = (ts + timedelta(minutes=TIMEOUT_MINUTES)).strftime('%Y-%m-%d %H:%M:%S')
        
        rows.append({
            "Par": symbol,
            "Dirección": direction,
            "Precio Entrada": entry,
            "Precio Actual": precio_actual,
            "Var (%)": pct_change,
            "Cantidad": abs(qty),
            "Margen": notional/LEVERAGE,
            "PnL": pnl,
            "TP": tp_fijo,
            "Tiempo": ts.strftime('%H:%M:%S'),
            "Liquidación": liquidation_price,
        })
    
    df = pd.DataFrame(rows)
    return df

def obtener_simbolos_disponibles():
    simbolos_desde_archivo = leer_simbolos_disponibles_desde_archivo()
    if simbolos_desde_archivo:
        return simbolos_desde_archivo
    return []

def get_account_balance():
    # Usar cache para reducir llamadas API
    if (datetime.now() - cache["last_balance_check"]).total_seconds() < 60:
        return cache["balance"]
    
    try:
        account = api_call_with_retry(client.get_account)
        if account and "equity" in account:
            balance = float(account["equity"])
            cache["last_balance_check"] = datetime.now()
            cache["balance"] = balance
            cache["api_errors"] = 0  # Reset error counter on success
            return balance
        return 0
    except Exception as e:
        st.error(f"Error obteniendo saldo: {e}")
        return 0

# --- AUTORREFRESCO MENOS FRECUENTE ---
refresh_interval = 30  # segundos
st_autorefresh(interval=refresh_interval * 1000, key="panel_autorefresh")

# --- ENCABEZADO Y MÉTRICAS PRINCIPALES ---
col1, col2, col3 = st.columns([1, 2, 1])

with col2:
    st.markdown("<h1 style='text-align: center;'>📊 Monitor de Trading Hyperliquid</h1>", unsafe_allow_html=True)

tiempo_inicio = leer_tiempo_inicio_bot()
tiempo_transcurrido = "No disponible"
if tiempo_inicio:
    tiempo_actual = datetime.now()
    tiempo_transcurrido_obj = tiempo_actual - tiempo_inicio
    horas, resto = divmod(tiempo_transcurrido_obj.seconds, 3600)
    minutos, segundos = divmod(resto, 60)
    tiempo_transcurrido = f"{tiempo_transcurrido_obj.days}d {horas}h {minutos}m {segundos}s"

# --- INFO GENERAL ---
st.markdown(f"<div style='text-align:center'>Actualización cada <b>{refresh_interval}s</b> | Tiempo activo: <b>{tiempo_transcurrido}</b></div>", unsafe_allow_html=True)

# --- CONFIGURACIÓN DE TRADING EN TARJETAS ---
col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    st.markdown("<div class='metric-card'><p class='metric-label'>TP</p><p class='big-metric'>" + 
                f"{ATR_TP_MULT}×ATR</p><small>(máx {MAX_TP_PCT*100:.1f}%)</small></div>", unsafe_allow_html=True)

with col2:
    st.markdown("<div class='metric-card'><p class='metric-label'>SL</p><p class='big-metric'>NO</p></div>", unsafe_allow_html=True)

with col3:
    st.markdown("<div class='metric-card'><p class='metric-label'>APALANCAMIENTO</p><p class='big-metric'>" + 
                f"{LEVERAGE}×</p></div>", unsafe_allow_html=True)

with col4:
    st.markdown("<div class='metric-card'><p class='metric-label'>MARGEN/TRADE</p><p class='big-metric'>" + 
                f"{MARGIN_PER_TRADE}</p><small>USDT</small></div>", unsafe_allow_html=True)

with col5:
    st.markdown("<div class='metric-card'><p class='metric-label'>TIMEOUT</p><p class='big-metric'>" + 
                (f"{TIMEOUT_MINUTES}min" if TIMEOUT_MINUTES < 525600 else "NO") + "</p></div>", unsafe_allow_html=True)

# --- SALDO DE CUENTA ---
current_balance = get_account_balance()
st.markdown(f"<div style='text-align:center; margin: 20px 0;'><span class='big-metric'>{current_balance:.2f} USDT</span> <span class='metric-label'>Saldo actual</span></div>", unsafe_allow_html=True)

# --- POSICIONES ABIERTAS ---
st.markdown("<div class='header-decoration'><h3>Posiciones Abiertas</h3></div>", unsafe_allow_html=True)
operaciones_vivas = get_open_positions()

def highlight_cells(row):
    """Highlight cells based on PnL and direction"""
    pct_color = 'color: green' if row['Var (%)'] > 0 else 'color: red'
    pnl_color = 'color: green' if row['PnL'] > 0 else 'color: red'
    direction_color = 'background-color: #d4edda; color: black' if row['Dirección'] == 'LONG' else 'background-color: #f8d7da; color: black'
    
    result = [''] * len(row)
    result[row.index.get_loc('Var (%)')] = pct_color
    result[row.index.get_loc('PnL')] = pnl_color
    result[row.index.get_loc('Dirección')] = direction_color
    
    # Si hay TP, destacarlo
    if pd.notna(row['TP']):
        tp_price = row['TP']
        current_price = row['Precio Actual']
        direction = row['Dirección']
        
        distance = abs(tp_price - current_price) / current_price * 100
        
        # Cambiar color según cercanía al TP
        if ((direction == 'LONG' and tp_price > current_price) or 
            (direction == 'SHORT' and tp_price < current_price)):
            if distance < 1:
                result[row.index.get_loc('TP')] = 'background-color: #d4edda; font-weight: bold'
            elif distance < 3:
                result[row.index.get_loc('TP')] = 'background-color: #fff3cd; font-weight: bold'
            else:
                result[row.index.get_loc('TP')] = 'background-color: #f8d7da'
    
    return result

if not operaciones_vivas.empty:
    # Define order and format of columns
    cols_to_show = ["Par", "Dirección", "Precio Entrada", "Precio Actual", "Var (%)", 
                   "Cantidad", "Margen", "PnL", "TP", "Tiempo"]
    
    # Apply formatting
    styled_df = operaciones_vivas[cols_to_show].style.apply(highlight_cells, axis=1).format({
        'Precio Entrada': '{:.4f}',
        'Precio Actual': '{:.4f}',
        'Var (%)': '{:.2f}%',
        'Cantidad': '{:.6f}',
        'Margen': '{:.2f}',
        'PnL': '{:.4f}',
        'TP': '{:.4f}',
    })
    
    st.dataframe(styled_df, use_container_width=True, hide_index=True)
    
    # Botón para cerrar operaciones
    col1, col2, col3 = st.columns([3, 1, 3])
    with col2:
        if st.button("🚫 Cerrar todas", use_container_width=True):
            with st.spinner("Cerrando posiciones..."):
                resultados = close_all_positions()
                for r in resultados:
                    st.success(r)
                st.rerun()  # Refrescar después de cerrar
else:
    st.info("😴 No hay operaciones abiertas en este momento.")

# --- SÍMBOLOS DISPONIBLES ---
st.markdown("<div class='header-decoration'><h3>Pares Disponibles</h3></div>", unsafe_allow_html=True)

ultima_actualizacion = None
try:
    if os.path.exists("ultima_verificacion_simbolos.txt"):
        with open("ultima_verificacion_simbolos.txt", "r") as f:
            ultima_actualizacion = datetime.fromisoformat(f.read().strip())
            tiempo_desde_actualizacion = datetime.now() - ultima_actualizacion
            mins_desde_actualizacion = int(tiempo_desde_actualizacion.total_seconds() / 60)
except:
    pass

simbolos = obtener_simbolos_disponibles()
if simbolos:
    # Mostrar la información de actualización
    if ultima_actualizacion:
        st.markdown(f"<div style='text-align:center; margin-bottom:10px;'>Última verificación: <b>{ultima_actualizacion.strftime('%d-%m-%Y %H:%M')}</b> (hace {mins_desde_actualizacion} min)</div>", unsafe_allow_html=True)
    
    # Crear grid con símbolos destacados visualmente
    st.markdown(f"<div style='text-align:center; font-weight:bold; margin-bottom:10px;'>{len(simbolos)}/{20} pares activos</div>", unsafe_allow_html=True)
    
    # Grid más visual para los símbolos
    symbol_cols = st.columns(5)
    for i, symbol in enumerate(simbolos):
        with symbol_cols[i % 5]:
            st.markdown(f"""
                <div style='background-color:#f0f2f6; border-radius:5px; padding:10px; text-align:center; margin-bottom:10px;'>
                    <span style='font-size:16px; font-weight:bold;'>{symbol}</span>
                </div>
            """, unsafe_allow_html=True)
else:
    st.warning("⚠️ No se encontró la lista de símbolos disponibles.")

# --- FOOTER ---
st.markdown("<hr>", unsafe_allow_html=True)
st.markdown("<div style='text-align:center; color:#777; font-size:12px;'>Monitor de Trading v1.0 | Desarrollado para Hyperliquid</div>", unsafe_allow_html=True)
