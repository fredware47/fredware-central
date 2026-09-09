import sqlite3

def conectar():
    """Establece conexión con la base de datos local."""
    return sqlite3.connect("trazabilidad_cocina.db")

def inicializar_base_datos():
    """Crea la estructura de la tabla asegurando todos los campos necesarios."""
    conexion = conectar()
    cursor = conexion.cursor()
    
    # Tabla de fichas (existente)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS fichas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre_produccion TEXT NOT NULL,
            lote TEXT NOT NULL,
            fecha_preparacion TEXT NOT NULL,
            fecha_llegada_ingredientes TEXT,
            ingredientes_detalle TEXT
        )
    """)
    
    # 🔥 TABLA: recepciones (historial local para fallback)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS recepciones (
            id TEXT PRIMARY KEY,
            producto TEXT NOT NULL,
            proveedor TEXT,
            cantidad INTEGER DEFAULT 1,
            unidad TEXT DEFAULT 'UN',
            fecha_registro TEXT,
            fecha_recibido TEXT,
            observaciones TEXT
        )
    """)
    
    # Tabla de mercancías (existente)
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
    
    # Tabla de recepciones_mercancia (APPCC local)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS recepciones_mercancia (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            producto TEXT NOT NULL,
            proveedor TEXT,
            temperatura REAL,
            conservacion TEXT,
            cantidad INTEGER DEFAULT 1,
            fecha_registro TEXT,
            autorizado_por TEXT
        )
    """)
    
    # Tabla de faltas (local)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS faltas_cocina (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            insumo TEXT NOT NULL,
            fecha_anotado TEXT
        )
    """)
    
    # Tabla de cesta (local)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cesta_pedidos (
            id TEXT PRIMARY KEY,
            detalle TEXT NOT NULL,
            proveedor_id TEXT,
            estado TEXT DEFAULT 'PENDIENTE',
            fecha_registro TEXT,
            fecha_entrega_esperada TEXT
        )
    """)
    
    conexion.commit()
    conexion.close()

def registrar_entrada_mercancia(producto, proveedor, fecha_recepcion):
    """
    Inserta la entrada del camión en la base de datos con el formato
    exacto que busca la aplicación principal al rellenar fichas.
    """
    conexion = conectar()
    cursor = conexion.cursor()
    
    linea_trazabilidad = f"• {producto.upper()} (Lote Prov: {proveedor.upper()}) - Llegada: {fecha_recepcion}"
    lote_recepcion = f"REC-{fecha_recepcion.replace('/', '')}"
    
    cursor.execute("""
        INSERT INTO fichas (nombre_produccion, lote, fecha_preparacion, fecha_llegada_ingredientes, ingredientes_detalle)
        VALUES (?, ?, ?, ?, ?)
    """, (f"ENTRADA MERCANCÍA: {producto.upper()}", lote_recepcion, fecha_recepcion, fecha_recepcion, linea_trazabilidad))
    
    conexion.commit()
    conexion.close()

if __name__ == "__main__":
    inicializar_base_datos()
    print("¡Base de datos inicializada correctamente con todos los campos!")
