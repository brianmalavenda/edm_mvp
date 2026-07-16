import hashlib
import os
from flask import Blueprint, request, jsonify, current_app
from werkzeug.utils import secure_filename
from .db.db import SessionLocal
from .db.models import Document, Note # hago referencia a la carpeta db.models para poder usar Document y Note en las rutas, y que SQLAlchemy pueda mapearlos a la base de datos.
# NOTA: SQLAlchemy es un ORM, y para que funcione correctamente, las clases de modelo (Document y Note) deben estar definidas en el mismo contexto que la sesión de la base de 
# datos.
from .tasks import queue_process_document

main_bp = Blueprint('main', __name__, url_prefix='/api')

UPLOAD_DIR = os.getenv('UPLOAD_DIR', '/data/uploads')  # bind mount, mismo patrón que tus otros servicios


@main_bp.post('/upload')
def upload_docx():
    if 'file' not in request.files:
        return jsonify({'error': 'falta el archivo'}), 400

    file = request.files['file']
    filename = secure_filename(file.filename)
    if not filename.endswith('.docx'):
        return jsonify({'error': 'sólo se aceptan .docx'}), 400

    file_bytes = file.read()
    file_hash = hashlib.sha256(file_bytes).hexdigest()

    db = SessionLocal()
    existing = db.query(Document).filter_by(file_hash=file_hash).first()
    if existing:
        return jsonify({'error': 'este archivo ya fue procesado', 'document_id': existing.id}), 409

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    filepath = os.path.join(UPLOAD_DIR, f'{file_hash}_{filename}')
    with open(filepath, 'wb') as f:
        f.write(file_bytes)

    doc = Document(filename=filename, file_hash=file_hash, status='pending')
    db.add(doc) # esto genera un INSERT en la tabla documents y asigna un id autoincremental a doc.id
    db.commit() # el commit es necesario para que se guarde en la base de datos y se genere el id, antes de encolar el job.

    queue_process_document(doc.id, filepath)  # encola el job async, no bloquea el request

    return jsonify({'document_id': doc.id, 'status': 'queued'}), 202


@main_bp.get('/documents/<int:doc_id>')
def get_document_status(doc_id):
    db = SessionLocal()
    doc = db.query(Document).get(doc_id)
    if not doc:
        return jsonify({'error': 'no encontrado'}), 404

    return jsonify({
        'id': doc.id,
        'filename': doc.filename,
        'status': doc.status,
        'total_notes': doc.total_notes,
        'error_message': doc.error_message,
        'notes': [{
            'id': n.id, 'titulo': n.titulo, 'status': n.status,
            'wp_link': n.wp_link, 'error_message': n.error_message,
        } for n in doc.notes]
    })


@main_bp.get('/notes')
def list_notes():
    status = request.args.get('status')
    categoria = request.args.get('categoria')

    db = SessionLocal()
    query = db.query(Note)
    if status:
        query = query.filter(Note.status == status)
    if categoria:
        query = query.filter(Note.categoria == categoria)

    notes = query.order_by(Note.created_at.desc()).limit(100).all()
    return jsonify([{
        'id': n.id, 'titulo': n.titulo, 'categoria': n.categoria,
        'status': n.status, 'wp_link': n.wp_link,
    } for n in notes])


@main_bp.post('/notes/<int:note_id>/retry')
def retry_note(note_id):
    """Reintenta publicar una nota que falló, sin re-parsear todo el docx."""
    from .tasks import queue_retry_note
    queue_retry_note(note_id)
    return jsonify({'status': 'requeued'})


@main_bp.post('/preview')
def preview_docx():
    """Parsea el docx SIN publicar ni persistir nada. Solo para que el
    frontend muestre qué se va a publicar antes de confirmarlo."""
    if 'file' not in request.files:
        return jsonify({'error': 'falta el archivo'}), 400

    file = request.files['file']
    filename = secure_filename(file.filename)
    if not filename.endswith('.docx'):
        return jsonify({'error': 'sólo se aceptan .docx'}), 400

    tmp_path = os.path.join('/tmp', filename)
    file.save(tmp_path)

    try:
        wp = WordToWordPress(
            current_app.config['WP_URL'],
            current_app.config['WP_USER'],
            current_app.config['WP_APP_PASSWORD'],
        )
        notes = wp.extract_notes(tmp_path)
    finally:
        os.remove(tmp_path)

    return jsonify({
        'notes': [{
            'indice': i,
            'titulo': n['titulo'] or '(sin título)',
            'tiene_volanta': bool(n['volanta']),
            'tiene_copete': bool(n['copete']),
            'tiene_imagen': n['imagen'] is not None,
        } for i, n in enumerate(notes, 1)]
    })