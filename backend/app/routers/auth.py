"""Authentication routes: JSON login + OAuth2 password form (for /docs)."""
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from ..audit import record_audit
from ..database import get_db
from ..deps import get_current_user
from ..models import User
from ..schemas import LoginRequest, Token, UserOut
from ..security import create_access_token, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _authenticate(db: Session, email: str, password: str) -> User:
    user = db.query(User).filter(User.email == email.lower()).first()
    if not user or not verify_password(password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account disabled")
    return user


@router.post("/login", response_model=Token)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    user = _authenticate(db, payload.email, payload.password)
    record_audit(
        db, user=user, action="login", entity_type="user", entity_id=user.id,
        details="User logged in", ip_address=request.client.host if request.client else None,
    )
    db.commit()
    token = create_access_token(subject=user.email, role=user.role)
    return Token(access_token=token, user=UserOut.model_validate(user))


@router.post("/token", response_model=Token)
def login_form(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """OAuth2 password flow so the Swagger 'Authorize' button works."""
    user = _authenticate(db, form.username, form.password)
    token = create_access_token(subject=user.email, role=user.role)
    return Token(access_token=token, user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
def me(current: User = Depends(get_current_user)):
    return current
