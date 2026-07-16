"""
Script de prueba local. Corre el parser (y opcionalmente publica) sin
necesitar levantar el servidor Flask.

Uso:
    python run_local.py preview nota_semana.docx
    python run_local.py publicar nota_semana.docx
"""
import os
import sys
from dotenv import load_dotenv
from word_to_wp import WordToWordPress

load_dotenv()

WP_URL = os.getenv('WP_URL')
WP_USER = os.getenv('WP_USER')
WP_APP_PASSWORD = os.getenv('WP_APP_PASSWORD')


def preview(docx_path):
    wp = WordToWordPress(WP_URL, WP_USER, WP_APP_PASSWORD)
    notes = wp.extract_notes(docx_path)

    if not notes:
        print('⚠️  No se detectó ninguna nota. Revisá que el primer párrafo con')
        print('    estilo @1VOLA esté bien aplicado en el Word.')
        return

    print(f'\n📋 Se detectaron {len(notes)} nota(s):\n')
    for i, n in enumerate(notes, 1):
        print(f'--- Nota {i} ---')
        print(f'  Volanta : {n["volanta"] or "(vacío)"}')
        print(f'  Título  : {n["titulo"] or "(vacío)"}')
        print(f'  Copete  : {n["copete"] or "(vacío)"}')
        print(f'  Categoría: {n["metadatos"]["categoria"] or "(sin categoría)"}')
        print(f'  Tags    : {n["metadatos"]["tags"] or "(sin tags)"}')
        print(f'  Imagen  : {"sí" if n["imagen"] else "no"}')
        print(f'  Párrafos de cuerpo: {len(n["cuerpo_parrafos"])}')
        print()


def publicar(docx_path):
    if not all([WP_URL, WP_USER, WP_APP_PASSWORD]):
        print('❌ Faltan variables de entorno. Revisá tu archivo .env')
        return

    resultados = process_file(docx_path, status='publish')

    print('\n📊 Resumen:')
    for r in resultados:
        estado = '✅' if r.get('ok') else '❌'
        print(f'  {estado} Nota: {r.get("titulo", "")} - Link: {r["link"] if r.get("ok") else "Error -> " + str(r.get("error"))}')

def process_file(docx_path, status='publish'):
    wp = WordToWordPress(WP_URL, WP_USER, WP_APP_PASSWORD)
    notes = wp.extract_notes(docx_path)
    for result in wp.publish_notes(notes, status=status):
        print(f'Nota: {result["titulo"]} -> {"Estado: " + ("✅" if result['status'] == 'published' else "❌")}')


if __name__ == '__main__':
    """PRUEBAS: Permite correr el parser y publicar notas sin levantar el servidor Flask."""

    if len(sys.argv) != 3 or sys.argv[1] not in ('preview', 'publicar'):
        print(__doc__)
        sys.exit(1)

    modo, archivo = sys.argv[1], sys.argv[2]
    if not os.path.exists(archivo):
        print(f'❌ No encuentro el archivo: {archivo}')
        sys.exit(1)

    if modo == 'preview':
        preview(archivo)
    else:
        publicar(archivo)