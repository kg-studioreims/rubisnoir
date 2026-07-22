from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import sqlite3
import os

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Email de l'administrateur
ADMIN_EMAIL = "kg.studio.reims@gmail.com"

# Fonction pour initialiser la base de données (profils uniquement)
def init_db():
    conn = sqlite3.connect('rubisnoir.db')
    cursor = conn.cursor()
    
    # Table des profils utilisateurs (photos, bio, ville, abonnements)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS profiles (
            email TEXT PRIMARY KEY,
            pseudo TEXT NOT NULL,
            city TEXT DEFAULT 'Reims',
            bio TEXT DEFAULT 'Membre de la communauté Rubis Noir.',
            photos_json TEXT DEFAULT '[]',
            is_subscribed INTEGER DEFAULT 0,
            subscription_plan TEXT DEFAULT ''
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
    
    return render_template('index.html', profiles=profiles, user=session.get('user_name'), is_admin=is_admin)

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

@app.route('/api/verify-payment', methods=['POST'])
def verify_payment():
    data = request.get_json() or {}
    plan_type = data.get('plan', 'pass_complet')
    payer_email = session.get('user_email')
    
    if not payer_email:
        return jsonify({'status': 'error', 'message': 'Utilisateur non connecté'}), 403
        
    conn = sqlite3.connect('rubisnoir.db')
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE profiles 
        SET is_subscribed = 1, subscription_plan = ? 
        WHERE email = ?
    ''', (plan_type, payer_email))
    conn.commit()
    conn.close()
    
    return jsonify({'status': 'success', 'message': 'Abonnement activé avec succès'})

if __name__ == '__main__':
    app.run(debug=True)
