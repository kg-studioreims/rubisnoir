from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
import os

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Email de l'administrateur
ADMIN_EMAIL = "kg.studio.reims@gmail.com"

# Fonction pour initialiser la base de données (posts et profils)
def init_db():
    conn = sqlite3.connect('rubisnoir.db')
    cursor = conn.cursor()
    
    # Table des publications / messages
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_email TEXT NOT NULL,
            user_name TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Table des profils utilisateurs (photos, bio, ville)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS profiles (
            email TEXT PRIMARY KEY,
            pseudo TEXT NOT NULL,
            city TEXT DEFAULT 'Reims',
            bio TEXT DEFAULT 'Membre de la communauté Rubis Noir.',
            photos_json TEXT DEFAULT '[]'
        )
    ''')
    
    conn.commit()
    conn.close()

# Initialisation au lancement
init_db()

@app.route('/')
def index():
    conn = sqlite3.connect('rubisnoir.db')
    cursor = conn.cursor()
    
    # Récupérer les posts
    cursor.execute('SELECT id, user_email, user_name, content, created_at FROM posts ORDER BY id DESC')
    posts = cursor.fetchall()
    
    # Récupérer tous les profils inscrits
    cursor.execute('SELECT email, pseudo, city, bio, photos_json FROM profiles')
    profiles_rows = cursor.fetchall()
    conn.close()
    
    # Formatage des profils pour le front
    profiles = []
    for row in profiles_rows:
        profiles.append({
            'email': row[0],
            'pseudo': row[1],
            'city': row[2],
            'bio': row[3],
            'photos': row[4]
        })

    user_email = session.get('user_email')
    is_admin = (user_email == ADMIN_EMAIL)
    
    return render_template('index.html', posts=posts, profiles=profiles, user=session.get('user_name'), is_admin=is_admin)

@app.route('/login', methods=['POST'])
def login():
    email = request.form.get('email')
    name = request.form.get('name')
    if email:
        session['user_email'] = email
        session['user_name'] = name
        
        # Vérifier si le profil existe déjà, sinon le créer par défaut
        conn = sqlite3.connect('rubisnoir.db')
        cursor = conn.cursor()
        cursor.execute('SELECT email FROM profiles WHERE email = ?', (email,))
        if not cursor.fetchone():
            cursor.execute('INSERT INTO profiles (email, pseudo, city, bio, photos_json) VALUES (?, ?, ?, ?, ?)',
                           (email, name, 'Reims', 'Membre de la communauté Rubis Noir.', '[]'))
            conn.commit()
        conn.close()
        
    return redirect(url_for('index'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/post', methods=['POST'])
def add_post():
    if 'user_email' not in session:
        return redirect(url_for('index'))
    
    content = request.form.get('content')
    if content:
        conn = sqlite3.connect('rubisnoir.db')
        cursor = conn.cursor()
        cursor.execute('INSERT INTO posts (user_email, user_name, content) VALUES (?, ?, ?)',
                       (session['user_email'], session['user_name'], content))
        conn.commit()
        conn.close()
        
    return redirect(url_for('index'))

@app.route('/admin/delete/<int:post_id>', methods=['POST'])
def delete_post(post_id):
    if session.get('user_email') == ADMIN_EMAIL:
        conn = sqlite3.connect('rubisnoir.db')
        cursor = conn.cursor()
        cursor.execute('DELETE FROM posts WHERE id = ?', (post_id,))
        conn.commit()
        conn.close()
        
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)
