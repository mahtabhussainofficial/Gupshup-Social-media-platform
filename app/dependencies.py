from fastapi import Depends, HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from . import models, oauth2
from .database import get_db


def get_visible_post(post_id: int, db: Session = Depends(get_db),
                     current_user: models.Users = Depends(oauth2.get_current_user)) -> models.Post:
    """A post is visible if it is published, or if you own it (your drafts).
    Anyone else gets 404, so they cannot even tell that a draft exists."""
    post = (
        db.query(models.Post)
        .filter(models.Post.id == post_id,
                or_(models.Post.published.is_(True), models.Post.owner_id == current_user.id))
        .first()
    )
    if post is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"Post with id: {post_id} does not exist")
    return post
