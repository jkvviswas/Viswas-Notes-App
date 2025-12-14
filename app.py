from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_jwt_extended import (
    JWTManager, create_access_token, jwt_required, get_jwt_identity
)
from models import db, User
from local_db import LocalDB
from sync_manager import SyncManager
from datetime import timedelta
import os

# Initialize Flask app
app = Flask(__name__)
CORS(app)  # Allow frontend to access backend

# Configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///notes.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JWT_SECRET_KEY'] = os.environ.get('JWT_SECRET_KEY', 'supersecret')
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=24)

# Initialize extensions
db.init_app(app)
jwt = JWTManager(app)

# Initialize sync manager
sync_manager = SyncManager(api_url="http://localhost:5000/api")

# ---------- Authentication ----------
@app.route('/api/register', methods=['POST'])
def register():
    """Register a new user"""
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({'error': 'Email and password required'}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({'error': 'Email already registered'}), 400

    user = User(email=email)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    token = create_access_token(identity=user.id)
    return jsonify({'message': 'Registered successfully', 'token': token, 'user': user.to_dict()}), 201


@app.route('/api/login', methods=['POST'])
def login():
    """Login user"""
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(password):
        return jsonify({'error': 'Invalid credentials'}), 401

    token = create_access_token(identity=user.id)
    return jsonify({'message': 'Login successful', 'token': token, 'user': user.to_dict()}), 200


# ---------- Notes CRUD ----------
@app.route('/api/notes', methods=['GET'])
@jwt_required()
def get_notes():
    user_id = get_jwt_identity()
    search = request.args.get('search')
    notes = LocalDB.get_notes(user_id, search)
    return jsonify(notes), 200


@app.route('/api/notes/<int:note_id>', methods=['GET'])
@jwt_required()
def get_note(note_id):
    user_id = get_jwt_identity()
    note = LocalDB.get_note(note_id, user_id)
    if not note:
        return jsonify({'error': 'Note not found'}), 404
    return jsonify(note), 200


@app.route('/api/notes', methods=['POST'])
@jwt_required()
def create_note():
    user_id = get_jwt_identity()
    data = request.get_json()
    title = data.get('title')
    content = data.get('content')
    tags = data.get('tags', [])
    if not title or not content:
        return jsonify({'error': 'Title and content required'}), 400
    note = LocalDB.create_note(user_id, title, content, tags)
    return jsonify(note), 201


@app.route('/api/notes/<int:note_id>', methods=['PUT'])
@jwt_required()
def update_note(note_id):
    user_id = get_jwt_identity()
    data = request.get_json()
    version = data.get('version')
    current = LocalDB.get_note(note_id, user_id)

    if not current:
        return jsonify({'error': 'Note not found'}), 404
    if version and current['version'] > version:
        return jsonify({'error': 'Conflict detected', 'note': current}), 409

    note = LocalDB.update_note(
        note_id, user_id, data.get('title'), data.get('content'), data.get('tags')
    )
    return jsonify(note), 200


@app.route('/api/notes/<int:note_id>', methods=['DELETE'])
@jwt_required()
def delete_note(note_id):
    user_id = get_jwt_identity()
    if not LocalDB.delete_note(note_id, user_id):
        return jsonify({'error': 'Note not found'}), 404
    return jsonify({'message': 'Note deleted'}), 200


# ---------- Health Check ----------
@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({'status': 'healthy'}), 200


# ---------- Initialize ----------
@app.before_request
def create_tables_once():
    """Create database tables only once (Flask 3.x compatible)"""
    if not hasattr(app, "_db_created"):
        with app.app_context():
            db.create_all()
            app._db_created = True



if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, host='0.0.0.0', port=5000)
