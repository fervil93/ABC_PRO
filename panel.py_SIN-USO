import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from streamlit_autorefresh import st_autorefresh
import json
import os

from hyperliquid_client import HyperliquidClient
import config

client = HyperliquidClient()

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

st.set_page_config(
    page_title="Panel de Control - Scalping Bot Microestructura v2 (Hyperliquid)",
    layout="wide",
    initial_sidebar_state="collapsed"
)

def close_all_positions():
    posiciones = client.get_account().get("positions", [])
    abiertas = [p for p in posiciones if float(p.get('size', 0)) != 0]
    resultados = []
    for p in abiertas:
        symbol = p['symbol']
        qty = float(p['size'])
        if qty == 0:
            continue
        side = 'sell' if qty > 0 else 'buy'
        try:
            order = client.create_order(symbol=symbol, side=side, size=abs(qty))
            if order.get("status") == "success":
                resultados.append(f"Posición en {symbol} cerrada correctamente.")
            else:
                resultados.append(f"Error cerrando {symbol}: {order}")
        except Exception as e:
            resultados.append(f"Error cerrando {symbol}: {e}")
    return resultados

def get_open_positions():
    posiciones = client.get_account().get("positions", [])
    abiertas = [p for p in posiciones if float(p.get('size', 0)) != 0]
    niveles_atr = leer_niveles_atr()
    rows = []
    for p in abiertas:
        symbol = p['symbol']
        qty = float(p['size'])
        entry = float(p['entryPrice'])
        direction = "long" if qty > 0 else "short"
        pnl = float(p.get('unrealizedPnl', 0))
        ts = datetime.now()
        precio_actual = float(client.get_price(symbol).get('price', entry))
        notional = abs(qty) * precio_actual
        tp_fijo = niveles_atr.get(symbol, {}).get("tp_fijo", "")
        rows.append({
            "Par": symbol,
            "Dirección": direction,
            "Precio Entrada": entry,
            "Cantidad": abs(qty),
            "Margen usado": notional,
            "Timestamp": ts.strftime('%Y-%m-%d %H:%M:%S'),
            "Precio Actual": precio_actual,
            "PnL en vivo": pnl,
            "TP fijo": tp_fijo,
        })
    df = pd.DataFrame(rows)
    return df

def obtener_tiempo_transcurrido(tiempo_inicio):
    tiempo_actual = datetime.now()
    tiempo_transcurrido = tiempo_actual - tiempo_inicio
    horas, resto = divmod(tiempo_transcurrido.seconds, 3600)
    minutos, segundos = divmod(resto, 60)
    return f"{tiempo_transcurrido.days}d {horas}h {minutos}m {segundos}s"

st_autorefresh(interval=10000, key="panel_autorefresh")

tiempo_inicio = leer_tiempo_inicio_bot()
if not tiempo_inicio:
    st.warning("No se encontró la hora de inicio del bot (tiempo_inicio_bot.txt).")

tiempo_transcurrido = obtener_tiempo_transcurrido(tiempo_inicio) if tiempo_inicio else "?"
st.markdown(
    f"<p style='text-align: center; font-size: 14px;'>El panel se actualizará automáticamente cada 10 segundos. "
    f"Tiempo Transcurrido: {tiempo_transcurrido}</p>",
    unsafe_allow_html=True
)

# -------- OPERACIONES ABIERTAS: tabla + botón centrado y compacto --------
st.markdown("<h4 style='text-align: center;'>Operaciones abiertas</h4>", unsafe_allow_html=True)
operaciones_vivas = get_open_positions()

def color_fila_por_antiguedad(row):
    try:
        fecha = pd.to_datetime(row['Timestamp'])
        dias = (datetime.now() - fecha).days
        if dias <= 1:
            color = 'background-color: #d4edda;'
        elif dias < 3:
            color = 'background-color: #fff3cd;'
        else:
            color = 'background-color: #f8d7da;'
    except Exception:
        color = ''
    return [color] * len(row)

if not operaciones_vivas.empty:
    operaciones_vivas_display = operaciones_vivas.copy()
    operaciones_vivas_display['Timestamp'] = pd.to_datetime(operaciones_vivas_display['Timestamp'], errors='coerce')
    float_cols = operaciones_vivas_display.select_dtypes(include='float').columns
    format_dict = {col: "{:.4f}" for col in float_cols}
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
