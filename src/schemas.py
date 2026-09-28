from dataclasses import dataclass, field
from typing import Any


VALID_VERDICTS = {"PASS", "FAIL", "UNCERTAIN", "PENDING"}


@dataclass
class ComplianceCheck:
    name: str
    verdict: str
    explanation: str
    evidence: list[str] = field(default_factory=list)

    def __post_init__(self):
        if self.verdict not in VALID_VERDICTS:
            raise ValueError(
                f"Invalid verdict: {self.verdict}. "
                f"Expected one of {VALID_VERDICTS}"
            )


@dataclass
class PrepResult:
    unit_id: str
    checks: list[ComplianceCheck]
    overall_status: str
    evidence: dict[str, Any] = field(default_factory=dict)
    requires_manual_review: bool = False

    def __post_init__(self):
        if self.overall_status not in VALID_VERDICTS:
            raise ValueError(
                f"Invalid overall status: {self.overall_status}"
            )


VALID_OBSERVATION_STATUSES = {"OK", "PENDING"}


@dataclass
class VisionCheckObservation:
    check_name: str
    observation: str
    evidence: str


@dataclass
class VisionObservationResult:
    unit_id: str
    image_path: str
    status: str
    checks: dict[str, VisionCheckObservation] = field(default_factory=dict)
    reason: str | None = None

    def __post_init__(self):
        if self.status not in VALID_OBSERVATION_STATUSES:
            raise ValueError(
                f"Invalid status: {self.status}. "
                f"Expected one of {VALID_OBSERVATION_STATUSES}"
            )


def parse_vision_result(raw: dict, unit_id: str, image_path: str) -> VisionObservationResult:
    if not isinstance(raw, dict):
        return VisionObservationResult(
            unit_id=unit_id,
            image_path=image_path,
            status="PENDING",
            checks={},
            reason=f"Malformed input: expected dict, got {type(raw).__name__}",
        )

    status = raw.get("status")

    if status == "OK":
        checks_raw = raw.get("checks")
        if not isinstance(checks_raw, dict):
            return VisionObservationResult(
                unit_id=unit_id,
                image_path=image_path,
                status="PENDING",
                checks={},
                reason="Malformed input: missing or invalid 'checks' in OK response",
            )

        parsed_checks: dict[str, VisionCheckObservation] = {}
        for check_name, check_data in checks_raw.items():
            if isinstance(check_data, dict):
                obs = str(check_data.get("observation", ""))
                evi = str(check_data.get("evidence", ""))
            else:
                obs = str(check_data)
                evi = ""
            parsed_checks[check_name] = VisionCheckObservation(
                check_name=check_name,
                observation=obs,
                evidence=evi,
            )

        return VisionObservationResult(
            unit_id=unit_id,
            image_path=image_path,
            status="OK",
            checks=parsed_checks,
            reason=None,
        )

    if status == "PENDING":
        return VisionObservationResult(
            unit_id=unit_id,
            image_path=image_path,
            status="PENDING",
            checks={},
            reason=raw.get("reason", "Unknown error"),
        )

    # Malformed status (missing or unexpected value)
    if status is None:
        reason_desc = "Malformed input: missing 'status' field"
    else:
        reason_desc = f"Malformed input: unexpected status '{status}'"

    return VisionObservationResult(
        unit_id=unit_id,
        image_path=image_path,
        status="PENDING",
        checks={},
        reason=reason_desc,
    )