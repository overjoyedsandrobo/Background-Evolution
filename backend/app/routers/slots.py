from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import crud, schemas
from app.db import get_db

router = APIRouter(prefix="/slots", tags=["slots"])


def _get_slot_or_404(db: Session, slot_id: int):
    try:
        return crud.get_slot(db, slot_id)
    except crud.SlotNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("", response_model=list[schemas.SlotSummary])
def list_slots(db: Session = Depends(get_db)):
    return crud.list_slots(db)


@router.get("/{slot_id}", response_model=schemas.SlotDetail)
def get_slot(slot_id: int, db: Session = Depends(get_db)):
    slot = _get_slot_or_404(db, slot_id)
    return crud.slot_detail_dict(slot)


@router.post("/{slot_id}/new", response_model=schemas.SlotDetail)
def new_slot(slot_id: int, db: Session = Depends(get_db)):
    _get_slot_or_404(db, slot_id)
    slot = crud.new_slot(db, slot_id)
    return crud.slot_detail_dict(slot)


@router.post("/{slot_id}/reset", response_model=schemas.SlotDetail)
def reset_slot(slot_id: int, db: Session = Depends(get_db)):
    _get_slot_or_404(db, slot_id)
    slot = crud.reset_slot(db, slot_id)
    return crud.slot_detail_dict(slot)


@router.patch("/{slot_id}", response_model=schemas.SlotDetail)
def patch_slot(slot_id: int, patch: schemas.SlotPatch, db: Session = Depends(get_db)):
    _get_slot_or_404(db, slot_id)
    data = patch.model_dump(exclude_unset=True)
    if "environment_slot_keys" in data and len(data["environment_slot_keys"]) != 4:
        raise HTTPException(
            status_code=422, detail="environment_slot_keys must have exactly 4 entries"
        )
    slot = crud.patch_slot(db, slot_id, data)
    return crud.slot_detail_dict(slot)
