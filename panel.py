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

# Estilo CSS personalizado
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: 700;
        text-align: center;
        margin-bottom: 1rem;
        color: #1E88E5;
    }
    .metric-card {
        background-color: #f8f9fa;
        border-radius: 10px;
        padding: 20px;
        box-shadow: 0 2px 5px rgba(0, 0, 0, 0.1);
    }
    .metric-value {
        font-size: 1.8rem;
        font-weight: 700;
    }
    .metric-label {
        font-size: 1rem;
        color: #6c757d;
    }
    .profit {
        color: #28a745;
    }
    .loss {
        color: #dc3545;
    }
    .info-text {
        background-color: #e3f2fd;
        padding: 10px;
        border-radius: 5px;
        font-size: 0.9rem;
    }
    .stTabs [data-baseweb="tab-list"] button [data-testid="stMarkdownContainer"] p {
        font-size: 1.2rem;
    }
    div[data-testid="stVerticalBlock"] div[style*="flex-direction: column;"] div[data-testid="stVerticalBlock"] {
        background-color: #f8f9fa;
        border-radius: 10px;
        padding: 1rem;
        margin-bottom: 0.5rem;
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

# Encabezado principal
st.markdown('<h1 class="main-header">📊 Monitor de Trading Hyperliquid</h1>', unsafe_allow_html=True)

# Mostrar hora de actualización
col_update, col_uptime = st.columns([3, 2])
with col_update:
    st.write(f"Actualización cada 30s | Tiempo activo: {tiempo_actividad_bot() if tiempo_actividad_bot() else 'N/A'}")

# Cargar configuración
config = cargar_configuracion()

# Mostrar métricas de configuración
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("TP", f"{config['atr_tp_mult']}×ATR", help="Multiplicador de ATR para el Take Profit")
    st.caption(f"(máx {config['max_tp_pct']*100}%)")
with col2:
    st.metric("SL", "NO", help="Sin Stop Loss automático")
with col3:
    st.metric("APALANCAMIENTO", f"{config['leverage']}×", help="Nivel de apalancamiento utilizado")
with col4:
    st.metric("MARGEN/TRADE", f"{config['margin_per_trade']}", help="Margen utilizado por operación")
    st.caption("USDT")

# Mostrar saldo
saldo_actual = obtener_saldo()
if saldo_actual is not None:
    st.markdown(f"<h2 style='text-align: center; color: #1E88E5;'>{formatear_numero(saldo_actual, 2)} USDT <span style='font-size: 0.8rem; color: gray;'>Saldo actual</span></h2>", unsafe_allow_html=True)
else:
    st.warning("No se pudo obtener el saldo actual.")

# Posiciones abiertas
st.header("Posiciones Abiertas")
try:
    posiciones = obtener_posiciones_hyperliquid()
    if not posiciones:
        st.info("🧙‍♂️ No hay operaciones abiertas en este momento.")
    else:
        # Crear una tabla con las posiciones
        tabla_data = []
        for pos in posiciones:
            pnl_class = "profit" if pos['unrealizedPnl'] >= 0 else "loss"
            pnl_formatted = formatear_numero(pos['unrealizedPnl'], 2)
            tabla_data.append({
                "Símbolo": pos['symbol'],
                "Dirección": pos['direction'],
                "Tamaño": formatear_numero(pos['size'], 1),
                "Precio Entrada": formatear_numero(pos['entryPrice'], 5),
                "PnL": f"<span class='{pnl_class}'>{pnl_formatted}</span>"
            })
        
        # Convertir a DataFrame y mostrar
        df = pd.DataFrame(tabla_data)
        st.write(df.to_html(escape=False, index=False), unsafe_allow_html=True)
except Exception as e:
    st.error(f"Error al obtener posiciones: {str(e)}")

# Pares disponibles
st.header("Pares Disponibles")
simbolos = obtener_simbolos_disponibles()
if simbolos:
    # Crear una visualización de botones para los símbolos
    num_cols = 5
    cols = st.columns(num_cols)
    for i, simbolo in enumerate(simbolos):
        with cols[i % num_cols]:
            st.button(simbolo, key=f"symbol_{simbolo}")
else:
    st.info("No se encontraron símbolos disponibles.")

# Historial de operaciones
st.header("Historial de Operaciones")
trades = obtener_historial_trades()
if trades:
    # Crear una tabla para el historial
    historial_data = []
    for trade in trades:
        fecha = datetime.fromisoformat(trade.get('fecha', '')) if 'fecha' in trade else datetime.now()
        pnl_class = "profit" if trade.get('pnl', 0) >= 0 else "loss"
        pnl_formatted = formatear_numero(trade.get('pnl', 0), 2)
        historial_data.append({
            "Fecha": fecha.strftime("%Y-%m-%d %H:%M"),
            "Símbolo": trade.get('symbol', ''),
            "Tipo": trade.get('tipo', ''),
            "Entrada": formatear_numero(trade.get('entry', 0), 5),
            "Salida": formatear_numero(trade.get('exit', 0), 5),
            "PnL": f"<span class='{pnl_class}'>{pnl_formatted}</span>"
        })
    
    # Convertir a DataFrame y mostrar
    df_hist = pd.DataFrame(historial_data)
    st.write(df_hist.to_html(escape=False, index=False), unsafe_allow_html=True)
else:
    st.info("No hay historial de operaciones disponible.")

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
