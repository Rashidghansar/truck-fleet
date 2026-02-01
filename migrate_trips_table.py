"""
Migration script to add missing columns to trips table.
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

    # Check existing columns
    cursor.execute("PRAGMA table_info(trips)")
    existing_columns = {col[1] for col in cursor.fetchall()}
    print(f"Existing columns in trips table: {existing_columns}")

    # Define all columns that should exist in trips table
    columns_to_add = {
        'expected_arrival_time': 'DATETIME',
        'expected_duration_minutes': 'REAL',
        'actual_arrival_time': 'DATETIME',
        'is_delayed': 'BOOLEAN DEFAULT 0',
        'delay_minutes': 'REAL DEFAULT 0.0',
        'delay_reason': 'TEXT',
        'delay_notified_at': 'DATETIME',
        'current_latitude': 'REAL',
        'current_longitude': 'REAL',
        'current_speed': 'REAL',
        'last_location_update': 'DATETIME',
        'distance_covered': 'REAL DEFAULT 0.0',
        'distance_remaining': 'REAL',
        'total_distance': 'REAL',
        'progress_percentage': 'REAL DEFAULT 0.0',
        'delivery_photos': 'TEXT',
        'receiver_name': 'VARCHAR(255)',
        'receiver_phone': 'VARCHAR(15)',
        'receiver_signature': 'TEXT',
        'delivery_otp': 'VARCHAR(6)',
        'delivery_otp_verified': 'BOOLEAN DEFAULT 0',
        'delivery_condition': 'VARCHAR(100)',
        'delivery_remarks': 'TEXT',
        'actual_delivery_time': 'DATETIME',
        'milestones': 'TEXT',
        'completed_at': 'DATETIME',
    }

    # Add missing columns
    for col_name, col_type in columns_to_add.items():
        if col_name not in existing_columns:
            try:
                sql = f"ALTER TABLE trips ADD COLUMN {col_name} {col_type}"
                cursor.execute(sql)
                print(f"Added column: {col_name}")
            except sqlite3.OperationalError as e:
                print(f"Error adding {col_name}: {e}")

    conn.commit()
    
    # Verify columns
    cursor.execute("PRAGMA table_info(trips)")
    final_columns = {col[1] for col in cursor.fetchall()}
    print(f"\nFinal columns in trips table: {final_columns}")
    
    conn.close()
    print("\nMigration completed successfully!")

if __name__ == "__main__":
    migrate()
