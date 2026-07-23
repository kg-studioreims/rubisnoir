import os
import sqlite3
import json
import time
from flask import Flask, render_template, request, session, jsonify, g
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Middleware pour autoriser la communication de la popup Google (Cross-Origin-Opener-Policy)
@app.after_request
def add_cors_headers(response):
    response.headers['Cross-Origin-Opener-Policy'] = 'unsafe-none'
    response.headers['Cross-Origin-Embedder-Policy'] = 'unsafe-none'
    return response

GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "YOUR_GOOGLE_CLIENT_ID.apps.googleusercontent.com")
DATABASE = '/data/rubis_noir.db' if os.path.exists('/data') else 'rubis_noir.db'
ADMIN_EMAIL = 'kg.studio.reims@gmail.com'

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None: db.close()

def init_db():
    with app.app_context():
        db = get_db()
        db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                email TEXT PRIMARY KEY, pseudo TEXT, bio TEXT, city TEXT, photos TEXT, albums TEXT,
                approved INTEGER DEFAULT 0, sub_invisible INTEGER DEFAULT 0, sub_boost INTEGER DEFAULT 0,
                sub_albums INTEGER DEFAULT 0, sub_pack INTEGER DEFAULT 0
            )
        ''')
        db.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT, sender_email TEXT, receiver_email TEXT,
                content TEXT, file_data TEXT, file_type TEXT, timestamp INTEGER
            )
        ''')
        # Maj du schéma si on a utilisé l'ancienne db sans file_data
        try:
            db.execute("ALTER TABLE messages ADD COLUMN file_data TEXT")
            db.execute("ALTER TABLE messages ADD COLUMN file_type TEXT")
        except:
            pass
        db.commit()

init_db()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/auth/google', methods=['POST'])
def google_auth():
    token = request.json.get('token')
    try:
        idinfo = id_token.verify_oauth2_token(token, google_requests.Request(), GOOGLE_CLIENT_ID)
        email = idinfo['email']
    except:
        return jsonify({'success': False}), 401

    session['user_email'] = email
    db = get_db()
    cursor = db.execute('SELECT * FROM users WHERE email = ?', (email,))
    row = cursor.fetchone()
    is_admin = 1 if email.lower() == ADMIN_EMAIL.lower() else 0
    
    if not row:
        initial_approval = 1 if is_admin else 1 
        db.execute('INSERT INTO users (email, pseudo, photos, albums, approved) VALUES (?, ?, ?, ?, ?)', 
                   (email, email.split('@')[0], '[]', '', initial_approval))
        db.commit()
        row = db.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()

    user_data = dict(row)
    user_data['photos'] = json.loads(user_data['photos']) if user_data['photos'] else []
    user_data['is_admin'] = is_admin
    return jsonify({'success': True, 'user': user_data})

@app.route('/api/auth/session', methods=['GET'])
def check_session():
    user_email = session.get('user_email')
    if not user_email: return jsonify({'success': False})
    row = get_db().execute('SELECT * FROM users WHERE email = ?', (user_email,)).fetchone()
    if not row: return jsonify({'success': False})
    user_data = dict(row)
    user_data['photos'] = json.loads(user_data['photos']) if user_data['photos'] else []
    user_data['is_admin'] = (user_data['email'].lower() == ADMIN_EMAIL.lower())
    return jsonify({'success': True, 'user': user_data})

@app.route('/api/profile/update', methods=['POST'])
def update_profile():
    user_email = session.get('user_email')
    if not user_email: return jsonify({'success': False}), 401
    data = request.json
    db = get_db()
    photos = data.get('photos', [])[:5]
    photos_str = json.dumps(photos)
    
    if user_email.lower() == ADMIN_EMAIL.lower():
        approved_status = 1
    else:
        approved_status = 1 if len(photos) >= 2 else 0

    db.execute('UPDATE users SET pseudo = ?, bio = ?, photos = ?, albums = ?, approved = ? WHERE email = ?', 
               (data.get('pseudo'), data.get('bio'), photos_str, data.get('albums'), approved_status, user_email))
    db.commit()
    return jsonify({'success': True, 'approved': approved_status})

@app.route('/api/users/active', methods=['GET'])
def get_active_users():
    db = get_db()
    cursor = db.execute("SELECT email, pseudo, photos, sub_boost, sub_pack FROM users WHERE approved = 1 AND sub_invisible = 0")
    users = []
    for row in cursor.fetchall():
        u = dict(row)
        u['photos'] = json.loads(u['photos']) if u['photos'] else []
        users.append(u)
    return jsonify({'success': True, 'users': users})

@app.route('/api/chat/messages', methods=['GET'])
def get_messages():
    user_email = session.get('user_email')
    other_user = request.args.get('user')
    cursor = get_db().execute('''
        SELECT sender_email as sender, content, file_data, file_type 
        FROM messages WHERE (sender_email = ? AND receiver_email = ?) OR (sender_email = ? AND receiver_email = ?)
        ORDER BY timestamp ASC
    ''', (user_email, other_user, other_user, user_email))
    return jsonify({'success': True, 'messages': [dict(r) for r in cursor.fetchall()]})

@app.route('/api/chat/send', methods=['POST'])
def send_message():
    sender = session.get('user_email')
    data = request.json
    db = get_db()
    db.execute('INSERT INTO messages (sender_email, receiver_email, content, file_data, file_type, timestamp) VALUES (?, ?, ?, ?, ?, ?)',
               (sender, data.get('receiver'), data.get('content', ''), data.get('file_data'), data.get('file_type'), int(time.time())))
    db.commit()
    return jsonify({'success': True})

@app.route('/api/chat/delete', methods=['POST'])
def delete_chat():
    user_email = session.get('user_email')
    other_user = request.json.get('other_user')
    db = get_db()
    db.execute('''DELETE FROM messages 
                  WHERE (sender_email = ? AND receiver_email = ?) 
                  OR (sender_email = ? AND receiver_email = ?)''', 
               (user_email, other_user, other_user, user_email))
    db.commit()
    return jsonify({'success': True})

@app.route('/api/paypal-success', methods=['POST'])
def paypal_success():
    user_email = session.get('user_email')
    plan = request.json.get('plan')
    db = get_db()
    if plan == 'invisible': db.execute('UPDATE users SET sub_invisible = 1 WHERE email = ?', (user_email,))
    elif plan == 'boost': db.execute('UPDATE users SET sub_boost = 1 WHERE email = ?', (user_email,))
    elif plan == 'albums': db.execute('UPDATE users SET sub_albums = 1 WHERE email = ?', (user_email,))
    else: db.execute('UPDATE users SET sub_pack = 1, sub_invisible = 1, sub_boost = 1, sub_albums = 1 WHERE email = ?', (user_email,))
    db.commit()
    return jsonify({'success': True})

@app.route('/api/admin/data', methods=['GET'])
def admin_data():
    if session.get('user_email', '').lower() != ADMIN_EMAIL.lower(): return jsonify({'success': False}), 403
    db = get_db()
    pending = [dict(r) for r in db.execute("SELECT email, pseudo FROM users WHERE approved = 0").fetchall()]
    messages = [dict(r) for r in db.execute("SELECT sender_email, receiver_email, content, file_data, file_type FROM messages ORDER BY timestamp DESC LIMIT 100").fetchall()]
    return jsonify({'success': True, 'pending': pending, 'messages': messages})

@app.route('/api/admin/approve', methods=['POST'])
def approve_user():
    db = get_db()
    db.execute("UPDATE users SET approved = 1 WHERE email = ?", (request.json.get('email'),))
    db.commit()
    return jsonify({'success': True})

if __name__ == '__main__':
    app.run(debug=True, port=5000)
