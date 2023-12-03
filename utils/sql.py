import base64
import json
import sqlite3
from sqlite3 import Error
import base64

def create_connection(db_file):
    conn = None
    try:
        conn = sqlite3.connect(db_file, check_same_thread=False)
        return conn
    except Error as e:
        print(e)

    return conn


def create_tables(conn):
    try:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS Users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                login TEXT NOT NULL,
                context TEXT,
                documents TEXT
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS MessageHistory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                message TEXT,
                FOREIGN KEY (user_id) REFERENCES Users (id)
            )
        ''')

        conn.commit()
    except Error as e:
        print(e)


def check_user_existence(conn, login):
    try:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT EXISTS (
                SELECT 1
                FROM Users
                WHERE login = ?
            )
        ''', (login,))

        result = cursor.fetchone()
        return result[0] == 1

    except Error as e:
        print(e)
        return False


def insert_user(conn, login, context, documents):
    try:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO Users (login, context, documents)
            VALUES (?, ?, ?)
        ''', (login, context, documents))
        conn.commit()
    except Error as e:
        print(e)


def get_user_documents(conn, login):
    try:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT Users.documents
            FROM Users
            WHERE login = ?
        ''', (login,))

        result = cursor.fetchone()
        if result:
            documents = json.loads(result[0])
            return documents
        else:
            return []
    except Error as e:
        print(e)
        return None


def get_user_context(conn, login):
    try:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT Users.context
            FROM Users
            WHERE login = ?
        ''', (login,))

        result = cursor.fetchone()
        return result
    except Error as e:
        print(e)
        return None


def update_user_documents(conn, login, new_documents):
    try:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE Users
            SET documents = ?
            WHERE login = ?
        ''', (new_documents, login))
        conn.commit()
    except Error as e:
        print(e)


def update_user_context(conn, login, new_context):
    try:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE Users
            SET context = ?
            WHERE login = ?
        ''', (new_context, login))
        conn.commit()
    except Error as e:
        print(e)


def insert_message(conn, login, message):
    try:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id FROM Users WHERE login = ?
        ''', (login,))

        user_id = cursor.fetchone()

        if user_id is not None:
            user_id = user_id[0]
            cursor.execute('''
                INSERT INTO MessageHistory (user_id, message)
                VALUES (?, ?)
            ''', (user_id, message))
        conn.commit()
    except Error as e:
        print(e)


def get_message_history(conn, login):
    try:        
        cursor = conn.cursor()
        cursor.execute('''
            SELECT MessageHistory.message
            FROM MessageHistory
            JOIN Users ON Users.id = MessageHistory.user_id
            WHERE Users.login = ?
        ''', (login,))

        rows = cursor.fetchall()
        return rows
    except Error as e:
        raise e


def clear_messages(conn, login):
    try:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id FROM Users WHERE login = ?
        ''', (login,))

        user_id = cursor.fetchone()

        if user_id is not None:
            user_id = user_id[0]
            cursor.execute('''
                DELETE FROM MessageHistory WHERE MessageHistory.user_id = ?
            ''', (user_id,))
        conn.commit()
    except Error as e:
        print(e)
