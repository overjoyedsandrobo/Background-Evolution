from typing import Literal

from pydantic import BaseModel, Field

EvolutionStage = Literal["dormant", "cracked", "hatching", "petawaru"]
Tab = Literal["stats", "environment"]


class EnvironmentSchema(BaseModel):
    name: str
    weights: dict[str, float]
    traits: dict[str, float]
    tier: float
    parents: list[str]

    model_config = {"from_attributes": True}


class SlotSummary(BaseModel):
    id: int
    used: bool
    current_tab: Tab
    evolution_stage: EvolutionStage
    time_alive_seconds: float

    model_config = {"from_attributes": True}


class SlotDetail(SlotSummary):
    evolution_click_progress: int
    selected_environment: str | None
    hidden_revealed: bool
    hidden_environment_name: str | None
    hidden_cycle_index: int
    hidden_slot_index: int
    environment_slot_keys: list[str]
    awaiting_hidden_relock_choice: bool
    environment_time_seconds: dict[str, float]
    known_environments: dict[str, EnvironmentSchema]


class SlotPatch(BaseModel):
    current_tab: Tab | None = None
    time_alive_seconds: float | None = None
    evolution_stage: EvolutionStage | None = None
    evolution_click_progress: int | None = Field(default=None, ge=0, le=2)
    selected_environment: str | None = None
    environment_time_seconds: dict[str, float] | None = None
    hidden_revealed: bool | None = None
    hidden_environment_name: str | None = None
    hidden_cycle_index: int | None = Field(default=None, ge=1)
    hidden_slot_index: int | None = Field(default=None, ge=0, le=3)
    environment_slot_keys: list[str] | None = None
    awaiting_hidden_relock_choice: bool | None = None
