import streamlit as st
import os
import pandas as pd
import time
from datetime import datetime, timedelta
import json
from hyperliquid_client import HyperliquidClient

# Configuración de página Streamlit
st.set_page_config(
    page_title="Monitor de Trading Hyperliquid",
    page_icon="📈",
    layout="wide"
)

# Estilos CSS simplificados y eficaces
st.markdown("""
<style>
    /* Estilos generales */
    .main-header {
        font-size: 2rem;
        font-weight: 700;
        text-align: center;
        margin-bottom: 1rem;
        color: #1E88E5;
    }
    
    /* Estilos para métricas */
    .metric-container {
        background-color: #f8f9fa;
        border-radius: 8px;
        padding: 15px;
        margin-bottom: 10px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }
    
    /* Estilos para valores de PnL */
    .profit {
        color: #28a745;
        font-weight: 600;
    }
    .loss {
        color: #dc3545;
        font-weight: 600;
    }
    
    /* Estilos para badges */
    .badge {
        padding: 3px 8px;
        border-radius: 4px;
        font-size: 0.8rem;
        font-weight: 600;
    }
    .long-badge {
        background-color: rgba(40, 167, 69, 0.2);
        color: #28a745;
    }
    .short-badge {
        background-color: rgba(220, 53, 69, 0.2);
        color: #dc3545;
    }
    
    /* Estilos para saldo */
    .saldo-grande {
        font-size: 2rem;
        font-weight: 700;
        color: #1E88E5;
        text-align: center;
        margin: 20px 0 5px 0;
    }
    .saldo-label {
        font-size: 0.9rem;
        color: #6c757d;
        text-align: center;
        margin-bottom: 20px;
    }
    
    /* Estilos para mensajes */
    .success-msg {
        background-color: #d4edda;
        color: #155724;
        padding: 10px;
        border-radius: 4px;
        margin-bottom: 15px;
    }
    .error-msg {
        background-color: #f8d7da;
        color: #721c24;
        padding: 10px;
        border-radius: 4px;
        margin-bottom: 15px;
    }
</style>
""", unsafe_allow_html=True)

# Inicializar cliente Hyperliquid
client = HyperliquidClient()

# Funciones básicas
def cargar_configuracion():
    """Carga la configuración desde el archivo config.py"""
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

def obtener_saldo():
    """Obtiene el saldo actual de la cuenta"""
    try:
        if os.path.exists("ultimo_saldo.txt"):
            with open("ultimo_saldo.txt", "r") as f:
                saldo = float(f.read().strip())
                return saldo
        
        # Intentar obtener directamente de la API como respaldo
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

def obtener_posiciones_hyperliquid():
    """Obtiene las posiciones abiertas en Hyperliquid"""
    try:
        account = client.get_account()
        
        if not account or "assetPositions" not in account:
            return []
        
        posiciones_abiertas = []
        
        for item in account["assetPositions"]:
            try:
                # Extraer datos de la posición
                p = item['position'] if 'position' in item and isinstance(item['position'], dict) else item
                
                # Obtener símbolo
                symbol = ""
                for key in ['coin', 'asset', 'symbol']:
                    if key in p:
                        symbol = p[key]
                        break
                
                if not symbol:
                    continue
                
                # Obtener tamaño de posición
                position_size = None
                if 'szi' in p:
                    try:
                        position_size = float(p['szi'])
                    except (ValueError, TypeError):
                        continue
                
                # Solo procesar posiciones no-cero
                if position_size is None or abs(position_size) < 0.0001:
                    continue
                
                # Extraer precio de entrada
                entry_price = 0
                if 'entryPx' in p:
                    try:
                        entry_price = float(p['entryPx'])
                    except (ValueError, TypeError):
                        pass
                
                # Extraer PnL
                unrealized_pnl = 0
                if 'unrealizedPnl' in p:
                    try:
                        unrealized_pnl = float(p['unrealizedPnl'])
                    except (ValueError, TypeError):
                        pass
                
                # Crear objeto de posición
                posicion_formateada = {
                    'symbol': symbol,
                    'size': abs(position_size),
                    'entryPrice': entry_price,
                    'unrealizedPnl': unrealized_pnl,
                    'direction': "LONG" if position_size > 0 else "SHORT",
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

def obtener_simbolos_disponibles():
    """Obtiene la lista de símbolos disponibles para operar"""
    try:
        if os.path.exists("simbolos_disponibles.txt"):
            with open("simbolos_disponibles.txt", "r") as f:
                return f.read().strip().split(",")
        return []
    except Exception as e:
        print(f"Error al obtener símbolos disponibles: {e}")
        return []

def obtener_historial_trades(limit=10):
    """Obtiene el historial reciente de trades"""
    try:
        if os.path.exists("historial_trades.json"):
            with open("historial_trades.json", "r") as f:
                trades = json.load(f)
                return trades[:limit]
        return []
    except Exception as e:
        print(f"Error al obtener historial de trades: {e}")
        return []

def tiempo_actividad_bot():
    """Calcula el tiempo de actividad del bot"""
    try:
        if os.path.exists("tiempo_inicio_bot.txt"):
            with open("tiempo_inicio_bot.txt", "r") as f:
                inicio = datetime.fromisoformat(f.read().strip())
                return datetime.now() - inicio
        return None
    except Exception as e:
        print(f"Error al calcular tiempo de actividad: {e}")
        return None

def cerrar_posicion(symbol, position_amount):
    """Cierra una posición específica en Hyperliquid"""
    try:
        # Determinar el lado (compra/venta) según la dirección de la posición
        side = "sell" if float(position_amount) > 0 else "buy"
        quantity = abs(float(position_amount))
        
        # Ejecutar la orden para cerrar la posición
        for intento in range(1, 4):  # Máximo 3 intentos
            try:
                order = client.create_order(symbol=symbol, side=side, size=quantity)
                
                if order and "status" in order:
                    print(f"Posición cerrada para {symbol}: {order}")
                    
                    # Cancelar también cualquier orden TP pendiente
                    try:
                        if os.path.exists("tp_orders.json"):
                            with open("tp_orders.json", "r") as f:
                                tp_orders = json.load(f)
                            
                            if symbol in tp_orders and "order_id" in tp_orders[symbol]:
                                client.cancel_order(symbol=symbol, order_id=tp_orders[symbol]["order_id"])
                                print(f"Orden TP cancelada para {symbol}")
                                
                                # Eliminar del archivo
                                del tp_orders[symbol]
                                with open("tp_orders.json", "w") as f:
                                    json.dump(tp_orders, f)
                    except Exception as e:
                        print(f"Error cancelando orden TP: {e}")
                        
                    return True, f"Posición cerrada para {symbol}"
                else:
                    print(f"Intento {intento}/3: Error en respuesta al cerrar posición para {symbol}")
            except Exception as e:
                print(f"Intento {intento}/3: Error al cerrar posición para {symbol}: {e}")
                time.sleep(1)  # Esperar antes de reintentar
        
        return False, f"Error al cerrar posición para {symbol} después de varios intentos"
    except Exception as e:
        return False, f"Error al cerrar posición para {symbol}: {e}"

# Inicializar estados de sesión
if 'mensaje' not in st.session_state:
    st.session_state.mensaje = None
    st.session_state.tipo_mensaje = None
    st.session_state.procesando_cierre = False

# Encabezado principal
st.markdown('<h1 class="main-header">📊 Monitor de Trading Hyperliquid</h1>', unsafe_allow_html=True)

# Mostrar hora de actualización
tiempo_activo = tiempo_actividad_bot() if tiempo_actividad_bot() else timedelta(0)
st.write(f"Actualización cada 30s | Tiempo activo: {str(tiempo_activo).split('.')[0]}")

# Cargar configuración
config = cargar_configuracion()

# Mostrar métricas de configuración (simplificadas)
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

# Mostrar saldo actual
saldo_actual = obtener_saldo()
if saldo_actual is not None:
    st.markdown(f'<div class="saldo-grande">{saldo_actual:.2f} USDT</div><div class="saldo-label">Saldo actual</div>', unsafe_allow_html=True)
else:
    st.warning("No se pudo obtener el saldo actual.")

# Mostrar mensajes (éxito/error)
if st.session_state.mensaje:
    msg_class = "success-msg" if st.session_state.tipo_mensaje == "success" else "error-msg"
    st.markdown(f'<div class="{msg_class}">{st.session_state.mensaje}</div>', unsafe_allow_html=True)
    # Reset mensaje después de mostrarlo una vez
    st.session_state.mensaje = None
    st.session_state.tipo_mensaje = None

# Posiciones abiertas
st.header("Posiciones Abiertas")

posiciones = obtener_posiciones_hyperliquid()
if not posiciones:
    st.info("🧙‍♂️ No hay operaciones abiertas en este momento.")
else:
    # Crear DataFrame con las posiciones
    data = []
    for pos in posiciones:
        data.append({
            "Símbolo": pos['symbol'],
            "Dirección": pos['direction'],
            "Tamaño": f"{pos['size']:.1f}",
            "Precio Entrada": f"{pos['entryPrice']:.5f}",
            "PnL": f"{pos['unrealizedPnl']:.2f}",
            "raw_position": pos['raw_position']
        })
    
    df = pd.DataFrame(data)
    
    # Crear tabla sin la columna raw_position
    tabla_display = df.drop(columns=['raw_position'])
    
    # Función para aplicar formato condicional a las celdas
    def highlight_direccion(val):
        if val == 'LONG':
            return 'background-color: rgba(40, 167, 69, 0.2); color: #28a745; font-weight: 600'
        elif val == 'SHORT':
            return 'background-color: rgba(220, 53, 69, 0.2); color: #dc3545; font-weight: 600'
        return ''
    
    def highlight_pnl(val):
        try:
            num = float(val)
            if num > 0:
                return 'color: #28a745; font-weight: 600'
            elif num < 0:
                return 'color: #dc3545; font-weight: 600'
        except:
            pass
        return ''
    
    # Aplicar formato condicional
    tabla_formateada = tabla_display.style.applymap(highlight_direccion, subset=['Dirección']).applymap(highlight_pnl, subset=['PnL'])
    
    # Mostrar tabla de posiciones
    st.dataframe(tabla_formateada, use_container_width=True)
    
    # Botones para cerrar posiciones
    st.write("Selecciona una posición para cerrar:")
    for i, pos in enumerate(posiciones):
        if st.button(f"Cerrar {pos['symbol']} ({pos['direction']})", key=f"btn_close_{pos['symbol']}"):
            with st.spinner(f"Cerrando posición {pos['symbol']}..."):
                success, mensaje = cerrar_posicion(pos['symbol'], pos['raw_position'])
                st.session_state.mensaje = mensaje
                st.session_state.tipo_mensaje = "success" if success else "error"
                st.experimental_rerun()

# Pares disponibles
st.header("Pares Disponibles")
simbolos = obtener_simbolos_disponibles()
if simbolos:
    # Mostrar chips o badges para los símbolos
    chunks = [simbolos[i:i+5] for i in range(0, len(simbolos), 5)]
    for chunk in chunks:
        cols = st.columns(5)
        for i, simbolo in enumerate(chunk):
            cols[i].write(f"**{simbolo}**")
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
        historial_data.append({
            "Fecha": fecha.strftime("%Y-%m-%d %H:%M"),
            "Símbolo": trade.get('symbol', ''),
            "Tipo": trade.get('tipo', '').upper(),
            "Entrada": f"{trade.get('entry', 0):.5f}",
            "Salida": f"{trade.get('exit', 0):.5f}",
            "PnL": f"{trade.get('pnl', 0):.2f}"
        })
    
    # Convertir a DataFrame
    df_hist = pd.DataFrame(historial_data)
    
    # Función para aplicar formato condicional a las celdas
    def highlight_tipo(val):
        if val == 'BUY':
            return 'background-color: rgba(40, 167, 69, 0.2); color: #28a745; font-weight: 600'
        elif val == 'SELL':
            return 'background-color: rgba(220, 53, 69, 0.2); color: #dc3545; font-weight: 600'
        return ''
    
    def highlight_pnl_hist(val):
        try:
            num = float(val)
            if num > 0:
                return 'color: #28a745; font-weight: 600'
            elif num < 0:
                return 'color: #dc3545; font-weight: 600'
        except:
            pass
        return ''
    
    # Aplicar formato condicional
    historial_formateado = df_hist.style.applymap(highlight_tipo, subset=['Tipo']).applymap(highlight_pnl_hist, subset=['PnL'])
    
    # Mostrar historial
    st.dataframe(historial_formateado, use_container_width=True)
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
