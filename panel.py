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
        posiciones = client.get_account().get("assetPositions", [])
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

def close_all_positions():
    try:
        posiciones = client.get_account().get("assetPositions", [])
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
        posiciones = client.get_account().get("assetPositions", [])
        abiertas = [p for p in posiciones if float(p.get('position', 0)) != 0]
        niveles_atr = leer_niveles_atr()
        rows = []
        
        for p in abiertas:
            symbol = p['asset']
            qty = float(p.get('position', 0))
            entry = float(p.get('entryPrice', 0))
            direction = "long" if qty > 0 else "short"
            pnl = float(p.get('unrealizedPnl', 0))
            
            # Hyperliquid no proporciona timestamp de actualización como Binance,
            # usaremos la hora actual
            ts = datetime.now()
            
            # Obtener precio actual
            precio_ticker = client.get_price(symbol)
            precio_actual = float(precio_ticker.get('mid', 0)) if precio_ticker else 0
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

def get_trade_fills():
    try:
        # Hyperliquid no tiene un endpoint directo para el historial de trades como Binance
        # Usaremos el historial de órdenes como aproximación
        # Esto es una adaptación simplificada, la API real puede requerir ajustes
        
        trade_history = client.get_fill_history()  # Función que necesitarías implementar
        rows = []
        
        # Esta es una estructura sugerida; ajústala según la respuesta real de la API
        for t in trade_history:
            symbol = t.get('coin', '')  # El nombre del activo en Hyperliquid
            side = "long" if t.get('side') == "buy" else "short"
            qty = float(t.get('size', 0))
            price = float(t.get('price', 0))
            fee = float(t.get('fee', 0))
            realized_pnl = float(t.get('pnl', 0))
            timestamp = datetime.fromtimestamp(int(t.get('time', 0)) / 1000)
            order_id = t.get('orderHash', '')
            time_str = timestamp.strftime('%Y-%m-%d %H:%M:%S')
            margin_used = (qty * price) / LEVERAGE  # Ajustado por el apalancamiento
            
            rows.append({
                "Order ID": order_id,
                "Par": symbol,
                "Acción": side,
                "Precio": price,
                "Volumen": qty,
                "Fee": fee,
                "PnL": realized_pnl,
                "time": time_str,
                "Margen usado": margin_used,
                "_fecha_real": timestamp
            })
            
        df = pd.DataFrame(rows)
        if not df.empty:
            df = df.sort_values(by="_fecha_real", ascending=False).reset_index(drop=True)
        return df
    except Exception as e:
        st.error(f"Error obteniendo historial de trades: {e}")
        return pd.DataFrame()

def saldo_inicio_bot(fills, balance_inicial=0, tiempo_inicio=None):
    if tiempo_inicio is None or fills.empty:
        return balance_inicial
    primer_fill = fills[fills['_fecha_real'] >= tiempo_inicio].head(1)
    if not primer_fill.empty:
        return balance_inicial
    return balance_inicial

def generar_grafico_balance_acumulado(fills, balance_inicial=0, tiempo_inicio=None):
    if tiempo_inicio is None or fills.empty or '_fecha_real' not in fills.columns or 'PnL' not in fills.columns or 'Fee' not in fills.columns:
        fig, ax = plt.subplots(figsize=(9, 2))
        ax.set_xlabel("") 
        ax.set_ylabel("Balance ($)", fontsize=9)
        ax.grid()
        fig.tight_layout()
        return fig

    fills = fills[fills['_fecha_real'] >= tiempo_inicio]
    fills = fills.sort_values(by="_fecha_real", ascending=True).reset_index(drop=True)

    balances = [saldo_inicio_bot(fills, balance_inicial, tiempo_inicio)]
    fechas = []

    for _, row in fills.iterrows():
        if pd.notnull(row['_fecha_real']) and pd.notnull(row['PnL']) and pd.notnull(row['Fee']):
            if row['PnL'] == 0:
                nuevo_balance = balances[-1] - row['Fee']
            else:
                nuevo_balance = balances[-1] + row['PnL']
            balances.append(nuevo_balance)
            fechas.append(row['_fecha_real'])

    if not fechas or len(balances) <= 1:
        fig, ax = plt.subplots(figsize=(9, 2))
        ax.set_xlabel("")
        ax.set_ylabel("Balance ($)", fontsize=9)
        ax.grid()
        fig.tight_layout()
        return fig

    fig, ax = plt.subplots(figsize=(9, 2))
    ax.plot(fechas, [round(b, 4) for b in balances[1:]], color="blue", marker="o")
    ax.set_xlabel("") 
    ax.set_ylabel("Balance ($)", fontsize=9)
    ax.grid(True, linestyle='--', alpha=0.5)

    # Cambios aquí: eje X diario
    ax.xaxis.set_major_locator(mdates.DayLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))

    plt.xticks(rotation=25, fontsize=7)
    plt.yticks(fontsize=9)
    fig.tight_layout(pad=0.3)
    return fig

def obtener_tiempo_transcurrido(tiempo_inicio):
    tiempo_actual = datetime.now()
    tiempo_transcurrido = tiempo_actual - tiempo_inicio
    horas, resto = divmod(tiempo_transcurrido.seconds, 3600)
    minutos, segundos = divmod(resto, 60)
    return f"{tiempo_transcurrido.days}d {horas}h {minutos}m {segundos}s"

def calcular_pnl_diario(fills, tiempo_inicio=None):
    """Devuelve un DataFrame con el PNL neto por día (desde tiempo_inicio si se indica)."""
    if tiempo_inicio is not None:
        fills = fills[fills['_fecha_real'] >= tiempo_inicio]
    if fills.empty:
        return pd.DataFrame(columns=["Fecha", "PNL Neto"])
    fills = fills.copy()
    fills["Fecha"] = fills["_fecha_real"].dt.date
    fills["PNL Neto"] = fills["PnL"].fillna(0)  # ya incluye fees negativos
    pnl_diario = fills.groupby("Fecha")["PNL Neto"].sum().reset_index()
    pnl_diario["PNL Neto"] = pnl_diario["PNL Neto"].round(4)

    # Incluir todos los días desde tiempo_inicio hasta hoy
    fecha_inicio = tiempo_inicio.date() if tiempo_inicio else fills["Fecha"].min()
    fecha_fin = datetime.now().date()
    fechas_todas = pd.date_range(fecha_inicio, fecha_fin, freq="D")
    df_fechas = pd.DataFrame({"Fecha": fechas_todas.date})
    pnl_diario = df_fechas.merge(pnl_diario, on="Fecha", how="left").fillna(0)
    pnl_diario["PNL Neto"] = pnl_diario["PNL Neto"].round(4)
    return pnl_diario

# Obtener el saldo de la cuenta
def get_account_balance():
    try:
        account = client.get_account()
        if account and "equity" in account:
            return float(account["equity"])
        return 0
    except Exception as e:
        st.error(f"Error obteniendo saldo: {e}")
        return 0

balance_inicial = get_account_balance()

# --- AUTORREFRESCO SEGURO ---
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

# ----------- OBTENER FILLS Y GENERAR GRÁFICO -----------
fills = get_trade_fills()

# ----------- MODIFICACIÓN: FILTRAR FILLS DESDE ARRANQUE Y MOSTRARLO EN EL TÍTULO -----------
if tiempo_inicio and not fills.empty:
    fills = fills[fills['_fecha_real'] >= tiempo_inicio]
    balance_msg = "<h4 style='text-align: center;'>Balance acumulado desde arranque</h4>"
    fills_title = "<h4 style='text-align: center;'>Fills (Trade History) desde arranque</h4>"
else:
    balance_msg = "<h4 style='text-align: center;'>Balance acumulado</h4>"
    fills_title = "<h4 style='text-align: center;'>Fills (Trade History)</h4>"

if not fills.empty:
    st.markdown(balance_msg, unsafe_allow_html=True)
    grafico_balance = generar_grafico_balance_acumulado(
        fills, balance_inicial=balance_inicial, tiempo_inicio=tiempo_inicio
    )
    if grafico_balance:
        st.pyplot(grafico_balance)
        plt.close(grafico_balance)
    else:
        st.warning("No se pudo generar el gráfico de balance acumulado.")
else:
    st.info("No hay fills/trades registrados para calcular el balance acumulado.")

# -------- PNL DIARIO --------
if not fills.empty:
    st.markdown("<h4 style='text-align: center;'>PNL neto por día</h4>", unsafe_allow_html=True)
    pnl_diario = calcular_pnl_diario(fills, tiempo_inicio=tiempo_inicio)
    st.dataframe(
        pnl_diario.style.map(lambda x: 'color: green;' if x > 0 else ('color: red;' if x < 0 else ''), subset=["PNL Neto"]),
        use_container_width=True,
        hide_index=True
    )

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

# -------- HISTORIAL DE FILLS DESDE ARRANQUE --------
st.markdown(fills_title, unsafe_allow_html=True)

if not fills.empty:
    float_cols = fills.select_dtypes(include='float').columns
    format_dict = {col: "{:.8f}" for col in float_cols}
    def color_pnl_fills(val):
        color = 'green' if val > 0 else 'red' if val < 0 else 'black'
        return f'color: {color};'

    columnas_a_mostrar = ["Order ID", "Par", "Acción", "Precio", "Volumen", "Fee", "PnL", "time", "Margen usado"]
    if len(fills) > 0:
        st.dataframe(
            fills[columnas_a_mostrar].style.format(format_dict).map(color_pnl_fills, subset=["PnL"]),
            use_container_width=True,
            hide_index=True
        )
else:
    st.info("No hay fills/trades registrados.")

# Sección para los símbolos disponibles
st.markdown("<h4 style='text-align: center;'>Símbolos disponibles para operar</h4>", unsafe_allow_html=True)

# Leer la lista de símbolos desde un archivo
def leer_simbolos_disponibles():
    try:
        with open("ultima_verificacion_simbolos.txt") as f:
            ultima_verificacion = datetime.fromisoformat(f.read().strip())
            
            # Lista de símbolos (puedes adaptar esto para leer desde un archivo)
            simbolos = client.get_exchange_config().get("universe", [])
            st.markdown(f"<p style='text-align: center;'>Última verificación: {ultima_verificacion.strftime('%Y-%m-%d %H:%M:%S')}</p>", unsafe_allow_html=True)
            return simbolos
    except Exception as e:
        st.warning(f"No se pudo obtener la lista de símbolos disponibles: {e}")
        return []

simbolos = leer_simbolos_disponibles()
if simbolos:
    # Crear una tabla con los símbolos disponibles
    cols = st.columns(4)
    for i, symbol in enumerate(simbolos):
        cols[i % 4].write(f"✅ {symbol}")
else:
    st.warning("No se encontró información sobre símbolos disponibles.")
