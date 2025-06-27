import streamlit as st
import requests
import time
import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import plotly.graph_objects as go
from hyperliquid_client import HyperliquidClient
import json

# Configuración de página Streamlit
st.set_page_config(
    page_title="Monitor de Trading Hyperliquid",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Estilo CSS personalizado con colores más atractivos y mejor formato
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: 700;
        text-align: center;
        margin-bottom: 1rem;
        color: #1E88E5;
    }
    .dashboard-card {
        background-color: #f8f9fa;
        border-radius: 10px;
        padding: 15px;
        margin: 10px 0px;
        box-shadow: 0 2px 5px rgba(0, 0, 0, 0.1);
    }
    .metric-value {
        font-size: 1.8rem;
        font-weight: 700;
    }
    .metric-label {
        font-size: 0.9rem;
        color: #6c757d;
        margin-top: -5px;
    }
    .profit {
        color: #28a745 !important;
    }
    .loss {
        color: #dc3545 !important;
    }
    .neutral {
        color: #6c757d !important;
    }
    .info-text {
        background-color: #e3f2fd;
        padding: 10px;
        border-radius: 5px;
        font-size: 0.9rem;
    }
    /* Estilos para tablas */
    .dataframe {
        width: 100%;
        border-collapse: collapse;
    }
    .dataframe th {
        background-color: #f1f3f5;
        color: #495057;
        font-weight: 600;
        text-align: left;
        padding: 12px 8px;
        border-bottom: 2px solid #dee2e6;
    }
    .dataframe td {
        padding: 12px 8px;
        border-bottom: 1px solid #dee2e6;
        font-size: 0.95rem;
    }
    .dataframe tr:nth-child(even) {
        background-color: #f8f9fa;
    }
    /* Estilos para botones de símbolos */
    div.row-widget.stButton {
        background-color: #f0f2f5;
        border-radius: 6px;
        padding: 0px;
        margin-bottom: 5px;
        transition: all 0.3s ease;
    }
    div.row-widget.stButton:hover {
        background-color: #e0e7ff;
        transform: scale(1.02);
    }
    div.row-widget.stButton > button {
        width: 100%;
        border: none;
        background: transparent;
        font-weight: 500;
        color: #444;
        padding: 5px 0px;
    }
    .status-badge {
        display: inline-block;
        padding: 3px 8px;
        font-size: 0.75rem;
        font-weight: 600;
        border-radius: 12px;
    }
    .badge-long {
        background-color: #d3f9d8;
        color: #0b7724;
    }
    .badge-short {
        background-color: #ffe3e3;
        color: #c92a2a;
    }
    .saldo-grande {
        font-size: 2.2rem;
        font-weight: 700;
        color: #1E88E5;
        text-align: center;
        margin: 15px 0;
    }
    .saldo-label {
        font-size: 0.9rem;
        color: #6c757d;
        text-align: center;
        margin-top: -10px;
    }
    /* Mejoras estéticas generales */
    h1, h2, h3, h4 {
        color: #333;
        margin-top: 20px;
        margin-bottom: 15px;
    }
    .section-container {
        padding: 5px;
        margin-bottom: 20px;
    }
</style>
""", unsafe_allow_html=True)

# Inicializar cliente de Hyperliquid
client = HyperliquidClient()

# Función para formatear números con separadores de miles
def formatear_numero(numero, decimales=2):
    if isinstance(numero, (int, float)):
        return f"{numero:,.{decimales}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return numero

# Función para obtener saldo actual
def obtener_saldo():
    try:
        # Intentar leer el saldo desde el archivo que actualiza el bot
        if os.path.exists("ultimo_saldo.txt"):
            with open("ultimo_saldo.txt", "r") as f:
                saldo = float(f.read().strip())
                return saldo
        
        # Si no hay archivo, intentar obtener directamente de la API
        account = client.get_account()
        if account:
            if "equity" in account:
                return float(account["equity"])
            elif "marginSummary" in account and "accountValue" in account["marginSummary"]:
                return float(account["marginSummary"]["accountValue"])
        
        return None
    except Exception as e:
        print(f"Error al obtener saldo: {e}")
        return None

# Función para obtener posiciones abiertas
def obtener_posiciones_hyperliquid():
    """
    Obtiene las posiciones abiertas en Hyperliquid y las formatea para uso del panel.
    Implementación robusta que maneja la estructura específica de la API de Hyperliquid.
    """
    try:
        account = client.get_account()
        
        # Verificar si tenemos la estructura esperada
        if not account or "assetPositions" not in account:
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
                        break
                
                if not symbol:
                    continue
                
                # Extraer el tamaño de la posición
                position_float = None
                if 'szi' in p:
                    try:
                        position_float = float(p['szi'])
                    except (ValueError, TypeError):
                        continue
                
                # Solo procesar posiciones no-cero
                if position_float is None or abs(position_float) < 0.0001:
                    continue
                
                # Extraer precio de entrada
                entry_price_float = 0
                if 'entryPx' in p:
                    try:
                        entry_price_float = float(p['entryPx'])
                    except (ValueError, TypeError):
                        pass
                
                # Extraer PnL
                unrealized_pnl_float = 0
                if 'unrealizedPnl' in p:
                    try:
                        unrealized_pnl_float = float(p['unrealizedPnl'])
                    except (ValueError, TypeError):
                        pass
                
                # Calcular dirección (long/short)
                direccion = "LONG" if position_float > 0 else "SHORT"
                
                # Crear una posición formateada
                posicion_formateada = {
                    'symbol': symbol,
                    'size': abs(position_float),
                    'entryPrice': entry_price_float,
                    'unrealizedPnl': unrealized_pnl_float,
                    'direction': direccion
                }
                posiciones_abiertas.append(posicion_formateada)
                
            except Exception as e:
                # Solo registrar error y continuar con la siguiente posición
                print(f"Error procesando posición: {e}")
                continue
        
        return posiciones_abiertas
    except Exception as e:
        # Registrar el error específico para depuración
        error_msg = f"Error al obtener posiciones: {str(e)}"
        print(error_msg)
        return []

# Función para obtener historial reciente de trades
def obtener_historial_trades(limit=10):
    try:
        trades = []
        if os.path.exists("historial_trades.json"):
            with open("historial_trades.json", "r") as f:
                trades = json.load(f)
        return trades[:limit]
    except Exception as e:
        print(f"Error al obtener historial de trades: {e}")
        return []

# Función para obtener símbolos disponibles
def obtener_simbolos_disponibles():
    try:
        if os.path.exists("simbolos_disponibles.txt"):
            with open("simbolos_disponibles.txt", "r") as f:
                return f.read().strip().split(",")
        return []
    except Exception as e:
        print(f"Error al obtener símbolos disponibles: {e}")
        return []

# Función para verificar tiempo de actividad del bot
def tiempo_actividad_bot():
    try:
        if os.path.exists("tiempo_inicio_bot.txt"):
            with open("tiempo_inicio_bot.txt", "r") as f:
                inicio = datetime.fromisoformat(f.read().strip())
                return datetime.now() - inicio
        return None
    except Exception as e:
        print(f"Error al calcular tiempo de actividad: {e}")
        return None

# Función para cargar configuración
def cargar_configuracion():
    try:
        from config import LEVERAGE, MARGIN_PER_TRADE, ATR_TP_MULT, MAX_TP_PCT
        return {
            "leverage": LEVERAGE,
            "margin_per_trade": MARGIN_PER_TRADE,
            "atr_tp_mult": ATR_TP_MULT,
            "max_tp_pct": MAX_TP_PCT
        }
    except Exception as e:
        print(f"Error al cargar configuración: {e}")
        return {
            "leverage": 10,
            "margin_per_trade": 100,
            "atr_tp_mult": 1.2,
            "max_tp_pct": 0.02
        }

# Función para dar formato a las tablas HTML
def formato_tabla_html(df, titulo_columnas=None):
    """
    Aplica estilos mejorados a un DataFrame y lo convierte a HTML
    """
    # Si se proporcionaron títulos de columnas personalizados
    if titulo_columnas:
        df.columns = titulo_columnas
    
    # Aplicar estilos según el tipo de datos (especialmente para PnL)
    styles = []
    for col in df.columns:
        if col in ['PnL', 'unrealizedPnl']:
            styles.append({
                'selector': f'td:nth-child({list(df.columns).index(col) + 1})',
                'props': [
                    ('color', lambda x: 'green' if x > 0 else 'red' if x < 0 else 'inherit')
                ]
            })
    
    # Convertir a HTML con estilos
    tabla_html = df.to_html(classes='dataframe', escape=False, index=False)
    return tabla_html

# Encabezado principal
st.markdown('<h1 class="main-header">📊 Monitor de Trading Hyperliquid</h1>', unsafe_allow_html=True)

# Mostrar hora de actualización
tiempo_activo = tiempo_actividad_bot() if tiempo_actividad_bot() else timedelta(0)
st.write(f"Actualización cada 30s | Tiempo activo: {str(tiempo_activo).split('.')[0]}")

# Cargar configuración
config = cargar_configuracion()

# Contenedor para métricas/configuración
with st.container():
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        with st.container():
            st.markdown('<div class="dashboard-card">', unsafe_allow_html=True)
            st.metric("TP", f"{config['atr_tp_mult']}×ATR")
            st.markdown(f'<div class="metric-label">(máx {config["max_tp_pct"]*100}%)</div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)
            
    with col2:
        with st.container():
            st.markdown('<div class="dashboard-card">', unsafe_allow_html=True)
            st.metric("SL", "NO")
            st.markdown('<div class="metric-label">Sin Stop Loss</div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)
            
    with col3:
        with st.container():
            st.markdown('<div class="dashboard-card">', unsafe_allow_html=True)
            st.metric("APALANCAMIENTO", f"{config['leverage']}×")
            st.markdown('<div class="metric-label">Nivel de apalancamiento</div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)
            
    with col4:
        with st.container():
            st.markdown('<div class="dashboard-card">', unsafe_allow_html=True)
            st.metric("MARGEN/TRADE", f"{config['margin_per_trade']}")
            st.markdown('<div class="metric-label">USDT</div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

# Mostrar saldo en formato grande y atractivo
saldo_actual = obtener_saldo()
if saldo_actual is not None:
    st.markdown(f'<div class="saldo-grande">{formatear_numero(saldo_actual, 2)} USDT</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="saldo-label">Saldo actual</div>', unsafe_allow_html=True)
else:
    st.warning("No se pudo obtener el saldo actual.")

# Posiciones abiertas
st.markdown('<div class="section-container">', unsafe_allow_html=True)
st.header("Posiciones Abiertas")

posiciones = obtener_posiciones_hyperliquid()
if not posiciones:
    st.info("🧙‍♂️ No hay operaciones abiertas en este momento.")
else:
    # Crear un DataFrame para mostrar las posiciones de manera más atractiva
    tabla_data = []
    for pos in posiciones:
        pnl_class = "profit" if pos['unrealizedPnl'] >= 0 else "loss"
        direccion_class = "badge-long" if pos['direction'] == "LONG" else "badge-short"
        
        tabla_data.append({
            "Símbolo": pos['symbol'],
            "Dirección": f'<span class="status-badge {direccion_class}">{pos["direction"]}</span>',
            "Tamaño": formatear_numero(pos['size'], 1),
            "Precio Entrada": formatear_numero(pos['entryPrice'], 5),
            "PnL": f'<span class="{pnl_class}">{formatear_numero(pos["unrealizedPnl"], 2)}</span>'
        })
    
    # Crear DataFrame y mostrar como tabla HTML estilizada
    df = pd.DataFrame(tabla_data)
    st.markdown(formato_tabla_html(df), unsafe_allow_html=True)

st.markdown('</div>', unsafe_allow_html=True)

# Pares disponibles
st.markdown('<div class="section-container">', unsafe_allow_html=True)
st.header("Pares Disponibles")
simbolos = obtener_simbolos_disponibles()

if simbolos:
    # Crear botones más atractivos para los símbolos
    # Determinar número de columnas según cantidad de símbolos
    num_simbolos = len(simbolos)
    num_cols = min(5, max(2, num_simbolos // 4 + 1))
    
    cols = st.columns(num_cols)
    for i, simbolo in enumerate(simbolos):
        with cols[i % num_cols]:
            st.button(simbolo, key=f"symbol_{simbolo}")
else:
    st.info("No se encontraron símbolos disponibles.")
st.markdown('</div>', unsafe_allow_html=True)

# Historial de operaciones
st.markdown('<div class="section-container">', unsafe_allow_html=True)
st.header("Historial de Operaciones")

trades = obtener_historial_trades()
if trades:
    # Crear una tabla para el historial
    historial_data = []
    for trade in trades:
        fecha = datetime.fromisoformat(trade.get('fecha', '')) if 'fecha' in trade else datetime.now()
        pnl_class = "profit" if trade.get('pnl', 0) >= 0 else "loss"
        pnl_formatted = formatear_numero(trade.get('pnl', 0), 2)
        tipo_class = "badge-long" if trade.get('tipo', '').upper() == "BUY" else "badge-short"
        
        historial_data.append({
            "Fecha": fecha.strftime("%Y-%m-%d %H:%M"),
            "Símbolo": trade.get('symbol', ''),
            "Tipo": f'<span class="status-badge {tipo_class}">{trade.get("tipo", "").upper()}</span>',
            "Entrada": formatear_numero(trade.get('entry', 0), 5),
            "Salida": formatear_numero(trade.get('exit', 0), 5),
            "PnL": f'<span class="{pnl_class}">{pnl_formatted}</span>'
        })
    
    # Convertir a DataFrame y mostrar
    df_hist = pd.DataFrame(historial_data)
    st.markdown(formato_tabla_html(df_hist), unsafe_allow_html=True)
else:
    st.info("No hay historial de operaciones disponible.")
st.markdown('</div>', unsafe_allow_html=True)

# Función para actualizar automáticamente la página
st.markdown(
    """
    <script>
        function updatePage() {
            window.location.reload();
        }
        setTimeout(updatePage, 30000);
    </script>
    """,
    unsafe_allow_html=True
)
