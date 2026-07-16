from datetime import datetime
from sqlalchemy import (Column, Integer, String, Text, DateTime,
                         ForeignKey, JSON, UniqueConstraint)
from sqlalchemy.orm import relationship, declarative_base

Base = declarative_base()


class Document(Base):
    __tablename__ = 'documents'

    id = Column(Integer, primary_key=True)
    filename = Column(String(255), nullable=False)
    file_hash = Column(String(64), unique=True, index=True)  # sha256, evita re-procesar el mismo docx
    status = Column(String(20), default='pending')  # pending | processing | done | error
    total_notes = Column(Integer, default=0)
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    error_message = Column(Text, nullable=True)

    notes = relationship('Note', back_populates='document', cascade='all, delete-orphan')


class Note(Base):
    __tablename__ = 'notes'

    id = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey('documents.id'), nullable=False)
    indice = Column(Integer)  # orden dentro del docx

    volanta = Column(String(255))
    titulo = Column(String(255))
    copete = Column(Text)
    cuerpo_parrafos = Column(JSON)  # lista de strings
    categoria = Column(String(120))
    tags = Column(JSON)

    status = Column(String(20), default='pending')  # pending | publishing | published | failed
    wp_post_id = Column(Integer, nullable=True)
    wp_link = Column(String(500), nullable=True)
    error_message = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    document = relationship('Document', back_populates='notes')


class TermCache(Base):
    """Reemplaza el cache en memoria de categorías/tags de word_to_wp.py.
    Necesario porque con Gunicorn multi-worker o RQ workers separados,
    un dict en memoria no se comparte entre procesos."""
    __tablename__ = 'term_cache'
    __table_args__ = (UniqueConstraint('name', 'taxonomy', name='uq_term'),)

    id = Column(Integer, primary_key=True)
    name = Column(String(120), nullable=False)
    taxonomy = Column(String(20), nullable=False)  # categories | tags
    wp_term_id = Column(Integer, nullable=False)