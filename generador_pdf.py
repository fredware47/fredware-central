import os
import sys
import json
import threading
import subprocess
from datetime import datetime, timedelta
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing

# ============================================================
# 🛠️ FUNCIÓN DE RUTA PARA PYINSTALLER
# ============================================================
def ruta_recurso(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# 🔒 LOCK para escritura segura del JSON de etiquetas
etiquetas_lock = threading.Lock()

# Intentar importar win32api para obtener la impresora predeterminada
try:
    import win32print
    IMPRESION_DIRECTA = True
except ImportError:
    IMPRESION_DIRECTA = False
    print("⚠️ pywin32 no instalado.")

# =========================================================================
# 🎛️ CONFIGURACIÓN DE IMPRESORA CENTRAL
# =========================================================================
TIPO_IMPRESORA = "BROTHER"

# 🔥 NOMBRE EXACTO DE TU IMPRESORA
IMPRESORA_FORZADA = "Brother QL-810W"

ARCHIVO_ETIQUETAS_DIA = ruta_recurso("etiquetas_dia.json")

# ============================================================
# 🔥 TAMAÑO DE ETIQUETA: 62mm x 60mm (PARA TODAS LAS ETIQUETAS)
# ============================================================
def obtener_medidas_rollo():
    """Retorna el tamaño de etiqueta: 62mm de ancho x 60mm de alto"""
    return 62 * mm, 60 * mm

# ============================================================
# 🔥 IMPRESIÓN DIRECTA CON SUMATRAPDF
# ============================================================
def imprimir_pdf(nombre_archivo):
    """
    Imprime el PDF directamente usando SumatraPDF.
    """
    print("🖨️  Imprimiendo directamente con SumatraPDF...")
    
    try:
        if IMPRESORA_FORZADA:
            nombre_impresora = IMPRESORA_FORZADA
        else:
            try:
                nombre_impresora = win32print.GetDefaultPrinter()
            except:
                nombre_impresora = "Brother QL-810W"
        
        print(f"🖨️  Impresora: {nombre_impresora}")
        print(f"🖨️  Archivo: {nombre_archivo}")
        
        sumatra_path = os.path.join(os.path.dirname(__file__), "SumatraPDF.exe")
        
        if not os.path.exists(sumatra_path):
            import shutil
            sumatra_path = shutil.which("SumatraPDF.exe")
        
        if not sumatra_path or not os.path.exists(sumatra_path):
            print("❌ SumatraPDF no encontrado.")
            return False
        
        print(f"✅ SumatraPDF encontrado: {sumatra_path}")
        
        comando = [
            sumatra_path,
            "-print-to", nombre_impresora,
            "-silent",
            nombre_archivo
        ]
        
        print(f"🖨️  Ejecutando: {' '.join(comando)}")
        
        resultado = subprocess.run(
            comando,
            capture_output=True,
            text=True,
            timeout=30,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        )
        
        if resultado.returncode == 0:
            print(f"✅ Etiqueta enviada a {nombre_impresora}")
            return True
        else:
            print(f"❌ Error al imprimir: {resultado.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print("❌ Timeout al imprimir")
        return False
    except Exception as e:
        print(f"❌ Error en impresión: {e}")
        return False

# =========================================================================
# ACUMULACIÓN DE ETIQUETAS DEL DÍA
# =========================================================================
def cargar_etiquetas_dia():
    if os.path.exists(ARCHIVO_ETIQUETAS_DIA):
        try:
            with open(ARCHIVO_ETIQUETAS_DIA, 'r', encoding='utf-8') as f:
                datos = json.load(f)
                hoy = datetime.now().strftime("%Y-%m-%d")
                if datos.get("fecha") == hoy:
                    return datos.get("etiquetas", [])
                else:
                    return []
        except Exception as e:
            print(f"Error al cargar etiquetas: {e}")
    return []

def guardar_etiquetas_dia(etiquetas):
    hoy = datetime.now().strftime("%Y-%m-%d")
    datos = {"fecha": hoy, "etiquetas": etiquetas}
    try:
        with etiquetas_lock:
            with open(ARCHIVO_ETIQUETAS_DIA, 'w', encoding='utf-8') as f:
                json.dump(datos, f, ensure_ascii=False, indent=4)
        return True
    except Exception as e:
        print(f"Error al guardar etiquetas: {e}")
        return False

def acumular_etiqueta(etiqueta):
    etiquetas = cargar_etiquetas_dia()
    etiquetas.append(etiqueta)
    guardar_etiquetas_dia(etiquetas)
    total = len(etiquetas)
    print(f"📌 Etiqueta acumulada: {etiqueta.get('producto', 'S/P')} - Total día: {total}")
    return total

def get_total_etiquetas_dia():
    return len(cargar_etiquetas_dia())

def get_etiquetas_dia():
    return cargar_etiquetas_dia()

# =========================================================================
# GUARDAR ETIQUETAS EN SUPABASE
# =========================================================================
def guardar_etiquetas_supabase(etiquetas, supabase_client=None):
    if supabase_client is None:
        try:
            from supabase import create_client
            SUPABASE_URL = "https://bhyprsjokwgazzzlfnbf.supabase.co"
            SUPABASE_KEY = "sb_publishable_i-g5o4tO1R8u6Fe7Fc2Q8Q_V_FV271y"
            supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
        except ImportError:
            print("⚠️ Supabase no disponible para guardar etiquetas")
            return False
    
    try:
        hoy = datetime.now().strftime("%Y-%m-%d")
        datos = {
            "fecha": hoy,
            "total_etiquetas": len(etiquetas),
            "etiquetas": json.dumps(etiquetas, ensure_ascii=False),
            "fecha_registro": datetime.now().isoformat()
        }
        
        response = supabase_client.table('registro_etiquetas')\
            .select('*')\
            .eq('fecha', hoy)\
            .execute()
        
        if response.data and len(response.data) > 0:
            supabase_client.table('registro_etiquetas')\
                .update(datos)\
                .eq('fecha', hoy)\
                .execute()
            print(f"☁️ Registro de etiquetas actualizado en Supabase ({len(etiquetas)} etiquetas)")
        else:
            supabase_client.table('registro_etiquetas')\
                .insert(datos)\
                .execute()
            print(f"☁️ Registro de etiquetas creado en Supabase ({len(etiquetas)} etiquetas)")
        
        return True
    except Exception as e:
        print(f"⚠️ Error guardando etiquetas en Supabase: {e}")
        return False

# =========================================================================
# GUARDADO AUTOMÁTICO A LAS 00:00
# =========================================================================
def programar_guardado_automatico(supabase_client=None):
    ahora = datetime.now()
    manana = ahora + timedelta(days=1)
    medianoche = manana.replace(hour=0, minute=0, second=0, microsecond=0)
    segundos_hasta_medianoche = (medianoche - ahora).total_seconds()
    
    print(f"⏰ Próximo guardado automático programado en {segundos_hasta_medianoche/3600:.1f} horas")
    
    threading.Timer(segundos_hasta_medianoche, ejecutar_guardado_automatico, args=[supabase_client]).start()

def ejecutar_guardado_automatico(supabase_client=None):
    print("🔄 Ejecutando guardado automático de etiquetas...")
    
    etiquetas = cargar_etiquetas_dia()
    if etiquetas:
        guardar_etiquetas_supabase(etiquetas, supabase_client)
        generar_resumen_dia()
    else:
        print("📭 No hay etiquetas para guardar hoy")
    
    programar_guardado_automatico(supabase_client)

def generar_resumen_dia(nombre_archivo=None):
    etiquetas = cargar_etiquetas_dia()
    if not etiquetas:
        print("No hay etiquetas para hoy.")
        return False

    if nombre_archivo is None:
        hoy = datetime.now().strftime("%d%m%Y")
        nombre_archivo = f"Resumen_Dia_{hoy}.pdf"

    for etiq in etiquetas:
        etiq.setdefault('producto', 'S/P')
        etiq.setdefault('unidad', '1 de 1')
        etiq.setdefault('fecha', datetime.now().strftime("%d/%m/%Y"))
        etiq.setdefault('texto_qr', 'FREDWARE')

    generar_etiquetas_recepcion(etiquetas, nombre_archivo, es_resumen=True)
    return True

# =========================================================================
# GENERADORES DE PDF
# =========================================================================

def generar_ficha_a4(datos_fichas, nombre_archivo="Ficha_Trazabilidad.pdf"):
    if isinstance(datos_fichas, dict):
        fichas = [datos_fichas]
    else:
        fichas = datos_fichas

    doc = SimpleDocTemplate(nombre_archivo, pagesize=A4, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
    styles = getSampleStyleSheet()
    
    style_titulo = ParagraphStyle('TxtTitA4', parent=styles['Heading1'], fontName='Helvetica-Bold', fontSize=20, leading=24, textColor=colors.HexColor("#1E293B"), spaceAfter=15)
    style_label = ParagraphStyle('TxtLblA4', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=11, leading=14, textColor=colors.HexColor("#475569"))
    style_valor = ParagraphStyle('TxtValA4', parent=styles['Normal'], fontName='Helvetica', fontSize=11, leading=14, textColor=colors.HexColor("#0F172A"))
    style_ingredientes = ParagraphStyle('TxtIngA4', parent=styles['Normal'], fontName='Courier', fontSize=10, leading=14, textColor=colors.HexColor("#1E293B"))

    story = []
    for i, ficha in enumerate(fichas):
        story.append(Paragraph("FREDWARE • FICHA DE PRODUCCION", style_titulo))
        story.append(Spacer(1, 10))
        
        datos_tabla = [
            [Paragraph("Producto / Preparación:", style_label), Paragraph(ficha.get('nombre', 'N/A'), style_valor)],
            [Paragraph("Número de Lote Interno:", style_label), Paragraph(ficha.get('lote', 'N/A'), style_valor)],
            [Paragraph("Fecha de Elaboración:", style_label), Paragraph(ficha.get('fecha_prep', 'N/A'), style_valor)]
        ]
        
        t_info = Table(datos_tabla, colWidths=[150, 320])
        t_info.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#F8FAFC")),
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('PADDING', (0,0), (-1,-1), 8),
            ('LINEBELOW', (0,0), (-1,-1), 0.5, colors.HexColor("#E2E8F0")),
            ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#CBD5E1")),
        ]))
        story.append(t_info)
        story.append(Spacer(1, 20))
        
        story.append(Paragraph("📋 COMPOSICIÓN Y TRAZABILIDAD DE INGREDIENTES:", style_label))
        story.append(Spacer(1, 8))
        
        texto_ingredientes_limpio = ficha.get('ingredientes', 'Sin ingredientes registrados.').replace('\r', '')
        p_ingredientes = Paragraph(texto_ingredientes_limpio.replace('\n', '<br/>'), style_ingredientes)
        
        t_ingredientes = Table([[p_ingredientes]], colWidths=[470])
        t_ingredientes.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#FFFFFF")),
            ('PADDING', (0,0), (-1,-1), 12),
            ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#94A3B8")),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ]))
        story.append(t_ingredientes)
        story.append(Spacer(1, 25))
        
        story.append(Paragraph("🔒 CÓDIGO QR DE VERIFICACIÓN:", style_label))
        story.append(Spacer(1, 10))
        
        contenido_qr = f"Producto:{ficha.get('nombre', 'N/A')} Lote:{ficha.get('lote', 'N/A')} Fecha:{ficha.get('fecha_prep', 'N/A')}"
        qr_widget = QrCodeWidget(contenido_qr)
        qr_widget.barWidth = 100
        qr_widget.barHeight = 100
        qr_widget.qrVersion = 4
        
        dibujo_qr = Drawing(100, 100)
        dibujo_qr.add(qr_widget)
        
        t_qr = Table([[dibujo_qr]], colWidths=[470])
        t_qr.setStyle(TableStyle([('ALIGN', (0,0), (-1,-1), 'LEFT'), ('PADDING', (0,0), (-1,-1), 0)]))
        story.append(t_qr)
        
        if i < len(fichas) - 1:
            story.append(PageBreak())

    doc.build(story)
    try:
        os.startfile(nombre_archivo)
    except:
        pass

# ============================================================
# 🔥 GENERAR ETIQUETAS STICKER (62mm x 60mm)
# ============================================================
def generar_etiquetas_sticker(datos_fichas, nombre_archivo="Etiquetas_Stickers.pdf"):
    if isinstance(datos_fichas, dict):
        fichas = [datos_fichas]
    else:
        fichas = datos_fichas

    ancho, alto = obtener_medidas_rollo()  # 62mm x 60mm
    
    print(f"📏 Generando sticker: {ancho/mm:.1f}mm x {alto/mm:.1f}mm")
    
    doc = SimpleDocTemplate(
        nombre_archivo, 
        pagesize=(ancho, alto), 
        rightMargin=2*mm, 
        leftMargin=2*mm, 
        topMargin=4*mm, 
        bottomMargin=4*mm
    )
    styles = getSampleStyleSheet()
    
    # Estilos para el nuevo tamaño
    style_tit_sticker = ParagraphStyle(
        'TitStk', 
        parent=styles['Normal'], 
        fontName='Helvetica-Bold', 
        fontSize=12, 
        leading=14,
        spaceAfter=2
    )
    style_txt_sticker = ParagraphStyle(
        'TxtStk', 
        parent=styles['Normal'], 
        fontName='Helvetica', 
        fontSize=10, 
        leading=12,
        spaceAfter=2
    )

    ancho_texto = 38 * mm
    ancho_qr = 20 * mm  # Ligeramente más pequeño para el nuevo formato

    story = []
    for i, ficha in enumerate(fichas):
        story.append(Paragraph("<b>🏷️ FREDWARE</b>", style_tit_sticker))
        story.append(Spacer(1, 1))
        
        lineas_info = (
            f"<b>PROD:</b> {ficha.get('nombre', 'N/A')[:25].upper()}<br/>"
            f"<b>LOTE:</b> {ficha.get('lote', 'N/A')}<br/>"
            f"<b>FECHA:</b> {ficha.get('fecha_prep', 'N/A')}"
        )
        p_info = Paragraph(lineas_info, style_txt_sticker)
        
        contenido_qr = f"Producto:{ficha.get('nombre', 'N/A')} Lote:{ficha.get('lote', 'N/A')} Fecha:{ficha.get('fecha_prep', 'N/A')}"
        qr_widget = QrCodeWidget(contenido_qr)
        qr_widget.barWidth = ancho_qr
        qr_widget.barHeight = ancho_qr
        qr_widget.qrVersion = 4
        
        dibujo_qr = Drawing(ancho_qr, ancho_qr)
        dibujo_qr.add(qr_widget)
        
        tabla_sticker = Table([[p_info, dibujo_qr]], colWidths=[ancho_texto, ancho_qr + 2*mm])
        tabla_sticker.setStyle(TableStyle([
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('ALIGN', (1,0), (1,0), 'RIGHT'),
            ('PADDING', (0,0), (-1,-1), 1*mm),
        ]))
        story.append(tabla_sticker)
        
        if i < len(fichas) - 1:
            story.append(PageBreak())

    doc.build(story)
    imprimir_pdf(nombre_archivo)

# ============================================================
# 🔥 GENERAR ETIQUETAS RECEPCIÓN (62mm x 60mm)
# ============================================================
def generar_etiquetas_recepcion(lote_etiquetas, nombre_archivo="Etiquetas_Recepcion.pdf", imprimir=True, es_resumen=False):
    ancho, alto = obtener_medidas_rollo()  # 62mm x 60mm
    
    print(f"📏 Generando etiqueta recepción: {ancho/mm:.1f}mm x {alto/mm:.1f}mm")
    
    doc = SimpleDocTemplate(
        nombre_archivo, 
        pagesize=(ancho, alto), 
        rightMargin=2*mm, 
        leftMargin=2*mm, 
        topMargin=4*mm, 
        bottomMargin=4*mm
    )
    
    styles = getSampleStyleSheet()
    
    # Estilos ajustados para el nuevo tamaño
    style_tit = ParagraphStyle(
        'TitRec', 
        fontName='Helvetica-Bold', 
        fontSize=12, 
        leading=14,
        spaceAfter=2
    )
    style_body = ParagraphStyle(
        'BodyRec', 
        fontName='Helvetica', 
        fontSize=10, 
        leading=12,
        spaceAfter=2
    )

    ancho_texto = 38 * mm
    ancho_qr = 20 * mm  # Ligeramente más pequeño

    story = []
    for i, etiq in enumerate(lote_etiquetas):
        nom_prod = etiq.get('producto', 'S/P')[:28].upper()
        story.append(Paragraph(f"<b>📥 {nom_prod}</b>", style_tit))
        story.append(Spacer(1, 1))

        unidad = etiq.get('unidad', '1 de 1')
        temp = etiq.get('temperatura', '4')
        prov = etiq.get('proveedor', 'MAKRO')[:18].upper()
        fecha = etiq.get('fecha', '')

        lineas_datos = (
            f"<b>BOTE:</b> {unidad}<br/>"
            f"<b>TEMP:</b> {temp} °C<br/>"
            f"<b>PROV:</b> {prov}<br/>"
            f"<b>FECHA:</b> {fecha}"
        )
        p_datos = Paragraph(lineas_datos, style_body)

        qr_widget = QrCodeWidget(etiq.get('texto_qr', 'FREDWARE'))
        qr_widget.barWidth = ancho_qr
        qr_widget.barHeight = ancho_qr
        qr_widget.qrVersion = 4
        
        dibujo_qr = Drawing(ancho_qr, ancho_qr)
        dibujo_qr.add(qr_widget)

        tabla = Table([[p_datos, dibujo_qr]], colWidths=[ancho_texto, ancho_qr + 2*mm])
        tabla.setStyle(TableStyle([
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('ALIGN', (1,0), (1,0), 'RIGHT'),
            ('PADDING', (0,0), (-1,-1), 1*mm),
        ]))
        story.append(tabla)

        if i < len(lote_etiquetas) - 1:
            story.append(PageBreak())

    doc.build(story)
    
    if imprimir:
        imprimir_pdf(nombre_archivo)
        if es_resumen:
            print(f"📄 Resumen del día impreso: {nombre_archivo} ({len(lote_etiquetas)} etiquetas)")
        else:
            print(f"📄 Etiqueta recepción impresa: {nombre_archivo}")
        
        if not es_resumen:
            for etiq in lote_etiquetas:
                total = acumular_etiqueta(etiq)
                print(f"📌 Total etiquetas hoy: {total}")
    else:
        print(f"📄 PDF generado (sin imprimir): {nombre_archivo}")

# ============================================================
# 🔥 GENERAR ETIQUETAS CADUCIDADES (62mm x 60mm)
# ============================================================
def generar_etiquetas_caducidades(lote_etiquetas, nombre_archivo="Etiquetas_Caducidades.pdf", imprimir=True):
    """
    Genera etiquetas para caducidades con formato de 62mm x 60mm.
    Incluye: Producto, Lote, Proceso, Caducidad y QR.
    """
    ancho, alto = obtener_medidas_rollo()  # 62mm x 60mm
    
    print(f"📏 Generando etiqueta caducidad: {ancho/mm:.1f}mm x {alto/mm:.1f}mm")
    
    doc = SimpleDocTemplate(
        nombre_archivo, 
        pagesize=(ancho, alto), 
        rightMargin=2*mm, 
        leftMargin=2*mm, 
        topMargin=4*mm, 
        bottomMargin=4*mm
    )
    
    styles = getSampleStyleSheet()
    
    # Estilos ajustados para el nuevo tamaño
    style_titulo = ParagraphStyle(
        'TitCad',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=14,
        spaceAfter=2
    )
    
    style_dato = ParagraphStyle(
        'DatoCad',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=12,
        spaceAfter=2
    )
    
    style_dato_grande = ParagraphStyle(
        'DatoCadGrande',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=13,
        leading=15,
        spaceAfter=2,
        textColor=colors.HexColor("#DC2626")
    )

    ancho_texto = 38 * mm
    ancho_qr = 20 * mm

    story = []
    for i, etiq in enumerate(lote_etiquetas):
        producto = etiq.get('producto', 'S/P')[:28].upper()
        story.append(Paragraph(f"<b>📦 {producto}</b>", style_titulo))
        story.append(Spacer(1, 1))
        
        lote = etiq.get('unidad', 'S/L')[:15].upper()
        story.append(Paragraph(f"<b>LOTE:</b> {lote}", style_dato))
        
        proceso = etiq.get('proceso', 'ELABORADO')[:18].upper()
        story.append(Paragraph(f"<b>PROCESO:</b> {proceso}", style_dato))
        
        fecha = etiq.get('fecha', 'S/F')
        story.append(Paragraph(f"<b>🕐 VENCE:</b> {fecha}", style_dato_grande))
        
        story.append(Spacer(1, 2))
        
        qr_widget = QrCodeWidget(etiq.get('texto_qr', 'FREDWARE'))
        qr_widget.barWidth = ancho_qr
        qr_widget.barHeight = ancho_qr
        qr_widget.qrVersion = 4
        
        dibujo_qr = Drawing(ancho_qr, ancho_qr)
        dibujo_qr.add(qr_widget)
        
        tabla = Table([[dibujo_qr]], colWidths=[ancho_qr + 2*mm])
        tabla.setStyle(TableStyle([
            ('ALIGN', (0,0), (-1,-1), 'RIGHT'),
            ('PADDING', (0,0), (-1,-1), 1*mm),
        ]))
        story.append(tabla)

        if i < len(lote_etiquetas) - 1:
            story.append(PageBreak())

    doc.build(story)
    
    if imprimir:
        imprimir_pdf(nombre_archivo)
        print(f"📄 Etiqueta caducidad impresa: {nombre_archivo}")
        
        for etiq in lote_etiquetas:
            total = acumular_etiqueta(etiq)
            print(f"📌 Total etiquetas hoy: {total}")
    else:
        print(f"📄 PDF generado (sin imprimir): {nombre_archivo}")
    
    return True

# ============================================================
# 🔥 FUNCIONES PARA EL SERVIDOR FLASK
# ============================================================

def iniciar_servidor():
    """
    Función para iniciar el servidor Flask con todas las rutas.
    """
    try:
        from flask import Flask, request, jsonify
        from flask_cors import CORS
        
        app = Flask(__name__)
        CORS(app)
        
        # ============================================================
        # RUTAS EXISTENTES
        # ============================================================
        
        @app.route('/imprimir_lote', methods=['POST'])
        def imprimir_lote():
            """Endpoint para imprimir etiquetas de recepción"""
            try:
                data = request.get_json()
                etiquetas = data.get('etiquetas', [])
                
                if not etiquetas:
                    return jsonify({'error': 'No hay etiquetas'}), 400
                
                nombre_archivo = f"etiquetas_{datetime.now().strftime('%H%M%S')}.pdf"
                generar_etiquetas_recepcion(etiquetas, nombre_archivo, imprimir=True)
                
                return jsonify({
                    'success': True,
                    'message': f'Etiquetas impresas: {len(etiquetas)}',
                    'total_dia': get_total_etiquetas_dia()
                })
                
            except Exception as e:
                print(f"❌ Error en /imprimir_lote: {e}")
                return jsonify({'error': str(e)}), 500
        
        @app.route('/guardar_mercancia', methods=['POST'])
        def guardar_mercancia():
            """Endpoint para guardar mercancía en la base de datos"""
            try:
                data = request.get_json()
                print(f"📦 Datos guardados: {data}")
                return jsonify({'success': True, 'message': 'Datos guardados'})
            except Exception as e:
                print(f"❌ Error en /guardar_mercancia: {e}")
                return jsonify({'error': str(e)}), 500
        
        @app.route('/generar_ficha_a4', methods=['POST'])
        def generar_ficha_a4_endpoint():
            """Endpoint para generar ficha A4"""
            try:
                data = request.get_json()
                fichas = data.get('fichas', [data])
                nombre_archivo = f"ficha_{datetime.now().strftime('%H%M%S')}.pdf"
                generar_ficha_a4(fichas, nombre_archivo)
                return jsonify({'success': True, 'message': 'Ficha generada'})
            except Exception as e:
                print(f"❌ Error en /generar_ficha_a4: {e}")
                return jsonify({'error': str(e)}), 500
        
        @app.route('/generar_sticker', methods=['POST'])
        def generar_sticker():
            """Endpoint para generar stickers de producción"""
            try:
                data = request.get_json()
                fichas = [data]
                nombre_archivo = f"sticker_{datetime.now().strftime('%H%M%S')}.pdf"
                generar_etiquetas_sticker(fichas, nombre_archivo)
                return jsonify({'success': True, 'message': 'Sticker generado'})
            except Exception as e:
                print(f"❌ Error en /generar_sticker: {e}")
                return jsonify({'error': str(e)}), 500
        
        @app.route('/generar_ficha_a4_masiva', methods=['POST'])
        def generar_ficha_a4_masiva():
            """Endpoint para generar múltiples fichas A4"""
            try:
                data = request.get_json()
                fichas = data.get('fichas', [])
                nombre_archivo = f"fichas_masivas_{datetime.now().strftime('%H%M%S')}.pdf"
                generar_ficha_a4(fichas, nombre_archivo)
                return jsonify({'success': True, 'message': f'{len(fichas)} fichas generadas'})
            except Exception as e:
                print(f"❌ Error en /generar_ficha_a4_masiva: {e}")
                return jsonify({'error': str(e)}), 500
        
        @app.route('/generar_sticker_masivo', methods=['POST'])
        def generar_sticker_masivo():
            """Endpoint para generar múltiples stickers"""
            try:
                data = request.get_json()
                stickers = data.get('stickers', [])
                nombre_archivo = f"stickers_masivos_{datetime.now().strftime('%H%M%S')}.pdf"
                generar_etiquetas_sticker(stickers, nombre_archivo)
                return jsonify({'success': True, 'message': f'{len(stickers)} stickers generados'})
            except Exception as e:
                print(f"❌ Error en /generar_sticker_masivo: {e}")
                return jsonify({'error': str(e)}), 500
        
        @app.route('/obtener_mercancias', methods=['GET'])
        def obtener_mercancias():
            """Endpoint para obtener mercancías"""
            return jsonify([])
        
        @app.route('/obtener_catalogo', methods=['GET'])
        def obtener_catalogo():
            """Endpoint para obtener catálogo de productos"""
            catalogo = ['ARROZ', 'LENTEJAS', 'GARBANZOS', 'AZÚCAR', 'HARINA', 'SAL', 'ACEITE', 'VINAGRE', 'PASTA', 'TOMATE']
            return jsonify({'productos': catalogo})
        
        # ============================================================
        # 🔥 RUTA PARA CADUCIDADES
        # ============================================================
        
        @app.route('/imprimir_lote_caducidades', methods=['POST'])
        def imprimir_lote_caducidades():
            """Endpoint para imprimir etiquetas de caducidades (62mm x 60mm)"""
            try:
                data = request.get_json()
                etiquetas = data.get('etiquetas', [])
                
                if not etiquetas:
                    return jsonify({'error': 'No hay etiquetas'}), 400
                
                for etiq in etiquetas:
                    etiq.setdefault('proceso', 'ELABORADO')
                    etiq.setdefault('unidad', 'S/L')
                    etiq.setdefault('fecha', datetime.now().strftime("%d/%m/%Y"))
                    etiq.setdefault('texto_qr', 'FREDWARE')
                
                nombre_archivo = f"caducidades_{datetime.now().strftime('%H%M%S')}.pdf"
                generar_etiquetas_caducidades(etiquetas, nombre_archivo, imprimir=True)
                
                return jsonify({
                    'success': True,
                    'message': f'Etiquetas impresas: {len(etiquetas)}',
                    'total_dia': get_total_etiquetas_dia()
                })
                
            except Exception as e:
                print(f"❌ Error en /imprimir_lote_caducidades: {e}")
                return jsonify({'error': str(e)}), 500
        
        # ============================================================
        # RUTAS PARA ETIQUETAS
        # ============================================================
        
        @app.route('/api/etiquetas/imprimir_resumen', methods=['POST'])
        def imprimir_resumen():
            """Endpoint para imprimir resumen del día"""
            try:
                resultado = generar_resumen_dia()
                if resultado:
                    return jsonify({'success': True, 'message': 'Resumen impreso'})
                else:
                    return jsonify({'success': False, 'message': 'No hay etiquetas para hoy'}), 400
            except Exception as e:
                print(f"❌ Error en /api/etiquetas/imprimir_resumen: {e}")
                return jsonify({'error': str(e)}), 500
        
        @app.route('/api/etiquetas/guardar_supabase', methods=['POST'])
        def guardar_supabase():
            """Endpoint para guardar etiquetas en Supabase"""
            try:
                etiquetas = cargar_etiquetas_dia()
                if etiquetas:
                    guardar_etiquetas_supabase(etiquetas)
                    return jsonify({'success': True, 'message': f'{len(etiquetas)} etiquetas guardadas'})
                else:
                    return jsonify({'success': False, 'message': 'No hay etiquetas'}), 400
            except Exception as e:
                print(f"❌ Error en /api/etiquetas/guardar_supabase: {e}")
                return jsonify({'error': str(e)}), 500
        
        @app.route('/api/contador_dia', methods=['GET'])
        def contador_dia():
            """Endpoint para obtener el total de etiquetas del día"""
            try:
                total = get_total_etiquetas_dia()
                return jsonify({'total': total})
            except Exception as e:
                print(f"❌ Error en /api/contador_dia: {e}")
                return jsonify({'error': str(e)}), 500
        
        @app.route('/api/etiquetas/total_dia', methods=['GET'])
        def total_dia():
            """Endpoint para obtener etiquetas del día"""
            try:
                etiquetas = get_etiquetas_dia()
                return jsonify({'total': len(etiquetas), 'etiquetas': etiquetas})
            except Exception as e:
                print(f"❌ Error en /api/etiquetas/total_dia: {e}")
                return jsonify({'error': str(e)}), 500
        
        return app
        
    except ImportError:
        print("⚠️ Flask no instalado. Las rutas HTTP no estarán disponibles.")
        return None

# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    app = iniciar_servidor()
    if app:
        print("🚀 Servidor iniciado en http://localhost:5000")
        print("📏 Tamaño de etiqueta: 62mm x 60mm")
        print("🖨️  Impresora: Brother QL-810W")
        app.run(host='0.0.0.0', port=5000, debug=False)
    else:
        print("❌ No se pudo iniciar el servidor. Verifica que Flask esté instalado.")