import re
from datetime import datetime
from typing import Annotated, Literal, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, computed_field, field_validator

USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_]{3,30}$")
DEFAULT_AVATAR_URL = "/static/img/default-avatar.svg"


def _check_password(value: str) -> str:
    # bcrypt silently ignores everything after 72 *bytes*, so we reject longer passwords
    # instead of letting people think a long password is fully used.
    if len(value) < 8:
        raise ValueError("Password must be at least 8 characters")
    if len(value.encode("utf-8")) > 72:
        raise ValueError("Password must be at most 72 bytes")
    return value


def _check_username(value: str) -> str:
    if not USERNAME_PATTERN.match(value):
        raise ValueError("Username must be 3-30 characters: letters, numbers and underscores only")
    return value


# --- User schemas ---

class UserCreate(BaseModel):
    email: EmailStr
    username: str
    password: str

    _username = field_validator("username")(_check_username)
    _password = field_validator("password")(_check_password)


class UserPublic(BaseModel):
    """What other users may see. No email."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    bio: Optional[str] = None
    created_at: datetime
    image_file: Optional[str] = Field(default=None, exclude=True)

    @computed_field
    @property
    def image_url(self) -> str:
        if self.image_file:
            return f"/media/profile_pics/{self.image_file}"
        return DEFAULT_AVATAR_URL


class UserResponse(UserPublic):
    """What the account owner sees about themselves."""
    email: EmailStr


class UserProfile(UserPublic):
    posts_count: int = 0


class UserUpdate(BaseModel):
    username: Optional[str] = None
    bio: Optional[str] = Field(default=None, max_length=300)

    @field_validator("username")
    @classmethod
    def _username(cls, v):
        return _check_username(v) if v is not None else v


class ChangePassword(BaseModel):
    current_password: str
    new_password: str

    _new = field_validator("new_password")(_check_password)


class UserLogin(BaseModel):
    email: EmailStr
    password: str

    model_config = ConfigDict(from_attributes=True)


# --- Post schemas ---

class PostCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=5000)
    published: bool = True


class PostResponse(PostCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    owner_id: int
    owner: UserPublic


class PostOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    Post: PostResponse
    votes: int
    comments: int = 0
    voted: bool = False


SortOption = Literal["newest", "oldest", "top", "discussed"]


# --- Comments ---

class CommentCreate(BaseModel):
    content: str = Field(min_length=1, max_length=1000)


class CommentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    post_id: int
    content: str
    created_at: datetime
    author: UserPublic


# --- Auth / vote schemas ---

class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    id: Optional[int | str] = None


class Vote(BaseModel):
    post_id: int
    dir: Annotated[int, Field(le=1, ge=0)]


class ForgotPassword(BaseModel):
    email: EmailStr


class ResetPassword(BaseModel):
    token: str = Field(min_length=10, max_length=200)
    new_password: str

    _new = field_validator("new_password")(_check_password)


class Message(BaseModel):
    detail: str
