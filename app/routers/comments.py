from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session, joinedload

from .. import models, oauth2, schemas
from ..database import get_db
from ..dependencies import get_visible_post

router = APIRouter(tags=['Comments'])


@router.get("/posts/{post_id}/comments", response_model=List[schemas.CommentResponse])
def list_comments(post: models.Post = Depends(get_visible_post), db: Session = Depends(get_db),
                  limit: int = Query(50, ge=1, le=100), skip: int = Query(0, ge=0)):
    return (
        db.query(models.Comment)
        .options(joinedload(models.Comment.author))
        .filter(models.Comment.post_id == post.id)
        .order_by(models.Comment.created_at.asc(), models.Comment.id.asc())
        .limit(limit).offset(skip).all()
    )


@router.post("/posts/{post_id}/comments", response_model=schemas.CommentResponse,
             status_code=status.HTTP_201_CREATED)
def add_comment(payload: schemas.CommentCreate, post: models.Post = Depends(get_visible_post),
                db: Session = Depends(get_db),
                current_user: models.Users = Depends(oauth2.get_current_user)):
    comment = models.Comment(post_id=post.id, user_id=current_user.id, content=payload.content.strip())
    if not comment.content:
        raise HTTPException(422, detail="Comment cannot be empty")
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return comment


@router.delete("/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_comment(comment_id: int, db: Session = Depends(get_db),
                   current_user: models.Users = Depends(oauth2.get_current_user)):
    comment = db.query(models.Comment).filter(models.Comment.id == comment_id).first()
    if comment is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Comment does not exist")
    # The comment's author and the post's owner may delete it.
    if current_user.id not in (comment.user_id, comment.post.owner_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Not authorized to perform requested action")
    db.delete(comment)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
