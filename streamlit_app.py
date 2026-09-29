import os
import sys
import tempfile
import time
from pathlib import Path

from dotenv import load_dotenv
import streamlit as st

# Ensure project root is on sys.path for direct imports
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv()

from src.app import process_unit
from src.storage import init_db, save_result, save_image, get_results_for_org

init_db()

st.set_page_config(page_title="Prep Manager \u2014 Visual Compliance Check", layout="centered")

# 1. Page Title
st.title("Prep Manager \u2014 Visual Compliance Check")

# 2. Active Vision Provider Caption and Mock Warning Banner
vision_provider = os.environ.get("VISION_PROVIDER", "gemini")
st.caption(f"Active vision provider: {vision_provider}")
if vision_provider == "mock":
    st.warning("Running on MOCK vision data for development \u2014 these are not real observations.")

# 3. Work Order Input Section (Sidebar or Expander)
with st.sidebar:
    st.header("Work Order Settings")
    org_id = st.text_input("Organization ID", value="org_demo_alpha")
    polybag_required = st.checkbox("Polybag required?", value=True)
    suffocation_required = st.checkbox("Suffocation warning required?", value=True)
    expiry_required = st.checkbox("Expiry date required?", value=False)
    handling_marks_input = st.text_input(
        "Handling marks required (semicolon-separated, e.g. fragile;this_way_up, leave blank if none)",
        value="fragile",
    )

    work_order = {
        "wo_polybag": "True" if polybag_required else "False",
        "wo_suffocation_warning": "True" if suffocation_required else "False",
        "wo_expiry_date": "True" if expiry_required else "False",
        "wo_handling_marks": handling_marks_input.strip(),
    }

# 4. Text Input for unit_id
unit_id = st.text_input("Unit Identifier", value=f"UI-UNIT-{int(time.time())}")

# 5. File Uploader with Immediate Preview
uploaded_file = st.file_uploader("Upload package photo", type=["jpg", "jpeg", "png"])
if uploaded_file is not None:
    st.image(uploaded_file, caption="Uploaded Package Photo", use_container_width=True)

# 6. Analyze Button (only runs on click)
if st.button("Analyze"):
    if uploaded_file is None:
        st.error("Please upload a photo first.")
        st.stop()

    suffix = Path(uploaded_file.name).suffix or ".jpg"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
        tmp_file.write(uploaded_file.getvalue())
        temp_path = tmp_file.name

    try:
        result = process_unit(image_path=temp_path, unit_id=unit_id, work_order=work_order)
        try:
            image_bytes = Path(temp_path).read_bytes()
            saved_image_path = save_image(org_id, unit_id, image_bytes, suffix)
            save_result(org_id, unit_id, saved_image_path, result)
        except Exception as e:
            st.warning(f"Result computed successfully but could not be saved to history: {e}")
    except Exception as e:
        st.error(f"Analysis failed: {e}")
        st.stop()
    finally:
        try:
            os.remove(temp_path)
        except OSError:
            pass

    # 7. Render PrepResult
    st.subheader("Compliance Result")

    if result.overall_status == "PASS":
        st.success(f"Overall Status: PASS \u2014 Unit {result.unit_id}")
    elif result.overall_status == "FAIL":
        st.error(f"Overall Status: FAIL \u2014 Unit {result.unit_id}")
    elif result.overall_status == "UNCERTAIN":
        st.warning(f"Overall Status: UNCERTAIN \u2014 Unit {result.unit_id}")
    elif result.overall_status == "PENDING":
        st.info(f"Overall Status: PENDING \u2014 Unit {result.unit_id}")

    # Manual review distinct warning
    if result.requires_manual_review:
        st.warning(
            "Manual review required: 2 checks need manual review "
            "(fnsku_label_placement and original_barcode_covered)."
        )

    # If PENDING, show reason prominently
    if result.overall_status == "PENDING":
        reason = result.evidence.get("reason", "No reason provided")
        st.info(f"Pending Reason: {reason}")

    # Checks breakdown
    st.write("### Checks Evaluation")
    verdict_icons = {
        "PASS": "\u2705 PASS",
        "FAIL": "\u274c FAIL",
        "UNCERTAIN": "\u26a0\ufe0f UNCERTAIN",
        "PENDING": "\u23f3 PENDING",
    }

    if not result.checks and result.overall_status == "PENDING":
        st.info("No individual checks evaluated because analysis is pending.")
    else:
        for check in result.checks:
            badge = verdict_icons.get(check.verdict, check.verdict)
            with st.expander(f"{check.name} \u2014 {badge}"):
                st.write(f"**Explanation:** {check.explanation}")
                if check.evidence:
                    if isinstance(check.evidence, list):
                        st.write(f"**Evidence:** {'; '.join(check.evidence)}")
                    else:
                        st.write(f"**Evidence:** {check.evidence}")
                else:
                    st.write("**Evidence:** None recorded")

with st.expander("Recent checks for this organization"):
    try:
        history_rows = get_results_for_org(org_id) if org_id and org_id.strip() else []
    except Exception:
        history_rows = []

    if history_rows:
        display_data = [
            {
                "unit_id": r["unit_id"],
                "overall_status": r["overall_status"],
                "requires_manual_review": bool(r["requires_manual_review"]),
                "created_at": r["created_at"],
            }
            for r in history_rows
        ]
        st.dataframe(display_data, use_container_width=True)
    else:
        st.caption("No saved checks yet for this organization.")
