from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User
from app.schemas import UserCreate, UserLogin, UserResponse, Token, TokenPair, RefreshTokenRequest
from app.auth import (
    get_password_hash, verify_password,
    create_access_token, create_refresh_token,
    decode_refresh_token, get_current_user,
    TOKEN_TYPE_ACCESS,
)
from app.config import settings
from app.services.captcha_service import create_captcha, verify_captcha
from app.services.rate_limit_service import login_limiter

router = APIRouter(prefix="/api/auth", tags=["认证"])


@router.get("/captcha")
def get_captcha():
    captcha_id, svg = create_captcha()
    return {
        "captcha_id": captcha_id,
        "image": svg,
    }


@router.post("/register", response_model=UserResponse)
def register(user_data: UserCreate, db: Session = Depends(get_db)):
    if not verify_captcha(user_data.captcha_id, user_data.captcha_code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="验证码错误或已过期"
        )
    existing_user = db.query(User).filter(
        (User.username == user_data.username) | (User.email == user_data.email)
    ).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户名或邮箱已被注册"
        )
    new_user = User(
        username=user_data.username,
        email=user_data.email,
        password_hash=get_password_hash(user_data.password),
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


@router.post("/login", response_model=TokenPair)
def login(user_data: UserLogin, request: Request, db: Session = Depends(get_db)):
    client_ip = request.client.host if request.client else "unknown"

    # 登录限流：检查是否被锁定
    if login_limiter.is_locked(client_ip, user_data.username):
        remaining = login_limiter.remaining_lockout(client_ip, user_data.username)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"登录失败次数过多，已锁定，请 {remaining} 秒后再试"
        )

    user = db.query(User).filter(User.username == user_data.username).first()
    if not user or not verify_password(user_data.password, user.password_hash):
        # 记录失败
        login_limiter.record_failure(client_ip, user_data.username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误"
        )
    # 登录成功，重置限流
    login_limiter.reset(client_ip, user_data.username)
    token_data = {"sub": str(user.id)}
    access_token = create_access_token(data=token_data)
    refresh_token = create_refresh_token(data=token_data)
    return TokenPair(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/refresh", response_model=TokenPair)
def refresh_token(body: RefreshTokenRequest, db: Session = Depends(get_db)):
    """用 refresh token 换取新的 access token（含新的 refresh token）"""
    payload = decode_refresh_token(body.refresh_token)
    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(status_code=401, detail="无效的 refresh token")
    user = db.query(User).filter(User.id == int(user_id)).first()
    if user is None:
        raise HTTPException(status_code=401, detail="用户不存在")
    token_data = {"sub": str(user.id)}
    return TokenPair(
        access_token=create_access_token(data=token_data),
        refresh_token=create_refresh_token(data=token_data),
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user
