import os
import sys
import json
import threading
from flask import Flask, request, jsonify, make_response
from flask_cors import CORS
from datetime import datetime

# ============================================================
# 🛠️ FUNCIÓN DE RUTA PARA PYINSTALLER
# ============================================================
def ruta_recurso(relative_path):
    """Obtiene la ruta absoluta al recurso para dev y PyInstaller"""
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# 🔒 ESCUDO MAESTRO DE CONCURRENCIA: Evita que escrituras simultáneas corrompan el JSON
json_lock = threading.Lock()

# 🔌 INTEGRACIÓN NATIVA Y OBLIGATORIA DE MÓDULOS DE LA COCINA
try:
    import base_datos
    import generador_pdf
    print("✅ Módulos 'base_datos' y 'generador_pdf' detectados e integrados correctamente.")
except ImportError as e:
    print(f"❌ ERROR CRÍTICO DE ARCHIVOS: No se encuentra '{e.name}.py' en esta carpeta.")
    print("El servidor no puede arrancar sin sus módulos base.")
    sys.exit(1)

# 🔌 CONEXIÓN A SUPABASE
try:
    from supabase import create_client
    SUPABASE_URL = "https://bhyprsjokwgazzzlfnbf.supabase.co"
    SUPABASE_KEY = "sb_publishable_i-g5o4tO1R8u6Fe7Fc2Q8Q_V_FV271y"
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    print("✅ Conexión a Supabase establecida correctamente.")
except ImportError:
    print("❌ Módulo 'supabase' no instalado. Las funciones de Supabase no estarán disponibles.")
    supabase = None
except Exception as e:
    print(f"⚠️ Error al conectar con Supabase: {e}")
    supabase = None

app = Flask(__name__)

# 🔓 APERTURA MAESTRA DE CORS: Configuración global con after_request
@app.after_request
def add_cors_headers(response):
    """Añade cabeceras CORS a todas las respuestas automáticamente."""
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, ngrok-skip-browser-warning"
    response.headers["Access-Control-Allow-Methods"] = "POST, GET, OPTIONS, DELETE"
    return response

# 🎨 CABECERA CORPORATIVA DE ARTE ASCII
def mostrar_logo_fredware():
    logo = """
    #################################################################
    #                                                               #
    #   #####  ######  #####  #####   #    #   ##   #####  #####    #
    #   #      #    #  #      #    #  #    #  #  #  #    # #        #
    #   #####  ######  #####  #    #  #    # #    # #    # #####    #
    #   #      #   #   #      #    #  # ## # ###### #####  #        #
    #   #      #    #  #####  #####   ##  ## #    # #   #  #####    #
    #                                                               #
    #                    S I S T E M A   C E N T R A L              #
    #################################################################
    """
    print(logo)
    print(f"  🚀 Servidor Activo | {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print("  🔒 Modo Elevado: Administrador Autorizado")
    print("  📡 Escuchando peticiones de Cocina y Oficina...\n")

# ============================================================
# 🗑️ ENDPOINT: ELIMINAR MERCANCÍAS (CON SUPABASE)
# ============================================================
@app.route('/eliminar_mercancia', methods=['POST', 'OPTIONS'])
def eliminar_mercancia():
    """
    Elimina productos de la base de datos SQLite y de Supabase
    """
    if request.method == 'OPTIONS':
        return '', 200
    
    try:
        datos = request.get_json(silent=True)
        if not datos:
            return jsonify({"status": "error", "message": "Falta el cuerpo JSON"}), 400
        
        ids_a_eliminar = datos.get('ids', [])
        if not ids_a_eliminar or not isinstance(ids_a_eliminar, list):
            return jsonify({"status": "error", "message": "Se esperaba una lista de IDs"}), 400
        
        print(f"🗑️ [Túnel Online] Eliminando {len(ids_a_eliminar)} producto(s) de la base de datos...")
        
        # 1️⃣ ELIMINAR DE SQLITE LOCAL
        eliminados_sqlite = 0
        try:
            conn = base_datos.conectar()
            cursor = conn.cursor()
            
            # Primero, obtener los productos a eliminar para mostrarlos en el log
            placeholders = ','.join(['?'] * len(ids_a_eliminar))
            cursor.execute(f"SELECT producto, proveedor FROM mercancias_entradas WHERE id IN ({placeholders})", ids_a_eliminar)
            productos_a_eliminar = cursor.fetchall()
            
            # Eliminar de SQLite
            cursor.execute(f"DELETE FROM mercancias_entradas WHERE id IN ({placeholders})", ids_a_eliminar)
            eliminados_sqlite = cursor.rowcount
            conn.commit()
            conn.close()
            
            print(f"  ↳ ✅ SQLite: {eliminados_sqlite} producto(s) eliminado(s)")
            if productos_a_eliminar:
                for prod in productos_a_eliminar:
                    print(f"    - {prod[0]} ({prod[1]})")
                    
        except Exception as e:
            print(f"  ↳ ⚠️ Error en SQLite: {e}")
            # Continuamos con Supabase aunque SQLite falle
        
        # 2️⃣ ELIMINAR DE SUPABASE (si está disponible)
        eliminados_supabase = 0
        if supabase:
            try:
                # Intentar eliminar de Supabase
                # NOTA: Asumiendo que tienes una tabla 'mercancias_entradas' en Supabase con columna 'id'
                result = supabase.table('mercancias_entradas').delete().in_('id', ids_a_eliminar).execute()
                
                # Si la tabla no existe, intentar con 'mercancias'
                if not result.data and hasattr(result, 'error'):
                    result = supabase.table('mercancias').delete().in_('id', ids_a_eliminar).execute()
                
                eliminados_supabase = len(result.data) if result.data else 0
                print(f"  ↳ ✅ Supabase: {eliminados_supabase} producto(s) eliminado(s)")
                
            except Exception as e:
                print(f"  ↳ ⚠️ Error en Supabase: {e}")
                # Continuamos, no fallamos por Supabase
        else:
            print("  ↳ ⚠️ Supabase no disponible - omitiendo eliminación en la nube")
        
        # 3️⃣ TAMBIÉN ELIMINAR DE LA CESTA LOCAL (archivo JSON)
        eliminados_cesta = 0
        try:
            datos_compras = cargar_datos_compras()
            cesta_original = datos_compras.get('cesta', [])
            # Convertir IDs a string para comparación
            ids_str = [str(id) for id in ids_a_eliminar]
            nueva_cesta = [item for item in cesta_original if str(item.get('id', '')) not in ids_str]
            eliminados_cesta = len(cesta_original) - len(nueva_cesta)
            datos_compras['cesta'] = nueva_cesta
            guardar_datos_compras(datos_compras)
            print(f"  ↳ ✅ Cesta local: {eliminados_cesta} producto(s) eliminado(s)")
        except Exception as e:
            print(f"  ↳ ⚠️ Error en cesta local: {e}")
        
        return jsonify({
            "status": "success",
            "message": f"✅ {len(ids_a_eliminar)} producto(s) eliminado(s)",
            "detalles": {
                "sqlite": eliminados_sqlite,
                "supabase": eliminados_supabase,
                "cesta_local": eliminados_cesta
            }
        }), 200
        
    except Exception as e:
        print(f"  ↳ ❌ ERROR EN ELIMINACIÓN: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

# ============================================================
# 📦 ENDPOINT: OBTENER MERCANCÍAS RECIBIDAS DESDE SQLITE
# ============================================================
@app.route('/obtener_mercancias', methods=['GET', 'OPTIONS'])
def obtener_mercancias():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        conn = base_datos.conectar()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, producto, proveedor, conservacion, temperatura, cantidad, fecha_registro 
            FROM mercancias_entradas 
            ORDER BY id DESC
        """)
        filas = cursor.fetchall()
        conn.close()
        
        mercancias = []
        for fila in filas:
            mercancias.append({
                "id": fila[0],
                "producto": fila[1],
                "proveedor": fila[2],
                "conservacion": fila[3],
                "temperatura": fila[4],
                "cantidad": fila[5],
                "fecha_registro": fila[6]
            })
        
        return jsonify(mercancias), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# ============================================================
# 🚚 RUTA: guardar_mercancia
# ============================================================
@app.route('/guardar_mercancia', methods=['POST', 'OPTIONS'])
def guardar_mercancia():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        datos = request.get_json(silent=True)
        if not datos:
            return jsonify({"status": "error", "message": "Falta el cuerpo JSON o el formato es incorrecto"}), 400

        producto = datos.get('producto', '').upper()
        proveedor = datos.get('proveedor', 'S/P').upper()
        conservacion = datos.get('conservacion', 'NEVERA').upper()
        
        try:
            temperatura = float(datos.get('temperatura', 4.0))
        except (ValueError, TypeError):
            temperatura = 4.0
        
        try:
            cantidad = int(datos.get('cantidad_total', datos.get('cantidad', 1)))
        except (ValueError, TypeError):
            cantidad = 1
            
        fecha_iso = datos.get('fecha_registro')

        try:
            dt = datetime.fromisoformat(fecha_iso.replace("Z", "+00:00"))
            fecha_formateada = dt.strftime("%d/%m/%Y")
        except:
            fecha_formateada = datetime.now().strftime("%d/%m/%Y")

        print(f"🚚 [Túnel Online] Recibido camión: {cantidad}x {producto} de {proveedor}")

        # 📦 Registro 1: Tabla interna del Almacén Oculto
        try:
            conn = base_datos.conectar()
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS mercancias_entradas (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    producto TEXT,
                    proveedor TEXT,
                    conservacion TEXT,
                    temperatura REAL,
                    cantidad INTEGER,
                    fecha_registro TEXT
                )
            """)
            cursor.execute("""
                INSERT INTO mercancias_entradas (producto, proveedor, conservacion, temperatura, cantidad, fecha_registro)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (producto, proveedor, conservacion, temperatura, cantidad, fecha_formateada))
            conn.commit()
            # Obtener el ID del registro insertado
            nuevo_id = cursor.lastrowid
            conn.close()
            print(f"  ↳ 📦 Fichado en el historial del Almacén Oculto (ID: {nuevo_id})")
        except Exception as err_sql:
            print(f"  ↳ ⚠️ Nota al inyectar en mercancias_entradas: {err_sql}")

        # 📝 Registro 2: Vinculación con las fichas de producción
        try:
            base_datos.registrar_entrada_mercancia(producto, proveedor, fecha_formateada)
            print("  ↳ 📝 Vinculado en la tabla de fichas de producción.")
        except Exception as err_bd:
            print(f"  ↳ ⚠️ Nota al registrar en tabla de fichas: {err_bd}")

        return jsonify({"status": "success", "message": "Materia prima registrada con éxito"}), 200
    except Exception as e:
        print(f"  ↳ ❌ ERROR CRÍTICO EN RUTA: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

# ============================================================
# 🖨️ RUTA: imprimir_lote
# ============================================================
@app.route('/imprimir_lote', methods=['POST', 'OPTIONS'])
def imprimir_lote():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        datos = request.get_json(silent=True)
        if not datos:
            return jsonify({"status": "error", "message": "Cuerpo vacío"}), 400
            
        etiquetas = datos.get('etiquetas', [])
        if not etiquetas: 
            return jsonify({"status": "error", "message": "Lote de stickers vacío"}), 400

        print(f"🖨️  [Túnel Online] Procesando {len(etiquetas)} stickers contra el generador de PDF...")
        lote_rec_pdf = []
        for etiq in etiquetas:
            lote_rec_pdf.append({
                "producto": etiq.get("producto", etiq.get("nombre", "S/P")),
                "unidad": etiq.get("unidad", "1 de 1"),
                "fecha": etiq.get("fecha", datetime.now().strftime("%d/%m/%Y")),
                "texto_qr": etiq.get("texto_qr", "FREDWARE-READY")
            })

        generador_pdf.generar_etiquetas_recepcion(lote_rec_pdf)
        print("  ↳ 🚀 ¡PDF generado y visor ejecutado con éxito!")
        
        return jsonify({"status": "success", "message": "Pegatinas enviadas al rodillo"}), 200
    except Exception as e:
        print(f"  ↳ ❌ ERROR EN IMPRESIÓN: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

# ============================================================
# 📋 RUTA: obtener_catalogo
# ============================================================
@app.route('/obtener_catalogo', methods=['GET', 'OPTIONS'])
def obtener_catalogo():
    if request.method == 'OPTIONS':
        return '', 200
        
    productos_ya_vistos = set(["ATÚN ROJO", "PIMIENTOS DE PIQUILLO", "KETCHUP", "HARINA DE TRIGO"])
    proveedores_ya_vistos = set(["MAKRO", "PESCASA", "DISTRIBUCIONES GALICIA", "FRUTAS PEPE"])
    
    try:
        conn = base_datos.conectar()
        cursor = conn.cursor()
        cursor.execute("SELECT nombre_produccion, ingredientes_detalle FROM fichas")
        for fila in cursor.fetchall():
            if fila[0]: 
                productos_ya_vistos.add(fila[0].replace("ENTRADA MERCANCÍA: ", "").upper())
        conn.close()
    except: 
        pass
    
    return jsonify({"status": "success", "productos": sorted(list(productos_ya_vistos)), "proveedores": sorted(list(proveedores_ya_vistos))}), 200

# =====================================================================
# 🆕 ENDPOINTS: RESUMEN DIARIO Y CONTADOR DE ETIQUETAS
# =====================================================================
@app.route('/api/resumen_dia', methods=['POST', 'OPTIONS'])
def resumen_dia():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        exito = generador_pdf.generar_resumen_dia()
        if exito:
            return jsonify({"status": "success", "message": "Resumen del día generado e impreso"}), 200
        else:
            return jsonify({"status": "error", "message": "No hay etiquetas para hoy"}), 400
    except Exception as e:
        print(f"Error en resumen diario: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/contador_dia', methods=['GET', 'OPTIONS'])
def contador_dia():
    if request.method == 'OPTIONS':
        return '', 200
    etiquetas = generador_pdf.cargar_etiquetas_dia()
    return jsonify({"total": len(etiquetas)}), 200

# =====================================================================
# 🆕 ENDPOINTS PARA GESTIÓN DE ETIQUETAS (NUEVOS)
# =====================================================================

@app.route('/api/etiquetas/total_dia', methods=['GET', 'OPTIONS'])
def total_etiquetas_dia():
    """Devuelve el número de etiquetas acumuladas hoy."""
    if request.method == 'OPTIONS':
        return '', 200
    try:
        total = generador_pdf.get_total_etiquetas_dia()
        return jsonify({"total": total, "fecha": datetime.now().strftime("%Y-%m-%d")}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/etiquetas/imprimir_resumen', methods=['POST', 'OPTIONS'])
def imprimir_resumen_etiquetas():
    """Genera e imprime un PDF con TODAS las etiquetas acumuladas del día."""
    if request.method == 'OPTIONS':
        return '', 200
    try:
        exito = generador_pdf.generar_resumen_dia()
        if exito:
            return jsonify({"status": "success", "message": "Resumen del día impreso con éxito"}), 200
        else:
            return jsonify({"status": "error", "message": "No hay etiquetas para hoy"}), 400
    except Exception as e:
        print(f"Error en resumen diario: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/etiquetas/guardar_supabase', methods=['POST', 'OPTIONS'])
def guardar_etiquetas_supabase():
    """Guarda las etiquetas del día en Supabase."""
    if request.method == 'OPTIONS':
        return '', 200
    try:
        etiquetas = generador_pdf.cargar_etiquetas_dia()
        if not etiquetas:
            return jsonify({"status": "error", "message": "No hay etiquetas para guardar"}), 400
        
        if supabase:
            exito = generador_pdf.guardar_etiquetas_supabase(etiquetas, supabase)
            if exito:
                return jsonify({"status": "success", "message": f"Guardadas {len(etiquetas)} etiquetas en Supabase"}), 200
            else:
                return jsonify({"status": "error", "message": "Error al guardar en Supabase"}), 500
        else:
            return jsonify({"status": "error", "message": "Supabase no disponible"}), 500
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# =====================================================================
# 🆕🆕🆕 NUEVOS ENDPOINTS PARA FICHAS TÉCNICAS (AÑADIDOS)
# =====================================================================

@app.route('/generar_ficha_a4', methods=['POST', 'OPTIONS'])
def generar_ficha_a4():
    """Genera una ficha A4 con QR para un producto."""
    if request.method == 'OPTIONS':
        return '', 200
    try:
        datos = request.get_json()
        generador_pdf.generar_ficha_a4(datos)
        return jsonify({"status": "success", "message": "Ficha A4 generada"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/generar_sticker', methods=['POST', 'OPTIONS'])
def generar_sticker():
    """Genera un sticker para la Brother."""
    if request.method == 'OPTIONS':
        return '', 200
    try:
        datos = request.get_json()
        generador_pdf.generar_etiquetas_sticker(datos)
        return jsonify({"status": "success", "message": "Sticker generado"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/generar_ficha_a4_masiva', methods=['POST', 'OPTIONS'])
def generar_ficha_a4_masiva():
    """Genera múltiples fichas A4 en lote."""
    if request.method == 'OPTIONS':
        return '', 200
    try:
        datos = request.get_json()
        fichas = datos.get('fichas', [])
        if not fichas:
            return jsonify({"status": "error", "message": "No hay fichas"}), 400
        
        for ficha in fichas:
            generador_pdf.generar_ficha_a4(ficha)
        return jsonify({"status": "success", "message": f"{len(fichas)} fichas generadas"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/generar_sticker_masivo', methods=['POST', 'OPTIONS'])
def generar_sticker_masivo():
    """Genera múltiples stickers en lote."""
    if request.method == 'OPTIONS':
        return '', 200
    try:
        datos = request.get_json()
        stickers = datos.get('stickers', [])
        if not stickers:
            return jsonify({"status": "error", "message": "No hay stickers"}), 400
        
        generador_pdf.generar_etiquetas_sticker(stickers)
        return jsonify({"status": "success", "message": f"{len(stickers)} stickers generados"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# =====================================================================
# 🛒 EXTENSIÓN ONLINE: GESTIÓN DE COMPRAS Y FALTAS DE COCINA
# =====================================================================
DATA_FILE = ruta_recurso("fredware_compras_db.json")

def cargar_datos_compras():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f: 
                return json.load(f)
        except: 
            pass
    return {"cesta": [], "faltas": [], "proveedores": []}

def guardar_datos_compras(datos):
    with json_lock:
        with open(DATA_FILE, 'w', encoding='utf-8') as f: 
            json.dump(datos, f, ensure_ascii=False, indent=4)

@app.route('/api/datos', methods=['GET', 'OPTIONS'])
def obtener_datos_compras():
    if request.method == 'OPTIONS':
        return '', 200
    return jsonify(cargar_datos_compras()), 200

@app.route('/api/cesta', methods=['POST', 'OPTIONS'])
def actualizar_cesta():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        nueva_cesta = request.get_json(silent=True)
        if not isinstance(nueva_cesta, list):
            return jsonify({"status": "error", "message": "Se esperaba un formato de lista válido"}), 400
            
        datos = cargar_datos_compras()
        datos["cesta"] = nueva_cesta
        guardar_datos_compras(datos)
        print("🛒 [Túnel Online] Cesta de la compra actualizada con éxito.")
        return jsonify({"status": "success"}), 200
    except Exception as e: 
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/faltas', methods=['POST', 'OPTIONS'])
def actualizar_faltas():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        nuevas_faltas = request.get_json(silent=True)
        if not isinstance(nuevas_faltas, list):
            return jsonify({"status": "error", "message": "Formato malformado"}), 400
            
        datos = cargar_datos_compras()
        datos["faltas"] = nuevas_faltas
        guardar_datos_compras(datos)
        print("⚠️ [Túnel Online] Lista de faltas modificada por el equipo.")
        return jsonify({"status": "success"}), 200
    except Exception as e: 
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/proveedores', methods=['POST', 'OPTIONS'])
def actualizar_proveedores():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        nuevos_prov = request.get_json(silent=True)
        if not isinstance(nuevos_prov, list):
            return jsonify({"status": "error", "message": "Formato incorrecto"}), 400
            
        datos = cargar_datos_compras()
        datos["proveedores"] = nuevos_prov
        guardar_datos_compras(datos)
        print("🏢 [Túnel Online] Lista de proveedores unificada en disco.")
        return jsonify({"status": "success"}), 200
    except Exception as e: 
        return jsonify({"status": "error", "message": str(e)}), 500

# ➕ ENDPOINT DE CONTROL
@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({
        "status": "online",
        "timestamp": datetime.now().isoformat(),
        "version": "5.5-Stable",
        "supabase": "connected" if supabase else "disconnected"
    }), 200

# ============================================================
# 🚀 INICIO DEL SERVIDOR
# ============================================================
if __name__ == '__main__':
    mostrar_logo_fredware()
    
    try:
        base_datos.inicializar_base_datos()
        print("✅ Base de datos inicializada correctamente.")
    except Exception as e:
        print(f"⚠️ Nota al iniciar BD global: {e}")
        print("⚠️ El servidor arrancará igualmente, pero algunas funciones podrían fallar.")
    
    # 🔥 PROGRAMAR GUARDADO AUTOMÁTICO A LAS 00:00
    if supabase:
        try:
            generador_pdf.programar_guardado_automatico(supabase)
            print("⏰ Guardado automático programado para las 00:00")
        except Exception as e:
            print(f"⚠️ Error programando guardado automático: {e}")
    else:
        print("⚠️ Supabase no disponible. Guardado automático desactivado.")
    
    print("🚀 Iniciando servidor Fredware en http://0.0.0.0:8000")
    app.run(host='0.0.0.0', port=8000, debug=False, threaded=True)