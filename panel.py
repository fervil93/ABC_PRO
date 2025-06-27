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

# Estilos CSS simples
st.markdown("""
<style>
    /* Estilos generales */
    .block-container {padding-top: 1rem; padding-bottom: 1rem;}
    h1 {font-size: 1.5rem; margin-bottom: 0.5rem;}
    
    /* Tabla más compacta */
    .dataframe {width: 100%; font-size: 0.9rem;}
    .dataframe th {background-color: #f1f3f5; text-align: left; padding: 5px;}
    .dataframe td {padding: 5px;}
    
    /* Colores para PnL */
    .profit {color: #28a745;}
    .loss {color: #dc3545;}
    
    /* Barra de estado */
    .status-line {
        display: flex;
        justify-content: space-between;
        background-color: #f8f9fa;
        padding: 8px;
        border-radius: 5px;
        margin-bottom: 15px;
        font-size: 0.85rem;
    }
    .status-item {flex: 1; text-align: center;}
    
    /* Mensaje */
    .mensaje {
        padding: 8px;
        border-radius: 5px;
        margin-bottom: 10px;
        font-size: 0.9rem;
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
        
        # Obtener configuración desde la API si está disponible
        config = {}
        try:
            # Intentar obtener desde la API - simulado
            pass
        except Exception:
            # Valores por defecto básicos (mínimo)
            config = {"leverage": "N/A", "margin_per_trade": "N/A"}
        
        return {
            'saldo': saldo,
            'posiciones': posiciones,
            'config': config
        }
    except Exception as e:
        st.error(f"Error al obtener datos de Hyperliquid: {e}")
        return {'saldo': None, 'posiciones': [], 'config': {}}

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
st.markdown("## 📊 Monitor Trading Hyperliquid")

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
st.markdown(
    f"""
    <div class="status-line">
        <div class="status-item">⏱️ Activo: <strong>{tiempo_activo}</strong></div>
        <div class="status-item">💰 Saldo: <strong>{saldo:.2f if saldo else 'N/A'} USDT</strong></div>
        <div class="status-item">⚙️ Configuración desde archivo config.py</div>
    </div>
    """,
    unsafe_allow_html=True
)

# Mostrar mensajes si hay
if st.session_state.mensaje:
    msg_class = "mensaje" + (" profit" if st.session_state.tipo_mensaje == "success" else " loss")
    st.markdown(
        f'<div class="{msg_class}">{st.session_state.mensaje}</div>',
        unsafe_allow_html=True
    )
    st.session_state.mensaje = None
    st.session_state.tipo_mensaje = None

# Posiciones abiertas
st.markdown("### Posiciones Abiertas")

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
    
    # Botones para cerrar posiciones
    st.write("### Cerrar posiciones")
    
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
                    st.experimental_rerun()

# Pares disponibles (simple)
st.markdown("### Pares Disponibles")
simbolos = []
try:
    if os.path.exists("simbolos_disponibles.txt"):
        with open("simbolos_disponibles.txt", "r") as f:
            simbolos = f.read().strip().split(",")
except Exception:
    pass

if simbolos:
    st.write(" | ".join([f"`{s}`" for s in simbolos]))
else:
    st.info("No hay pares disponibles.")

# Auto-actualización
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
