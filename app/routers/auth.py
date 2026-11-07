import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi.security.oauth2 import OAuth2PasswordRequestForm
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from .. import database, mailer, models, oauth2, schemas, utils
from ..config import settings

router = APIRouter(tags=['authentication'])


def _hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode()).hexdigest()


@router.post("/login", response_model=schemas.Token)
def login(user_credentials: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(database.get_db)):
    # The form field is called "username" (OAuth2 standard) but we accept email OR username.
    identifier = user_credentials.username.strip().lower()
    user = db.query(models.Users).filter(
        or_(func.lower(models.Users.email) == identifier, func.lower(models.Users.username) == identifier)
    ).first()

    # Same message for "no such user" and "wrong password" so attackers cannot probe for accounts.
    if not user or not utils.verify(user_credentials.password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = oauth2.create_access_token(data={"user_id": user.id})
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/forgot-password", response_model=schemas.Message, status_code=status.HTTP_202_ACCEPTED)
def forgot_password(payload: schemas.ForgotPassword, background_tasks: BackgroundTasks,
                    db: Session = Depends(database.get_db)):
    user = db.query(models.Users).filter(models.Users.email == utils.normalize_email(payload.email)).first()
    if user:
        # Only the newest link works: remove older unused ones.
        db.query(models.PasswordResetToken).filter(models.PasswordResetToken.user_id == user.id).delete()
        raw_token = secrets.token_urlsafe(32)  # 256 bits from the OS's secure random source
        db.add(models.PasswordResetToken(
            user_id=user.id,
            token_hash=_hash_token(raw_token),
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=settings.reset_token_expire_minutes),
        ))
        db.commit()
        link = f"{settings.app_base_url.rstrip('/')}/reset-password?token={raw_token}"
        background_tasks.add_task(mailer.send_password_reset_email, user.email, link)
    # Identical answer whether or not the email exists.
    return {"detail": "If that email is registered, a reset link has been sent."}


@router.post("/reset-password", response_model=schemas.Message)
def reset_password(payload: schemas.ResetPassword, db: Session = Depends(database.get_db)):
    record = db.query(models.PasswordResetToken).filter(
        models.PasswordResetToken.token_hash == _hash_token(payload.token),
        models.PasswordResetToken.expires_at > datetime.now(timezone.utc),
    ).first()
    if record is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Invalid or expired reset link")

    user = db.query(models.Users).filter(models.Users.id == record.user_id).first()
    user.password = utils.hash(payload.new_password)
    # One-time use: remove every reset token for this user.
    db.query(models.PasswordResetToken).filter(models.PasswordResetToken.user_id == user.id).delete()
    db.commit()
    return {"detail": "Password updated. You can log in now."}
