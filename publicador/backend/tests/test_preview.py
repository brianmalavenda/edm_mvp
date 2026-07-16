"""Tests automatizados del modo preview.

Verifican que los documentos de ejemplo en test/docs produzcan la cantidad
y forma de notas descritas en test/descripcion_test.md, sin necesidad de
conectarse a WordPress.
"""

import os
import pytest
from backend.word_to_wp import WordToWordPress

DOCS_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'test', 'docs')


def _doc_path(filename):
    return os.path.abspath(os.path.join(DOCS_DIR, filename))


@pytest.fixture
def wp():
    """Instancia del parser sin credenciales reales (solo extrae notas)."""
    return WordToWordPress('http://dummy.test', 'user', 'pass')


def test_prueba_01_dos_notas_con_metadata_e_imagen(wp):
    """prueba_01.docx: 2 notas con categoría/tags; solo la primera imagen."""
    notes = wp.extract_notes(_doc_path('prueba_01.docx'))

    assert len(notes) == 2, f"Se esperaban 2 notas, se obtuvieron {len(notes)}"

    for n in notes:
        assert n['volanta'], "La volanta no puede ser vacía"
        assert n['titulo'], "El título no puede ser vacío"
        assert n['copete'], "El copete no puede ser vacío"
        assert n['cuerpo_parrafos'], "El cuerpo debe tener al menos un párrafo"
        assert n['metadatos']['categoria'], "Se esperaba categoría"
        assert n['metadatos']['tags'], "Se esperaban tags"

    assert notes[0]['imagen'] is not None, "La primera nota debe tener imagen"
    assert notes[1]['imagen'] is None, "La segunda nota no debe tener imagen"


def test_prueba_02_diez_notas_sin_metadata(wp):
    """prueba_02.docx: 10 notas, 4 con imagen, sin categoría/tags."""
    notes = wp.extract_notes(_doc_path('prueba_02.docx'))

    assert len(notes) == 10, f"Se esperaban 10 notas, se obtuvieron {len(notes)}"

    with_image = sum(1 for n in notes if n['imagen'] is not None)
    assert with_image == 4, f"Se esperaban 4 notas con imagen, se obtuvieron {with_image}"

    for i, n in enumerate(notes, start=1):
        assert n['volanta'], f"Nota {i}: la volanta no puede ser vacía"
        assert n['titulo'], f"Nota {i}: el título no puede ser vacío"
        assert n['copete'], f"Nota {i}: el copete no puede ser vacío"
        assert n['cuerpo_parrafos'], f"Nota {i}: el cuerpo debe tener al menos un párrafo"
        assert n['metadatos']['categoria'] is None, f"Nota {i}: no debe tener categoría"
        assert n['metadatos']['tags'] == [], f"Nota {i}: no debe tener tags"


def test_prueba_03_trece_notas_ignora_indice_inicial(wp):
    """prueba_03.docx: 13 notas ignorando el índice previo, 4 con imagen."""
    notes = wp.extract_notes(_doc_path('prueba_03.docx'))

    assert len(notes) == 13, f"Se esperaban 13 notas, se obtuvieron {len(notes)}"

    with_image = sum(1 for n in notes if n['imagen'] is not None)
    assert with_image == 4, f"Se esperaban 4 notas con imagen, se obtuvieron {with_image}"

    for i, n in enumerate(notes, start=1):
        assert n['volanta'], f"Nota {i}: la volanta no puede ser vacía"
        assert n['titulo'], f"Nota {i}: el título no puede ser vacío"
        assert n['copete'], f"Nota {i}: el copete no puede ser vacío"
        assert n['cuerpo_parrafos'], f"Nota {i}: el cuerpo debe tener al menos un párrafo"
        assert n['metadatos']['categoria'] is None, f"Nota {i}: no debe tener categoría"
        assert n['metadatos']['tags'] == [], f"Nota {i}: no debe tener tags"
