import os
import sys
import json
import threading
import time
import queue
import sqlite3
from flask import Flask, request, jsonify, make_response
from flask_cors import CORS
from datetime import datetime
from functools import wraps

# ============================================================
# 🛠️ FUNCIÓN DE RUTA PARA PYINSTALLER
# ============================================================
def ruta_recurso(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# ============================================================
# 📂 DEFINIR DATA_FILE Y FUNCIONES DE CARGA/GUARDADO
# ============================================================
DATA_FILE = ruta_recurso("fredware_compras_db.json")
JSON_LOCK = threading.Lock()

def cargar_datos_compras():
    for attempt in range(3):
        try:
            if os.path.exists(DATA_FILE):
                with open(DATA_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {"cesta": [], "faltas": [], "proveedores": []}
        except Exception as e:
            if attempt < 2:
                time.sleep(0.5 * (attempt + 1))
                continue
            print(f"⚠️ Error cargando datos: {e}")
            return {"cesta": [], "faltas": [], "proveedores": []}

def guardar_datos_compras(datos):
    with JSON_LOCK:
        try:
            temp_file = DATA_FILE + '.tmp'
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(datos, f, ensure_ascii=False, indent=4)
            os.replace(temp_file, DATA_FILE)
            return True
        except Exception as e:
            print(f"❌ Error guardando datos: {e}")
            return False

# ============================================================
# 🔧 CONFIGURACIÓN
# ============================================================
MAX_RETRIES = 3
RETRY_DELAY = 0.5

# ============================================================
# 🔒 SISTEMA DE LOCKS
# ============================================================
class LockManager:
    def __init__(self):
        self._locks = {}
        self._global_lock = threading.Lock()
    
    def get_lock(self, resource_name):
        with self._global_lock:
            if resource_name not in self._locks:
                self._locks[resource_name] = threading.Lock()
            return self._locks[resource_name]

lock_manager = LockManager()
json_lock = lock_manager.get_lock('json_file')
sqlite_lock = lock_manager.get_lock('sqlite')

# ============================================================
# ⏱️ DECORADOR DE RETRY
# ============================================================
def with_retry(max_retries=MAX_RETRIES, delay=RETRY_DELAY):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_error = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_error = e
                    if attempt < max_retries - 1:
                        time.sleep(delay * (attempt + 1))
                        continue
                    raise last_error
            raise last_error
        return wrapper
    return decorator

# ============================================================
# 🔌 INTEGRACIÓN DE MÓDULOS
# ============================================================
try:
    import base_datos
    import generador_pdf
    print("✅ Módulos 'base_datos' y 'generador_pdf' detectados e integrados correctamente.")
except ImportError as e:
    print(f"❌ ERROR CRÍTICO: No se encuentra '{e.name}.py'")
    sys.exit(1)

# ============================================================
# 🗄️ POOL DE CONEXIONES SQLITE
# ============================================================
class SQLiteConnectionPool:
    def __init__(self, db_path, max_connections=5):
        self.db_path = db_path
        self.max_connections = max_connections
        self._connections = []
        self._lock = threading.Lock()
    
    def get_connection(self):
        with self._lock:
            if self._connections:
                return self._connections.pop()
            conn = sqlite3.connect(self.db_path, timeout=10.0)
            conn.execute("PRAGMA busy_timeout = 5000")
            conn.execute("PRAGMA journal_mode = WAL")
            return conn
    
    def return_connection(self, conn):
        if conn:
            with self._lock:
                if len(self._connections) < self.max_connections:
                    self._connections.append(conn)
                else:
                    conn.close()

db_pool = SQLiteConnectionPool('fredware.db')

def conectar_bd_parchada():
    return db_pool.get_connection()

if hasattr(base_datos, 'conectar'):
    base_datos.conectar = conectar_bd_parchada

# ============================================================
# 🔌 CONEXIÓN A SUPABASE
# ============================================================
try:
    from supabase import create_client
    SUPABASE_URL = "https://bhyprsjokwgazzzlfnbf.supabase.co"
    SUPABASE_KEY = "sb_publishable_i-g5o4tO1R8u6Fe7Fc2Q8Q_V_FV271y"
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    print("✅ Conexión a Supabase establecida correctamente.")
except Exception as e:
    print(f"⚠️ Error al conectar con Supabase: {e}")
    supabase = None

app = Flask(__name__)

# ============================================================
# 🆕 COLA DE IMPRESIÓN PARA ETIQUETAS RÁPIDAS V2 (AISLADA)
# ============================================================
cola_etiquetas_v2 = queue.Queue()
cola_status_v2 = {
    "pendientes": 0,
    "procesadas": 0,
    "ultimo_error": None,
    "ultima_impresion": None,
    "activo": True
}

def worker_etiquetas_v2():
    """Worker DEDICADO para etiquetas rápidas V2 - NO afecta a otras apps"""
    while True:
        try:
            item = cola_etiquetas_v2.get(timeout=2)
            if item is None:
                break
                
            pdf_path, producto, cantidad, intentos = item
            
            exito = False
            for intento in range(intentos):
                try:
                    print(f"🖨️ [Worker V2] Imprimiendo {cantidad}x {producto} (intento {intento+1}/{intentos})")
                    imprimir_con_sumatra(pdf_path)
                    exito = True
                    cola_status_v2["ultima_impresion"] = datetime.now().isoformat()
                    cola_status_v2["ultimo_error"] = None
                    cola_status_v2["procesadas"] += 1
                    break
                except Exception as e:
                    if intento < intentos - 1:
                        time.sleep(0.5 * (intento + 1))
                    else:
                        cola_status_v2["ultimo_error"] = str(e)
                        print(f"❌ [Worker V2] Error tras {intentos} intentos: {e}")
            
            time.sleep(1.5)
            try:
                if os.path.exists(pdf_path):
                    os.unlink(pdf_path)
            except Exception as e:
                print(f"⚠️ [Worker V2] No se pudo eliminar {pdf_path}: {e}")
            
            cola_etiquetas_v2.task_done()
            cola_status_v2["pendientes"] = cola_etiquetas_v2.qsize()
            
        except queue.Empty:
            time.sleep(0.5)
        except Exception as e:
            print(f"❌ [Worker V2] Error crítico: {e}")
            time.sleep(1)

# ============================================================
# 🔓 CONFIGURACIÓN CORS
# ============================================================
@app.before_request
def handle_preflight():
    if request.method == "OPTIONS":
        response = make_response()
        response.headers.add("Access-Control-Allow-Origin", "*")
        response.headers.add("Access-Control-Allow-Headers", "*")
        response.headers.add("Access-Control-Allow-Methods", "*")
        response.headers.add("Access-Control-Max-Age", "86400")
        response.headers.add("Access-Control-Allow-Credentials", "true")
        return response

@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "*"
    response.headers["Access-Control-Expose-Headers"] = "*"
    response.headers["Access-Control-Allow-Credentials"] = "true"
    return response

# ============================================================
# 🎨 LOGO
# ============================================================
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
# 📦 ENDPOINT: OBTENER MERCANCÍAS
# ============================================================
@app.route('/obtener_mercancias', methods=['GET', 'OPTIONS'])
def obtener_mercancias():
    if request.method == 'OPTIONS':
        return '', 200
    
    try:
        if supabase:
            result = supabase.table('mercancia_recibida').select("*").order('id', desc=True).execute()
            print(f"📦 Obtenidas {len(result.data) if result.data else 0} mercancías de Supabase")
            return jsonify(result.data if result.data else []), 200
        else:
            conn = None
            try:
                conn = base_datos.conectar()
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT id, producto, proveedor, conservacion, temperatura, cantidad, fecha_registro 
                    FROM mercancias_entradas 
                    ORDER BY id DESC
                """)
                filas = cursor.fetchall()
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
                print(f"⚠️ Error en SQLite: {e}")
                return jsonify([]), 200
            finally:
                if conn:
                    db_pool.return_connection(conn)
                    
    except Exception as e:
        print(f"❌ Error en obtener_mercancias: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500

# ============================================================
# 🗑️ ENDPOINT: ELIMINAR MERCANCÍAS
# ============================================================
@app.route('/eliminar_mercancia', methods=['POST', 'OPTIONS'])
@with_retry(max_retries=3)
def eliminar_mercancia():
    if request.method == 'OPTIONS':
        return '', 200
    
    try:
        datos = request.get_json(silent=True)
        if not datos:
            return jsonify({"status": "error", "message": "Falta el cuerpo JSON"}), 400
        
        ids_a_eliminar = datos.get('ids', [])
        if not ids_a_eliminar or not isinstance(ids_a_eliminar, list):
            return jsonify({"status": "error", "message": "Se esperaba una lista de IDs"}), 400
        
        print(f"🗑️ Eliminando {len(ids_a_eliminar)} producto(s)...")
        
        eliminados_supabase = 0
        if supabase:
            try:
                result = supabase.table('mercancia_recibida').delete().in_('id', ids_a_eliminar).execute()
                eliminados_supabase = len(result.data) if result.data else 0
                print(f"  ↳ ✅ Supabase: {eliminados_supabase} eliminados")
            except Exception as e:
                print(f"  ↳ ⚠️ Error Supabase: {e}")
        
        eliminados_sqlite = 0
        conn = None
        try:
            conn = base_datos.conectar()
            cursor = conn.cursor()
            placeholders = ','.join(['?'] * len(ids_a_eliminar))
            cursor.execute(f"DELETE FROM mercancias_entradas WHERE id IN ({placeholders})", ids_a_eliminar)
            eliminados_sqlite = cursor.rowcount
            conn.commit()
            print(f"  ↳ ✅ SQLite: {eliminados_sqlite} eliminados")
        except Exception as e:
            print(f"  ↳ ⚠️ Error SQLite: {e}")
        finally:
            if conn:
                db_pool.return_connection(conn)
        
        eliminados_cesta = 0
        try:
            datos_compras = cargar_datos_compras()
            cesta_original = datos_compras.get('cesta', [])
            ids_str = [str(id) for id in ids_a_eliminar]
            nueva_cesta = [item for item in cesta_original if str(item.get('id', '')) not in ids_str]
            eliminados_cesta = len(cesta_original) - len(nueva_cesta)
            datos_compras['cesta'] = nueva_cesta
            guardar_datos_compras(datos_compras)
            print(f"  ↳ ✅ Cesta local: {eliminados_cesta} eliminados")
        except Exception as e:
            print(f"  ↳ ⚠️ Error cesta: {e}")
        
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
        print(f"❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500

# ============================================================
# 🚚 RUTA: guardar_mercancia
# ============================================================
@app.route('/guardar_mercancia', methods=['POST', 'OPTIONS'])
@with_retry(max_retries=3)
def guardar_mercancia():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        datos = request.get_json(silent=True)
        if not datos:
            return jsonify({"status": "error", "message": "Falta el cuerpo JSON"}), 400

        producto = datos.get('producto', '').upper()
        proveedor = datos.get('proveedor', 'S/P').upper()
        conservacion = datos.get('conservacion', 'NEVERA').upper()
        temperatura = float(datos.get('temperatura', 4.0))
        cantidad = int(datos.get('cantidad_total', datos.get('cantidad', 1)))
        fecha_formateada = datetime.now().strftime("%d/%m/%Y")

        print(f"🚚 Recibido: {cantidad}x {producto} de {proveedor}")

        if supabase:
            try:
                data = {
                    "producto": producto,
                    "proveedor": proveedor,
                    "conservacion": conservacion,
                    "temperatura": temperatura,
                    "cantidad_total": cantidad,
                    "fecha_registro": datetime.now().isoformat()
                }
                result = supabase.table('mercancia_recibida').insert(data).execute()
                print(f"  ↳ ✅ Supabase: Registrado con ID: {result.data[0]['id'] if result.data else 'N/A'}")
            except Exception as e:
                print(f"  ↳ ⚠️ Error Supabase: {e}")

        conn = None
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
            print(f"  ↳ ✅ SQLite: Registrado con ID: {cursor.lastrowid}")
        except Exception as e:
            print(f"  ↳ ⚠️ Error SQL: {e}")
        finally:
            if conn:
                db_pool.return_connection(conn)

        try:
            base_datos.registrar_entrada_mercancia(producto, proveedor, fecha_formateada)
            print("  ↳ ✅ Vinculado en fichas de producción.")
        except Exception as e:
            print(f"  ↳ ⚠️ Error en fichas: {e}")

        return jsonify({"status": "success", "message": "Materia prima registrada con éxito"}), 200
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500

# ============================================================
# 🖨️ RUTA: imprimir_lote (PARA OTRAS APPS - CON BOTE, TEMP, PROVEEDOR)
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

        print(f"🖨️ Procesando {len(etiquetas)} stickers (con bote, temp, proveedor)...")
        lote_rec_pdf = []
        for etiq in etiquetas:
            lote_rec_pdf.append({
                "producto": etiq.get("producto", etiq.get("nombre", "S/P")),
                "unidad": etiq.get("unidad", "1 de 1"),
                "fecha": etiq.get("fecha", datetime.now().strftime("%d/%m/%Y")),
                "texto_qr": etiq.get("texto_qr", "FREDWARE-READY")
            })

        generador_pdf.generar_etiquetas_recepcion(lote_rec_pdf)
        print("  ↳ ✅ PDF generado (con bote, temp, proveedor)")
        
        return jsonify({"status": "success", "message": "Pegatinas enviadas al rodillo"}), 200
        
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500


# ============================================================
# 🖨️ ENDPOINT: ETIQUETAS RÁPIDAS (FORMATO LIMPIO) - VERSIÓN ORIGINAL
# ============================================================
@app.route('/imprimir_etiqueta_rapida', methods=['POST', 'OPTIONS'])
def imprimir_etiqueta_rapida():
    """
    Endpoint para etiquetas rápidas con formato limpio:
    - Producto (grande)
    - Lote
    - Elaborado/Descongelado: fecha (abreviado)
    - CAD: fecha
    - QR abajo
    """
    if request.method == 'OPTIONS':
        return '', 200
    try:
        datos = request.get_json(silent=True)
        if not datos:
            return jsonify({"status": "error", "message": "Cuerpo vacío"}), 400
            
        etiquetas = datos.get('etiquetas', [])
        if not etiquetas: 
            return jsonify({"status": "error", "message": "Lote de stickers vacío"}), 400

        print(f"🖨️ Procesando {len(etiquetas)} stickers RÁPIDOS...")
        
        for etiq in etiquetas:
            producto = etiq.get("producto", "S/P")
            lote = etiq.get("unidad", "S/L")
            fecha = etiq.get("fecha", "")
            qr_texto = etiq.get("texto_qr", "FREDWARE")
            
            generar_etiqueta_rapida(producto, lote, fecha, qr_texto)
        
        return jsonify({"status": "success", "message": "Etiquetas rápidas enviadas"}), 200
        
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500


def generar_etiqueta_rapida(producto, lote, fecha, qr_texto):
    """
    Genera una etiqueta en BLANCO Y NEGRO con formato compacto
    Tamaño: 62mm x 60mm
    QR abajo, textos abreviados
    QR: 20mm x 20mm, separado de la caducidad (Y=2mm)
    """
    try:
        from reportlab.lib.pagesizes import mm
        from reportlab.pdfgen import canvas
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.lib.utils import ImageReader
        import tempfile
        import os
        import subprocess
        import io
        import qrcode
        import time
        
        # Buscar fuentes
        font_paths = [
            "C:/Windows/Fonts/arialbd.ttf",
            "C:/Windows/Fonts/arial.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/System/Library/Fonts/Helvetica.ttc"
        ]
        
        font_grande = "Helvetica-Bold"
        font_normal = "Helvetica"
        
        for path in font_paths:
            if os.path.exists(path):
                try:
                    pdfmetrics.registerFont(TTFont('CustomFont', path))
                    font_grande = 'CustomFont'
                    font_normal = 'CustomFont'
                    break
                except:
                    pass
        
        # TAMAÑO DE ETIQUETA: 62mm x 60mm
        ancho_mm = 62
        alto_mm = 60
        
        pdf_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
        pdf_path = pdf_file.name
        pdf_file.close()
        
        c = canvas.Canvas(pdf_path, pagesize=(ancho_mm * mm, alto_mm * mm))
        
        # Márgenes
        margen_x = 2 * mm
        margen_y = 2 * mm
        
        # ============================================================
        # 📌 TEXTO (ARRIBA) - QR (ABAJO)
        # ============================================================
        
        # --- PRODUCTO (grande, en negrita) ---
        c.setFont(font_grande, 16)
        c.setFillColorRGB(0, 0, 0)
        producto_display = producto[:20] if len(producto) > 20 else producto
        c.drawString(margen_x, 54 * mm, producto_display)
        
        # --- LOTE (tamaño 10) ---
        c.setFont(font_grande, 10)
        c.setFillColorRGB(0, 0, 0)
        c.drawString(margen_x, 44 * mm, f"LOTE: {lote[:12]}")
        
        # --- FECHA DE ORIGEN (ABREVIADA) ---
        fecha_limpia = fecha
        tipo_texto = "ELAB"
        
        if "Descongelado" in fecha:
            tipo_texto = "DESC"
            fecha_limpia = fecha.replace("Descongelado:", "").replace("Descongelado", "").strip()
        elif "Elaborado" in fecha:
            tipo_texto = "ELAB"
            fecha_limpia = fecha.replace("Elaborado:", "").replace("Elaborado", "").strip()
        
        if "|" in fecha_limpia:
            fecha_limpia = fecha_limpia.split("|")[0].strip()
        
        c.setFont(font_normal, 10)
        c.setFillColorRGB(0, 0, 0)
        c.drawString(margen_x, 34 * mm, f"{tipo_texto}: {fecha_limpia}")
        
        # --- CADUCIDAD (tamaño 10) ---
        caducidad = ""
        if qr_texto and "CAD:" in qr_texto:
            for parte in qr_texto.split("|"):
                if "CAD:" in parte:
                    caducidad = parte.replace("CAD:", "").strip()
                    break
        
        if caducidad:
            c.setFont(font_grande, 10)
            c.setFillColorRGB(0, 0, 0)
            c.drawString(margen_x, 24 * mm, f"CAD: {caducidad}")
        
        # --- QR ABAJO (20mm x 20mm, centrado y separado) ---
        if qr_texto:
            try:
                qr = qrcode.QRCode(box_size=4, border=1)
                qr.add_data(qr_texto)
                qr.make(fit=True)
                qr_img = qr.make_image(fill_color="black", back_color="white")
                
                qr_buffer = io.BytesIO()
                qr_img.save(qr_buffer, format='PNG')
                qr_buffer.seek(0)
                
                qr_reader = ImageReader(qr_buffer)
                # QR abajo: 20mm x 20mm, centrado y separado de la caducidad (Y=2mm)
                c.drawImage(qr_reader, 21 * mm, 2 * mm, width=20 * mm, height=20 * mm)
            except:
                c.rect(21 * mm, 2 * mm, 20 * mm, 20 * mm)
                c.setFont(font_normal, 6)
                c.drawString(27 * mm, 10 * mm, "QR")
        
        c.save()
        
        print(f"  ↳ ✅ PDF generado: {pdf_path}")
        
        # Imprimir con SumatraPDF
        imprimir_con_sumatra(pdf_path)
        
        # Limpiar archivo temporal después de un tiempo
        def limpiar():
            time.sleep(5)
            try:
                if os.path.exists(pdf_path):
                    os.unlink(pdf_path)
            except:
                pass
        
        threading.Thread(target=limpiar).start()
        
    except Exception as e:
        print(f"❌ Error generando etiqueta rápida: {e}")
        import traceback
        traceback.print_exc()


def imprimir_con_sumatra(ruta_pdf):
    """
    Imprime un PDF usando SumatraPDF
    """
    import subprocess
    import os
    
    try:
        # Buscar SumatraPDF
        sumatra_paths = [
            os.path.join(os.path.dirname(__file__), "SumatraPDF.exe"),
            "C:/Program Files/SumatraPDF/SumatraPDF.exe",
            "C:/Program Files (x86)/SumatraPDF/SumatraPDF.exe"
        ]
        
        sumatra_exe = None
        for path in sumatra_paths:
            if os.path.exists(path):
                sumatra_exe = path
                break
        
        if not sumatra_exe:
            print("❌ SumatraPDF no encontrado")
            return False
        
        # Imprimir con SumatraPDF
        cmd = f'"{sumatra_exe}" -print-to "Brother QL-810W" -silent "{ruta_pdf}"'
        result = subprocess.run(cmd, shell=True, capture_output=True)
        
        if result.returncode == 0:
            print(f"✅ Etiqueta RÁPIDA enviada a impresora")
            return True
        else:
            print(f"❌ Error en SumatraPDF: {result.stderr}")
            return False
        
    except Exception as e:
        print(f"❌ Error imprimiendo: {e}")
        return False


# ============================================================
# 🆕 FUNCIÓN: GENERAR PDF SIN IMPRIMIR (PARA V2)
# ============================================================
def generar_pdf_etiqueta_rapida_v2(producto, lote, fecha, qr_texto):
    """
    Genera PDF de etiqueta rápida SIN IMPRIMIR (solo crea el archivo)
    Retorna la ruta del archivo
    """
    try:
        from reportlab.lib.pagesizes import mm
        from reportlab.pdfgen import canvas
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.lib.utils import ImageReader
        import tempfile
        import io
        import qrcode
        
        # Buscar fuentes
        font_paths = [
            "C:/Windows/Fonts/arialbd.ttf",
            "C:/Windows/Fonts/arial.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/System/Library/Fonts/Helvetica.ttc"
        ]
        
        font_grande = "Helvetica-Bold"
        font_normal = "Helvetica"
        
        for path in font_paths:
            if os.path.exists(path):
                try:
                    pdfmetrics.registerFont(TTFont('CustomFont', path))
                    font_grande = 'CustomFont'
                    font_normal = 'CustomFont'
                    break
                except:
                    pass
        
        ancho_mm = 62
        alto_mm = 60
        
        pdf_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
        pdf_path = pdf_file.name
        pdf_file.close()
        
        c = canvas.Canvas(pdf_path, pagesize=(ancho_mm * mm, alto_mm * mm))
        margen_x = 2 * mm
        
        # PRODUCTO
        c.setFont(font_grande, 16)
        c.setFillColorRGB(0, 0, 0)
        producto_display = producto[:20] if len(producto) > 20 else producto
        c.drawString(margen_x, 54 * mm, producto_display)
        
        # LOTE
        c.setFont(font_grande, 10)
        c.setFillColorRGB(0, 0, 0)
        c.drawString(margen_x, 44 * mm, f"LOTE: {lote[:12]}")
        
        # FECHA
        fecha_limpia = fecha
        tipo_texto = "ELAB"
        
        if "Descongelado" in fecha:
            tipo_texto = "DESC"
            fecha_limpia = fecha.replace("Descongelado:", "").replace("Descongelado", "").strip()
        elif "Elaborado" in fecha:
            tipo_texto = "ELAB"
            fecha_limpia = fecha.replace("Elaborado:", "").replace("Elaborado", "").strip()
        
        if "|" in fecha_limpia:
            fecha_limpia = fecha_limpia.split("|")[0].strip()
        
        c.setFont(font_normal, 10)
        c.setFillColorRGB(0, 0, 0)
        c.drawString(margen_x, 34 * mm, f"{tipo_texto}: {fecha_limpia}")
        
        # CADUCIDAD
        caducidad = ""
        if qr_texto and "CAD:" in qr_texto:
            for parte in qr_texto.split("|"):
                if "CAD:" in parte:
                    caducidad = parte.replace("CAD:", "").strip()
                    break
        
        if caducidad:
            c.setFont(font_grande, 10)
            c.setFillColorRGB(0, 0, 0)
            c.drawString(margen_x, 24 * mm, f"CAD: {caducidad}")
        
        # QR
        if qr_texto:
            try:
                qr = qrcode.QRCode(box_size=4, border=1)
                qr.add_data(qr_texto)
                qr.make(fit=True)
                qr_img = qr.make_image(fill_color="black", back_color="white")
                
                qr_buffer = io.BytesIO()
                qr_img.save(qr_buffer, format='PNG')
                qr_buffer.seek(0)
                
                qr_reader = ImageReader(qr_buffer)
                c.drawImage(qr_reader, 21 * mm, 2 * mm, width=20 * mm, height=20 * mm)
            except:
                c.rect(21 * mm, 2 * mm, 20 * mm, 20 * mm)
                c.setFont(font_normal, 6)
                c.drawString(27 * mm, 10 * mm, "QR")
        
        c.save()
        print(f"  ↳ [V2] PDF generado: {os.path.basename(pdf_path)}")
        return pdf_path
        
    except Exception as e:
        print(f"❌ [V2] Error generando PDF: {e}")
        import traceback
        traceback.print_exc()
        raise


# ============================================================
# 🆕 NUEVO ENDPOINT: ETIQUETAS RÁPIDAS V2 (ASÍNCRONO)
# ============================================================
@app.route('/imprimir_etiqueta_rapida_v2', methods=['POST', 'OPTIONS'])
def imprimir_etiqueta_rapida_v2():
    """
    🆕 VERSIÓN ASÍNCRONA - NO AFECTA A OTRAS APPS
    Retorna inmediatamente, imprime en background
    """
    if request.method == 'OPTIONS':
        return '', 200
    
    try:
        datos = request.get_json(silent=True)
        if not datos:
            return jsonify({"status": "error", "message": "Cuerpo vacío"}), 400
            
        etiquetas = datos.get('etiquetas', [])
        if not etiquetas:
            return jsonify({"status": "error", "message": "No hay etiquetas"}), 400

        cantidad_total = len(etiquetas)
        print(f"🖨️ [V2] Recibidas {cantidad_total} etiquetas - ENCOLANDO...")
        
        for etiq in etiquetas:
            producto = etiq.get("producto", "S/P")
            lote = etiq.get("unidad", "S/L")
            fecha = etiq.get("fecha", "")
            qr_texto = etiq.get("texto_qr", "FREDWARE")
            
            pdf_path = generar_pdf_etiqueta_rapida_v2(producto, lote, fecha, qr_texto)
            cola_etiquetas_v2.put((pdf_path, producto, cantidad_total, 3))
            
        cola_status_v2["pendientes"] = cola_etiquetas_v2.qsize()
        
        return jsonify({
            "status": "success",
            "message": f"✅ {cantidad_total} etiqueta(s) en cola de impresión",
            "cola": cola_status_v2["pendientes"],
            "procesadas_hoy": cola_status_v2["procesadas"]
        }), 200
        
    except Exception as e:
        print(f"❌ [V2] Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500


# ============================================================
# 🆕 ENDPOINT: ESTADO DE LA COLA (SOLO CONSULTA)
# ============================================================
@app.route('/api/estado_cola_etiquetas', methods=['GET', 'OPTIONS'])
def estado_cola_etiquetas_v2():
    """
    Endpoint para monitorear la cola de impresión
    NO MODIFICA NADA, solo consulta
    """
    if request.method == 'OPTIONS':
        return '', 200
    
    return jsonify({
        "pendientes": cola_status_v2["pendientes"],
        "procesadas": cola_status_v2["procesadas"],
        "ultima_impresion": cola_status_v2["ultima_impresion"],
        "ultimo_error": cola_status_v2["ultimo_error"],
        "activo": cola_status_v2["activo"]
    }), 200


# ============================================================
# 🆕 ENDPOINT: LIMPIAR COLA (SOLO PARA EMERGENCIAS)
# ============================================================
@app.route('/api/limpiar_cola_etiquetas', methods=['POST', 'OPTIONS'])
def limpiar_cola_etiquetas_v2():
    """
    Endpoint de emergencia para limpiar la cola
    """
    if request.method == 'OPTIONS':
        return '', 200
    
    try:
        datos = request.get_json(silent=True)
        if not datos or datos.get('clave') != 'FREDWARE2024':
            return jsonify({"status": "error", "message": "Clave incorrecta"}), 401
        
        pendientes = cola_etiquetas_v2.qsize()
        
        while not cola_etiquetas_v2.empty():
            try:
                item = cola_etiquetas_v2.get_nowait()
                if item and isinstance(item, tuple) and len(item) > 0:
                    pdf_path = item[0]
                    try:
                        if os.path.exists(pdf_path):
                            os.unlink(pdf_path)
                    except:
                        pass
                cola_etiquetas_v2.task_done()
            except:
                break
        
        cola_status_v2["pendientes"] = 0
        
        return jsonify({
            "status": "success",
            "message": f"✅ Cola limpiada: {pendientes} etiquetas eliminadas"
        }), 200
        
    except Exception as e:
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
    
    conn = None
    try:
        conn = base_datos.conectar()
        cursor = conn.cursor()
        cursor.execute("SELECT nombre_produccion, ingredientes_detalle FROM fichas")
        for fila in cursor.fetchall():
            if fila[0]: 
                productos_ya_vistos.add(fila[0].replace("ENTRADA MERCANCÍA: ", "").upper())
    except Exception as e:
        print(f"⚠️ Error obteniendo catálogo: {e}")
    finally:
        if conn:
            db_pool.return_connection(conn)
    
    return jsonify({"status": "success", "productos": sorted(list(productos_ya_vistos)), "proveedores": sorted(list(proveedores_ya_vistos))}), 200

# ============================================================
# 🆕 ENDPOINTS: RESUMEN DIARIO
# ============================================================
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
    try:
        etiquetas = generador_pdf.cargar_etiquetas_dia()
        return jsonify({"total": len(etiquetas)}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# ============================================================
# 🆕 ENDPOINTS: ETIQUETAS
# ============================================================
@app.route('/api/etiquetas/total_dia', methods=['GET', 'OPTIONS'])
def total_etiquetas_dia():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        total = generador_pdf.get_total_etiquetas_dia()
        return jsonify({"total": total, "fecha": datetime.now().strftime("%Y-%m-%d")}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/etiquetas/imprimir_resumen', methods=['POST', 'OPTIONS'])
def imprimir_resumen_etiquetas():
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

# ============================================================
# 🆕 ENDPOINTS: FICHAS TÉCNICAS
# ============================================================
@app.route('/generar_ficha_a4', methods=['POST', 'OPTIONS'])
def generar_ficha_a4():
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

# ============================================================
# 🛒 EXTENSIÓN ONLINE: GESTIÓN DE COMPRAS
# ============================================================
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
        print("🛒 Cesta actualizada con éxito.")
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
        print("⚠️ Lista de faltas actualizada.")
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
        print("🏢 Lista de proveedores actualizada.")
        return jsonify({"status": "success"}), 200
    except Exception as e: 
        return jsonify({"status": "error", "message": str(e)}), 500

# ============================================================
# 📊 ENDPOINT DE CONTROL
# ============================================================
@app.route('/health', methods=['GET', 'OPTIONS'])
def health_check():
    if request.method == 'OPTIONS':
        return '', 200
    
    conn_status = "unknown"
    try:
        conn = base_datos.conectar()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.fetchone()
        db_pool.return_connection(conn)
        conn_status = "ok"
    except:
        conn_status = "error"
    
    return jsonify({
        "status": "online",
        "timestamp": datetime.now().isoformat(),
        "version": "5.6-Stable",
        "supabase": "connected" if supabase else "disconnected",
        "database": conn_status,
        "threads": threading.active_count(),
        "pool_size": len(db_pool._connections),
        "impresora": "SumatraPDF (WiFi)"
    }), 200

# ============================================================
# 🚀 INICIO DEL SERVIDOR
# ============================================================
if __name__ == '__main__':
    mostrar_logo_fredware()
    
    print("🖨️ Modo de impresión: SumatraPDF por WiFi")
    print("   Impresora: Brother QL-810W")
    print("   IP: 172.20.101.56")
    print("   Endpoints disponibles:")
    print("     - /imprimir_lote → Etiquetas completas (con bote, temp, proveedor)")
    print("     - /imprimir_etiqueta_rapida → Etiquetas rápidas (formato limpio)")
    print("     - /imprimir_etiqueta_rapida_v2 → Etiquetas rápidas (ASÍNCRONO) 🆕")
    
    try:
        base_datos.inicializar_base_datos()
        print("✅ Base de datos inicializada correctamente.")
    except Exception as e:
        print(f"⚠️ Nota al iniciar BD global: {e}")
    
    if supabase:
        try:
            if hasattr(generador_pdf, 'programar_guardado_automatico'):
                generador_pdf.programar_guardado_automatico(supabase)
                print("⏰ Guardado automático programado para las 00:00")
            else:
                print("⚠️ Función 'programar_guardado_automatico' no encontrada")
        except Exception as e:
            print(f"⚠️ Error programando guardado automático: {e}")
    
    # Iniciar worker de etiquetas V2
    threading.Thread(target=worker_etiquetas_v2, daemon=True).start()
    print("✅ Worker de etiquetas rápidas V2 iniciado (aislado)")
    
    print("🚀 Iniciando servidor Fredware en http://0.0.0.0:8000")
    print(f"🔧 Pool de conexiones SQLite: {db_pool.max_connections} conexiones")
    
    app.run(
        host='0.0.0.0', 
        port=8000, 
        debug=False, 
        threaded=True
    )