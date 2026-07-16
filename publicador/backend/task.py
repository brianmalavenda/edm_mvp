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


def process_document(document_id, filepath):
    db = SessionLocal()
    doc = db.query(Document).get(document_id)
    doc.status = 'processing'
    db.commit()

    try:
        wp = WordToWordPress(
            os.getenv('WP_URL'), os.getenv('WP_USER'), os.getenv('WP_APP_PASSWORD')
        )
        parsed_notes = wp.extract_notes(filepath)
        doc.total_notes = len(parsed_notes)
        db.commit()

        for i, note_data in enumerate(parsed_notes, 1):
            note = Note(
                document_id=doc.id, indice=i,
                volanta=note_data['volanta'], titulo=note_data['titulo'],
                copete=note_data['copete'], cuerpo_parrafos=note_data['cuerpo_parrafos'],
                categoria=note_data['metadatos']['categoria'],
                tags=note_data['metadatos']['tags'],
                status='publishing',
            )
            db.add(note)
            db.commit()

            result = wp.create_post(note_data, status='publish')
            if result.get('ok'):
                note.status = 'published'
                note.wp_post_id = result['id']
                note.wp_link = result['link']
            else:
                note.status = 'failed'
                note.error_message = str(result.get('error'))
            db.commit()

        doc.status = 'done'
    except Exception as e:
        doc.status = 'error'
        doc.error_message = str(e)
    finally:
        db.commit()


def queue_retry_note(note_id):
    queue.enqueue(retry_note_job, note_id)


def retry_note_job(note_id):
    # misma lógica que un item del loop de arriba, reconstruyendo el dict
    # note_data desde la fila de Note para volver a llamar wp.create_post()
    ...