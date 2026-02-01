"""
Database migration script to add missing columns to bookings table
Run this script to update the database schema without losing data
"""
import sqlite3
import os
from pathlib import Path

# Get database path
db_path = Path(__file__).parent / "cfs_transport.db"

if not db_path.exists():
    print(f"Database not found at {db_path}")
    exit(1)

print(f"Connecting to database: {db_path}")
conn = sqlite3.connect(str(db_path))
cursor = conn.cursor()

try:
    # Check if gate_numeric_code column exists
    cursor.execute("PRAGMA table_info(bookings)")
    columns = [column[1] for column in cursor.fetchall()]
    
    print(f"Current columns in bookings table: {len(columns)}")
    
    # List of columns that should exist
    required_columns = {
        'gate_numeric_code': 'VARCHAR(6)',
        'gate_code_generated_at': 'DATETIME',
        'checkin_qr_scanned': 'BOOLEAN DEFAULT 0',
        'checkin_time': 'DATETIME',
        'checkin_method': 'VARCHAR(20)',
        'checkout_qr_scanned': 'BOOLEAN DEFAULT 0',
        'checkout_time': 'DATETIME',
        'checkout_method': 'VARCHAR(20)',
    }
    
    # Add missing columns
    for column_name, column_type in required_columns.items():
        if column_name not in columns:
            print(f"Adding column: {column_name} ({column_type})")
            try:
                cursor.execute(f"ALTER TABLE bookings ADD COLUMN {column_name} {column_type}")
                print(f"[OK] Added {column_name}")
            except sqlite3.OperationalError as e:
                if "duplicate column name" in str(e).lower():
                    print(f"  Column {column_name} already exists, skipping...")
                else:
                    print(f"  Error adding {column_name}: {e}")
        else:
            print(f"  Column {column_name} already exists, skipping...")
    
    # Commit changes
    conn.commit()
    print("\n[SUCCESS] Database migration completed successfully!")
    
    # Verify
    cursor.execute("PRAGMA table_info(bookings)")
    columns_after = [column[1] for column in cursor.fetchall()]
    print(f"\nTotal columns after migration: {len(columns_after)}")
    
except Exception as e:
    conn.rollback()
    print(f"\n[ERROR] Error during migration: {e}")
    import traceback
    traceback.print_exc()
finally:
    conn.close()

