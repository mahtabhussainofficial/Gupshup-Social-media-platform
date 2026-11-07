from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash(password: str):
    return pwd_context.hash(password)


def verify(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def normalize_email(email: str) -> str:
    """Emails are stored lowercase so "Ali@x.com" and "ali@x.com" are one account."""
    return email.strip().lower()
