from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import exists, func, or_, select
from sqlalchemy.orm import Session, joinedload

from .. import models, oauth2, schemas
from ..database import get_db
from ..dependencies import get_visible_post

router = APIRouter(prefix="/posts", tags=['Posts'])


def _posts_with_counts(db: Session, current_user: models.Users):
    """Base query: each post plus its vote count, comment count and 'did I vote?'.

    Counts are scalar subqueries rather than JOINs. Joining both votes and comments would
    multiply the rows (3 votes x 4 comments = 12 rows) and give wrong counts.
    """
    votes = (select(func.count()).select_from(models.Votes)
             .where(models.Votes.post_id == models.Post.id).correlate(models.Post).scalar_subquery())
    comments = (select(func.count()).select_from(models.Comment)
                .where(models.Comment.post_id == models.Post.id).correlate(models.Post).scalar_subquery())
    voted = exists().where(models.Votes.post_id == models.Post.id, models.Votes.user_id == current_user.id)
    return (
        db.query(models.Post, votes.label("votes"), comments.label("comments"), voted.label("voted"))
        .options(joinedload(models.Post.owner)),
        votes, comments,
    )


def _visible_to(current_user: models.Users):
    return or_(models.Post.published.is_(True), models.Post.owner_id == current_user.id)


def _escape_like(text: str) -> str:
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


# Plain `def` (not `async def`): SQLAlchemy here is synchronous, and FastAPI runs plain
# `def` routes in a thread pool. An `async def` route that blocks on the database would
# freeze the whole server for everyone while it waits.

@router.post("/", response_model=schemas.PostResponse, status_code=status.HTTP_201_CREATED)
def create_post(post: schemas.PostCreate, db: Session = Depends(get_db),
                current_user: models.Users = Depends(oauth2.get_current_user)):
    new_post = models.Post(owner_id=current_user.id, **post.model_dump())
    db.add(new_post)
    db.commit()
    db.refresh(new_post)
    return new_post


@router.get("/", response_model=List[schemas.PostOut])
def read_posts(
    response: Response,
    db: Session = Depends(get_db),
    current_user: models.Users = Depends(oauth2.get_current_user),
    limit: int = Query(10, ge=1, le=50),
    skip: int = Query(0, ge=0),
    search: Optional[str] = "",
    owner: Optional[str] = Query(None, description="Only posts by this username"),
    sort: schemas.SortOption = "newest",
):
    query, votes, comments = _posts_with_counts(db, current_user)
    conditions = [_visible_to(current_user)]
    if search:
        pattern = f"%{_escape_like(search)}%"
        conditions.append(or_(models.Post.title.ilike(pattern, escape="\\"),
                              models.Post.content.ilike(pattern, escape="\\")))
    if owner:
        conditions.append(models.Post.owner.has(func.lower(models.Users.username) == owner.lower()))

    # The id is always the last sort key so pages never repeat or skip posts when
    # several posts tie on votes or time.
    order = {
        "newest": (models.Post.created_at.desc(), models.Post.id.desc()),
        "oldest": (models.Post.created_at.asc(), models.Post.id.asc()),
        "top": (votes.desc(), models.Post.id.desc()),
        "discussed": (comments.desc(), models.Post.id.desc()),
    }[sort]

    response.headers["X-Total-Count"] = str(
        db.query(func.count(models.Post.id)).filter(*conditions).scalar()
    )
    return query.filter(*conditions).order_by(*order).limit(limit).offset(skip).all()


@router.get("/{id}", response_model=schemas.PostOut)
def get_post(id: int, db: Session = Depends(get_db),
             current_user: models.Users = Depends(oauth2.get_current_user)):
    query, _, _ = _posts_with_counts(db, current_user)
    row = query.filter(models.Post.id == id, _visible_to(current_user)).first()
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"Post with id: {id} does not exist")
    return row


@router.put("/{id}", response_model=schemas.PostResponse)
def update_post(id: int, updated_post: schemas.PostCreate, db: Session = Depends(get_db),
                current_user: models.Users = Depends(oauth2.get_current_user)):
    post = db.query(models.Post).filter(models.Post.id == id).first()
    if post is None or (not post.published and post.owner_id != current_user.id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"Post with id: {id} does not exist")
    if post.owner_id != current_user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Not authorized to perform requested action")

    for key, value in updated_post.model_dump().items():
        setattr(post, key, value)
    db.commit()
    db.refresh(post)
    return post


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_post(id: int, db: Session = Depends(get_db),
                current_user: models.Users = Depends(oauth2.get_current_user)):
    post = db.query(models.Post).filter(models.Post.id == id).first()
    if post is None or (not post.published and post.owner_id != current_user.id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"Post with id: {id} does not exist")
    if post.owner_id != current_user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Not authorized to perform requested action")

    db.delete(post)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
