from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from .schemas import KwsEvent, StopCommandResult


class DryRunStopActuator:
    """Safe actuator used before a relay, PLC, or motor controller is available."""

    mode = "dry_run"

    def stop(self, event: KwsEvent | None, reason: str = "kws_detected") -> StopCommandResult:
        return StopCommandResult(
            accepted=True,
            mode=self.mode,
            command_id=f"stop_{uuid4().hex[:10]}",
            reason=reason,
            timestamp=datetime.now().astimezone().isoformat(timespec="milliseconds"),
            detail={
                "event_id": event.event_id if event else None,
                "message": "No physical conveyor command was sent. This verifies the control path safely.",
            },
        )


def get_actuator(mode: str) -> DryRunStopActuator:
    if mode != "dry_run":
        # Keep unsafe hardware integrations explicit until the team chooses relay/PLC details.
        raise ValueError(f"Unsupported actuator mode: {mode}. Only dry_run is enabled.")
    return DryRunStopActuator()

