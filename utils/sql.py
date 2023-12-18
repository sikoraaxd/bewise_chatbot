import json
import psycopg2
from psycopg2 import Error

def create_connection():
    """Создает и возвращает соединение с базой данных PostgreSQL."""
    conn = None
    try:
        conn = psycopg2.connect(
            host="localhost",
            port="5432",
            database="chatbot_db",
            user="chatbot_worker",
            password="password")
        return conn
    except Error as e:
        print(e)
    return conn

def create_tables(conn):
    """Создает таблицы в базе данных."""
    try:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                login TEXT NOT NULL,
                context TEXT
            );
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS messagehistory (
                id SERIAL PRIMARY KEY,
                user_id INTEGER,
                message TEXT,
                FOREIGN KEY (user_id) REFERENCES users (id)
            );
        ''')
        conn.commit()
    except Error as e:
        print(e)

def check_user_existence(conn, login):
    """Проверяет существование пользователя по логину."""
    try:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT EXISTS (
                SELECT 1
                FROM users
                WHERE login = %s
            )
        ''', (login,))
        result = cursor.fetchone()
        return result[0]
    except Error as e:
        print(e)
        return False

def insert_user(conn, login, context):
    """Вставляет пользователя в таблицу users."""
    try:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO users (login, context)
            VALUES (%s, %s)
        ''', (login, context))
        conn.commit()
    except Error as e:
        print(e)

def get_user_context(conn, login):
    """Возвращает контекст пользователя."""
    try:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT context
            FROM users
            WHERE login = %s
        ''', (login,))
        result = cursor.fetchone()
        return result
    except Error as e:
        print(e)
        return None

def update_user_context(conn, login, new_context):
    """Обновляет контекст пользователя."""
    try:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE users
            SET context = %s
            WHERE login = %s
        ''', (new_context, login))
        conn.commit()
    except Error as e:
        print(e)

def insert_message(conn, login, message):
    """Вставляет сообщение в таблицу messagehistory."""
    try:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id FROM users WHERE login = %s
        ''', (login,))
        user_id = cursor.fetchone()

        if user_id is not None:
            user_id = user_id[0]
            cursor.execute('''
                INSERT INTO messagehistory (user_id, message)
                VALUES (%s, %s)
            ''', (user_id, message))
        conn.commit()
    except Error as e:
        print(e)

def get_message_history(conn, login):
    """Возвращает историю сообщений пользователя."""
    try:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT message
            FROM messagehistory
            JOIN users ON users.id = messagehistory.user_id
            WHERE users.login = %s
        ''', (login,))

        rows = cursor.fetchall()
        return rows
    except Error as e:
        print(e)

def clear_messages(conn, login):
    """Очищает историю сообщений пользователя."""
    try:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id FROM users WHERE login = %s
        ''', (login,))

        user_id = cursor.fetchone()

        if user_id is not None:
            user_id = user_id[0]
            cursor.execute('''
                DELETE FROM messagehistory WHERE user_id = %s
            ''', (user_id,))
        conn.commit()
    except Error as e:
        print(e)
