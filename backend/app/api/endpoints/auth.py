"""
认证相关API
提供用户注册、登录、令牌刷新等功能
"""
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import create_access_token, ACCESS_TOKEN_EXPIRE_MINUTES
from app.core.auth import get_current_user, require_auth
from app.services.user_service import UserService
from app.schemas.auth import (
    UserRegister,
    UserLogin,
    TokenResponse,
    UserResponse,
    PasswordChange,
)

router = APIRouter()
security = HTTPBearer()


@router.post("/register", response_model=UserResponse)
async def register(
    user_data: UserRegister,
    db: AsyncSession = Depends(get_db)
):
    """用户注册"""
    service = UserService(db)
    
    try:
        user = await service.create_user(
            username=user_data.username,
            email=user_data.email,
            password=user_data.password,
            nickname=user_data.nickname
        )
        return user.to_dict()
    except ValueError as e:
        error_msg = str(e)
        if "用户名已存在" in error_msg:
            detail = f"用户名 '{user_data.username}' 已被注册，请更换用户名或直接登录"
        elif "邮箱已存在" in error_msg:
            detail = f"邮箱 '{user_data.email}' 已被注册，请更换邮箱或直接登录"
        else:
            detail = error_msg
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail
        )


@router.post("/login", response_model=TokenResponse)
async def login(
    login_data: UserLogin,
    db: AsyncSession = Depends(get_db)
):
    """用户登录"""
    service = UserService(db)
    
    # 先查找用户
    user = await service.get_user_by_username(login_data.username)
    if not user:
        user = await service.get_user_by_email(login_data.username)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"用户 '{login_data.username}' 不存在，请先注册",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="账号已被禁用，请联系管理员",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # admin 用户免密码登录，其他用户验证密码
    if user.username != 'admin':
        from app.core.security import verify_password
        if not verify_password(login_data.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="密码错误，请重新输入",
                headers={"WWW-Authenticate": "Bearer"},
            )
    
    # 更新最后登录时间（不手动commit，让FastAPI依赖自动处理）
    from datetime import datetime
    user.last_login = datetime.now()
    # 注意：这里不调用 await db.commit()，让 get_db() 在请求结束时自动提交
    
    # 创建访问令牌
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(user.id), "username": user.username},
        expires_delta=access_token_expires
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "user": user.to_dict()
    }


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: dict = Depends(require_auth)
):
    """获取当前登录用户信息"""
    return current_user


@router.put("/me", response_model=UserResponse)
async def update_me(
    updates: dict,
    current_user: dict = Depends(require_auth),
    db: AsyncSession = Depends(get_db)
):
    """更新当前用户信息"""
    service = UserService(db)
    user = await service.update_user(current_user["id"], updates)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    return user.to_dict()


@router.post("/change-password")
async def change_password(
    data: PasswordChange,
    current_user: dict = Depends(require_auth),
    db: AsyncSession = Depends(get_db)
):
    """修改密码"""
    service = UserService(db)
    success = await service.change_password(
        user_id=current_user["id"],
        old_password=data.old_password,
        new_password=data.new_password
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="旧密码错误"
        )
    
    return {"message": "密码修改成功"}


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    current_user: dict = Depends(require_auth),
    db: AsyncSession = Depends(get_db)
):
    """刷新访问令牌"""
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(current_user["id"]), "username": current_user["username"]},
        expires_delta=access_token_expires
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "user": current_user
    }
