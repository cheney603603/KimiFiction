"""
认证依赖模块
提供FastAPI依赖注入用的认证功能
"""
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import decode_access_token
from app.services.user_service import UserService

# 使用HTTPBearer获取Authorization头
security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> Optional[dict]:
    """
    获取当前登录用户
    
    Args:
        credentials: HTTP认证凭证
        db: 数据库会话
        
    Returns:
        用户信息字典，未登录返回None
    """
    if not credentials:
        return None
    
    token = credentials.credentials
    payload = decode_access_token(token)
    
    if not payload:
        return None
    
    user_id = payload.get("sub")
    if not user_id:
        return None
    
    try:
        user_service = UserService(db)
        user = await user_service.get_user(int(user_id))
        if user and user.is_active:
            return user.to_dict()
        return None
    except Exception:
        return None


async def require_auth(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> dict:
    """
    要求用户必须登录
    
    Args:
        credentials: HTTP认证凭证
        db: 数据库会话
        
    Returns:
        用户信息字典
        
    Raises:
        HTTPException: 未登录或令牌无效
    """
    user = await get_current_user(credentials, db)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未登录或令牌无效",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return user


async def require_superuser(
    current_user: dict = Depends(require_auth)
) -> dict:
    """
    要求超级用户权限
    
    Args:
        current_user: 当前用户信息
        
    Returns:
        用户信息字典
        
    Raises:
        HTTPException: 权限不足
    """
    if not current_user.get("is_superuser"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要超级用户权限"
        )
    
    return current_user


class OptionalAuth:
    """
    可选认证依赖
    
    用法:
        @app.get("/items/")
        async def get_items(user: Optional[dict] = Depends(OptionalAuth())):
            if user:
                return {"message": f"Hello {user['username']}"}
            return {"message": "Hello guest"}
    """
    
    async def __call__(
        self,
        credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
        db: AsyncSession = Depends(get_db)
    ) -> Optional[dict]:
        return await get_current_user(credentials, db)
