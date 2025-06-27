import streamlit as st
import os
import pandas as pd
import time
from datetime import datetime, timedelta
import json
from hyperliquid_client import HyperliquidClient

# Configuración de página Streamlit
st.set_page_config(
    page_title="Monitor Hyperliquid",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Estilo minimalista
st.markdown("""
<style>
    /* Reset y estilo general */
    .block-container {
        padding-top: 1rem;
        padding-bottom: 1rem;
    }
    h1 {
        font-size: 1.5rem;
        margin-bottom: 0.5rem;
    }
    h2 {
        font-size: 1.2rem;
        margin: 0.8rem 0 0.5rem 0;
    }
    .stMetric {
        background-color: #f8f9fa;
        padding: 5px 10px;
        border-radius: 5px;
        box-shadow: none;
        margin-bottom: 0;
    }
    
    /* Tablas compactas */
    .dataframe {
        font-size: 0.85rem;
    }
    .dataframe th {
        padding: 5px;
        font-size: 0.8rem;
        font-weight: 600;
    }
    .dataframe td {
        padding: 5px;
    }
    
    /* Colores para PnL */
    .profit { color: #28a745; }
    .loss { color: #dc3545; }
    
    /* Botones */
    .btn-close {
        background-color: #dc3545;
        color: white;
        border: none;
        border-radius: 3px;
        padding: 2px 5px;
        font-size: 0.75rem;
        cursor: pointer;
    }
    .btn-close:hover {
        background-color: #bd2130;
    }
    
    /* Estado en línea */
    .status-line {
        font-size: 0.8rem;
        color: #6c757d;
        margin-top: -5px;
        margin-bottom: 5px;
    }
    
    /* Contadores */
    .stat-container {
        display: flex;
        justify-content: space-between;
        margin-bottom: 10px;
        background-color: #f8f9fa;
        padding: 8px;
        border-radius: 5px;
    }
    .stat-item {
        text-align: center;
    }
    .stat-value {
        font-size: 1.2rem;
        font-weight: 600;
    }
    .stat-label {
        font-size: 0.7rem;
        color: #6c757d;
    }
    
    /* Mensajes */
    .msg {
        padding: 8px;
        border-radius: 4px;
        margin-bottom: 10px;
        font-size: 0.85rem;
    }
    .msg-success { background-color: #d4edda; color: #155724; }
    .msg-error { background-color: #f8d7da; color: #721c24; }
</style>
""", unsafe_allow_html=True)

# Inicializar cliente
client = HyperliquidClient()

# Funciones auxiliares
def obtener_saldo():
    """Obtiene el saldo actual de la cuenta"""
    try:
        if os.path.exists("ultimo_saldo.txt"):
            with open("ultimo_saldo.txt", "r") as f:
                return float(f.read().strip())
        
        # Respaldo API
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

def cargar_configuracion():
    """Carga la configuración básica"""
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
        return {"leverage": 10, "margin_per_trade": 100, "atr_tp_mult": 1.2, "max_tp_pct": 0.02}

def obtener_posiciones_hyperliquid():
    """Obtiene las posiciones abiertas en Hyperliquid"""
    try:
        account = client.get_account()
        if not account or "assetPositions" not in account:
            return []
        
        posiciones_abiertas = []
        for item in account["assetPositions"]:
            try:
                p = item['position'] if 'position' in item and isinstance(item['position'], dict) else item
                
                # Símbolo
                symbol = ""
                for key in ['coin', 'asset', 'symbol']:
                    if key in p:
                        symbol = p[key]
                        break
                if not symbol: continue
                
                # Tamaño
                if 'szi' not in p: continue
                position_size = float(p.get('szi', 0))
                if abs(position_size) < 0.0001: continue
                
                # Datos básicos
                entry_price = float(p.get('entryPx', 0))
                unrealized_pnl = float(p.get('unrealizedPnl', 0))
                direction = "LONG" if position_size > 0 else "SHORT"
                
                # Obtener precio actual para calcular liquidación
                precio_actual = None
                liquidation_price = None
                try:
                    ticker = client.get_price(symbol)
                    if ticker and 'mid' in ticker:
                        precio_actual = float(ticker['mid'])
                        
                        # Cálculo simplificado de liquidación (aproximado)
                        config = cargar_configuracion()
                        leverage = config["leverage"]
                        
                        # Para long: precio_entrada - precio_entrada/leverage
                        # Para short: precio_entrada + precio_entrada/leverage
                        if direction == "LONG":
                            liquidation_price = entry_price * (1 - 0.9/leverage)
                        else:
                            liquidation_price = entry_price * (1 + 0.9/leverage)
                except Exception:
                    pass
                
                # Calcular TP (según configuración)
                tp_price = None
                try:
                    config = cargar_configuracion()
                    atr_tp_mult = config["atr_tp_mult"]
                    max_tp_pct = config["max_tp_pct"]
                    
                    # Buscar si hay info de ATR guardada
                    if os.path.exists("trade_levels_atr.json"):
                        with open("trade_levels_atr.json", "r") as f:
                            niveles = json.load(f)
                            if symbol in niveles and "tp_fijo" in niveles[symbol]:
                                tp_price = niveles[symbol]["tp_fijo"]
                            else:
                                # TP estimado basado en la configuración
                                if direction == "LONG":
                                    tp_price = entry_price * (1 + max_tp_pct)
                                else:
                                    tp_price = entry_price * (1 - max_tp_pct)
                    else:
                        # TP estimado basado en la configuración
                        if direction == "LONG":
                            tp_price = entry_price * (1 + max_tp_pct)
                        else:
                            tp_price = entry_price * (1 - max_tp_pct)
                except Exception as e:
                    print(f"Error calculando TP: {e}")
                
                # Posición formateada
                posicion_formateada = {
                    'symbol': symbol,
                    'size': abs(position_size),
                    'entryPrice': entry_price,
                    'currentPrice': precio_actual,
                    'unrealizedPnl': unrealized_pnl,
                    'direction': direction,
                    'tp_price': tp_price,
                    'liquidation_price': liquidation_price,
                    'raw_position': position_size
                }
                posiciones_abiertas.append(posicion_formateada)
                
            except Exception as e:
                print(f"Error procesando posición: {e}")
                continue
        
        return posiciones_abiertas
    except Exception as e:
        print(f"Error al obtener posiciones: {e}")
        return []

def cerrar_posicion(symbol, position_amount):
    """Cierra una posición específica en Hyperliquid"""
    try:
        side = "sell" if float(position_amount) > 0 else "buy"
        quantity = abs(float(position_amount))
        
        # Ejecutar la orden
        for intento in range(1, 4):
            try:
                order = client.create_order(symbol=symbol, side=side, size=quantity)
                
                if order and "status" in order:
                    # Cancelar TP pendiente si existe
                    try:
                        if os.path.exists("tp_orders.json"):
                            with open("tp_orders.json", "r") as f:
                                tp_orders = json.load(f)
                            
                            if symbol in tp_orders and "order_id" in tp_orders[symbol]:
                                client.cancel_order(symbol=symbol, order_id=tp_orders[symbol]["order_id"])
                                del tp_orders[symbol]
                                with open("tp_orders.json", "w") as f:
                                    json.dump(tp_orders, f)
                    except Exception:
                        pass
                        
                    # Eliminar de trade_levels_atr.json
                    try:
                        if os.path.exists("trade_levels_atr.json"):
                            with open("trade_levels_atr.json", "r") as f:
                                niveles = json.load(f)
                            
                            if symbol in niveles:
                                del niveles[symbol]
                                with open("trade_levels_atr.json", "w") as f:
                                    json.dump(niveles, f)
                    except Exception:
                        pass
                        
                    return True, f"Posición {symbol} cerrada"
                else:
                    print(f"Intento {intento}/3: Error en respuesta")
            except Exception as e:
                print(f"Intento {intento}/3: Error: {e}")
                time.sleep(1)
        
        return False, f"Error al cerrar {symbol}"
    except Exception as e:
        return False, f"Error: {e}"

# Inicializar estados de sesión
if 'mensaje' not in st.session_state:
    st.session_state.mensaje = None
    st.session_state.tipo_mensaje = None

# Cabecera compacta
st.markdown("## 📊 Monitor Trading Hyperliquid")

# Info de estado y saldo - Todo en una línea
col_info1, col_info2, col_info3 = st.columns([1.5, 1, 1.5])
with col_info1:
    tiempo_activo = "N/A"
    try:
        if os.path.exists("tiempo_inicio_bot.txt"):
            with open("tiempo_inicio_bot.txt", "r") as f:
                inicio = datetime.fromisoformat(f.read().strip())
                tiempo_activo = str(datetime.now() - inicio).split('.')[0]
    except Exception:
        pass
    st.markdown(f"<div class='status-line'>⏱️ Activo: {tiempo_activo}</div>", unsafe_allow_html=True)

with col_info2:
    saldo_actual = obtener_saldo()
    if saldo_actual is not None:
        st.markdown(f"<div class='status-line'>💰 Saldo: <b>{saldo_actual:.2f} USDT</b></div>", unsafe_allow_html=True)
    else:
        st.markdown("<div class='status-line'>💰 Saldo: N/A</div>", unsafe_allow_html=True)

with col_info3:
    config = cargar_configuracion()
    st.markdown(f"<div class='status-line'>🔧 {config['leverage']}× | {config['margin_per_trade']} USDT | TP: {config['atr_tp_mult']}×ATR</div>", unsafe_allow_html=True)

# Mostrar mensajes si existen
if st.session_state.mensaje:
    msg_class = "msg msg-success" if st.session_state.tipo_mensaje == "success" else "msg msg-error"
    st.markdown(f'<div class="{msg_class}">{st.session_state.mensaje}</div>', unsafe_allow_html=True)
    st.session_state.mensaje = None
    st.session_state.tipo_mensaje = None

# Posiciones abiertas
st.markdown("### Posiciones Abiertas")

posiciones = obtener_posiciones_hyperliquid()
if not posiciones:
    st.info("🧙‍♂️ No hay operaciones abiertas.")
else:
    # Preparar datos en formato compacto y enfocado
    data = []
    for pos in posiciones:
        # Formatear datos
        pnl_class = "profit" if pos['unrealizedPnl'] > 0 else "loss"
        pnl_formatted = f"<span class='{pnl_class}'>{pos['unrealizedPnl']:.2f}</span>"
        
        # Clases para botón
        close_btn = f"<button class='btn-close' onclick=\"document.getElementById('btn_{pos['symbol']}').click()\">✖</button>"
        
        # Formatear TP y liquidación
        tp_price = pos.get('tp_price')
        liquidation_price = pos.get('liquidation_price')
        
        tp_formatted = f"{tp_price:.5f}" if tp_price is not None else "N/A"
        liq_formatted = f"{liquidation_price:.5f}" if liquidation_price is not None else "N/A"
        
        data.append({
            "Símbolo": pos['symbol'],
            "Dir": "L" if pos['direction'] == "LONG" else "S",
            "Tamaño": f"{pos['size']:.1f}",
            "Entry": f"{pos['entryPrice']:.5f}",
            "TP": tp_formatted,
            "Liq": liq_formatted,
            "PnL": pnl_formatted,
            "Acción": close_btn
        })
    
    # Convertir a DataFrame para mostrar
    df = pd.DataFrame(data)
    
    # Mostrar la tabla con datos
    st.write(df.to_html(escape=False, index=False), unsafe_allow_html=True)
    
    # Botones ocultos para cerrar posiciones (detrás de los botones visuales)
    for pos in posiciones:
        if st.button("Cerrar", key=f"btn_{pos['symbol']}", help=f"Cerrar posición {pos['direction']} en {pos['symbol']}", type="primary", use_container_width=True):
            with st.spinner(f"Cerrando {pos['symbol']}..."):
                success, mensaje = cerrar_posicion(pos['symbol'], pos['raw_position'])
                st.session_state.mensaje = mensaje
                st.session_state.tipo_mensaje = "success" if success else "error"
                time.sleep(1)  # Pequeña pausa para asegurar que la API procese la operación
                st.experimental_rerun()

# Pares disponibles (compactos)
simbolos = []
try:
    if os.path.exists("simbolos_disponibles.txt"):
        with open("simbolos_disponibles.txt", "r") as f:
            simbolos = f.read().strip().split(",")
except Exception:
    pass

if simbolos:
    st.markdown("### Pares Disponibles")
    # Mostrar símbolos en línea
    simbolos_texto = " ".join([f"`{s}`" for s in simbolos])
    st.markdown(simbolos_texto)

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
