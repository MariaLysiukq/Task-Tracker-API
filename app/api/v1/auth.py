"""Registration and login endpoints."""

from fastapi import APIRouter, Depends, status

from app.api.deps import SessionDep, login_rate_limit, register_rate_limit
from app.schemas.user import LoginRequest, TokenRead, UserCreate, UserRead
from app.services import auth as auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(register_rate_limit)],
)
async def register(data: UserCreate, session: SessionDep) -> UserRead:
    """Register a new account.

    Parameters
    ----------
    data : UserCreate
        Email, password and full name.
    session : AsyncSession
        Request database session.

    Returns
    -------
    UserRead
        The created user (409 if the email is taken, 429 if rate limited).
    """
    return UserRead.model_validate(await auth_service.register(session, data))


@router.post("/login", dependencies=[Depends(login_rate_limit)])
async def login(data: LoginRequest, session: SessionDep) -> TokenRead:
    """Exchange credentials for a bearer access token.

    Parameters
    ----------
    data : LoginRequest
        Email and password.
    session : AsyncSession
        Request database session.

    Returns
    -------
    TokenRead
        Access token (401 on bad credentials, 429 if rate limited).
    """
    return TokenRead(access_token=await auth_service.login(session, data))
