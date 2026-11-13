import sqlite3

def init_db():
    conn = sqlite3.connect("dating_bot.db")
    cursor = conn.cursor()
    
    # Foydalanuvchilar jadvali
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            name TEXT,
            age INTEGER,
            city TEXT,
            gender TEXT,
            bio TEXT,
            photo TEXT,
            is_premium INTEGER DEFAULT 0
        )
    ''')
    
    # Kim kimni yoqtirganini saqlash uchun (Like / Dislike)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS likes (
            user_id INTEGER,
            target_id INTEGER,
            action TEXT,
            PRIMARY KEY (user_id, target_id)
        )
    ''')
    
    # O'zaro matchlar jadvali
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS matches (
            user1 INTEGER,
            user2 INTEGER
        )
    ''')
    
    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    print("Ma'lumotlar bazasi muvaffaqiyatli yangilandi!")