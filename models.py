from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import os

class User(UserMixin):
    def __init__(self, id, email, name, phone, shop_name=None, shop_address=None, profile_pic=None):
        self.id = id
        self.email = email
        self.name = name
        self.phone = phone
        self.shop_name = shop_name
        self.shop_address = shop_address
        self.profile_pic = profile_pic

    @staticmethod
    def get(user_id):
        """Get user by ID for Flask-Login"""
        return get_user_by_id(user_id)

def init_db():
    """Initialize the database and create tables if they don't exist"""
    db_path = os.path.join(os.path.dirname(__file__), 'database', 'users.db')
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    # Create users table
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            phone TEXT NOT NULL,
            shop_name TEXT,
            shop_address TEXT,
            profile_pic TEXT,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Add shop_name, shop_address, and profile_pic columns if they don't exist (for existing databases)
    for col_sql in [
        'ALTER TABLE users ADD COLUMN shop_name TEXT',
        'ALTER TABLE users ADD COLUMN shop_address TEXT',
        'ALTER TABLE users ADD COLUMN profile_pic TEXT'
    ]:
        try:
            c.execute(col_sql)
        except sqlite3.OperationalError:
            pass  # Column already exists

    conn.commit()
    conn.close()

def get_user_by_email(email):
    """Get user by email (case-insensitive)"""
    db_path = os.path.join(os.path.dirname(__file__), 'database', 'users.db')
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    c.execute('SELECT id, email, name, phone, shop_name, shop_address, profile_pic FROM users WHERE LOWER(email) = LOWER(?)', (email,))
    user_data = c.fetchone()

    conn.close()

    if user_data:
        return User(*user_data)
    return None

def get_user_by_id(user_id):
    """Get user by ID"""
    db_path = os.path.join(os.path.dirname(__file__), 'database', 'users.db')
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    c.execute('SELECT id, email, name, phone, shop_name, shop_address, profile_pic FROM users WHERE id = ?', (user_id,))
    user_data = c.fetchone()

    conn.close()

    if user_data:
        return User(*user_data)
    return None

def create_user(email, name, phone, password):
    """Create a new user"""
    db_path = os.path.join(os.path.dirname(__file__), 'database', 'users.db')
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    password_hash = generate_password_hash(password)
    email = email.lower()  # Normalize email to lowercase

    try:
        c.execute('''
            INSERT INTO users (email, name, phone, shop_name, shop_address, profile_pic, password_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (email, name, phone, None, None, None, password_hash))

        user_id = c.lastrowid
        conn.commit()
        conn.close()

        return User(user_id, email, name, phone, None, None, None)
    except sqlite3.IntegrityError:
        conn.close()
        return None  # Email already exists

def verify_password(email, password):
    """Verify user password (case-insensitive email)"""
    print(f"\n[DEBUG] ===== VERIFY_PASSWORD CALLED =====")
    print(f"[DEBUG] Input email: '{email}'")
    print(f"[DEBUG] Input password: '{password}'")
    
    db_path = os.path.join(os.path.dirname(__file__), 'database', 'users.db')
    print(f"[DEBUG] Database path: {db_path}")
    print(f"[DEBUG] Database exists: {os.path.exists(db_path)}")
    
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    # First, let's see ALL users in database
    c.execute('SELECT id, email FROM users')
    all_users = c.fetchall()
    print(f"[DEBUG] All users in database: {all_users}")

    c.execute('SELECT id, email, name, phone, shop_name, shop_address, profile_pic, password_hash FROM users WHERE LOWER(email) = LOWER(?)', (email,))
    user_data = c.fetchone()

    conn.close()

    print(f"[DEBUG] User found: {user_data is not None}")
    
    if user_data:
        print(f"[DEBUG] User ID: {user_data[0]}")
        print(f"[DEBUG] User email: {user_data[1]}")
        print(f"[DEBUG] Password hash: {user_data[7][:20]}..." if user_data[7] else "None")
        password_match = check_password_hash(user_data[7], password)
        print(f"[DEBUG] Password match: {password_match}")
    else:
        print(f"[DEBUG] NO USER FOUND with email: {email.lower()}")

    # user_data layout: id,email,name,phone,shop_name,shop_address,profile_pic,password_hash
    if user_data and user_data[7] and check_password_hash(user_data[7], password):
        print(f"[DEBUG] LOGIN SUCCESS!")
        # construct User object with the proper fields
        return User(
            user_data[0],  # id
            user_data[1],  # email
            user_data[2],  # name
            user_data[3],  # phone
            user_data[4],  # shop_name
            user_data[5],  # shop_address
            user_data[6],  # profile_pic
        )
    print(f"[DEBUG] LOGIN FAILED!")
    print(f"[DEBUG] ===== END VERIFY_PASSWORD =====\n")
    return None

def update_user(user_id, name=None, phone=None, email=None, shop_name=None, shop_address=None, profile_pic=None):
    """Update user information"""
    db_path = os.path.join(os.path.dirname(__file__), 'database', 'users.db')
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    updates = []
    params = []

    if name is not None:
        updates.append('name = ?')
        params.append(name)
    if phone is not None:
        updates.append('phone = ?')
        params.append(phone)
    if email is not None:
        updates.append('email = ?')
        params.append(email.lower())  # Normalize email to lowercase
    if shop_name is not None:
        updates.append('shop_name = ?')
        params.append(shop_name)
    if shop_address is not None:
        updates.append('shop_address = ?')
        params.append(shop_address)
    if profile_pic is not None:
        updates.append('profile_pic = ?')
        params.append(profile_pic)

    if updates:
        params.append(user_id)
        query = f'UPDATE users SET {", ".join(updates)} WHERE id = ?'
        c.execute(query, params)
        conn.commit()

    conn.close()