"""
Manual test script for VisionObservationResult schema and parser.
"""

import sys
from pathlib import Path
from pprint import pprint

# Ensure project root is on sys.path for direct script execution
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.schemas import parse_vision_result
from src.vision_agent import analyze_unit_photo


def main():
    image_path = "fixtures/prep/a.jpg"
    unit_id = "TEST-001"

    print("=== Test 1: Real / Mock analyze_unit_photo Output ===")
    raw_result = analyze_unit_photo(image_path)
    parsed_result = parse_vision_result(raw_result, unit_id=unit_id, image_path=image_path)
    pprint(parsed_result)

    print("\n=== Test 2: Deliberately Malformed Input ===")
    malformed_input = {"status": "weird"}
    malformed_result = parse_vision_result(malformed_input, unit_id=unit_id, image_path=image_path)
    pprint(malformed_result)


if __name__ == "__main__":
    main()
