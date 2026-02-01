from sqlalchemy import create_engine, event, Index
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from .config import settings

# SQLite specific configuration
connect_args = {"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {}

# Create engine with appropriate settings for the database type
if "sqlite" in settings.DATABASE_URL:
    # SQLite doesn't use connection pooling the same way
    engine = create_engine(
        settings.DATABASE_URL,
        echo=settings.DB_ECHO,
        connect_args=connect_args,
    )
else:
    # PostgreSQL/MySQL use connection pooling
    engine = create_engine(
        settings.DATABASE_URL,
        echo=settings.DB_ECHO,
        connect_args=connect_args,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
    )

# Enable foreign keys for SQLite
if "sqlite" in settings.DATABASE_URL:
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Use SQLAlchemy 2.0 DeclarativeBase
class Base(DeclarativeBase):
    pass

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """Initialize database tables and indexes"""
    # Import all models to register them with Base
    from .models import (
        user, booking, truck, driver, gate_activity, notification, transaction,
        otp, audit_log, user_session, document, payment_transaction, notification_log
    )
    
    # Create all tables
    Base.metadata.create_all(bind=engine)
    
    # Create indexes for frequently queried fields
    try:
        create_indexes()
    except Exception as e:
        # Indexes might already exist, log and continue
        import logging
        logging.getLogger(__name__).warning(f"Error creating indexes: {e}")

def create_indexes():
    """Create database indexes for performance optimization"""
    from sqlalchemy import text
    
    indexes = [
        # Booking indexes
        "CREATE INDEX IF NOT EXISTS idx_bookings_status ON bookings(status)",
        "CREATE INDEX IF NOT EXISTS idx_bookings_cfs_id ON bookings(cfs_id)",
        "CREATE INDEX IF NOT EXISTS idx_bookings_created_at ON bookings(created_at)",
        "CREATE INDEX IF NOT EXISTS idx_bookings_aggregator_id ON bookings(aggregator_id)",
        "CREATE INDEX IF NOT EXISTS idx_bookings_driver_id ON bookings(driver_id)",
        "CREATE INDEX IF NOT EXISTS idx_bookings_truck_id ON bookings(truck_id)",
        
        # User indexes
        "CREATE INDEX IF NOT EXISTS idx_users_user_type ON users(user_type)",
        "CREATE INDEX IF NOT EXISTS idx_users_is_active ON users(is_active)",
        "CREATE INDEX IF NOT EXISTS idx_users_created_at ON users(created_at)",
        
        # Truck indexes
        "CREATE INDEX IF NOT EXISTS idx_trucks_is_available ON trucks(is_available)",
        "CREATE INDEX IF NOT EXISTS idx_trucks_owner_id ON trucks(owner_id)",
        
        # Negotiation indexes
        "CREATE INDEX IF NOT EXISTS idx_negotiations_booking_id ON negotiations(booking_id)",
        "CREATE INDEX IF NOT EXISTS idx_negotiations_status ON negotiations(status)",
        
        # OTP indexes
        "CREATE INDEX IF NOT EXISTS idx_otps_phone ON otps(phone)",
        "CREATE INDEX IF NOT EXISTS idx_otps_purpose ON otps(purpose)",
        
        # Session indexes
        "CREATE INDEX IF NOT EXISTS idx_user_sessions_user_id ON user_sessions(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_user_sessions_token ON user_sessions(token)",
        "CREATE INDEX IF NOT EXISTS idx_user_sessions_expires_at ON user_sessions(expires_at)",
        
        # Payment transaction indexes
        "CREATE INDEX IF NOT EXISTS idx_payment_transactions_booking_id ON payment_transactions(booking_id)",
        "CREATE INDEX IF NOT EXISTS idx_payment_transactions_status ON payment_transactions(status)",
        "CREATE INDEX IF NOT EXISTS idx_payment_transactions_created_at ON payment_transactions(created_at)",
        
        # Notification log indexes
        "CREATE INDEX IF NOT EXISTS idx_notification_logs_user_id ON notification_logs(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_notification_logs_is_read ON notification_logs(is_read)",
        "CREATE INDEX IF NOT EXISTS idx_notification_logs_created_at ON notification_logs(created_at)",
        
        # Audit log indexes
        "CREATE INDEX IF NOT EXISTS idx_audit_logs_user_id ON audit_logs(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_audit_logs_resource_type ON audit_logs(resource_type)",
        "CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON audit_logs(created_at)",
    ]
    
    with engine.connect() as conn:
        for index_sql in indexes:
            try:
                conn.execute(text(index_sql))
                conn.commit()
            except Exception as e:
                # Index might already exist, ignore error
                pass
