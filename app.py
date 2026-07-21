from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3

app = Flask(__name__)
app.secret_key = 'remplace_ce_secret_par_une_chaine_aleatoire' # Nécessaire pour les sessions

# Email de l'administrateur (mets le tien ici)
ADMIN_EMAIL = "kg.studio.reims@gmail.com"

# Fonction pour initialiser la base de données
def init_db():
    conn = sqlite3.connect('rubisnoir.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_email TEXT NOT NULL,
            user_name TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

# Initialisation au lancement
init_db()

@app.route('/')
def index():
    # Récupérer tous les posts de la base de données pour les afficher
    conn = sqlite3.connect('rubisnoir.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id, user_email, user_name, content, created_at FROM posts ORDER BY id DESC')
    posts = cursor.fetchall()
    conn.close()
    
    is_admin = session.get('user_email') == ADMIN_EMAIL
    return render_template('index.html', posts=posts, user=session.get('user_name'), is_admin=is_admin)

@app.route('/login', methods=['POST'])
def login():
    # Récupération des infos envoyées par le Google Sign-In du front
    email = request.form.get('email')
    name = request.form.get('name')
    if email:
        session['user_email'] = email
        session['user_name'] = name
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
    # Sécurité : vérifier que c'est bien l'admin
    if session.get('user_email') == ADMIN_EMAIL:
        conn = sqlite3.connect('rubisnoir.db')
        cursor = conn.cursor()
        cursor.execute('DELETE FROM posts WHERE id = ?', (post_id,))
        conn.commit()
        conn.close()
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)
