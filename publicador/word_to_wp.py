import os
import requests
import base64
from docx import Document
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
import re

class WordToWordPress:
    def __init__(self, wp_url, username, app_password):
        self.wp_url = wp_url.rstrip('/')
        self.auth = (username, app_password)
        self.headers = {'Content-Type': 'application/json'}
    
    def extract_content(self, docx_path):
        """Extrae contenido del Word por estilos"""
        doc = Document(docx_path)
        content = {
            'volanta': '',
            'titulo': '',
            'copete': '',
            'cuerpo': '',
            'images': []
        }
        
        # Mapeo de estilos (ajusta según tus estilos reales en Word)
        style_map = {
            'VOLANTA': 'volanta',
            'TITULO': 'titulo', 
            'TÍTULO': 'titulo',
            'COPETE': 'copete',
            'CUERPO': 'cuerpo'
        }
        
        current_section = 'cuerpo'
        html_content = []
        
        for para in doc.paragraphs:
            style_name = para.style.name.upper()
            text = para.text.strip()
            
            if not text:
                continue
            
            # Detectar sección por estilo
            for word_style, section in style_map.items():
                if word_style in style_name:  # ¿El estilo del párrafo contiene "VOLANTA"?
                    current_section = section # → Ahora estamos en sección "volanta"
                     # Si es volanta, título o copete, guarda el texto en el diccionario
                    if section in ['volanta', 'titulo', 'copete', 'cuerpo']:
                        content[section] = text 
                    break
            
            # Construir HTML según sección
            if current_section == 'volanta':
                html_content.append(f'<p class="volanta">{text}</p>')
            elif current_section == 'titulo':
                html_content.append(f'<h1 class="titulo">{text}</h1>')
            elif current_section == 'copete':
                html_content.append(f'<p class="copete"><strong>{text}</strong></p>')
            elif current_section == 'cuerpo':
                html_content.append(f'<p>{text}</p>')
        
        # Extraer imágenes
        image_count = 0
        for rel in doc.part.rels.values():
            if "image" in rel.target_ref:
                image_count += 1
                image_data = rel.target_part.blob
                image_name = f'image_{image_count}.jpg'
                content['images'].append({
                    'name': image_name,
                    'data': image_data
                })
        
        content['cuerpo'] = '\n'.join(html_content)
        return content
    
    def upload_image(self, image_data, image_name):
        """Sube imagen a WordPress y retorna ID"""
        url = f'{self.wp_url}/wp-json/wp/v2/media'
        headers = {
            'Content-Type': 'image/jpeg',
            'Content-Disposition': f'attachment; filename={image_name}'
        }
        
        response = requests.post(
            url,
            headers=headers,
            auth=self.auth,
            data=image_data
        )
        
        if response.status_code == 201:
            return response.json()['id'], response.json()['media_details']['sizes']['medium']['source_url']
        return None, None
    
    def create_post(self, content, category_id=None):
        """Crea el post en WordPress"""
        url = f'{self.wp_url}/wp-json/wp/v2/posts'
        
        # Subir primera imagen como featured
        featured_image_id = None
        final_content = content['cuerpo']
        
        if content['images']:
            # Primera imagen como featured
            img_id, img_url = self.upload_image(
                content['images'][0]['data'],
                content['images'][0]['name']
            )
            featured_image_id = img_id
            
            # Insertar resto de imágenes en el contenido
            for i, img in enumerate(content['images'][1:], 1):
                img_id, img_url = self.upload_image(img['data'], img['name'])
                if img_url:
                    final_content += f'<figure class="wp-block-image"><img src="{img_url}"/></figure>'
        
        post_data = {
            'title': content['titulo'],
            'content': final_content,
            'excerpt': content['copete'],
            'status': 'draft',  # Cambiar a 'publish' para publicar directo
            'meta': {
                'volanta': content['volanta']
            }
        }
        
        if featured_image_id:
            post_data['featured_media'] = featured_image_id
        
        if category_id:
            post_data['categories'] = [category_id]
        
        response = requests.post(
            url,
            json=post_data,
            auth=self.auth,
            headers=self.headers
        )
        
        if response.status_code == 201:
            post_id = response.json()['id']
            post_link = response.json()['link']
            print(f'✅ Post creado: {post_link}')
            return post_id
        else:
            print(f'❌ Error: {response.text}')
            return None
    
    def process_file(self, docx_path, category_id=None):
        """Procesa un archivo completo"""
        print(f'📄 Procesando: {docx_path}')
        content = self.extract_content(docx_path)
        
        if not content['titulo']:
            print('⚠️ No se encontró título, saltando...')
            return None
        
        return self.create_post(content, category_id)