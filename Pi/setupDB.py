import sqlite3

# Connect to SQLite database (or create it if it doesn’t exist)
conn = sqlite3.connect('gpio_data.db')
cursor = conn.cursor()

# Create a table for storing GPIO data
cursor.execute('''
    CREATE TABLE IF NOT EXISTS gpio_data (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        pin_value INTEGER,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
''')

# Commit changes and close the connection
conn.commit()
conn.close()

print("Database and table setup complete.")
