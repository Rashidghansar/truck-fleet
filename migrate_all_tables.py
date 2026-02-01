"""
Comprehensive database migration script to add all missing columns
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

def get_table_columns(table_name):
    """Get existing columns for a table"""
    cursor.execute(f"PRAGMA table_info({table_name})")
    return [column[1] for column in cursor.fetchall()]

def add_column_if_not_exists(table_name, column_name, column_type):
    """Add column if it doesn't exist"""
    columns = get_table_columns(table_name)
    if column_name not in columns:
        try:
            cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")
            print(f"  [OK] Added {table_name}.{column_name}")
            return True
        except sqlite3.OperationalError as e:
            if "duplicate column name" not in str(e).lower():
                print(f"  [ERROR] Failed to add {table_name}.{column_name}: {e}")
            return False
    else:
        print(f"  [SKIP] {table_name}.{column_name} already exists")
        return False

try:
    print("\n" + "="*60)
    print("DATABASE MIGRATION - Adding Missing Columns")
    print("="*60)
    
    # ============================================
    # DRIVERS TABLE
    # ============================================
    print("\n[1/4] Migrating DRIVERS table...")
    
    drivers_columns = {
        'auto_created': 'BOOLEAN DEFAULT 0',
        'temp_password': 'VARCHAR(255)',
        'password_changed': 'BOOLEAN DEFAULT 1',
        'created_by_user_id': 'VARCHAR(36)',
        'completed_trips': 'INTEGER DEFAULT 0',
    }
    
    for column_name, column_type in drivers_columns.items():
        add_column_if_not_exists('drivers', column_name, column_type)
    
    # ============================================
    # BOOKINGS TABLE
    # ============================================
    print("\n[2/4] Migrating BOOKINGS table...")
    
    bookings_columns = {
        'gate_numeric_code': 'VARCHAR(6)',
        'gate_code_generated_at': 'DATETIME',
        'checkin_qr_scanned': 'BOOLEAN DEFAULT 0',
        'checkin_time': 'DATETIME',
        'checkin_method': 'VARCHAR(20)',
        'checkout_qr_scanned': 'BOOLEAN DEFAULT 0',
        'checkout_time': 'DATETIME',
        'checkout_method': 'VARCHAR(20)',
        'cfs_location_id': 'VARCHAR(36)',
        'cfs_location_name': 'VARCHAR(255)',
    }
    
    for column_name, column_type in bookings_columns.items():
        add_column_if_not_exists('bookings', column_name, column_type)
    
    # ============================================
    # USERS TABLE
    # ============================================
    print("\n[3/4] Migrating USERS table...")
    
    users_columns = {
        'cfs_id': 'VARCHAR(36)',
        'cfs_name': 'VARCHAR(200)',
        'cfs_address': 'VARCHAR(500)',
        'cfs_license': 'VARCHAR(100)',
    }
    
    for column_name, column_type in users_columns.items():
        add_column_if_not_exists('users', column_name, column_type)
    
    # ============================================
    # CFS_LOCATIONS TABLE (Create if not exists)
    # ============================================
    print("\n[4/4] Checking CFS_LOCATIONS table...")
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cfs_locations (
            id VARCHAR(36) PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            address TEXT NOT NULL,
            city VARCHAR(100),
            state VARCHAR(100),
            pincode VARCHAR(10),
            latitude FLOAT,
            longitude FLOAT,
            contact_person VARCHAR(255),
            contact_phone VARCHAR(15),
            is_active BOOLEAN DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    print("  [OK] CFS_LOCATIONS table verified")
    
    # Create CFS_BAYS table if not exists
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cfs_bays (
            id VARCHAR(36) PRIMARY KEY,
            cfs_id VARCHAR(36),
            bay_number VARCHAR(50) NOT NULL,
            supervisor_name VARCHAR(255),
            supervisor_phone VARCHAR(15),
            is_available BOOLEAN DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (cfs_id) REFERENCES cfs_locations(id)
        )
    """)
    print("  [OK] CFS_BAYS table verified")
    
    # Commit changes
    conn.commit()
    
    print("\n" + "="*60)
    print("[SUCCESS] Database migration completed!")
    print("="*60)
    
    # Verification
    print("\nVerification:")
    for table in ['drivers', 'bookings', 'users', 'cfs_locations', 'cfs_bays']:
        try:
            columns = get_table_columns(table)
            print(f"  {table}: {len(columns)} columns")
        except:
            print(f"  {table}: ERROR")

except Exception as e:
    conn.rollback()
    print(f"\n[ERROR] Error during migration: {e}")
    import traceback
    traceback.print_exc()
finally:
    conn.close()
