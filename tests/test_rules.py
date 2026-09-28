"""
Manual test suite for rule evaluation and prep result builder.
"""

import sys
from pathlib import Path
from pprint import pprint

# Ensure project root is on sys.path for direct script execution
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.rules import build_prep_result, evaluate_check
from src.schemas import VisionCheckObservation, VisionObservationResult


def main():
    print("=" * 70)
    print("TEST 1: Case with all passing checks (4 applicable checks)")
    print("=" * 70)
    vision_all_pass = VisionObservationResult(
        unit_id="UNIT-PASS-01",
        image_path="fixtures/prep/test.jpg",
        status="OK",
        checks={
            "polybag_present_sealed": VisionCheckObservation(
                check_name="polybag_present_sealed",
                observation="yes",
                evidence="Bag present and continuous seal visible.",
            ),
            "suffocation_warning": VisionCheckObservation(
                check_name="suffocation_warning",
                observation="legible",
                evidence="Suffocation warning printed clearly.",
            ),
            "expiry_date": VisionCheckObservation(
                check_name="expiry_date",
                observation="legible",
                evidence="Expiry date clearly readable.",
            ),
            "handling_marks": VisionCheckObservation(
                check_name="handling_marks",
                observation="all_present",
                evidence="All fragile/this-way-up labels present.",
            ),
        },
    )
    wo_all_pass = {
        "wo_polybag": "True",
        "wo_suffocation_warning": "True",
        "wo_expiry_date": "True",
        "wo_handling_marks": "fragile",
    }
    result_1 = build_prep_result(vision_all_pass, wo_all_pass)
    pprint(result_1)

    print("\n" + "=" * 70)
    print("TEST 2: Case with FAIL in suffocation_warning")
    print("=" * 70)
    vision_fail_suffocation = VisionObservationResult(
        unit_id="UNIT-FAIL-02",
        image_path="fixtures/prep/test.jpg",
        status="OK",
        checks={
            "polybag_present_sealed": VisionCheckObservation(
                check_name="polybag_present_sealed",
                observation="yes",
                evidence="Bag is sealed.",
            ),
            "suffocation_warning": VisionCheckObservation(
                check_name="suffocation_warning",
                observation="missing",
                evidence="No suffocation warning on bag.",
            ),
            "expiry_date": VisionCheckObservation(
                check_name="expiry_date",
                observation="legible",
                evidence="Expiry date readable.",
            ),
            "handling_marks": VisionCheckObservation(
                check_name="handling_marks",
                observation="all_present",
                evidence="Handling marks visible.",
            ),
        },
    )
    wo_fail_suffocation = {
        "wo_polybag": "True",
        "wo_suffocation_warning": "True",
        "wo_expiry_date": "True",
        "wo_handling_marks": "fragile",
    }
    result_2 = build_prep_result(vision_fail_suffocation, wo_fail_suffocation)
    pprint(result_2)

    print("\n" + "=" * 70)
    print("TEST 3: Case with wo_polybag NOT required (passes despite missing bag)")
    print("=" * 70)
    vision_not_required = VisionObservationResult(
        unit_id="UNIT-NOTREQ-03",
        image_path="fixtures/prep/test.jpg",
        status="OK",
        checks={
            "polybag_present_sealed": VisionCheckObservation(
                check_name="polybag_present_sealed",
                observation="missing",
                evidence="No polybag observed.",
            ),
            "suffocation_warning": VisionCheckObservation(
                check_name="suffocation_warning",
                observation="missing",
                evidence="No warning observed.",
            ),
            "expiry_date": VisionCheckObservation(
                check_name="expiry_date",
                observation="legible",
                evidence="Expiry date visible.",
            ),
            "handling_marks": VisionCheckObservation(
                check_name="handling_marks",
                observation="all_present",
                evidence="Marks present.",
            ),
        },
    )
    wo_not_required = {
        "wo_polybag": "False",
        "wo_suffocation_warning": "False",
        "wo_expiry_date": "True",
        "wo_handling_marks": "fragile",
    }
    result_3 = build_prep_result(vision_not_required, wo_not_required)
    pprint(result_3)

    print("\n" + "=" * 70)
    print("TEST 4: Case with PENDING vision_result (fails open, preserves reason)")
    print("=" * 70)
    vision_pending = VisionObservationResult(
        unit_id="UNIT-PENDING-04",
        image_path="fixtures/prep/test.jpg",
        status="PENDING",
        checks={},
        reason="Model API timeout after 30s",
    )
    result_4 = build_prep_result(vision_pending, wo_all_pass)
    pprint(result_4)

    print("\n" + "=" * 70)
    print("TEST 5: Standard 6-check unit (shows always-UNCERTAIN checks)")
    print("=" * 70)
    vision_all_6 = VisionObservationResult(
        unit_id="UNIT-SIXCHECKS-05",
        image_path="fixtures/prep/test.jpg",
        status="OK",
        checks={
            "polybag_present_sealed": VisionCheckObservation(
                check_name="polybag_present_sealed",
                observation="yes",
                evidence="Mock data: bag sealed.",
            ),
            "suffocation_warning": VisionCheckObservation(
                check_name="suffocation_warning",
                observation="legible",
                evidence="Mock data: warning legible.",
            ),
            "fnsku_label_placement": VisionCheckObservation(
                check_name="fnsku_label_placement",
                observation="flat",
                evidence="Mock data: label flat.",
            ),
            "original_barcode_covered": VisionCheckObservation(
                check_name="original_barcode_covered",
                observation="yes",
                evidence="Mock data: barcode covered.",
            ),
            "expiry_date": VisionCheckObservation(
                check_name="expiry_date",
                observation="legible",
                evidence="Mock data: expiry legible.",
            ),
            "handling_marks": VisionCheckObservation(
                check_name="handling_marks",
                observation="all_present",
                evidence="Mock data: marks present.",
            ),
        },
    )
    result_5 = build_prep_result(vision_all_6, wo_all_pass)
    pprint(result_5)


if __name__ == "__main__":
    main()
