import os
import re
import requests
import base64
from docx import Document
from docx.oxml.ns import qn
from html import escape as html_escape


class WordToWordPress:
    """
    Parsea un .docx del periódico EDM (con estilos @1VOLA, @2TITULO, @3COPETE,
    @4NOTA) y publica cada nota detectada como una entrada nueva en WordPress
    vía REST API.

    Formato esperado por nota dentro del Word:

        [@1VOLA]   La volanta
        [normal]   [cat: Institucionales | tags: elecciones, centro de estudiantes]
        [@2TITULO] El título
        [@3COPETE] El copete
        [imagen embebida]   (opcional, se sube como featured image)
        [@4NOTA]   Cuerpo de la nota (uno o varios párrafos)

    La siguiente nota arranca en el próximo párrafo con estilo @1VOLA.
    """

    # Nombres de estilo normalizados (sin espacios, mayúsculas) -> sección lógica
    STYLE_MAP = {
        '@1VOLA': 'volanta',
        '@2TITULO': 'titulo',
        '@3COPETE': 'copete',
        '@4NOTA': 'cuerpo',
    }

    # [cat: Institucionales | tags: elecciones, centro de estudiantes]
    METADATA_PATTERN = re.compile(
        r'\[\s*cat\s*:\s*(?P<cat>[^|\]]+?)\s*\|\s*tags\s*:\s*(?P<tags>[^\]]+?)\s*\]',
        re.IGNORECASE,
    )

    # constructor de esta clase, recibe la url del wordpress, el usuario y la contraseña de aplicación
    def __init__(self, wp_url, username, app_password):
        self.wp_url = wp_url.rstrip('/')
        credentials = f"{username}:{app_password}"
        credentials_encoded = base64.b64encode(credentials.encode('utf-8')).decode('utf-8')

        self.headers = {
            'Content-Type': 'application/json',
            # 'Authorization': f'Basic {credentials_encoded}',
        }
        # Cache en memoria para no repetir llamadas si varias notas comparten
        # categoría/etiqueta dentro de la misma corrida
        self._category_cache = {}
        self._tag_cache = {}

        self.session = requests.Session()
        self.auth = (username, app_password)
        self.session.auth = self.auth
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) EDM-Publicador/1.0',
        })

    # ------------------------------------------------------------------
    # Parseo del .docx
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_style(style_name):
        """Normaliza el nombre de estilo para poder compararlo con STYLE_MAP."""
        return re.sub(r'\s+', '', style_name or '').upper()

    @staticmethod
    def _new_empty_note():
        return {
            'volanta': '',
            'titulo': '',
            'copete': '',
            'cuerpo_parrafos': [],
            'metadatos': {
                'categoria': None,
                'tags': []
            },
            'imagen': None,  # {'data': bytes, 'filename': str, 'content_type': str}
        }

    def _extract_image_from_paragraph(self, paragraph, doc_part):
        """Busca una imagen embebida dentro de un párrafo específico
        (no en todo el documento), para poder asociarla a la nota correcta."""
        for run in paragraph.runs:
            drawings = run._element.findall('.//' + qn('w:drawing'))
            for drawing in drawings:
                blip = drawing.find('.//' + qn('a:blip'))
                if blip is None:
                    continue
                embed_id = blip.get(qn('r:embed'))
                if not embed_id:
                    continue
                image_part = doc_part.related_parts.get(embed_id)
                if image_part is None:
                    continue
                ext = image_part.content_type.split('/')[-1]
                ext = 'jpg' if ext == 'jpeg' else ext
                return {
                    'data': image_part.blob,
                    'filename': f'imagen.{ext}',
                    'content_type': image_part.content_type,
                }
        return None

    def extract_notes(self, docx_path):
        """Recorre el .docx y devuelve una lista de notas (dicts).
        Cada @1VOLA cierra la nota anterior (si existía) y abre una nueva."""
        doc = Document(docx_path)
        doc_part = doc.part

        notes = []
        current_note = None
        current_section = None

        for para in doc.paragraphs:
            style_key = self._normalize_style(para.style.name)
            """ strip() para eliminar espacios en blanco al inicio y al final del texto del párrafo. """
            text = para.text.strip()

            # Inicio de una nota nueva
            if style_key == '@1VOLA':
                if current_note is not None:
                    notes.append(current_note)
                current_note = self._new_empty_note()
                current_note['volanta'] = text
                # current_section es la sección siguiente que se espera luego de setear el paraffo en curso. En este caso la siguiente seccion esperada son los metadatos
                current_section = 'metadatos'
                continue

            # Si todavía no arrancó ninguna nota (ej. texto suelto antes del
            # primer @1VOLA, recuadros, etc.), lo ignoramos por ahora
            if current_note is None:
                continue

            # Línea de metadata [cat: ... | tags: ...] — se busca sin importar
            # el estilo del párrafo, y no pasa al cuerpo
            if current_section == 'metadatos':
                meta_match = self.METADATA_PATTERN.search(text)
                if meta_match:
                    current_note['metadatos']['categoria'] = meta_match.group('cat').strip()
                    current_note['metadatos']['tags'] = [
                        t.strip() for t in meta_match.group('tags').split(',') if t.strip()
                    ]
                    current_section = 'titulo'  # siguiente sección esperada
                    continue
                else:
                    print(f'⚠️ No se detectó metadata en el párrafo: "{text}"')
                    current_section = 'titulo'

            # Cambio de sección por estilo reconocido
            # print(f'current_section: {current_section}, style_key: {style_key}, text: {text}')

            if style_key in self.STYLE_MAP:
                current_style = self.STYLE_MAP[style_key]

                if current_section == 'titulo' and current_style == 'titulo':
                    current_note['titulo'] = text
                    current_section = 'copete'  # siguiente sección esperada    
                    continue
                elif current_section == 'copete' and current_style == 'copete':
                    current_note['copete'] = text
                    current_section = 'cuerpo'  # siguiente sección esperada    
                    continue
                # en la seccion del cuerpo se puede encontrar con una imagen o un texto, en cualquier orden de parrafo
                # por eso aca hay que tener en cuenta que si el current_section es 'cuerpo' y el texto no es vacio, se agrega a los parrafos del cuerpo, y si es una imagen se agrega a la nota
                # hay que verificar que la imagen del cuerpo de la nota tenga el estilo @NOTA para que se mapee con el tipo "cuerpo"
                elif current_section == 'cuerpo' and current_style == 'cuerpo':
                    if text:
                        current_note['cuerpo_parrafos'].append(text)
                    else:
                        # buscamos la imagen en el parrafo si la current_note no tiene aún una imgen seteada.
                        if current_note['imagen'] is None:
                            img = self._extract_image_from_paragraph(para, doc_part)
                            if img:
                                current_note['imagen'] = img

        if current_note is not None:
            notes.append(current_note)

        return notes

    def _build_content_html(self, note):
        parts = []
        if note['copete']:
            parts.append(f'<p class="copete"><strong>{html_escape(note["copete"])}</strong></p>')
        for parrafo in note['cuerpo_parrafos']:
            parts.append(f'<p>{html_escape(parrafo)}</p>')
        return '\n'.join(parts)

    # ------------------------------------------------------------------
    # WordPress REST API
    # ------------------------------------------------------------------
    def _get_or_create_term(self, name, taxonomy):
        """taxonomy: 'categories' o 'tags'. Reusa el término si ya existe,
        lo crea si no."""
        name = (name or '').strip()
        if not name:
            return None
 
        cache = self._category_cache if taxonomy == 'categories' else self._tag_cache
        key = name.lower()
        if key in cache:
            return cache[key]
 
        base_url = f'{self.wp_url}/wp-json/wp/v2/{taxonomy}'
 
        # 1) Buscar si ya existe
        resp = self.session.get(base_url, params={'search': name})
        if resp.status_code == 200:
            for item in resp.json():
                if item['name'].strip().lower() == key:
                    cache[key] = item['id']
                    return item['id']
        else:
            self._debug_error(f'Búsqueda de "{name}" en {taxonomy} falló', resp)
 
        # 2) No existía (o no lo encontramos): crearlo
        resp = self.session.post(
            base_url,
            json={'name': name, 'slug': name.lower(), 'description': ''},
        )
 
        if resp.status_code == 201:
            term_id = resp.json()['id']
            cache[key] = term_id
            return term_id
 
        # 3) Condición de carrera / búsqueda anterior falló pero el término
        # ya existía: WordPress devuelve el term_id directo en el error
        if resp.status_code == 400 and 'term_exists' in resp.text:
            try:
                term_id = resp.json().get('data', {}).get('term_id')
            except ValueError:
                term_id = None
            if term_id:
                cache[key] = term_id
                return term_id
 
        self._debug_error(f'No se pudo crear/obtener "{name}" en {taxonomy}', resp)
        return None

    def upload_image(self, image_data, filename, content_type):
        """Sube una imagen a la Media Library y devuelve (id, url)."""
        url = f'{self.wp_url}/wp-json/wp/v2/media'
        headers = {
            'Content-Type': content_type,
            'Content-Disposition': f'attachment; filename="{filename}"',
        }
        resp = self.session.post(url, headers=headers, data=image_data)
        if resp.status_code == 201:
            data = resp.json()
            return data['id'], data.get('source_url')
        print(f'⚠️ Error subiendo imagen "{filename}": {resp.text}')
        return None, None

    def create_post(self, note, status='publish'):
        """Crea el post en WordPress para una nota ya parseada."""
        category_ids = []
        if note['metadatos']['categoria']:
            cat_id = self._get_or_create_term(note['metadatos']['categoria'], 'categories')
            if cat_id:
                category_ids.append(cat_id)

        tag_ids = []
        for tag_name in note['metadatos']['tags']:
            tag_id = self._get_or_create_term(tag_name, 'tags')
            if tag_id:
                tag_ids.append(tag_id)

        featured_media_id = None
        if note['imagen']:
            featured_media_id, _ = self.upload_image(
                note['imagen']['data'],
                note['imagen']['filename'],
                note['imagen']['content_type'],
            )

        post_data = {
            'title': note['titulo'] or '(Sin título)',
            'excerpt': note['copete'],
            'status': status,
            'content': self._build_content_html(note),
            'meta': {
                'volanta': note['volanta'] or ''
            }
        }

        if featured_media_id:
            post_data['featured_media'] = featured_media_id
        if category_ids:
            post_data['categories'] = category_ids
        if tag_ids:
            post_data['tags'] = tag_ids

        url = f'{self.wp_url}/wp-json/wp/v2/posts'
        resp = self.session.post(url, json=post_data, headers=self.headers)
        print(f'Respuesta: {resp.status_code} - {resp.text}')
        if resp.status_code == 201:
            data = resp.json()
            print(f'✅ Post creado: {data["link"]}')
            return {'ok': True, 'id': data['id'], 'link': data['link']}

        print(f'❌ Error creando post "{note["titulo"]}": {resp.text}')
        return {'ok': False, 'error': resp.text}

    # ------------------------------------------------------------------
    # Orquestación
    # ------------------------------------------------------------------

    def process_file(self, docx_path, status='publish'):
        """Parsea el .docx completo y publica todas las notas detectadas.
        Devuelve una lista de resultados, uno por nota."""
        print(f'📄 Procesando: {docx_path}')
        notes = self.extract_notes(docx_path)

        if not notes:
            print('⚠️ No se detectaron notas en el archivo (¿falta el estilo @1VOLA?)')
            return []

        results = []
        for i, note in enumerate(notes, 1):
            if not note['titulo']:
                print(f'⚠️ Nota {i} sin título, se omite')
                results.append({'ok': False, 'error': 'sin título', 'nota_index': i})
                continue

            print(f'  → Nota {i}: {note["titulo"]}')
            result = self.create_post(note, status=status)
            result['nota_index'] = i
            result['titulo'] = note['titulo']
            results.append(result)

        return results