from typing import Generic, TypeVar

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.core.database import Base

ModelT = TypeVar("ModelT", bound=Base)


class Repository(Generic[ModelT]):
    def __init__(self, model: type[ModelT]):
        self.model = model

    def get(self, db: Session, entity_id: int) -> ModelT | None:
        return db.get(self.model, entity_id)

    def list(self, db: Session, *, offset: int = 0, limit: int = 50) -> list[ModelT]:
        return list(db.scalars(select(self.model).offset(offset).limit(limit)))

    def count(self, db: Session, query: Select | None = None) -> int:
        if query is None:
            return int(db.scalar(select(func.count()).select_from(self.model)) or 0)
        return int(db.scalar(select(func.count()).select_from(query.subquery())) or 0)

    def add(self, db: Session, entity: ModelT) -> ModelT:
        db.add(entity)
        db.flush()
        return entity

