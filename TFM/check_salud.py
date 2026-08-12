import sqlite3
conn = sqlite3.connect('data/tui_recomendador.db')
cur = conn.cursor()
cur.execute('PRAGMA integrity_check;')
print('Integridad:', cur.fetchone())
cur.execute('SELECT COUNT(*) FROM resenas')
print('Total resenas:', cur.fetchone()[0])
cur.execute("SELECT COUNT(*) FROM resenas WHERE texto_original IS NULL OR LENGTH(texto_original) < 15")
print('Resenas vacias/muy cortas:', cur.fetchone()[0])
