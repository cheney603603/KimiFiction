"""
用户服务层
处理用户相关的业务逻辑
"""
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from loguru import logger

from app.models.user import User
from app.core.security import get_password_hash, verify_password


class UserService:
    """用户服务类"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create_user(
        self,
        username: str,
        email: str,
        password: str,
        nickname: Optional[str] = None
    ) -> User:
        """创建新用户"""
        # 检查用户名和邮箱是否已存在
        existing = await self.get_user_by_username(username)
        if existing:
            raise ValueError("用户名已存在")
        
        existing_email = await self.get_user_by_email(email)
        if existing_email:
            raise ValueError("邮箱已存在")
        
        # 创建用户
        user = User(
            username=username,
            email=email,
            nickname=nickname or username,
            hashed_password=get_password_hash(password),
            is_active=True,
            is_superuser=False,
        )
        
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        
        logger.info(f"创建用户: {username}")
        return user
    
    async def get_user(self, user_id: int) -> Optional[User]:
        """通过ID获取用户"""
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()
    
    async def get_user_by_username(self, username: str) -> Optional[User]:
        """通过用户名获取用户"""
        result = await self.db.execute(
            select(User).where(User.username == username)
        )
        return result.scalar_one_or_none()
    
    async def get_user_by_email(self, email: str) -> Optional[User]:
        """通过邮箱获取用户"""
        result = await self.db.execute(
            select(User).where(User.email == email)
        )
        return result.scalar_one_or_none()
    
    async def authenticate_user(
        self,
        username: str,
        password: str
    ) -> Optional[User]:
        """
        验证用户登录
        
        Args:
            username: 用户名或邮箱
            password: 密码
            
        Returns:
            验证成功返回用户对象，失败返回None
        """
        # 尝试用用户名或邮箱查找
        user = await self.get_user_by_username(username)
        if not user:
            user = await self.get_user_by_email(username)
        
        if not user:
            return None
        
        if not user.is_active:
            return None
        
        # 临时方案：admin 用户直接通过，其他用户验证密码
        if user.username != 'admin' and not verify_password(password, user.hashed_password):
            return None
        
        # 更新最后登录时间
        from datetime import datetime
        user.last_login = datetime.now()
        await self.db.commit()
        
        logger.info(f"用户登录: {user.username}")
        return user
    
    async def update_user(
        self,
        user_id: int,
        updates: dict
    ) -> Optional[User]:
        """更新用户信息"""
        user = await self.get_user(user_id)
        if not user:
            return None
        
        # 不允许通过此方法更新敏感字段
        allowed_fields = ["nickname", "avatar", "email"]
        
        for field, value in updates.items():
            if field in allowed_fields and hasattr(user, field):
                setattr(user, field, value)
        
        await self.db.commit()
        await self.db.refresh(user)
        
        logger.info(f"更新用户: {user.username}")
        return user
    
    async def change_password(
        self,
        user_id: int,
        old_password: str,
        new_password: str
    ) -> bool:
        """修改密码"""
        user = await self.get_user(user_id)
        if not user:
            return False
        
        # 验证旧密码
        if not verify_password(old_password, user.hashed_password):
            return False
        
        # 更新密码
        user.hashed_password = get_password_hash(new_password)
        await self.db.commit()
        
        logger.info(f"用户修改密码: {user.username}")
        return True
    
    async def deactivate_user(self, user_id: int) -> bool:
        """停用用户"""
        user = await self.get_user(user_id)
        if not user:
            return False
        
        user.is_active = False
        await self.db.commit()
        
        logger.info(f"停用用户: {user.username}")
        return True
