from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from ..database import get_db
from ..models.user import User, UserType
from .security import decode_token

security = HTTPBearer()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    token = credentials.credentials
    payload = decode_token(token)
    
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )
    
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload"
        )
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is inactive"
        )
    
    return user

async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    return current_user

def require_user_type(*user_types: UserType):
    """Dependency factory to require specific user types"""
    async def check_user_type(current_user: User = Depends(get_current_user)) -> User:
        if current_user.user_type not in [ut.value for ut in user_types]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required user type: {', '.join([ut.value for ut in user_types])}"
            )
        return current_user
    return check_user_type

# Convenience dependencies for specific roles
get_cfs_admin = require_user_type(UserType.CFS_ADMIN)
get_security_officer = require_user_type(UserType.SECURITY_OFFICER)
get_aggregator = require_user_type(UserType.AGGREGATOR)
get_owner = require_user_type(UserType.OWNER)
get_driver = require_user_type(UserType.DRIVER)
get_supply_user = require_user_type(UserType.AGGREGATOR, UserType.OWNER, UserType.DRIVER)
