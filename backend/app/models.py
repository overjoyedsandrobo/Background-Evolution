from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db import Base

DEFAULT_ENVIRONMENT_SLOT_KEYS = ["water", "earth", "air", "fire"]
EVOLUTION_STAGES = ("dormant", "cracked", "hatching", "petawaru")
TABS = ("stats", "environment")


class SaveSlot(Base):
    __tablename__ = "save_slots"
    __table_args__ = (
        CheckConstraint(f"current_tab IN {TABS}", name="ck_save_slots_current_tab"),
        CheckConstraint(
            f"evolution_stage IN {EVOLUTION_STAGES}", name="ck_save_slots_evolution_stage"
        ),
        CheckConstraint(
            "evolution_click_progress >= 0 AND evolution_click_progress <= 2",
            name="ck_save_slots_evolution_click_progress",
        ),
        CheckConstraint("hidden_cycle_index >= 1", name="ck_save_slots_hidden_cycle_index"),
        CheckConstraint(
            "hidden_slot_index >= 0 AND hidden_slot_index <= 3",
            name="ck_save_slots_hidden_slot_index",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    used: Mapped[bool] = mapped_column(default=False)
    current_tab: Mapped[str] = mapped_column(String(16), default="stats")
    time_alive_seconds: Mapped[float] = mapped_column(Float, default=0.0)
    evolution_stage: Mapped[str] = mapped_column(String(16), default="dormant")
    evolution_click_progress: Mapped[int] = mapped_column(Integer, default=0)
    selected_environment: Mapped[str | None] = mapped_column(String(64), nullable=True)
    hidden_revealed: Mapped[bool] = mapped_column(default=False)
    hidden_environment_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    hidden_cycle_index: Mapped[int] = mapped_column(Integer, default=1)
    hidden_slot_index: Mapped[int] = mapped_column(Integer, default=3)
    environment_slot_keys: Mapped[list[str]] = mapped_column(
        JSONB, default=lambda: list(DEFAULT_ENVIRONMENT_SLOT_KEYS)
    )
    awaiting_hidden_relock_choice: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    environment_times: Mapped[list["EnvironmentTimeSeconds"]] = relationship(
        back_populates="slot", cascade="all, delete-orphan"
    )
    known_environments: Mapped[list["KnownEnvironment"]] = relationship(
        back_populates="slot", cascade="all, delete-orphan"
    )


class EnvironmentTimeSeconds(Base):
    __tablename__ = "environment_time_seconds"
    __table_args__ = (UniqueConstraint("slot_id", "environment_key", name="uq_env_time_slot_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slot_id: Mapped[int] = mapped_column(ForeignKey("save_slots.id", ondelete="CASCADE"))
    environment_key: Mapped[str] = mapped_column(String(64))
    seconds: Mapped[float] = mapped_column(Float, default=0.0)

    slot: Mapped[SaveSlot] = relationship(back_populates="environment_times")


class KnownEnvironment(Base):
    __tablename__ = "known_environments"
    __table_args__ = (UniqueConstraint("slot_id", "name", name="uq_known_env_slot_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slot_id: Mapped[int] = mapped_column(ForeignKey("save_slots.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(64))
    weights: Mapped[dict[str, float]] = mapped_column(JSONB)
    traits: Mapped[dict[str, float]] = mapped_column(JSONB)
    generation: Mapped[int] = mapped_column(Integer)
    parents: Mapped[list[str]] = mapped_column(JSONB)

    slot: Mapped[SaveSlot] = relationship(back_populates="known_environments")
