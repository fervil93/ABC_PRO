import streamlit as st
import pandas as pd
import time
import os
from datetime import datetime, timedelta
from hyperliquid_client import HyperliquidClient

# Configuración de página
st.set_page_config(
    page_title="Monitor Hyperliquid",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Estilos CSS mejorados con texto centrado y títulos consistentes
st.markdown("""
<style>
    /* Estilos generales y centrado */
    .block-container {
        padding-top: 1rem; 
        padding-bottom: 1rem;
        max-width: 1200px !important;
        margin-left: auto !important;
        margin-right: auto !important;
    }
    
    /* Centrar todo el texto por defecto */
    body {
        text-align: center !important;
    }
    
    /* Tamaños de título consistentes */
    h1, h2, h3, h4, h5, h6 {
        text-align: center !important;
        font-size: 1.1rem !important;
        margin-top: 1rem !important;
        margin-bottom: 0.5rem !important;
        font-weight: 600 !important;
    }
    
    /* Título principal un poco más grande */
    h1 {
        font-size: 1.3rem !important;
        margin-bottom: 1rem !important;
    }
    
    /* Párrafos centrados */
    p {
        text-align: center !important;
    }
    
    /* Información y mensajes centrados */
    .stAlert {
        text-align: center !important;
    }
    
    /* Tabla más profesional y centrada */
    .dataframe {
        width: 100%; 
        font-size: 1rem;
        border-collapse: collapse;
        margin-left: auto !important;
        margin-right: auto !important;
    }
    .dataframe th {
        background-color: #f1f3f5; 
        text-align: center !important; 
        padding: 8px;
        border-bottom: 2px solid #dee2e6;
        font-weight: 600;
    }
    .dataframe td {
        padding: 8px;
        border-bottom: 1px solid #e9ecef;
        text-align: center !important;
    }
    .dataframe tr:hover {
        background-color: #f8f9fa;
    }
    
    /* Colores para PnL */
    .profit {color: #28a745; font-weight: 600;}
    .loss {color: #dc3545; font-weight: 600;}
    
    /* Barra de estado centrada */
    .status-line {
        display: flex;
        justify-content: center;
        background-color: #f8f9fa;
        padding: 10px;
        border-radius: 5px;
        margin-bottom: 20px;
        font-size: 1rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        text-align: center;
    }
    .status-item {
        flex: 1; 
        text-align: center;
        padding: 0 20px;
    }
    
    /* Config-Box centrado */
    .config-box {
        background-color: #f8f9fa;
        padding: 12px;
        border-radius: 5px;
        margin-bottom: 20px;
        font-size: 1rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        text-align: center;
    }
    .config-item {
        display: inline-block;
        margin-right: 20px;
        text-align: center;
    }
    .config-value {
        font-weight: 600;
    }
    
    /* Mensaje centrado */
    .mensaje {
        padding: 10px;
        border-radius: 5px;
        margin-bottom: 15px;
        font-size: 1rem;
        text-align: center;
    }
    .mensaje.success {
        background-color: #d4edda; 
        color: #155724;
        border-left: 5px solid #28a745;
    }
    .mensaje.error {
        background-color: #f8d7da; 
        color: #721c24;
        border-left: 5px solid #dc3545;
    }
    
    /* Símbolos disponibles centrados */
    .symbol-container {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        justify-content: center;
    }
    .symbol-badge {
        background-color: #e9ecef;
        padding: 5px 10px;
        border-radius: 4px;
        font-size: 0.9rem;
        font-family: monospace;
    }
    
    /* Botones más visibles y centrados */
    .stButton > button {
        font-size: 1rem;
        padding: 0.5rem 1rem;
        width: 100%;
    }
    
    /* Nota de actualización */
    .refresh-note {
        text-align: center;
        font-size: 0.8rem;
        color: #6c757d;
        margin-top: 20px;
    }
    
    /* Hacer que la barra de recarga sea menos visible */
    .stProgress > div > div {
        background-color: #f8f9fa !important;
    }
</style>
""", unsafe_allow_html=True)

# Cliente Hyperliquid
@st.cache_resource
def get_client():
    return HyperliquidClient()

client = get_client()

# Inicializar estados de sesión
if 'mensaje' not in st.session_state:
    st.session_state.mensaje = None
    st.session_state.tipo_mensaje = None
    st.session_state.ultima_actualizacion = datetime.now()

# Configuración de auto-refresh (5 segundos)
AUTO_REFRESH_SECONDS = 5

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

# Función para obtener datos directamente de Hyperliquid
def obtener_datos_hyperliquid():
    try:
        # Obtener cuenta/posiciones
        account = client.get_account()
        
        # Extraer saldo
        saldo = None
        if account:
            if "equity" in account:
                saldo = float(account["equity"])
            elif "marginSummary" in account and "accountValue" in account["marginSummary"]:
                saldo = float(account["marginSummary"]["accountValue"])
        
        # Extraer posiciones
        posiciones = []
        if account and "assetPositions" in account:
            for item in account["assetPositions"]:
                try:
                    p = item['position'] if 'position' in item and isinstance(item['position'], dict) else item
                    
                    # Extraer símbolo
                    symbol = ""
                    for key in ['coin', 'asset', 'symbol']:
                        if key in p:
                            symbol = p[key]
                            break
                    if not symbol: continue
                    
                    # Extraer tamaño
                    if 'szi' not in p: continue
                    position_size = float(p.get('szi', 0))
                    if abs(position_size) < 0.0001: continue
                    
                    # Extraer datos principales
                    entry_price = float(p.get('entryPx', 0))
                    unrealized_pnl = float(p.get('unrealizedPnl', 0))
                    direction = "LONG" if position_size > 0 else "SHORT"
                    
                    # Si hay datos de liquidación y TP en la API, usarlos
                    liq_price = None
                    if 'liquidationPx' in p:
                        try:
                            liq_price = float(p['liquidationPx'])
                        except (ValueError, TypeError):
                            pass
                            
                    # Añadir la posición formateada
                    posiciones.append({
                        'symbol': symbol,
                        'direction': direction,
                        'size': abs(position_size),
                        'entryPrice': entry_price,
                        'unrealizedPnl': unrealized_pnl,
                        'liquidation_price': liq_price,
                        'raw_position': position_size
                    })
                except Exception as e:
                    print(f"Error procesando posición: {e}")
                    continue
        
        return {
            'saldo': saldo,
            'posiciones': posiciones
        }
    except Exception as e:
        st.error(f"Error al obtener datos de Hyperliquid: {e}")
        return {'saldo': None, 'posiciones': []}

# Función para cerrar posición
def cerrar_posicion(symbol, position_amount):
    try:
        side = "sell" if float(position_amount) > 0 else "buy"
        quantity = abs(float(position_amount))
        
        order = client.create_order(symbol=symbol, side=side, size=quantity)
        
        if order and "status" in order:
            return True, f"Posición {symbol} cerrada"
        else:
            return False, f"Error al cerrar {symbol}"
    except Exception as e:
        return False, f"Error: {e}"

# Encabezado
st.markdown("<h1>📊 Monitor Trading Hyperliquid</h1>", unsafe_allow_html=True)

# Mostrar el tiempo de la última actualización
ultima_act = st.session_state.ultima_actualizacion.strftime("%H:%M:%S")
st.markdown(f"<p class='refresh-note'>Última actualización: {ultima_act}</p>", unsafe_allow_html=True)

# Crear barra de progreso para el refresh
progress_bar = st.progress(0)

# Obtener datos de Hyperliquid
datos = obtener_datos_hyperliquid()
saldo = datos['saldo']
posiciones = datos['posiciones']

# Información de tiempo activo
tiempo_activo = "N/A"
try:
    if os.path.exists("tiempo_inicio_bot.txt"):
        with open("tiempo_inicio_bot.txt", "r") as f:
            inicio = datetime.fromisoformat(f.read().strip())
            tiempo_activo = str(datetime.now() - inicio).split('.')[0]
except Exception:
    pass

# Barra de estado
saldo_texto = f"{saldo:.2f} USDT" if saldo is not None else "N/A USDT"
st.markdown(
    f"""
    <div class="status-line">
        <div class="status-item">⏱️ Activo: <strong>{tiempo_activo}</strong></div>
        <div class="status-item">💰 Saldo: <strong>{saldo_texto}</strong></div>
    </div>
    """,
    unsafe_allow_html=True
)

# Mostrar configuración desde config.py
config = cargar_configuracion()
st.markdown(
    f"""
    <div class="config-box">
        <div class="config-item">🔧 Apalancamiento: <span class="config-value">{config['leverage']}×</span></div>
        <div class="config-item">💵 Margen por trade: <span class="config-value">{config['margin_per_trade']} USDT</span></div>
        <div class="config-item">📈 Take Profit: <span class="config-value">{config['atr_tp_mult']}×ATR</span></div>
        <div class="config-item">🔒 TP Máx: <span class="config-value">{config['max_tp_pct']*100}%</span></div>
    </div>
    """,
    unsafe_allow_html=True
)

# Mostrar mensajes si hay
if st.session_state.mensaje:
    msg_class = f"mensaje {'success' if st.session_state.tipo_mensaje == 'success' else 'error'}"
    st.markdown(
        f'<div class="{msg_class}">{st.session_state.mensaje}</div>',
        unsafe_allow_html=True
    )
    st.session_state.mensaje = None
    st.session_state.tipo_mensaje = None

# Posiciones abiertas - Todos los títulos ahora tienen el mismo tamaño
st.markdown("<h3>Posiciones Abiertas</h3>", unsafe_allow_html=True)

if not posiciones:
    st.info("🧙‍♂️ No hay operaciones abiertas.")
else:
    # Crear datos para la tabla
    data = []
    for pos in posiciones:
        # Formatear PnL
        pnl_class = "profit" if pos['unrealizedPnl'] > 0 else ("loss" if pos['unrealizedPnl'] < 0 else "")
        pnl_formatted = f"<span class='{pnl_class}'>{pos['unrealizedPnl']:.2f}</span>"
        
        # Formatear liquidación
        liq = "N/A"
        if pos.get('liquidation_price'):
            liq = f"{pos['liquidation_price']:.5f}"
            
        data.append({
            "Símbolo": pos['symbol'],
            "Dirección": pos['direction'],
            "Tamaño": f"{pos['size']:.1f}",
            "Precio Entrada": f"{pos['entryPrice']:.5f}",
            "Liquidación": liq,
            "PnL": pnl_formatted,
        })
    
    # Convertir a DataFrame
    df = pd.DataFrame(data)
    
    # Mostrar tabla
    st.write(df.to_html(escape=False, index=False), unsafe_allow_html=True)
    
    # Botones para cerrar posiciones - Ahora con h3 consistente
    st.markdown("<h3>Cerrar posiciones</h3>", unsafe_allow_html=True)
    
    # Crear dos columnas para mostrar botones en filas de a pares
    num_columns = 2
    cols = st.columns(num_columns)
    
    for i, pos in enumerate(posiciones):
        col_index = i % num_columns
        with cols[col_index]:
            if st.button(f"Cerrar {pos['symbol']} ({pos['direction']})", key=f"btn_{pos['symbol']}"):
                with st.spinner(f"Cerrando {pos['symbol']}..."):
                    success, mensaje = cerrar_posicion(pos['symbol'], pos['raw_position'])
                    st.session_state.mensaje = mensaje
                    st.session_state.tipo_mensaje = "success" if success else "error"
                    time.sleep(1)  # Pequeña pausa
                    st.rerun()  # Correcto en versiones recientes de Streamlit

# Pares disponibles (simple) - Ahora con h3 consistente
st.markdown("<h3>Pares Disponibles</h3>", unsafe_allow_html=True)
simbolos = []
try:
    if os.path.exists("simbolos_disponibles.txt"):
        with open("simbolos_disponibles.txt", "r") as f:
            simbolos = f.read().strip().split(",")
except Exception:
    pass

if simbolos:
    simbolos_html = "".join([f'<span class="symbol-badge">{s}</span>' for s in simbolos])
    st.markdown(f'<div class="symbol-container">{simbolos_html}</div>', unsafe_allow_html=True)
else:
    st.info("No hay pares disponibles.")

# Mostrar mensaje de actualización
st.markdown(f'<p class="refresh-note">Actualizando automáticamente cada {AUTO_REFRESH_SECONDS} segundos...</p>', unsafe_allow_html=True)

# Actualizar la página automáticamente usando método nativo de Streamlit
# En lugar de usar JavaScript, usamos un bucle con time.sleep
for i in range(AUTO_REFRESH_SECONDS * 10):
    # Actualizar barra de progreso
    progress_percent = i / (AUTO_REFRESH_SECONDS * 10)
    progress_bar.progress(progress_percent)
    time.sleep(0.1)

# Una vez completada la barra, actualizar la página
st.session_state.ultima_actualizacion = datetime.now()
st.rerun()
