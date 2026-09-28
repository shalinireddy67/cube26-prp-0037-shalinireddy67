"""
End-to-end pipeline test script.
"""

import os
import sys
from dataclasses import asdict
from pathlib import Path
from pprint import pprint
from unittest.mock import patch

# Ensure project root is on sys.path for direct script execution
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.app import process_unit
from src.schemas import VALID_VERDICTS


def main():
    image_path = "fixtures/prep/test.jpg"
    unit_id = "DEMO-UNIT-001"
    work_order = {
        "wo_polybag": "True",
        "wo_suffocation_warning": "True",
        "wo_expiry_date": "False",
        "wo_handling_marks": "fragile",
    }

    print("=" * 70)
    print("TEST 1: Standard pipeline run with configured provider (mock)")
    print("=" * 70)
    result = process_unit(image_path=image_path, unit_id=unit_id, work_order=work_order)

    # Assertions
    assert result.overall_status in VALID_VERDICTS, f"Invalid overall_status: {result.overall_status}"
    assert isinstance(result.requires_manual_review, bool), "requires_manual_review must be bool"
    assert result.unit_id == unit_id, "unit_id mismatch"
    assert len(result.checks) == 6, f"Expected 6 checks, got {len(result.checks)}"

    print(f"overall_status: {result.overall_status}")
    print(f"requires_manual_review: {result.requires_manual_review}")
    pprint(asdict(result))

    print("\n" + "=" * 70)
    print("TEST 2: Pipeline run with invalid VISION_PROVIDER (fail-open PENDING flow)")
    print("=" * 70)
    with patch.dict(os.environ, {"VISION_PROVIDER": "invalid_provider_xyz"}):
        pending_result = process_unit(image_path=image_path, unit_id="FAIL-OPEN-002", work_order=work_order)

        assert pending_result.overall_status == "PENDING", f"Expected PENDING, got {pending_result.overall_status}"
        assert pending_result.requires_manual_review is False, "PENDING unit should not have requires_manual_review True"
        assert len(pending_result.checks) == 0, "PENDING unit should have empty checks"
        assert "Unknown VISION_PROVIDER" in pending_result.evidence.get("reason", "")

        print(f"overall_status: {pending_result.overall_status}")
        print(f"requires_manual_review: {pending_result.requires_manual_review}")
        pprint(asdict(pending_result))

    print("\n[ALL PIPELINE TESTS PASSED]")


if __name__ == "__main__":
    main()
