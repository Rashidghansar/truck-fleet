"""
Migration script to add created_by_admin_id column to users table.
This links security officers to the admin who created them.
"""
import sqlite3
import os

def migrate():
    db_path = os.path.join(os.path.dirname(__file__), 'cfs_transport.db')
    
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check if column already exists
    cursor.execute("PRAGMA table_info(users)")
    columns = [col[1] for col in cursor.fetchall()]
    
    if 'created_by_admin_id' in columns:
        print("Column 'created_by_admin_id' already exists")
    else:
        print("Adding 'created_by_admin_id' column to users table...")
        cursor.execute("""
            ALTER TABLE users 
            ADD COLUMN created_by_admin_id VARCHAR(36) 
            REFERENCES users(id)
        """)
        
        # Create index for faster lookups
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS ix_users_created_by_admin_id 
            ON users(created_by_admin_id)
        """)
        
        conn.commit()
        print("Migration completed successfully!")
    
    conn.close()

if __name__ == "__main__":
    migrate()
