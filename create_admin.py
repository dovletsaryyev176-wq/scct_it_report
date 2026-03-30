"""
create_admin.py — Admin ulanyjy döretmek üçin skript.

Bu skript MySQL bazasyndaky `users` tablisasyna admin ulanyjy goşýar.
Parol werkzeug arkaly hash edilýär.

Ulanylyşy:
    python create_admin.py
"""

import pymysql
from werkzeug.security import generate_password_hash
from config import Config


def get_db_connection():
    """Maglumat bazasyna birikmek."""
    return pymysql.connect(
        host=Config.DB_HOST,
        user=Config.DB_USER,
        password=Config.DB_PASSWORD,
        database=Config.DB_NAME,
        cursorclass=pymysql.cursors.DictCursor
    )


def create_admin():
    """Interaktiw usulda admin ulanyjy döredýär."""
    print("=" * 50)
    print("   Admin ulanyjy döretmek")
    print("=" * 50)
    print()

    # ---- Ulanyjy maglumatlaryny almak ----
    username = input("Ulanyjy ady (username): ").strip()
    if not username:
        print("[✗] Ulanyjy ady boş bolup bilmez!")
        return

    full_name = input("Doly ady (full_name): ").strip()
    if not full_name:
        print("[✗] Doly ady boş bolup bilmez!")
        return

    phone = input("Telefon belgisi (mysal: +99361234567): ").strip() or None

    order_number = input("Buýruk belgisi (order_number, boş bolup biler): ").strip() or None

    order_date = input("Buýruk senesi (YYYY-MM-DD, boş bolup biler): ").strip() or None

    password = input("Parol: ").strip()
    if not password:
        print("[✗] Parol boş bolup bilmez!")
        return

    password_confirm = input("Paroly tassyklaň: ").strip()
    if password != password_confirm:
        print("[✗] Parollar gabat gelenok!")
        return

    # ---- Parol hash ----
    password_hash = generate_password_hash(password)

    # ---- Bazada barlamak we goşmak ----
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            # Ulanyjy adynyň öň barlygyny barlamak
            cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
            if cursor.fetchone():
                print(f"[✗] '{username}' ulanyjy ady eýýäm bar!")
                return

            # Telefon belgisiniň öň barlygyny barlamak
            if phone:
                cursor.execute("SELECT id FROM users WHERE phone = %s", (phone,))
                if cursor.fetchone():
                    print(f"[✗] '{phone}' telefon belgisi eýýäm ulanylýar!")
                    return

            # Admin ulanyjy goşmak
            cursor.execute("""
                INSERT INTO users (username, full_name, password_hash, phone, 
                                   order_number, order_date, role, status, is_verified)
                VALUES (%s, %s, %s, %s, %s, %s, 'admin', 'active', 1)
            """, (username, full_name, password_hash, phone, order_number, order_date))

            conn.commit()

            admin_id = cursor.lastrowid
            print()
            print("=" * 50)
            print(f"[✓] Admin ulanyjy üstünlikli döredildi!")
            print(f"    ID:            {admin_id}")
            print(f"    Ulanyjy ady:   {username}")
            print(f"    Doly ady:      {full_name}")
            print(f"    Telefon:       {phone or '—'}")
            print(f"    Buýruk №:      {order_number or '—'}")
            print(f"    Buýruk senesi: {order_date or '—'}")
            print(f"    Role:          admin")
            print(f"    Status:        active")
            print("=" * 50)

    except pymysql.err.OperationalError as e:
        print(f"[✗] Maglumat bazasyna birigip bolmady: {e}")
    except pymysql.err.IntegrityError as e:
        print(f"[✗] Maglumat bazasy hatasy: {e}")
    except Exception as e:
        print(f"[✗] Näbelli hata: {e}")
    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    create_admin()
