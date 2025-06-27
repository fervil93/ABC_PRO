#!/usr/bin/env python3
# diagnostico_pares.py - Script para diagnosticar la disponibilidad de pares en Hyperliquid

import time
import json
import sys
from datetime import datetime
import traceback
import requests

# Importamos los mismos módulos que el bot principal para mantener consistencia
from hyperliquid_client import HyperliquidClient
from config import API_URL  # Asegúrate de que estamos usando la misma API_URL que el bot principal

# Inicializa el cliente
client = HyperliquidClient()

# Lista de todos los símbolos que queremos verificar
TODOS_SIMBOLOS = [
    'BTC', 'ETH', 'SOL', 'BNB', 'DOGE', 'ARB', 'MATIC', 'SUI', 'PEPE', 'OP', 
    'XRP', 'AVAX', 'LINK', 'NEAR', 'DOT', 'ADA', 'ATOM', 'LTC', 'SHIB', 'UNI'
]

def verificar_api_general():
    """Verifica la conectividad general con la API"""
    print("\n==== VERIFICACIÓN GENERAL DE LA API ====")
    try:
        print(f"Usando API URL: {API_URL}")
        
        # Intenta consultar información básica de la API
        response = requests.get(f"{API_URL}/info")
        if response.status_code == 200:
            print(f"✅ Conexión exitosa a la API. Status: {response.status_code}")
            try:
                data = response.json()
                print(f"✅ Respuesta parseable como JSON: {type(data)}")
            except:
                print("❌ La respuesta no es JSON válido")
        else:
            print(f"❌ Error de conexión a la API. Status: {response.status_code}")
            print(f"Respuesta: {response.text[:200]}...")
    except Exception as e:
        print(f"❌ Error general al conectar a la API: {e}")
        traceback.print_exc()

def verificar_cuenta():
    """Verifica la información de cuenta"""
    print("\n==== VERIFICACIÓN DE LA CUENTA ====")
    try:
        account = client.get_account()
        if account:
            print(f"✅ Información de cuenta obtenida: {json.dumps(account, indent=2)[:200]}...")
        else:
            print("❌ No se pudo obtener información de la cuenta")
    except Exception as e:
        print(f"❌ Error al verificar la cuenta: {e}")
        traceback.print_exc()

def verificar_pares_disponibles():
    """Verifica exhaustivamente la disponibilidad de cada par"""
    print("\n==== VERIFICACIÓN DETALLADA DE PARES ====")
    
    resultados = {
        "con_precio_y_datos": [],
        "con_precio_sin_datos": [],
        "sin_precio": [],
        "con_error": []
    }
    
    # Intentar recuperar todos los símbolos disponibles desde la API si es posible
    try:
        print("Intentando obtener lista de todos los mercados disponibles...")
        # Nota: Esta URL podría necesitar ajustes dependiendo de la API de Hyperliquid
        response = requests.get(f"{API_URL}/info/meta")
        if response.status_code == 200:
            try:
                data = response.json()
                if 'universe' in data:
                    # Si existe un campo 'universe', podría contener información de mercados
                    print(f"✅ Símbolos disponibles según API: {data['universe']}")
            except:
                print("❌ No se pudo extraer información de mercados de la API")
    except Exception as e:
        print(f"❌ Error al consultar mercados disponibles: {e}")
    
    # Verificar cada símbolo de nuestra lista
    for symbol in TODOS_SIMBOLOS:
        print(f"\nVerificando {symbol}...")
        
        # 1. Verificar precio
        tiene_precio = False
        precio_mid = None
        try:
            inicio_tiempo = time.time()
            precio = client.get_price(symbol)
            tiempo_respuesta = time.time() - inicio_tiempo
            
            if precio and precio.get('mid'):
                tiene_precio = True
                precio_mid = precio.get('mid')
                print(f"✅ Tiene precio: {precio_mid} (tiempo respuesta: {tiempo_respuesta:.2f}s)")
            else:
                print(f"❌ No tiene precio: {precio} (tiempo respuesta: {tiempo_respuesta:.2f}s)")
        except Exception as e:
            print(f"❌ Error al obtener precio: {e}")
            resultados["con_error"].append(symbol)
            continue
        
        if not tiene_precio:
            resultados["sin_precio"].append(symbol)
            continue
        
        # 2. Verificar datos históricos
        try:
            inicio_tiempo = time.time()
            df = client.get_ohlcv(symbol, '1m', 10)
            tiempo_respuesta = time.time() - inicio_tiempo
            
            if df is not None and len(df) > 0:
                print(f"✅ Tiene datos históricos ({len(df)} registros) (tiempo respuesta: {tiempo_respuesta:.2f}s)")
                resultados["con_precio_y_datos"].append((symbol, precio_mid))
                
                # Verificar más detalles del par
                try:
                    order_book = client.get_order_book(symbol)
                    asks_len = len(order_book.get('asks', []))
                    bids_len = len(order_book.get('bids', []))
                    print(f"✅ Order book: {asks_len} asks, {bids_len} bids")
                except Exception as e:
                    print(f"⚠️ No se pudo obtener order book: {e}")
            else:
                print(f"❌ No tiene datos históricos (tiempo respuesta: {tiempo_respuesta:.2f}s)")
                resultados["con_precio_sin_datos"].append((symbol, precio_mid))
        except Exception as e:
            print(f"❌ Error al obtener datos históricos: {e}")
            resultados["con_precio_sin_datos"].append((symbol, precio_mid))
            traceback.print_exc()
    
    return resultados

def mostrar_resumen(resultados):
    """Muestra un resumen de los resultados"""
    print("\n\n==== RESUMEN DE VERIFICACIÓN ====")
    print(f"Fecha y hora: {datetime.now()}")
    print(f"\nPares COMPLETAMENTE disponibles ({len(resultados['con_precio_y_datos'])}): ")
    for symbol, precio in sorted(resultados['con_precio_y_datos']):
        print(f"  - {symbol} (precio: {precio})")
    
    print(f"\nPares con precio pero SIN datos históricos ({len(resultados['con_precio_sin_datos'])}): ")
    for symbol, precio in sorted(resultados['con_precio_sin_datos']):
        print(f"  - {symbol} (precio: {precio})")
    
    print(f"\nPares sin precio ({len(resultados['sin_precio'])}): ")
    for symbol in sorted(resultados['sin_precio']):
        print(f"  - {symbol}")
    
    print(f"\nPares con errores ({len(resultados['con_error'])}): ")
    for symbol in sorted(resultados['con_error']):
        print(f"  - {symbol}")
    
    # Guardar resultados en un archivo
    with open(f"diagnostico_pares_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt", "w") as f:
        f.write(f"==== RESUMEN DE VERIFICACIÓN ====\n")
        f.write(f"Fecha y hora: {datetime.now()}\n\n")
        
        f.write(f"Pares COMPLETAMENTE disponibles ({len(resultados['con_precio_y_datos'])}):\n")
        for symbol, precio in sorted(resultados['con_precio_y_datos']):
            f.write(f"  - {symbol} (precio: {precio})\n")
        
        f.write(f"\nPares con precio pero SIN datos históricos ({len(resultados['con_precio_sin_datos'])}):\n")
        for symbol, precio in sorted(resultados['con_precio_sin_datos']):
            f.write(f"  - {symbol} (precio: {precio})\n")
        
        f.write(f"\nPares sin precio ({len(resultados['sin_precio'])}):\n")
        for symbol in sorted(resultados['sin_precio']):
            f.write(f"  - {symbol}\n")
        
        f.write(f"\nPares con errores ({len(resultados['con_error'])}):\n")
        for symbol in sorted(resultados['con_error']):
            f.write(f"  - {symbol}\n")
    
    print(f"\nResultados guardados en archivo: diagnostico_pares_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")

def main():
    print("==== DIAGNÓSTICO DE PARES DISPONIBLES EN HYPERLIQUID ====")
    print(f"Fecha y hora: {datetime.now()}")
    print(f"Verificando {len(TODOS_SIMBOLOS)} pares: {', '.join(TODOS_SIMBOLOS)}")
    
    verificar_api_general()
    verificar_cuenta()
    resultados = verificar_pares_disponibles()
    mostrar_resumen(resultados)
    
    # Sugerencias basadas en los resultados
    print("\n==== SUGERENCIAS ====")
    if len(resultados["con_precio_y_datos"]) < 10:
        print("⚠️ Tienes menos de 10 pares completamente disponibles. Posibles soluciones:")
        print("  1. Verifica la configuración de API_URL en config.py")
        print("  2. Confirma si estás usando testnet o mainnet")
        print("  3. Aumenta los timeouts en las llamadas a la API")
        print("  4. Considera ajustar el código para permitir pares sin datos históricos completos")
    else:
        print("✅ Tienes una buena cantidad de pares disponibles.")

if __name__ == "__main__":
    main()
