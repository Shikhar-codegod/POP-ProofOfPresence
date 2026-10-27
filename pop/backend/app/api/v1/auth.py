"""Authentication and device credential API routes."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user, require_admin
from app.models.user import User
from app.schemas.device_key import DeviceKeyCreate, DeviceKeyCreatedResponse
from app.schemas.token import RefreshTokenRequest, TokenRefreshResponse, TokenResponse
from app.schemas.user import UserCreate, UserLogin, UserResponse
from app.services.auth_service import (
    authenticate_user,
    issue_user_tokens,
    provision_device_key,
    refresh_user_token,
    register_user,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=TokenResponse)
async def login(
    login_data: UserLogin,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Authenticate user with email and password, returning JWT access and refresh tokens."""
    user = await authenticate_user(db, email=login_data.email, password=login_data.password)
    return issue_user_tokens(user)


@router.post("/refresh", response_model=TokenRefreshResponse)
async def refresh_token(
    payload: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenRefreshResponse:
    """Issue a fresh JWT access token using a valid refresh token."""
    return await refresh_user_token(db, refresh_token=payload.refresh_token)


@router.get("/me", response_model=UserResponse)
async def get_my_profile(
    current_user: User = Depends(get_current_user),
) -> User:
    """Retrieve profile details of the currently authenticated user."""
    return current_user


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_in: UserCreate,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Admin-only endpoint to register new platform inspectors, admins, or viewers."""
    return await register_user(db, user_in=user_in)


@router.post("/device-keys", response_model=DeviceKeyCreatedResponse, status_code=status.HTTP_201_CREATED)
async def create_device_key(
    device_in: DeviceKeyCreate,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> DeviceKeyCreatedResponse:
    """Admin-only endpoint to provision an edge device API key.

    NOTE: The plaintext secret key is revealed only once in this response and cannot be recovered.
    """
    return await provision_device_key(db, device_in=device_in)
