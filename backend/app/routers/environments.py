from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import crud, schemas
from app.db import get_db

router = APIRouter(prefix="/slots/{slot_id}/environments", tags=["environments"])


def _get_slot_or_404(db: Session, slot_id: int):
    try:
        return crud.get_slot(db, slot_id)
    except crud.SlotNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("", response_model=list[schemas.EnvironmentSchema])
def list_environments(slot_id: int, db: Session = Depends(get_db)):
    slot = _get_slot_or_404(db, slot_id)
    return list(crud.slot_detail_dict(slot)["known_environments"].values())


@router.post("/generate", response_model=schemas.EnvironmentSchema)
def generate_environment(slot_id: int, db: Session = Depends(get_db)):
    slot = _get_slot_or_404(db, slot_id)
    name = crud.generate_environment_for_slot(db, slot)
    db.commit()
    db.refresh(slot)
    env = crud.get_environment_dict(slot, name)
    return schemas.EnvironmentSchema(**env)


@router.post("/{name}/ensure", response_model=schemas.EnvironmentSchema)
def ensure_environment(slot_id: int, name: str, db: Session = Depends(get_db)):
    slot = _get_slot_or_404(db, slot_id)
    if not crud.ensure_environment_known(db, slot, name):
        raise HTTPException(status_code=404, detail=f"'{name}' is not a known environment")
    db.commit()
    db.refresh(slot)
    env = crud.get_environment_dict(slot, name)
    return schemas.EnvironmentSchema(**env)
