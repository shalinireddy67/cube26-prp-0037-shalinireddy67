"""
Vision Agent for Product Prep Observation.

Performs visual inspection of product preparation photos via Gemini or Claude vision.
Reports strictly observable evidence and categorical observations without
making compliance or pass/fail determinations.
"""

import base64
import json
import mimetypes
import os
from pathlib import Path
from typing import Any

import anthropic
from dotenv import load_dotenv
from google import genai
from google.genai import types

# Load environment variables from .env file
load_dotenv()

# Allowed categorical observations per check key
ALLOWED_OBSERVATIONS: dict[str, set[str]] = {
    "polybag_present_sealed": {"yes", "not_sealed", "missing", "uncertain"},
    "suffocation_warning": {"legible", "obscured_by_fold", "missing", "uncertain"},
    "fnsku_label_placement": {"flat", "on_seam", "on_curve", "on_edge", "missing", "uncertain"},
    "original_barcode_covered": {"yes", "no", "uncertain"},
    "expiry_date": {"legible", "illegible_after_wrap", "uncertain"},
    "handling_marks": {"all_present", "some_missing", "uncertain"},
}

VISION_PROMPT = """Analyze this product preparation photo and report what is visually observable.

You must return ONLY strict JSON without any surrounding prose, preamble, explanation, or markdown formatting (do NOT use ```json or ``` code fences).

CRITICAL INSTRUCTIONS:
- Do not invent compliance rules.
- Do not decide pass/fail.
- Only report what is directly visible in the image.
- "evidence" must be a concise string describing exactly what is visible that supports the observation (e.g., "top edge of bag has a visible heat-seal line").
- If the image does not show enough to tell, observation MUST be "uncertain" and evidence must state what is missing from view (e.g., "top edge of unit is out of frame"). Never guess. Never leave evidence blank.

The output must be a single JSON object with EXACTLY these six keys, each an object with "observation" and "evidence":

1. "polybag_present_sealed":
   "observation" MUST be one of: ["yes", "not_sealed", "missing", "uncertain"]
   "evidence": explanation of visible seal/bag or what is missing from view.

2. "suffocation_warning":
   "observation" MUST be one of: ["legible", "obscured_by_fold", "missing", "uncertain"]
   "evidence": explanation of visible warning text/print or what is missing from view.

3. "fnsku_label_placement":
   "observation" MUST be one of: ["flat", "on_seam", "on_curve", "on_edge", "missing", "uncertain"]
   "evidence": explanation of visible label position on surface or what is missing from view.

4. "original_barcode_covered":
   "observation" MUST be one of: ["yes", "no", "uncertain"]
   "evidence": explanation of visible coverage of manufacturer barcode or what is missing from view.

5. "expiry_date":
   "observation" MUST be one of: ["legible", "illegible_after_wrap", "uncertain"]
   "evidence": explanation of visible expiration date marking or what is missing from view.

6. "handling_marks":
   "observation" MUST be one of: ["all_present", "some_missing", "uncertain"]
   "evidence": explanation of visible handling marks/labels or what is missing from view.

Return ONLY the raw JSON object.
"""


def _get_media_type(file_path: str | Path) -> str:
    """Return the MIME type for an image file based on its extension."""
    ext = Path(file_path).suffix.lower()
    media_types = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp",
    }
    if ext in media_types:
        return media_types[ext]
    mime, _ = mimetypes.guess_type(str(file_path))
    if mime and mime.startswith("image/"):
        return mime
    return "image/jpeg"


def _call_gemini(
    image_bytes: bytes,
    media_type: str,
    prompt: str,
    model: str | None = None,
) -> str:
    """Call Google Gemini vision model and return the raw text response."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key or not api_key.strip():
        raise ValueError(
            "GEMINI_API_KEY is missing from environment. "
            "Please fill in GEMINI_API_KEY in your .env file."
        )

    selected_model = model or os.environ.get("GEMINI_VISION_MODEL", "gemini-2.5-flash")
    client = genai.Client(api_key=api_key)
    image_part = types.Part.from_bytes(data=image_bytes, mime_type=media_type)
    response = client.models.generate_content(
        model=selected_model,
        contents=[image_part, prompt],
        config=types.GenerateContentConfig(
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True)
        ),
    )
    return (response.text or "").strip()


def _call_anthropic(
    image_bytes: bytes,
    media_type: str,
    prompt: str,
    model: str | None = None,
) -> str:
    """Call Anthropic Claude vision model and return the raw text response."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key or not api_key.strip():
        raise ValueError(
            "ANTHROPIC_API_KEY is missing from environment. "
            "Please fill in ANTHROPIC_API_KEY in your .env file."
        )

    selected_model = model or os.environ.get("VISION_MODEL", "claude-haiku-4-5-20251001")
    image_data = base64.b64encode(image_bytes).decode("utf-8")

    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model=selected_model,
        max_tokens=1024,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": image_data,
                        },
                    },
                    {
                        "type": "text",
                        "text": prompt,
                    },
                ],
            }
        ],
    )

    extracted_parts = []
    for block in response.content:
        if getattr(block, "type", None) == "text" or hasattr(block, "text"):
            extracted_parts.append(block.text)
    return "".join(extracted_parts).strip()


def _call_mock(image_bytes: bytes, media_type: str, prompt: str, model: str | None = None) -> str:
    """Return hard-coded mock JSON for offline development/testing. Not a real observation."""
    mock_result = {
        "polybag_present_sealed": {"observation": "yes", "evidence": "Mock data: bag visible with sealed top edge."},
        "suffocation_warning": {"observation": "obscured_by_fold", "evidence": "Mock data: warning text partially hidden by a fold in the bag."},
        "fnsku_label_placement": {"observation": "on_seam", "evidence": "Mock data: label appears to cross a seam."},
        "original_barcode_covered": {"observation": "uncertain", "evidence": "Mock data: barcode area not clearly visible in this synthetic response."},
        "expiry_date": {"observation": "legible", "evidence": "Mock data: expiry date visible and readable."},
        "handling_marks": {"observation": "some_missing", "evidence": "Mock data: only some required handling marks visible."},
    }
    return json.dumps(mock_result)


def analyze_unit_photo(image_path: str, model: str | None = None) -> dict[str, Any]:
    """
    Analyze a product prep photo using the configured vision provider.

    Makes exactly one vision API call per unit and validates the observations.
    Fails open by returning a PENDING status dict instead of raising exceptions.

    Args:
        image_path: Path to the image file to analyze.
        model: Optional model identifier override. If None, uses provider default.

    Returns:
        dict: Either {"status": "OK", "checks": {...}} or
              {"status": "PENDING", "reason": "...", "raw_response": "..."}
    """
    raw_response_text = ""
    try:
        # Check image path
        path_obj = Path(image_path)
        if not path_obj.is_file():
            raise FileNotFoundError(f"Image file not found: {image_path}")

        # Read image bytes and determine media_type
        media_type = _get_media_type(path_obj)
        with open(path_obj, "rb") as f:
            image_bytes = f.read()

        # Determine provider and call appropriate vision provider
        provider = os.environ.get("VISION_PROVIDER", "gemini").lower()
        if provider == "gemini":
            raw_response_text = _call_gemini(
                image_bytes=image_bytes,
                media_type=media_type,
                prompt=VISION_PROMPT,
                model=model,
            )
        elif provider == "mock":
            raw_response_text = _call_mock(
                image_bytes=image_bytes,
                media_type=media_type,
                prompt=VISION_PROMPT,
                model=model,
            )
        elif provider == "anthropic":
            raw_response_text = _call_anthropic(
                image_bytes=image_bytes,
                media_type=media_type,
                prompt=VISION_PROMPT,
                model=model,
            )
        else:
            return {
                "status": "PENDING",
                "reason": f"Unknown VISION_PROVIDER: {provider}",
                "raw_response": "",
            }

        if not raw_response_text:
            return {
                "status": "PENDING",
                "reason": "Empty response received from vision model",
                "raw_response": raw_response_text,
            }

        # Extract from markdown fences if present
        cleaned_text = raw_response_text.strip()
        if "```" in cleaned_text:
            start_fence = cleaned_text.find("```")
            end_fence = cleaned_text.rfind("```")
            if start_fence != -1 and end_fence != -1 and end_fence > start_fence:
                inner = cleaned_text[start_fence + 3 : end_fence].strip()
                if inner.lower().startswith("json"):
                    inner = inner[4:].strip()
                cleaned_text = inner

        # Parse JSON
        try:
            parsed = json.loads(cleaned_text)
        except json.JSONDecodeError as exc:
            return {
                "status": "PENDING",
                "reason": f"Response is not valid JSON: {exc}",
                "raw_response": raw_response_text,
            }

        if not isinstance(parsed, dict):
            return {
                "status": "PENDING",
                "reason": "Parsed JSON response is not an object",
                "raw_response": raw_response_text,
            }

        # Validate all six keys and observation values
        missing_keys = [k for k in ALLOWED_OBSERVATIONS if k not in parsed]
        if missing_keys:
            return {
                "status": "PENDING",
                "reason": f"Missing required check keys: {', '.join(missing_keys)}",
                "raw_response": raw_response_text,
            }

        validated_checks: dict[str, dict[str, str]] = {}
        for check_name, allowed_values in ALLOWED_OBSERVATIONS.items():
            check_data = parsed[check_name]
            if not isinstance(check_data, dict):
                return {
                    "status": "PENDING",
                    "reason": f"Check '{check_name}' must be an object with 'observation' and 'evidence'",
                    "raw_response": raw_response_text,
                }

            observation = check_data.get("observation")
            if observation not in allowed_values:
                return {
                    "status": "PENDING",
                    "reason": (
                        f"Invalid observation '{observation}' for check '{check_name}'. "
                        f"Must be one of {sorted(allowed_values)}"
                    ),
                    "raw_response": raw_response_text,
                }

            evidence = check_data.get("evidence")
            if not isinstance(evidence, str) or not evidence.strip():
                return {
                    "status": "PENDING",
                    "reason": f"Missing or empty evidence string for check '{check_name}'",
                    "raw_response": raw_response_text,
                }

            validated_checks[check_name] = {
                "observation": observation,
                "evidence": evidence.strip(),
            }

        # Return OK on success
        return {
            "status": "OK",
            "checks": validated_checks,
        }

    except Exception as exc:
        # Fail open: catch timeouts, API errors, or unexpected exceptions
        return {
            "status": "PENDING",
            "reason": str(exc),
            "raw_response": raw_response_text or str(exc),
        }


if __name__ == "__main__":
    result = analyze_unit_photo("fixtures/prep/test.jpg")
    print(json.dumps(result, indent=2))
