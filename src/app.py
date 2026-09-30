"""
Prep Manager Pipeline Entry Point.

Provides process_unit() connecting vision observation -> schema parsing -> rule evaluation.
"""

import json
import sys
from dataclasses import asdict
from pathlib import Path

# Ensure project root is on sys.path when running app.py directly
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.rules import build_prep_result
from src.schemas import PrepResult, parse_vision_result
from src.vision_agent import analyze_unit_photo


def process_unit(image_path: str, unit_id: str, work_order: dict) -> PrepResult:
    """
    Full pipeline: photo -> vision observation -> rules -> final result.
    Makes exactly one vision model call internally (via analyze_unit_photo).
    """
    raw = analyze_unit_photo(image_path)
    vision_result = parse_vision_result(raw, unit_id=unit_id, image_path=image_path)
    return build_prep_result(vision_result, work_order)


if __name__ == "__main__":
    demo_image = "fixtures/prep/a.jpg"
    demo_unit = "DEMO-UNIT-001"
    demo_wo = {
        "wo_polybag": "True",
        "wo_suffocation_warning": "True",
        "wo_expiry_date": "False",
        "wo_handling_marks": "fragile",
    }
    result = process_unit(demo_image, demo_unit, demo_wo)
    print(json.dumps(asdict(result), indent=2))
