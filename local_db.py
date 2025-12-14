from models import db, Note
from datetime import datetime
from sqlalchemy import or_

class LocalDB:
    """Handles local SQLite CRUD operations"""
    
    @staticmethod
    def create_note(user_id, title, content, tags=None):
        """Create a new note locally"""
        try:
            note = Note(
                user_id=user_id,
                title=title,
                content=content,
                tags=','.join(tags) if tags else '',
                version=1
            )
            db.session.add(note)
            db.session.commit()
            return note.to_dict()
        except Exception as e:
            db.session.rollback()
            raise Exception(f"Failed to create note: {str(e)}")
    
    @staticmethod
    def get_notes(user_id, search_query=None):
        """Retrieve all notes for a user with optional search"""
        try:
            query = Note.query.filter_by(user_id=user_id, is_deleted=False)
            
            if search_query:
                search = f"%{search_query}%"
                query = query.filter(
                    or_(
                        Note.title.ilike(search),
                        Note.content.ilike(search),
                        Note.tags.ilike(search)
                    )
                )
            
            notes = query.order_by(Note.updated_at.desc()).all()
            return [note.to_dict() for note in notes]
        except Exception as e:
            raise Exception(f"Failed to retrieve notes: {str(e)}")
    
    @staticmethod
    def get_note(note_id, user_id):
        """Get a specific note by ID"""
        try:
            note = Note.query.filter_by(
                id=note_id, 
                user_id=user_id, 
                is_deleted=False
            ).first()
            return note.to_dict() if note else None
        except Exception as e:
            raise Exception(f"Failed to retrieve note: {str(e)}")
    
    @staticmethod
    def update_note(note_id, user_id, title=None, content=None, tags=None):
        """Update an existing note"""
        try:
            note = Note.query.filter_by(
                id=note_id, 
                user_id=user_id, 
                is_deleted=False
            ).first()
            
            if not note:
                return None
            
            if title is not None:
                note.title = title
            if content is not None:
                note.content = content
            if tags is not None:
                note.tags = ','.join(tags) if tags else ''
            
            note.updated_at = datetime.utcnow()
            note.version += 1  # Increment version for conflict detection
            
            db.session.commit()
            return note.to_dict()
        except Exception as e:
            db.session.rollback()
            raise Exception(f"Failed to update note: {str(e)}")
    
    @staticmethod
    def delete_note(note_id, user_id):
        """Soft delete a note (for sync purposes)"""
        try:
            note = Note.query.filter_by(
                id=note_id, 
                user_id=user_id
            ).first()
            
            if not note:
                return False
            
            note.is_deleted = True
            note.updated_at = datetime.utcnow()
            note.version += 1
            
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            raise Exception(f"Failed to delete note: {str(e)}")
    
    @staticmethod
    def get_unsynced_notes(user_id):
        """Get notes that haven't been synced yet"""
        try:
            notes = Note.query.filter(
                Note.user_id == user_id,
                or_(
                    Note.synced_at.is_(None),
                    Note.updated_at > Note.synced_at
                )
            ).all()
            return [note.to_dict() for note in notes]
        except Exception as e:
            raise Exception(f"Failed to get unsynced notes: {str(e)}")
    
    @staticmethod
    def mark_synced(note_id):
        """Mark a note as successfully synced"""
        try:
            note = Note.query.get(note_id)
            if note:
                note.synced_at = datetime.utcnow()
                db.session.commit()
        except Exception as e:
            db.session.rollback()
            raise Exception(f"Failed to mark note as synced: {str(e)}")
