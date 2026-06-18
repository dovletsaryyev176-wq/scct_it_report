"""
init_db.py — Maglumat bazasyny we tablisalary döretmek üçin skript.

Bu skript:
  1. `reporting_db` bazasyny döredýär (eger ýok bolsa);
  2. `schema.sql` faýlyndaky ähli tablisalary awtomatiki döredýär;
  3. döredilen tablisalaryň sanawyny görkezýär.

Ulanylyşy:
    python init_db.py
"""

import os
import sys
import pymysql
from config import Config

# Windows konsolynda türkmen harplaryny dogry görkezmek üçin
try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

SCHEMA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "schema.sql")


def split_statements(sql_text):
    """SQL teksti aýratyn buýruklara (`;` boýunça) bölýär."""
    statements = []
    for raw in sql_text.split(";"):
        stmt = raw.strip()
        if stmt:
            statements.append(stmt)
    return statements


def create_database():
    """`reporting_db` bazasyny döredýär (eger ýok bolsa)."""
    conn = pymysql.connect(
        host=Config.DB_HOST,
        user=Config.DB_USER,
        password=Config.DB_PASSWORD,
        cursorclass=pymysql.cursors.DictCursor,
    )
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS `{Config.DB_NAME}` "
                f"CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
        conn.commit()
        print(f"[✓] Baza taýýar: `{Config.DB_NAME}`")
    finally:
        conn.close()


def run_schema():
    """`schema.sql` faýlyndaky buýruklary baza ýerine ýetirýär."""
    if not os.path.exists(SCHEMA_FILE):
        print(f"[✗] '{SCHEMA_FILE}' faýly tapylmady!")
        sys.exit(1)

    with open(SCHEMA_FILE, "r", encoding="utf-8") as f:
        sql_text = f.read()

    statements = split_statements(sql_text)

    conn = pymysql.connect(
        host=Config.DB_HOST,
        user=Config.DB_USER,
        password=Config.DB_PASSWORD,
        database=Config.DB_NAME,
        cursorclass=pymysql.cursors.DictCursor,
    )
    try:
        with conn.cursor() as cursor:
            for i, stmt in enumerate(statements, start=1):
                try:
                    cursor.execute(stmt)
                except pymysql.err.OperationalError as e:
                    # 1050 = Table already exists, 1060 = Duplicate column
                    code = e.args[0]
                    if code in (1050, 1060):
                        print(f"[!] {i}-buýruk goýberildi (eýýäm bar): {e.args[1]}")
                        continue
                    raise
        conn.commit()
        print(f"[✓] schema.sql ýerine ýetirildi ({len(statements)} buýruk)")
    finally:
        conn.close()


def show_tables():
    """Bazadaky tablisalaryň sanawyny görkezýär."""
    conn = pymysql.connect(
        host=Config.DB_HOST,
        user=Config.DB_USER,
        password=Config.DB_PASSWORD,
        database=Config.DB_NAME,
        cursorclass=pymysql.cursors.DictCursor,
    )
    try:
        with conn.cursor() as cursor:
            cursor.execute("SHOW TABLES")
            rows = cursor.fetchall()
        print()
        print(f"[✓] Bazada {len(rows)} tablisa bar:")
        for row in rows:
            table_name = list(row.values())[0]
            print(f"    - {table_name}")
    finally:
        conn.close()


def init_db():
    print("=" * 50)
    print("   Maglumat bazasyny taýýarlamak")
    print("=" * 50)
    print()
    try:
        create_database()
        run_schema()
        show_tables()
        print()
        print("=" * 50)
        print("[✓] Taýýar! Indi `python create_admin.py` işlediň.")
        print("=" * 50)
    except pymysql.err.OperationalError as e:
        print(f"[✗] Maglumat bazasyna birigip bolmady: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"[✗] Hata: {e}")
        sys.exit(1)


if __name__ == "__main__":
    init_db()
