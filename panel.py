import streamlit as st
import pandas as pd
import time
import os
import json
import matplotlib.pyplot as plt
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
        flex-wrap: wrap;
    }
    .status-item {
        flex: 1; 
        text-align: center;
        padding: 0 15px;
        min-width: 150px;
    }
    .symbol-badge {
        background-color: #e9ecef;
        padding: 3px 6px;
        border-radius: 4px;
        font-size: 0.7rem;
        font-family: monospace;
        margin: 0 1px;
        display: inline-block;
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
    
    /* Botones más pequeños y en línea */
    .close-buttons-row {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        justify-content: center;
        margin-bottom: 15px;
    }
    
    /* Hacer que los botones de Streamlit sean más pequeños y aparezcan en línea */
    .stButton > button {
        font-size: 0.8rem !important;
        padding: 0.2rem 0.5rem !important;
        height: auto !important;
        min-height: 0 !important;
        margin: 0 3px !important;
        flex-shrink: 1;
        white-space: nowrap;
    }
    /* Hacer que los botones se muestren en línea */
    .row-of-buttons .stButton {
        display: inline-block !important;
        margin: 0 2px !important;
        width: auto !important;
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
    
    /* Métricas destacadas */
    .metric-container {
        display: flex;
        justify-content: center;
        gap: 20px;
        background-color: #f8f9fa;
        padding: 15px;
        border-radius: 5px;
        margin-bottom: 20px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }
    .metric {
        text-align: center;
        flex: 1;
    }
    .metric-title {
        font-size: 0.9rem;
        color: #6c757d;
    }
    .metric-value {
        font-size: 1.5rem;
        font-weight: 600;
    }
    .metric-value.positive {
        color: #28a745;
    }
    .metric-value.negative {
        color: #dc3545;
    }
    
    /* Tabs centradas */
    .stTabs [data-baseweb="tab-list"] {
        gap: 24px;
        justify-content: center;
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        white-space: pre-wrap;
        background-color: #f8f9fa;
        border-radius: 4px;
        padding: 10px 16px;
        font-weight: 600;
    }
    .stTabs [aria-selected="true"] {
        background-color: #e9ecef;
        border-bottom: 2px solid #0066cc;
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
    st.session_state.tab_activa = "monitor"

# Configuración de auto-refresh (5 segundos)
AUTO_REFRESH_SECONDS = 5

# Constante para archivo de historial
PNL_HISTORY_FILE = "pnl_history.csv"

# Archivos de niveles TP
TP_ORDERS_FILE = "tp_orders.json"
ATR_LEVELS_FILE = "trade_levels_atr.json"

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

# Función para cargar símbolos disponibles
def cargar_simbolos_disponibles():
    try:
        if os.path.exists("simbolos_disponibles.txt"):
            with open("simbolos_disponibles.txt", "r") as f:
                return f.read().strip().split(",")
        return []
    except Exception:
        return []

# Función para cargar niveles TP
def cargar_niveles_tp():
    try:
        niveles_tp = {}
        
        # Intentar cargar desde tp_orders.json
        if os.path.exists(TP_ORDERS_FILE):
            with open(TP_ORDERS_FILE, "r") as f:
                tp_orders = json.load(f)
                for symbol, data in tp_orders.items():
                    niveles_tp[symbol] = data.get("price", 0)
        
        # Si no hay datos o faltan símbolos, intentar con trade_levels_atr.json
        if os.path.exists(ATR_LEVELS_FILE):
            with open(ATR_LEVELS_FILE, "r") as f:
                atr_levels = json.load(f)
                for symbol, data in atr_levels.items():
                    if symbol not in niveles_tp and "tp_fijo" in data:
                        niveles_tp[symbol] = data.get("tp_fijo", 0)
                        
        return niveles_tp
    except Exception as e:
        print(f"Error al cargar niveles TP: {e}")
        return {}

# Función para obtener el precio actual de un símbolo
def obtener_precio_actual(symbol):
    try:
        precio = client.get_price(symbol)
        if precio and "mid" in precio:
            return float(precio["mid"])
        return None
    except Exception as e:
        print(f"Error obteniendo precio para {symbol}: {e}")
        return None

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

# Función para cargar datos de historial
@st.cache_data(ttl=300)  # Cachear por 5 minutos
def cargar_datos_historial():
    if not os.path.exists(PNL_HISTORY_FILE):
        return pd.DataFrame()
    
    try:
        df = pd.read_csv(PNL_HISTORY_FILE)
        
        # Convertir timestamp a datetime
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        # Convertir tiempo_abierto a timedelta cuando no es N/A
        def parse_tiempo(t):
            if t == 'N/A':
                return pd.NaT
            try:
                parts = t.split(':')
                if len(parts) == 3:
                    h, m, s = map(int, parts)
                    return timedelta(hours=h, minutes=m, seconds=s)
                return pd.NaT
            except:
                return pd.NaT
        
        df['tiempo_abierto_td'] = df['tiempo_abierto'].apply(parse_tiempo)
        
        # Convertir pnl_real a float
        df['pnl_real'] = pd.to_numeric(df['pnl_real'], errors='coerce')
        
        return df
    except Exception as e:
        print(f"Error al cargar datos de historial: {e}")
        return pd.DataFrame()

# Encabezado
st.markdown("<h1>📊 Monitor Trading Hyperliquid</h1>", unsafe_allow_html=True)

# Mostrar el tiempo de la última actualización
ultima_act = st.session_state.ultima_actualizacion.strftime("%H:%M:%S")
st.markdown(f"<p class='refresh-note'>Última actualización: {ultima_act}</p>", unsafe_allow_html=True)

# Crear tabs para separar monitor y estadísticas
tab1, tab2 = st.tabs(["📊 Monitor", "📈 Estadísticas"])

# Tab 1: Monitor de trading
with tab1:
    # Obtener datos de Hyperliquid
    datos = obtener_datos_hyperliquid()
    saldo = datos['saldo']
    posiciones = datos['posiciones']
    
    # Cargar niveles TP
    niveles_tp = cargar_niveles_tp()
    
    # Información de tiempo activo
    tiempo_activo = "N/A"
    try:
        if os.path.exists("tiempo_inicio_bot.txt"):
            with open("tiempo_inicio_bot.txt", "r") as f:
                inicio = datetime.fromisoformat(f.read().strip())
                tiempo_activo = str(datetime.now() - inicio).split('.')[0]
    except Exception:
        pass
    
    # Cargar símbolos disponibles
    simbolos = cargar_simbolos_disponibles()
    simbolos_count = len(simbolos)
    simbolos_html = ""
    if simbolos:
        simbolos_html = "".join([f'<span class="symbol-badge">{s}</span>' for s in simbolos])
    
    # Barra de estado con pares disponibles integrados
    saldo_texto = f"{saldo:.2f} USDT" if saldo is not None else "N/A USDT"
    st.markdown(
        f"""
        <div class="status-line">
            <div class="status-item">⏱️ Activo: <strong>{tiempo_activo}</strong></div>
            <div class="status-item">💰 Saldo: <strong>{saldo_texto}</strong></div>
            <div class="status-item">📊 Pares: {simbolos_html or "N/A"}</div>
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
            symbol = pos['symbol']
            precio_actual = obtener_precio_actual(symbol)
            
            # Formatear PnL
            pnl_class = "profit" if pos['unrealizedPnl'] > 0 else ("loss" if pos['unrealizedPnl'] < 0 else "")
            pnl_formatted = f"<span class='{pnl_class}'>{pos['unrealizedPnl']:.2f}</span>"
            
            # Formatear liquidación
            liq = "N/A"
            if pos.get('liquidation_price'):
                liq = f"{pos['liquidation_price']:.2f}"
            
            # Obtener nivel de TP
            tp_price = niveles_tp.get(symbol, "N/A")
            
            # Calcular distancia al TP
            pct_al_tp = "N/A"
            if tp_price != "N/A" and precio_actual:
                if pos['direction'] == "LONG":  # LONG
                    pct_al_tp = (float(tp_price) - precio_actual) / precio_actual * 100
                else:  # SHORT
                    pct_al_tp = (precio_actual - float(tp_price)) / precio_actual * 100
                
                # Formatear con color según cercanía al TP
                pct_class = "profit" if pct_al_tp < 0.5 else ""
                pct_al_tp = f"<span class='{pct_class}'>{pct_al_tp:.2f}%</span>"
                
            data.append({
                "Símbolo": symbol,
                "Dirección": pos['direction'],
                "Tamaño": f"{pos['size']:.1f}",
                "Precio Entrada": f"{pos['entryPrice']:.2f}",
                "Precio Actual": f"{precio_actual:.2f}" if precio_actual else "N/A",
                "Take Profit": f"{float(tp_price):.2f}" if tp_price != "N/A" else "N/A",
                "% al TP": pct_al_tp,
                "PnL": pnl_formatted,
            })
        
        # Convertir a DataFrame
        df = pd.DataFrame(data)
        
        # Mostrar tabla
        st.write(df.to_html(escape=False, index=False), unsafe_allow_html=True)
        
        # Botones para cerrar posiciones - En una sola fila
        st.markdown("<h3>Cerrar posiciones</h3>", unsafe_allow_html=True)
        
        # Usar columnas para alinear los botones en una fila
        st.markdown('<div class="row-of-buttons" style="text-align: center;">', unsafe_allow_html=True)
        
        # Crear botones en línea
        for i, pos in enumerate(posiciones):
            # Crear el botón para cerrar la posición
            if st.button(f"Cerrar {pos['symbol']} ({pos['direction']})", key=f"btn_{pos['symbol']}"):
                with st.spinner(f"Cerrando {pos['symbol']}..."):
                    success, mensaje = cerrar_posicion(pos['symbol'], pos['raw_position'])
                    st.session_state.mensaje = mensaje
                    st.session_state.tipo_mensaje = "success" if success else "error"
                    time.sleep(1)
                    st.rerun()
        
        # Cerrar el div de los botones
        st.markdown('</div>', unsafe_allow_html=True)

# Tab 2: Estadísticas
with tab2:
    # Cargar datos de historial
    df = cargar_datos_historial()
    
    if df.empty:
        st.warning("No hay datos de historial disponibles.")
    else:
        # Filtros
        col1, col2, col3 = st.columns(3)
        
        # Filtro de fechas
        with col1:
            fecha_min = df['timestamp'].min().date()
            fecha_max = df['timestamp'].max().date()
            
            fecha_inicio = st.date_input("Desde:", fecha_min, min_value=fecha_min, max_value=fecha_max)
            fecha_fin = st.date_input("Hasta:", fecha_max, min_value=fecha_min, max_value=fecha_max)
        
        # Filtros de símbolo y dirección
        with col2:
            simbolos = ['Todos'] + sorted(df['symbol'].unique().tolist())
            simbolo_seleccionado = st.selectbox("Símbolo:", simbolos)
        
        with col3:
            direcciones = ['Todas', 'BUY', 'SELL']
            direccion_seleccionada = st.selectbox("Dirección:", direcciones)
        
        # Aplicar filtros
        df_filtrado = df.copy()
        
        # Filtro de fechas
        df_filtrado = df_filtrado[(df_filtrado['timestamp'].dt.date >= fecha_inicio) & 
                                 (df_filtrado['timestamp'].dt.date <= fecha_fin)]
        
        # Filtro de símbolo
        if simbolo_seleccionado != 'Todos':
            df_filtrado = df_filtrado[df_filtrado['symbol'] == simbolo_seleccionado]
        
        # Filtro de dirección
        if direccion_seleccionada != 'Todas':
            df_filtrado = df_filtrado[df_filtrado['direccion'] == direccion_seleccionada]
        
        # Métricas principales
        total_trades = len(df_filtrado)
        pnl_total = df_filtrado['pnl_real'].sum()
        trades_ganadores = len(df_filtrado[df_filtrado['pnl_real'] > 0])
        trades_perdedores = len(df_filtrado[df_filtrado['pnl_real'] < 0])
        
        winrate = (trades_ganadores / total_trades * 100) if total_trades > 0 else 0
        
        # Mostrar métricas
        st.markdown(
            f"""
            <div class="metric-container">
                <div class="metric">
                    <div class="metric-title">Total Trades</div>
                    <div class="metric-value">{total_trades}</div>
                </div>
                <div class="metric">
                    <div class="metric-title">PnL Total</div>
                    <div class="metric-value {'positive' if pnl_total >= 0 else 'negative'}">{pnl_total:.2f} USDT</div>
                </div>
                <div class="metric">
                    <div class="metric-title">Winrate</div>
                    <div class="metric-value {'positive' if winrate >= 50 else 'negative'}">{winrate:.1f}%</div>
                </div>
                <div class="metric">
                    <div class="metric-title">Ganadores/Perdedores</div>
                    <div class="metric-value">{trades_ganadores}/{trades_perdedores}</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )
        
        # Gráficos
        st.markdown("<h3>Análisis de PnL</h3>", unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Gráfico de PnL acumulado
            if not df_filtrado.empty:
                df_acum = df_filtrado.sort_values('timestamp')
                df_acum['pnl_acumulado'] = df_acum['pnl_real'].cumsum()
                
                fig_acum = plt.figure(figsize=(8, 4))
                plt.plot(df_acum['timestamp'], df_acum['pnl_acumulado'], marker='o', markersize=3)
                plt.grid(True, alpha=0.3)
                plt.title('PnL Acumulado')
                plt.xticks(rotation=45)
                plt.tight_layout()
                st.pyplot(fig_acum)
        
        with col2:
            # Distribución de PnL
            fig_dist = plt.figure(figsize=(8, 4))
            plt.hist(df_filtrado['pnl_real'], bins=20, color='skyblue', edgecolor='black')
            plt.grid(True, alpha=0.3)
            plt.title('Distribución de PnL')
            plt.axvline(0, color='red', linestyle='--')
            plt.tight_layout()
            st.pyplot(fig_dist)
        
        # Análisis por símbolo
        st.markdown("<h3>Análisis por Símbolo</h3>", unsafe_allow_html=True)
        
        # Agrupar por símbolo
        if not df_filtrado.empty:
            simbolo_stats = df_filtrado.groupby('symbol').agg(
                trades=('symbol', 'count'),
                pnl_total=('pnl_real', 'sum'),
                pnl_medio=('pnl_real', 'mean'),
                pnl_max=('pnl_real', 'max'),
                pnl_min=('pnl_real', 'min'),
                ganadores=('pnl_real', lambda x: (x > 0).sum()),
                tiempo_medio=('tiempo_abierto_td', lambda x: x.mean())
            ).reset_index()
            
            # Calcular winrate
            simbolo_stats['winrate'] = (simbolo_stats['ganadores'] / simbolo_stats['trades']) * 100
            
            # Formatear tiempo medio
            simbolo_stats['tiempo_medio_fmt'] = simbolo_stats['tiempo_medio'].apply(
                lambda x: str(x).split('.')[0] if pd.notna(x) else 'N/A'
            )
            
            # Mostrar tabla
            simbolo_stats_display = simbolo_stats[['symbol', 'trades', 'pnl_total', 'pnl_medio', 'winrate', 'tiempo_medio_fmt']]
            simbolo_stats_display.columns = ['Símbolo', 'Trades', 'PnL Total', 'PnL Medio', 'Winrate %', 'Tiempo Medio']
            
            # Formatear números
            simbolo_stats_display['PnL Total'] = simbolo_stats_display['PnL Total'].apply(lambda x: f"{x:.2f}")
            simbolo_stats_display['PnL Medio'] = simbolo_stats_display['PnL Medio'].apply(lambda x: f"{x:.2f}")
            simbolo_stats_display['Winrate %'] = simbolo_stats_display['Winrate %'].apply(lambda x: f"{x:.1f}%")
            
            st.write(simbolo_stats_display.to_html(index=False, escape=False), unsafe_allow_html=True)
            
            # Gráfico de PnL por símbolo
            fig_simbolos = plt.figure(figsize=(10, 5))
            plt.bar(simbolo_stats['symbol'], simbolo_stats['pnl_total'])
            plt.grid(True, alpha=0.3, axis='y')
            plt.title('PnL Total por Símbolo')
            plt.xticks(rotation=45)
            plt.tight_layout()
            st.pyplot(fig_simbolos)
        
        # Historial completo
        st.markdown("<h3>Historial Detallado</h3>", unsafe_allow_html=True)
        
        if st.checkbox("Mostrar historial completo"):
            # Preparar datos para mostrar
            display_df = df_filtrado.copy()
            display_df['timestamp'] = display_df['timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S')
            
            # Formatear PnL para colorearlo
            def format_pnl(pnl):
                pnl_class = 'profit' if float(pnl) > 0 else ('loss' if float(pnl) < 0 else '')
                return f'<span class="{pnl_class}">{float(pnl):.2f}</span>'
            
            display_df['pnl_formatted'] = display_df['pnl_real'].apply(format_pnl)
            
            # Formatear precios con menos decimales
            display_df['precio_entrada'] = display_df['precio_entrada'].apply(lambda x: f"{float(x):.2f}")
            display_df['precio_salida'] = display_df['precio_salida'].apply(lambda x: f"{float(x):.2f}")
            
            # Seleccionar y renombrar columnas
            display_df = display_df[['timestamp', 'symbol', 'direccion', 'precio_entrada', 
                                    'precio_salida', 'pnl_formatted', 'tiempo_abierto', 'razon_cierre']]
            display_df.columns = ['Fecha/Hora', 'Símbolo', 'Dirección', 'Precio Entrada', 
                                 'Precio Salida', 'PnL', 'Tiempo Abierto', 'Razón Cierre']
            
            # Mostrar tabla
            st.write(display_df.to_html(escape=False, index=False), unsafe_allow_html=True)

# Mostrar mensaje de actualización
st.markdown(f'<p class="refresh-note">Actualizando automáticamente cada {AUTO_REFRESH_SECONDS} segundos...</p>', unsafe_allow_html=True)

# Esperar AUTO_REFRESH_SECONDS antes de actualizar
time.sleep(AUTO_REFRESH_SECONDS)

# Una vez completado el tiempo, actualizar la página
st.session_state.ultima_actualizacion = datetime.now()
st.rerun()
