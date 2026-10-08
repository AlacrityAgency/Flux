"""Validated, snapshot-able configuration of the user's agent team."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class CustomAgent(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    id: str = Field(pattern=r"^custom_[a-z0-9]{8,32}$")
    name: str = Field(min_length=1, max_length=60)
    role: Literal['opus', 'sol', 'luna'] = 'luna'
    model_id: str
    instructions: str = Field(min_length=5, max_length=3000)
    enabled: bool = True

    @field_validator('name', 'instructions')
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError('متن نباید خالی باشد.')
        return value.strip()

    @field_validator('model_id')
    @classmethod
    def known_model(cls, value):
        from flux.budget.pricing import MODEL_PRICES
        if value not in MODEL_PRICES:
            raise ValueError('مدل انتخاب‌شده در فهرست مدل‌ها نیست.')
        return value


class AgentSettings(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    model_overrides: dict[str, str] = Field(default_factory=dict)
    custom_agents: list[CustomAgent] = Field(default_factory=list, max_length=5)

    @model_validator(mode='after')
    def validate_team(self):
        from flux.budget.pricing import MODEL_PRICES
        if any(k not in ('head', 'opus', 'sol', 'luna', 'verification') or v not in MODEL_PRICES
               for k, v in self.model_overrides.items()):
            raise ValueError('نقش یا مدل انتخاب‌شده معتبر نیست.')
        ids = [a.id for a in self.custom_agents]
        if len(ids) != len(set(ids)):
            raise ValueError('شناسهٔ Agent تکراری است.')
        return self
