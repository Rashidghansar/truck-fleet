from sqlalchemy.orm import Session
from ..models.user import User
from ..core.security import get_password_hash, verify_password, create_access_token, create_refresh_token

class AuthService:
    def __init__(self, db: Session):
        self.db = db
    
    def authenticate_user(self, phone: str, password: str) -> User | None:
        user = self.db.query(User).filter(User.phone == phone).first()
        if not user:
            return None
        if not verify_password(password, user.password_hash):
            return None
        return user
    
    def create_tokens(self, user: User) -> dict:
        access_token = create_access_token(data={"sub": user.id})
        refresh_token = create_refresh_token(data={"sub": user.id})
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer"
        }

