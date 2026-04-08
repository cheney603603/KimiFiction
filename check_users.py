import pymysql

# Connect to Docker MySQL
conn = pymysql.connect(
    host='127.0.0.1',
    port=3307,
    user='root',
    password='root_password',
    database='novel_system'
)

cursor = conn.cursor()
cursor.execute("SELECT username, email, is_superuser, is_active FROM users")
rows = cursor.fetchall()

print("Users in database:")
print("-" * 50)
for row in rows:
    print(f"Username: {row[0]}")
    print(f"Email: {row[1]}")
    print(f"Is Superuser: {row[2]}")
    print(f"Is Active: {row[3]}")
    print("-" * 50)

conn.close()
