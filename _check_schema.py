# -*- coding: utf-8 -*-
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "learn.db"
conn = sqlite3.connect(str(DB_PATH))
conn.row_factory = sqlite3.Row

print('=== terms ===')
for row in conn.execute('PRAGMA table_info(terms)').fetchall():
    print(f'  {row["name"]}: {row["type"]}')

print()
print('=== article_term_stats ===')
for row in conn.execute('PRAGMA table_info(article_term_stats)').fetchall():
    print(f'  {row["name"]}: {row["type"]}')

print()
print('=== Sample term statuses ===')
for row in conn.execute('SELECT canonical_text, status FROM terms LIMIT 10').fetchall():
    print(f'  {row["canonical_text"]}: {row["status"]}')
