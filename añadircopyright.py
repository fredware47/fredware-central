#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Añade aviso de copyright a todos los archivos del proyecto Fredware.
Ejecutar UNA vez desde la raíz del proyecto.
"""
import os
from pathlib import Path

# ════════════════════════════════════════════════════════════
# CONFIGURACIÓN — EDITA ESTAS DOS LÍNEAS
# ════════════════════════════════════════════════════════════
AUTOR = "TU NOMBRE COMPLETO"
EMAIL = "tu@email.com"
AÑO = "2026"

# ════════════════════════════════════════════════════════════
# PLANTILLAS DE AVISO POR TIPO DE ARCHIVO
# ════════════════════════════════════════════════════════════

AVISO_HTML = """<!--
════════════════════════════════════════════════════════════
  FREDWARE · {nombre}
  © {año} {autor} — Todos los derechos reservados.
  Software propietario. Prohibida su reproducción, distribución
  o modificación sin autorización escrita.
  Contacto: {email}
════════════════════════════════════════════════════════════
-->
"""

AVISO_JS = """// ════════════════════════════════════════════════════════════
//  FREDWARE · {nombre}
//  © {año} {autor} — Todos los derechos reservados.
//  Software propietario. Prohibida su reproducción, distribución
//  o modificación sin autorización escrita.
//  Contacto: {email}
// ════════════════════════════════════════════════════════════
"""

AVISO_PY = '''"""
════════════════════════════════════════════════════════════
  FREDWARE · {nombre}
  © {año} {autor} — Todos los derechos reservados.
  Software propietario. Prohibida su reproducción, distribución
  o modificación sin autorización escrita.
  Contacto: {email}
════════════════════════════════════════════════════════════
"""
'''

AVISO_CSS = """/* ════════════════════════════════════════════════════════════
 *  FREDWARE · {nombre}
 *  © {año} {autor} — Todos los derechos reservados.
 *  Software propietario.
 * ════════════════════════════════════════════════════════════ */
"""

AVISO_TXT = """════════════════════════════════════════════════════════════
  FREDWARE · {nombre}
  © {año} {autor} — Todos los derechos reservados.
  Software propietario. Contacto: {email}
════════════════════════════════════════════════════════════

"""

# ════════════════════════════════════════════════════════════
# EXTENSIONES Y SU AVISO
# ════════════════════════════════════════════════════════════
EXTENSIONES = {
    '.html': AVISO_HTML,
    '.htm':  AVISO_HTML,
    '.js':   AVISO_JS,
    '.py':   AVISO_PY,
    '.css':  AVISO_CSS,
    '.txt':  AVISO_TXT,
}

# Archivos a EXCLUIR (no queremos tocar estos)
EXCLUIR = {
    'LICENSE.txt',
    'añadir_copyright.py',
    'README.md',
}

# Texto que indica que ya tiene aviso (para no duplicar)
MARCA_YA_TIENE = 'FREDWARE · '


def tiene_aviso(contenido: str) -> bool:
    """Detecta si el archivo ya tiene nuestro aviso."""
    return MARCA_YA_TIENE in contenido[:800]


def añadir_aviso(ruta: Path) -> bool:
    """Añade el aviso al principio del archivo. Devuelve True si lo modificó."""
    ext = ruta.suffix.lower()
    if ext not in EXTENSIONES:
        return False
    if ruta.name in EXCLUIR:
        return False

    try:
        contenido = ruta.read_text(encoding='utf-8')
    except UnicodeDecodeError:
        print(f"   ⚠️  Saltado (no UTF-8): {ruta.name}")
        return False

    if tiene_aviso(contenido):
        print(f"   ○  Ya tiene aviso: {ruta.name}")
        return False

    # Para HTML, después de <!DOCTYPE html> si existe
    if ext in ('.html', '.htm'):
        aviso = EXTENSIONES[ext].format(nombre=ruta.name, año=AÑO, autor=AUTOR, email=EMAIL)
        # Buscar posición después de <!DOCTYPE html>\n
        lower = contenido.lower()
        idx = lower.find('<!doctype html>')
        if idx != -1:
            fin = contenido.find('>', idx) + 1
            nuevo = contenido[:fin] + '\n' + aviso + contenido[fin:]
        else:
            nuevo = aviso + contenido
    else:
        aviso = EXTENSIONES[ext].format(nombre=ruta.name, año=AÑO, autor=AUTOR, email=EMAIL)
        nuevo = aviso + contenido

    ruta.write_text(nuevo, encoding='utf-8')
    print(f"   ✅ Modificado: {ruta.name}")
    return True


def main():
    raiz = Path('.')
    print()
    print("════════════════════════════════════════════════════════")
    print("  AÑADIENDO COPYRIGHT A FREDWARE")
    print(f"  Autor: {AUTOR}")
    print(f"  Año: {AÑO}")
    print("════════════════════════════════════════════════════════")
    print()

    modificados = 0
    total = 0

    # Recorrer el proyecto
    for ruta in sorted(raiz.rglob('*')):
        # Saltar carpetas pesadas
        if any(part in ruta.parts for part in ('node_modules', '.git', '__pycache__', 'dist', 'build')):
            continue
        if not ruta.is_file():
            continue
        if ruta.suffix.lower() not in EXTENSIONES:
            continue

        total += 1
        if añadir_aviso(ruta):
            modificados += 1

    print()
    print("════════════════════════════════════════════════════════")
    print(f"  RESUMEN: {modificados} modificados de {total} archivos")
    print("════════════════════════════════════════════════════════")
    print()


if __name__ == '__main__':
    main()