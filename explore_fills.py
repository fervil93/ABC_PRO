"""
Script para explorar los endpoints de User Fills en Hyperliquid
"""
import json
import time
from hyperliquid_client import HyperliquidClient

client = HyperliquidClient()

def explore_user_fills():
    """Explora los endpoints de fills disponibles en la API"""
    try:
        # Intentar acceder a fills a través de diferentes métodos posibles
        methods_to_try = [
            # Método tradicional REST
            lambda: client.get_user_fills() if hasattr(client, 'get_user_fills') else None,
            
            # Explorar si hay un método websocket
            lambda: client.ws_get_fills() if hasattr(client, 'ws_get_fills') else None,
            
            # Explorar si hay un método para fills recientes
            lambda: client.get_recent_fills() if hasattr(client, 'get_recent_fills') else None,
            
            # Intentar acceder directamente a través de un endpoint REST
            lambda: client.get('https://api.hyperliquid.xyz/info') if hasattr(client, 'get') else None,
            
            # Explorar si hay métodos específicos para PnL
            lambda: client.get_pnl_history() if hasattr(client, 'get_pnl_history') else None,
        ]
        
        results = []
        for i, method in enumerate(methods_to_try):
            print(f"Probando método {i+1}...")
            try:
                result = method()
                if result:
                    print(f"¡Éxito! Método {i+1} devolvió datos")
                    results.append(result)
                    
                    # Guardar los resultados para análisis
                    with open(f"fill_method_{i+1}_result.json", "w") as f:
                        json.dump(result, f, indent=2)
            except Exception as e:
                print(f"Error con método {i+1}: {e}")
        
        return results
    
    except Exception as e:
        print(f"Error general: {e}")
        return []

def explore_rest_endpoints():
    """Explora endpoints REST específicos de Hyperliquid"""
    # Basado en documentación y estructura común de APIs
    endpoints = [
        "/user/fills",
        "/user/trades",
        "/user/history",
        "/user/positions/closed",
        "/user/pnl"
    ]
    
    base_url = "https://api.hyperliquid.xyz"
    
    for endpoint in endpoints:
        try:
            print(f"Probando endpoint {endpoint}...")
            # Si el cliente tiene un método request o similar
            if hasattr(client, 'request'):
                result = client.request('GET', f"{base_url}{endpoint}")
                print(f"Resultado: {result}")
            elif hasattr(client, 'get'):
                result = client.get(f"{base_url}{endpoint}")
                print(f"Resultado: {result}")
            else:
                print("Cliente no tiene métodos request/get")
        except Exception as e:
            print(f"Error con endpoint {endpoint}: {e}")

if __name__ == "__main__":
    print("Explorando User Fills en Hyperliquid...")
    fills = explore_user_fills()
    print("\nExplorando endpoints REST específicos...")
    explore_rest_endpoints()
