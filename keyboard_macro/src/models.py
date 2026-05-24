from dataclasses import dataclass, field
from typing import Optional
from uuid import uuid4


MIN_TAP_INTERVAL_MS = 80


def new_step_id() -> str:
    return uuid4().hex[:8]


@dataclass
class ActionStep:
    id: str = field(default_factory=new_step_id)
    direction_key: Optional[str] = None
    tap_keys: list[str] = field(default_factory=list)
    hold_seconds: float = 1.0
    tap_interval_ms: int = 200

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "direction_key": self.direction_key,
            "tap_keys": list(self.tap_keys),
            "hold_seconds": self.hold_seconds,
            "tap_interval_ms": self.tap_interval_ms,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ActionStep":
        direction_key = data.get("direction_key") or None
        if isinstance(direction_key, str):
            direction_key = direction_key.upper()

        return cls(
            id=str(data.get("id") or new_step_id()),
            direction_key=direction_key,
            tap_keys=[str(key).strip().lower() for key in data.get("tap_keys", []) if str(key).strip()],
            hold_seconds=max(float(data.get("hold_seconds", 1.0)), 0.01),
            tap_interval_ms=max(int(data.get("tap_interval_ms", 200)), MIN_TAP_INTERVAL_MS),
        )


@dataclass
class MacroSequence:
    name: str
    steps: list[ActionStep] = field(default_factory=list)
    loop: bool = False
    loop_count: Optional[int] = None

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "steps": [step.to_dict() for step in self.steps],
            "loop": self.loop,
            "loop_count": self.loop_count,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MacroSequence":
        loop_count = data.get("loop_count")
        if loop_count in ("", 0):
            loop_count = None
        elif loop_count is not None:
            loop_count = max(int(loop_count), 1)

        return cls(
            name=str(data.get("name") or "Untitled Macro"),
            steps=[ActionStep.from_dict(item) for item in data.get("steps", [])],
            loop=bool(data.get("loop", False)),
            loop_count=loop_count,
        )

    def clone(self) -> "MacroSequence":
        return MacroSequence.from_dict(self.to_dict())
