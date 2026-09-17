import sqlite3
from config import DB_PATH
from core.db import get_connection


def get_db():
    con = get_connection(DB_PATH, check_same_thread=False)
    con.row_factory = sqlite3.Row
    try:
        yield con
    finally:
        con.close()
