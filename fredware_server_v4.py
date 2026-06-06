import os
import sys
from flask import Flask, request, jsonify
from flask_cors import CORS
import sqlite3

app = Flask(__name__)
# Permitimos CORS para que tus futuras páginas de GitHub Pages conecten sin bloqueos
CORS(app, resources={r"/*": {"origins": "*"}})

DB_NAME = "fredware_central.db"

def conectar_bd():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

# 🛠️ MOTOR DE BASE DE DATOS (Verificación APPCC)
def inicializar_sistema():
    print("🖥️  Inicializando motores SQL de Fredware v4...")
    conn = conectar_bd()
    cursor = conn.cursor()
    
    # Tabla unificada y corregida para Recepción (Camiones y temperaturas)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS recepcion_mercancia (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            producto TEXT NOT NULL,
            temperatura REAL NOT NULL,
            conservacion TEXT NOT NULL,
            proveedor TEXT NOT NULL,
            cantidad_total INTEGER NOT NULL,
            fecha_registro TEXT NOT NULL
        )
    ''')
    
    # Tabla de respaldo para Caducidades (Botes del obrador)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS etiquetas_caducidad (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre_producto TEXT NOT NULL,
            dias_validez INTEGER NOT NULL,
            fecha_creacion TEXT NOT NULL,
            codigo_qr TEXT
        )
    ''')
    
    conn.commit()
    conn.close()
    print("✅ Base de datos local lista y verificada.")

# 🚚 ENDPOINT 1: GUARDAR TRAZABILIDAD EN SQL (Desde la Tablet)
@app.route('/guardar_mercancia', methods=['POST'])
def guardar_mercancia():
    try:
        datos = request.get_json()
        if not datos:
            return jsonify({"status": "error", "message": "Paquete vacío"}), 400
        
        conn = conectar_bd()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO recepcion_mercancia (producto, temperatura, conservacion, proveedor, cantidad_total, fecha_registro)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (datos['producto'], datos['temperatura'], datos['conservacion'], datos['proveedor'], datos['cantidad_total'], datos['fecha_registro']))
        
        conn.commit()
        conn.close()
        
        print(f"📦 [SQL] Albarán registrado: {datos['producto']} | {datos['temperatura']}°C | {datos['proveedor']}")
        return jsonify({"status": "ok", "message": "Datos guardados en el servidor de casa"}), 200
        
    except Exception as e:
        print(f"❌ Error en SQL Recepción: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

# 🖨️ ENDPOINT 2: RECIBIR LOTE E IMPRIMIR EN LA BROTHER
@app.route('/imprimir_lote', methods=['POST'])
def imprimir_lote():
    try:
        datos = request.get_json()
        if not datos or 'etiquetas' not in datos:
            return jsonify({"status": "error", "message": "Faltan las etiquetas"}), 400
        
        etiquetas = datos['etiquetas']
        print(f"\n🖨️  [Brother] Se ha recibido un lote de {len(etiquetas)} etiquetas para impresión:")
        
        for etiq in etiquetas:
            print(f"   -> Encolando: {etiq['producto']} ({etiq['unidad']})")
            print(f"      QR: {etiq['texto_qr']}")
            
            # 💡 AQUÍ VA TU LÓGICA DE COMANDO PARA LA IMPRESORA BROTHER:
            # Ejemplo: os.system(f"python imprimir_ticket.py ...")
            
        return jsonify({"status": "ok", "message": f"Lote de {len(etiquetas)} enviado a la cola"}), 200
        
    except Exception as e:
        print(f"❌ Error en el motor de impresión: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

# ⚡ ARRANQUE GLOBAL EN EL PUERTO 8000
if __name__ == '__main__':
    print("\n" + "="*50)
    print("✨ SVALENT COMPILATION - FREDWARE CENTRAL v4.0 ✨")
    print("📡 Entorno de Desarrollo Online (Sin Antena Virtual)")
    print("="*50)
    
    inicializar_sistema()
    
    print("\n🏢 Servidor Flask escuchando peticiones en el puerto 8000.")
    print("🚀 Listo para recibir tráfico seguro desde el túnel de ngrok.")
    
    app.run(host='0.0.0.0', port=8000, debug=False)