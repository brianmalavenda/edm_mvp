import os
from redis import Redis
from rq import Queue
from .db import SessionLocal
from .models import Document, Note
from .word_to_wp import WordToWordPress

redis_conn = Redis.from_url(os.getenv('REDIS_URL', 'redis://wordpress_redis:6379/1'))  # DB index 1 para no chocar con el object cache de WP
queue = Queue('publicador', connection=redis_conn)



def queue_process_document(document_id, filepath):
    queue.enqueue(process_document, document_id, filepath, job_timeout=600)

def make_term_cache_fns(db):
    def get(name, taxonomy):
        row = db.query(TermCache).filter_by(name=name.lower(), taxonomy=taxonomy).first()
        return row.wp_term_id if row else None

    def set_(name, taxonomy, term_id):
        db.add(TermCache(name=name.lower(), taxonomy=taxonomy, wp_term_id=term_id))
        db.commit()

    return get, set_

def process_document(document_id, filepath):
    """
    Este job se ejecuta en un worker de RQ, no en el request del usuario.
    Se encarga de procesar el docx, extraer las notas y publicarlas en
    """
    db = SessionLocal()
    get_fn, set_fn = make_term_cache_fns(db)
    doc = db.query(Document).get(document_id)
    doc.status = 'processing'
    db.commit()

    try:
        wp = WordToWordPress(
            os.getenv('WP_URL'), os.getenv('WP_USER'), os.getenv('WP_APP_PASSWORD'), term_cache_get=get_fn, term_cache_set=set_fn
        )
        notes = wp.extract_notes(filepath)

        ### Publicar las notas en WordPress ###

        # publish_notes es un generador que yield-ea el resultado de cada nota a medida que se publica, orquesta extract/create_post.
        for result in wp.publish_notes(parsed_notes, status='publish'):
            note_data = result['note_data']
            note.status = result['status']
            note.wp_post_id = result['id']
            note.wp_link = result['link']

            ## Guardar las notas en la base de datos ###
            doc.total_notes = len(notes)
            db.commit()
            note_data=result['note_data']
            
            note = Note(
                document_id=doc.id, indice=i,
                volanta=note_data['volanta'], titulo=note_data['titulo'],
                copete=note_data['copete'], cuerpo_parrafos=note_data['cuerpo_parrafos'][:2],  # solo los dos primeros parrafos
                categoria=note_data['metadatos']['categoria'],
                tags=note_data['metadatos']['tags']
            )

            db.add(note)
            db.commit()

        doc.status = 'done'
    except Exception as e:
        doc.status = 'error'
        doc.error_message = str(e)
    finally:
        db.commit()
        db.close()


def queue_retry_note(note_id):
    queue.enqueue(retry_note_job, note_id)


def retry_note_job(note_id):
    # misma lógica que un item del loop de arriba, reconstruyendo el dict
    # note_data desde la fila de Note para volver a llamar wp.create_post()
    ...