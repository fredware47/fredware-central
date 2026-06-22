import sqlite3

def conectar():
    """Establece conexión con la base de datos local."""
    return sqlite3.connect("trazabilidad_cocina.db")

def inicializar_base_datos():
    """Crea la estructura de la tabla asegurando todos los campos necesarios."""
    conexion = conectar()
    cursor = conexion.cursor()
    
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
    
    conexion.commit()
    conexion.close()

def registrar_entrada_mercancia(producto, proveedor, fecha_recepcion):
    """
    Inserta la entrada del camión en la base de datos con el formato
    exacto que busca la aplicación principal al rellenar fichas.
    """
    conexion = conectar()
    cursor = conexion.cursor()
    
    # Formato idéntico al del cuadro de texto: • PRODUCTO (Lote Prov: PROVEEDOR) - Llegada: DD/MM/YYYY
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