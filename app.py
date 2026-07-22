import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, g

app = Flask(__name__)
app.secret_key = os.urandom(24)
DATABASE = 'rubis_noir.db'

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_db():
    with app.app_context():
        db = get_db()
        db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                email TEXT PRIMARY KEY,
                pseudo TEXT,
                bio TEXT,
                city TEXT,
                photos TEXT,
                albums TEXT,
                sub_invisible INTEGER DEFAULT 0,
                sub_boost INTEGER DEFAULT 0,
                sub_albums INTEGER DEFAULT 0,
                sub_pack INTEGER DEFAULT 0,
                invisible_active INTEGER DEFAULT 0
            )
        ''')
        db.execute('''
            CREATE TABLE IF NOT EXISTS visitors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                profile_email TEXT,
                visitor_email TEXT,
                visitor_pseudo TEXT,
                visitor_photo TEXT,
                timestamp INTEGER
            )
        ''')
        db.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sender_email TEXT,
                receiver_email TEXT,
                content TEXT,
                timestamp INTEGER
            )
        ''')
        db.commit()

init_db()

@app.route('/')
def index():
    user_email = session.get('user_email')
    user_data = None
    if user_email:
        db = get_db()
        cursor = db.execute('SELECT * FROM users WHERE email = ?', (user_email,))
        row = cursor.fetchone()
        if row:
            user_data = dict(row)
    
    # Vérification admin (par exemple ton email ou un flag)
    is_admin = (user_email == 'admin@rubisnoir.fr')
    return render_template('index.html', user=user_email, user_data=user_data, is_admin=is_admin)

@app.route('/login', methods=['POST'])
def login():
    email = request.form.get('email')
    name = request.form.get('name')
    if email:
        session['user_email'] = email
        db = get_db()
        cursor = db.execute('SELECT * FROM users WHERE email = ?', (email,))
        if not cursor.fetchone():
            db.execute('INSERT INTO users (email, pseudo, bio, city, photos, albums) VALUES (?, ?, ?, ?, ?, ?)',
                       (email, name, 'Membre de la communauté Rubis Noir.', 'Reims', '[]', '[]'))
            db.commit()
    return redirect(url_for('index'))

@app.route('/logout')
def logout():
    session.pop('user_email', None)
    return redirect(url_for('index'))

@app.route('/api/profile', methods=['GET', 'POST'])
def handle_profile():
    user_email = session.get('user_email')
    if not user_email:
        return jsonify({'status': 'error', 'message': 'Non authentifié'}), 401
    
    db = get_db()
    if request.method == 'POST':
        data = request.json
        db.execute('''
            UPDATE users SET pseudo = ?, bio = ?, city = ?, photos = ?, albums = ?, invisible_active = ?
            WHERE email = ?
        ''', (
            data.get('pseudo'),
            data.get('bio'),
            data.get('city'),
            str(data.get('photos', [])),
            str(data.get('albums', [])),
            1 if data.get('invisible_active') else 0,
            user_email
        ))
        db.commit()
        return jsonify({'status': 'success'})
    
    cursor = db.execute('SELECT * FROM users WHERE email = ?', (user_email,))
    row = cursor.fetchone()
    return jsonify(dict(row) if row else {})

@app.route('/api/profiles', methods=['GET'])
def get_all_profiles():
    db = get_db()
    cursor = db.execute('SELECT email, pseudo, bio, city, photos, invisible_active FROM users')
    profiles = []
    for row in cursor.fetchall():
        if row['invisible_active'] and row['email'] == session.get('user_email'):
            continue
        profiles.append(dict(row))
    return jsonify(profiles)

@app.route('/api/verify-payment', methods=['POST'])
def verify_payment():
    user_email = session.get('user_email')
    if not user_email:
        return jsonify({'status': 'error', 'message': 'Non authentifié'}), 401
    
    data = request.json
    plan = data.get('plan')
    db = get_db()
    
    if plan == 'invisible':
        db.execute('UPDATE users SET sub_invisible = 1 WHERE email = ?', (user_email,))
    elif plan == 'albums_prives':
        db.execute('UPDATE users SET sub_albums = 1 WHERE email = ?', (user_email,))
    elif plan == 'mise_en_avant':
        db.execute('UPDATE users SET sub_boost = 1 WHERE email = ?', (user_email,))
    elif plan == 'pack_complet':
        db.execute('UPDATE users SET sub_pack = 1, sub_invisible = 1, sub_albums = 1, sub_boost = 1 WHERE email = ?', (user_email,))
    elif plan == 'cancel':
        db.execute('UPDATE users SET sub_invisible = 0, sub_boost = 0, sub_albums = 0, sub_pack = 0, invisible_active = 0 WHERE email = ?', (user_email,))
    
    db.commit()
    return jsonify({'status': 'success'})

if __name__ == '__main__':
    app.run(debug=True, port=5000)
