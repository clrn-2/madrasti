import sqlite3
import os
p=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'madrasti.db')
conn=sqlite3.connect(p)
cur=conn.cursor()
print('PRAGMA table_info(students):')
for r in cur.execute("PRAGMA table_info('students')"):
    print(r)
print('\nCount students:')
for r in cur.execute('SELECT COUNT(*) FROM students'):
    print(r)
print('\nSample rows:')
for r in cur.execute('SELECT id, class_id, full_name FROM students LIMIT 10'):
    print(r)
conn.close()
