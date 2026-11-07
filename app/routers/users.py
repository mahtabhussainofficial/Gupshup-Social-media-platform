from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import images, models, oauth2, schemas, storage, utils
from ..config import settings
from ..database import get_db

router = APIRouter(prefix="/users", tags=['users'])


def _username_taken(db: Session, username: str, exclude_id: int | None = None) -> bool:
    q = db.query(models.Users.id).filter(func.lower(models.Users.username) == username.lower())
    if exclude_id is not None:
        q = q.filter(models.Users.id != exclude_id)
    return db.query(q.exists()).scalar()


@router.post("/", status_code=status.HTTP_201_CREATED, response_model=schemas.UserResponse)
def create_users(user: schemas.UserCreate, db: Session = Depends(get_db)):
    email = utils.normalize_email(user.email)
    if db.query(models.Users.id).filter(models.Users.email == email).first():
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Email is already registered")
    if _username_taken(db, user.username):
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Username is already taken")

    new_user = models.Users(email=email, username=user.username, password=utils.hash(user.password))
    db.add(new_user)
    try:
        db.commit()
    except IntegrityError:
        # Two people registering the same name at the same instant: the database unique
        # constraints are the real guard, the checks above only give friendlier messages.
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Email or username is already taken")
    db.refresh(new_user)
    return new_user


# NOTE: the "/me" routes must be declared before "/{username}", otherwise FastAPI would
# treat the word "me" as a username.

@router.get("/me", response_model=schemas.UserResponse)
def read_me(current_user: models.Users = Depends(oauth2.get_current_user)):
    return current_user


@router.patch("/me", response_model=schemas.UserResponse)
def update_me(update: schemas.UserUpdate, db: Session = Depends(get_db),
              current_user: models.Users = Depends(oauth2.get_current_user)):
    data = update.model_dump(exclude_unset=True)
    if data.get("username") is None:
        data.pop("username", None)  # username cannot be cleared
    if "username" in data and _username_taken(db, data["username"], exclude_id=current_user.id):
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Username is already taken")
    for key, value in data.items():
        setattr(current_user, key, value)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Username is already taken")
    db.refresh(current_user)
    return current_user


@router.post("/me/password", response_model=schemas.Message)
def change_password(payload: schemas.ChangePassword, db: Session = Depends(get_db),
                    current_user: models.Users = Depends(oauth2.get_current_user)):
    if not utils.verify(payload.current_password, current_user.password):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect")
    current_user.password = utils.hash(payload.new_password)
    db.commit()
    return {"detail": "Password updated"}


@router.post("/me/picture", response_model=schemas.UserResponse)
def upload_picture(file: UploadFile = File(...), db: Session = Depends(get_db),
                   current_user: models.Users = Depends(oauth2.get_current_user)):
    max_bytes = settings.max_upload_mb * 1024 * 1024
    # Read one byte more than the limit: if we get it, the file is too big. This stops a
    # huge upload from being loaded fully into memory.
    data = file.file.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise HTTPException(413,
                            detail=f"Image must be smaller than {settings.max_upload_mb} MB")
    try:
        processed = images.process_profile_image(data)
    except images.InvalidImage as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc))

    old_file = current_user.image_file
    current_user.image_file = storage.save_profile_image(processed)
    db.commit()
    storage.delete_profile_image(old_file)  # only after the database change succeeded
    db.refresh(current_user)
    return current_user


@router.delete("/me/picture", response_model=schemas.UserResponse)
def remove_picture(db: Session = Depends(get_db),
                   current_user: models.Users = Depends(oauth2.get_current_user)):
    old_file = current_user.image_file
    current_user.image_file = None
    db.commit()
    storage.delete_profile_image(old_file)
    db.refresh(current_user)
    return current_user


@router.get("/{username}", response_model=schemas.UserProfile)
def read_profile(username: str, db: Session = Depends(get_db),
                 current_user: models.Users = Depends(oauth2.get_current_user)):
    user = db.query(models.Users).filter(func.lower(models.Users.username) == username.lower()).first()
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"User '{username}' does not exist")
    posts_count = db.query(func.count(models.Post.id)).filter(
        models.Post.owner_id == user.id, models.Post.published.is_(True)
    ).scalar()
    return schemas.UserProfile.model_validate(user).model_copy(update={"posts_count": posts_count})
