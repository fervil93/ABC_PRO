"""
Script de prueba para consultar información real de PnL y detalles de operaciones
en Hyperliquid sin interferir con el bot principal.
"""

import time
import json
import logging
from datetime import datetime
from hyperliquid_client import HyperliquidClient

# Configurar logging
logging.basicConfig(
    filename='hl_pnl_test.log',
    level=logging.INFO,
    format='%(asctime)s %(levelname)s:%(message)s'
)

# Instanciar el cliente
client = HyperliquidClient()

def explorar_account_info():
    """Explora la respuesta completa de account para identificar donde se encuentra la información real"""
    try:
        print("\n--- EXPLORANDO INFORMACIÓN DE CUENTA ---")
        account = client.get_account()
        
        # Guardar la respuesta completa para análisis
        with open("account_response.json", "w") as f:
            json.dump(account, f, indent=2)
        print(f"Respuesta completa guardada en account_response.json")
        
        # Imprimir las claves principales
        print("\nClaves principales en account:")
        for key in account:
            print(f" - {key}")
            
        # Verificar secciones específicas que pueden contener datos de trades
        if "assetPositions" in account:
            print("\nEstructura de assetPositions:")
            for pos in account["assetPositions"][:1]:  # Solo la primera para ejemplo
                print(json.dumps(pos, indent=2))
                
        # Buscar cualquier clave relacionada con PnL o trades
        pnl_keys = [key for key in account if "pnl" in key.lower() or "trade" in key.lower()]
        if pnl_keys:
            print(f"\nClaves relacionadas con PnL encontradas: {pnl_keys}")
            for key in pnl_keys:
                print(f"{key}: {account[key]}")
        
        return account
    except Exception as e:
        logging.error(f"Error explorando account info: {e}", exc_info=True)
        print(f"Error: {e}")
        return None

def explorar_order_history():
    """Explora el historial de órdenes para ver si contiene información de PnL"""
    try:
        print("\n--- EXPLORANDO HISTORIAL DE ÓRDENES ---")
        
        # Intentar diferentes métodos que podrían existir
        methods = [
            {"name": "get_order_history", "args": []},
            {"name": "get_trades_history", "args": []},
            {"name": "get_orders", "args": [{"status": "FILLED"}]},
            {"name": "get_closed_positions", "args": []}
        ]
        
        for method in methods:
            try:
                method_name = method["name"]
                print(f"\nProbando método: {method_name}")
                
                if hasattr(client, method_name):
                    func = getattr(client, method_name)
                    result = func(*method["args"])
                    
                    # Guardar resultado
                    with open(f"{method_name}_response.json", "w") as f:
                        json.dump(result, f, indent=2)
                    print(f"Respuesta guardada en {method_name}_response.json")
                    
                    # Analizar resultado
                    if isinstance(result, list) and len(result) > 0:
                        print(f"Ejemplo de entrada (primera de {len(result)}):")
                        print(json.dumps(result[0], indent=2))
                else:
                    print(f"Método {method_name} no encontrado")
            except Exception as e:
                print(f"Error con método {method_name}: {e}")
    except Exception as e:
        logging.error(f"Error explorando historial: {e}", exc_info=True)
        print(f"Error general: {e}")

def explorar_metodos_disponibles():
    """Explora los métodos disponibles en el cliente para identificar posibles APIs útiles"""
    print("\n--- EXPLORANDO MÉTODOS DISPONIBLES ---")
    methods = [name for name in dir(client) if not name.startswith('_')]
    
    relevant_methods = [m for m in methods if any(term in m.lower() for term in 
                       ['trade', 'order', 'history', 'pnl', 'position', 'account', 'fill'])]
    
    print(f"Métodos potencialmente útiles ({len(relevant_methods)}):")
    for method in sorted(relevant_methods):
        print(f" - {method}")
    
    # Verificar si el cliente tiene un objeto exchange interno
    if hasattr(client, 'exchange'):
        exchange_methods = [name for name in dir(client.exchange) if not name.startswith('_')]
        relevant_exchange_methods = [m for m in exchange_methods if any(term in m.lower() for term in 
                                 ['trade', 'order', 'history', 'pnl', 'position', 'account', 'fill'])]
        
        print(f"\nMétodos potencialmente útiles en client.exchange ({len(relevant_exchange_methods)}):")
        for method in sorted(relevant_exchange_methods):
            print(f" - {method}")

def probar_metodo(method_name, *args, **kwargs):
    """Prueba un método específico y muestra su resultado"""
    try:
        print(f"\n--- PROBANDO MÉTODO: {method_name} ---")
        if hasattr(client, method_name):
            func = getattr(client, method_name)
            print(f"Ejecutando {method_name}({args}, {kwargs})...")
            result = func(*args, **kwargs)
            
            # Guardar e imprimir resultado
            with open(f"{method_name}_test_result.json", "w") as f:
                json.dump(result, f, indent=2)
            print(f"Resultado guardado en {method_name}_test_result.json")
            
            # Mostrar una vista resumida
            if isinstance(result, dict):
                print("\nClaves encontradas:")
                for key in result:
                    print(f" - {key}")
            elif isinstance(result, list) and len(result) > 0:
                print(f"\nLista con {len(result)} elementos. Primer elemento:")
                print(json.dumps(result[0], indent=2) if len(result) > 0 else "[]")
            else:
                print(f"\nResultado: {result}")
                
            return result
        else:
            print(f"Método {method_name} no disponible")
            return None
    except Exception as e:
        logging.error(f"Error probando {method_name}: {e}", exc_info=True)
        print(f"Error: {e}")
        return None

def calcular_pnl_realizado(symbol=None):
    """Intenta calcular el PnL realizado para un símbolo específico o para todos"""
    try:
        print("\n--- CALCULANDO PNL REALIZADO ---")
        
        # Intentar diferentes enfoques para obtener PnL realizado
        
        # 1. Verificar si hay método directo para PnL
        metodos_directos = [
            {"name": "get_pnl", "args": [symbol] if symbol else []},
            {"name": "get_realized_pnl", "args": [symbol] if symbol else []}
        ]
        
        for metodo in metodos_directos:
            if hasattr(client, metodo["name"]):
                print(f"Intentando método directo: {metodo['name']}")
                try:
                    result = getattr(client, metodo["name"])(*metodo["args"])
                    print(f"Resultado: {result}")
                    return result
                except Exception as e:
                    print(f"Error con método {metodo['name']}: {e}")
        
        # 2. Inferir de historial de trades si está disponible
        if hasattr(client, "get_trade_history"):
            print("Intentando inferir de historial de trades")
            try:
                trades = client.get_trade_history(symbol) if symbol else client.get_trade_history()
                
                # Mostrar resultados obtenidos
                print(f"Se obtuvieron {len(trades)} trades")
                if trades:
                    print("Ejemplo de trade:")
                    print(json.dumps(trades[0], indent=2))
                
                # Intentar agregar PnL
                pnl_total = 0
                for trade in trades:
                    if "pnl" in trade:
                        pnl_total += float(trade["pnl"])
                    elif "realizedPnl" in trade:
                        pnl_total += float(trade["realizedPnl"])
                
                print(f"PnL total calculado: {pnl_total}")
                return pnl_total
            except Exception as e:
                print(f"Error obteniendo historial de trades: {e}")
        
        # 3. Inferir de posiciones cerradas
        print("No se pudo calcular PnL realizado con los métodos disponibles")
        return None
        
    except Exception as e:
        logging.error(f"Error calculando PnL realizado: {e}", exc_info=True)
        print(f"Error general: {e}")
        return None

if __name__ == "__main__":
    print(f"Iniciando pruebas de Hyperliquid PnL a las {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Realizar pruebas exploratorias para identificar las capacidades de la API
    account_info = explorar_account_info()
    explorar_metodos_disponibles()
    explorar_order_history()
    
    # Probar métodos específicos que parezcan prometedores
    # (Descomentar y ajustar según los resultados de la exploración)
    # probar_metodo("get_account_history")
    # probar_metodo("get_fills")
    # probar_metodo("get_positions", {"symbol": "SOL"})
    
    # Intentar calcular PnL para algunos símbolos comunes
    for symbol in ["SOL", "BTC", "ETH"]:
        print(f"\nIntentando calcular PnL para {symbol}")
        calcular_pnl_realizado(symbol)
    
    print("\nFin de las pruebas")
