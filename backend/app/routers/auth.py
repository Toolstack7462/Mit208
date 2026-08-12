"""Authentication routes: JSON login + OAuth2 password form (for /docs)."""
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from ..audit import record_audit
from ..config import settings
from ..database import get_db
from ..deps import get_current_user
from ..models import User
from ..ratelimit import LoginRateLimiter
from ..schemas import LoginRequest, Token, UserOut
from ..security import create_access_token, dummy_verify, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])

login_limiter = LoginRateLimiter(
    max_attempts=settings.login_max_attempts,
    window_seconds=settings.login_window_seconds,
)


def _client_key(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _authenticate(db: Session, email: str, password: str) -> User:
    user = db.query(User).filter(User.email == email.lower()).first()
    if not user:
        # Run a hash comparison anyway so an unknown address takes about the
        # same time as a known one. Without this, response timing reveals which
        # addresses have accounts.
        dummy_verify(password)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    if not verify_password(password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account disabled")
    return user


def _guarded_authenticate(db: Session, request: Request, email: str, password: str) -> User:
    """Authenticate, counting failures per client IP to slow password guessing."""
    key = _client_key(request)
    if login_limiter.is_blocked(key):
        retry = login_limiter.retry_after(key)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed login attempts. Please try again later.",
            headers={"Retry-After": str(retry)},
        )
    try:
        user = _authenticate(db, email, password)
    except HTTPException as exc:
        if exc.status_code == status.HTTP_401_UNAUTHORIZED:
            login_limiter.register_failure(key)
        raise
    login_limiter.reset(key)
    return user


@router.post("/login", response_model=Token)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    user = _guarded_authenticate(db, request, payload.email, payload.password)
    record_audit(
        db, user=user, action="login", entity_type="user", entity_id=user.id,
        details="User logged in", ip_address=_client_key(request),
    )
    db.commit()
    token = create_access_token(subject=user.email, role=user.role)
    return Token(access_token=token, user=UserOut.model_validate(user))


@router.post("/token", response_model=Token)
def login_form(
    request: Request,
    form: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """OAuth2 password flow so the Swagger 'Authorize' button works.

    Audited identically to /login. This is a real sign-in that mints a real access
    token, so leaving it unrecorded made "every login is recorded" false: signing in
    through the Swagger Authorize button produced a usable token and no audit row.
    """
    user = _guarded_authenticate(db, request, form.username, form.password)
    record_audit(
        db, user=user, action="login", entity_type="user", entity_id=user.id,
        details="User logged in via the OAuth2 password flow",
        ip_address=_client_key(request),
    )
    db.commit()
    token = create_access_token(subject=user.email, role=user.role)
    return Token(access_token=token, user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
def me(current: User = Depends(get_current_user)):
    return current
