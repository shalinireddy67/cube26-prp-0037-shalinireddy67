"""
Tests for src/storage.py.
Verifies SQLite storage, image persistence, and strict organization-level isolation.
"""

import json
from pathlib import Path
import pytest

from src.schemas import ComplianceCheck, PrepResult
from src.storage import (
    _sanitize_id,
    add_override,
    get_full_history,
    get_image_bytes,
    get_image_path,
    get_overrides_for_result,
    get_result_by_id,
    get_results_for_org,
    init_db,
    save_image,
    save_result,
)


@pytest.fixture
def temp_storage(tmp_path):
    """Provides isolated temporary database and images directory."""
    db_file = tmp_path / "test_prep_manager.db"
    images_dir = tmp_path / "images"
    return db_file, images_dir


def test_sanitize_id_valid():
    assert _sanitize_id("org_demo_alpha") == "org_demo_alpha"
    assert _sanitize_id("  UNIT-100  ") == "UNIT-100"
    assert _sanitize_id("valid-name_123") == "valid-name_123"


def test_sanitize_id_strips_separators():
    assert _sanitize_id("org/alpha") == "orgalpha"
    assert _sanitize_id("unit\\01") == "unit01"
    assert _sanitize_id("box..unit") == "boxunit"


def test_sanitize_id_rejects_empty_and_invalid():
    with pytest.raises(ValueError):
        _sanitize_id("")

    with pytest.raises(ValueError):
        _sanitize_id("   ")

    with pytest.raises(ValueError):
        _sanitize_id("..")

    with pytest.raises(ValueError):
        _sanitize_id("../../")

    with pytest.raises(ValueError):
        _sanitize_id("\\\\")

    with pytest.raises(ValueError):
        _sanitize_id("/")

    with pytest.raises(ValueError):
        _sanitize_id(None)


def test_init_db_idempotent(temp_storage):
    db_file, _ = temp_storage
    init_db(db_file)
    assert db_file.exists()

    # Calling again should not raise error
    init_db(db_file)


def test_save_and_retrieve_result(temp_storage):
    db_file, _ = temp_storage

    dummy_result = PrepResult(
        unit_id="UNIT-001",
        checks=[
            ComplianceCheck(
                name="polybag_present_sealed",
                verdict="PASS",
                explanation="Bag is sealed.",
                evidence=["Continuous heat seal visible."],
            ),
            ComplianceCheck(
                name="suffocation_warning",
                verdict="PASS",
                explanation="Warning legible.",
                evidence=["Printed suffocation warning."],
            ),
        ],
        overall_status="PASS",
        requires_manual_review=False,
    )

    row_id = save_result(
        org_id="org_demo_alpha",
        unit_id="UNIT-001",
        image_path="data/images/org_demo_alpha/UNIT-001.jpg",
        result=dummy_result,
        db_path=db_file,
    )

    assert row_id > 0

    results = get_results_for_org("org_demo_alpha", db_path=db_file)
    assert len(results) == 1
    record = results[0]

    assert record["id"] == row_id
    assert record["org_id"] == "org_demo_alpha"
    assert record["unit_id"] == "UNIT-001"
    assert record["overall_status"] == "PASS"
    assert record["requires_manual_review"] == 0
    assert record["image_path"] == "data/images/org_demo_alpha/UNIT-001.jpg"

    checks = json.loads(record["checks_json"])
    assert len(checks) == 2
    assert checks[0]["name"] == "polybag_present_sealed"
    assert checks[0]["verdict"] == "PASS"

    single_record = get_result_by_id("org_demo_alpha", row_id, db_path=db_file)
    assert single_record is not None
    assert single_record["unit_id"] == "UNIT-001"


def test_strict_organization_isolation(temp_storage):
    """
    R1 Engineering Rule: Row-level tenancy isolation.
    org_demo_bravo must see 0 rows and cannot access alpha's record even with guessed id.
    """
    db_file, _ = temp_storage

    dummy_result = PrepResult(
        unit_id="ALPHA-SECRET-UNIT",
        checks=[],
        overall_status="PASS",
        requires_manual_review=True,
    )

    alpha_row_id = save_result(
        org_id="org_demo_alpha",
        unit_id="ALPHA-SECRET-UNIT",
        image_path="data/images/org_demo_alpha/secret.jpg",
        result=dummy_result,
        db_path=db_file,
    )

    # 1. Bravo queries for its results -> must be empty
    bravo_results = get_results_for_org("org_demo_bravo", db_path=db_file)
    assert bravo_results == []

    # 2. Bravo attempts to fetch alpha's record id -> must be structurally unreachable (None)
    bravo_fetch = get_result_by_id("org_demo_bravo", alpha_row_id, db_path=db_file)
    assert bravo_fetch is None

    # 3. Path traversal attack via org_id parameter
    traversal_fetch = get_result_by_id("../org_demo_alpha", alpha_row_id, db_path=db_file)
    # Sanitization strips '../', turning it into 'org_demo_alpha' safely or rejecting
    assert traversal_fetch is not None
    assert traversal_fetch["org_id"] == "org_demo_alpha"


def test_image_storage_isolation(temp_storage):
    """
    Tests saving images under data/images/{org_id}/ and ensuring cross-tenant isolation.
    """
    _, images_dir = temp_storage

    alpha_bytes = b"\xff\xd8\xff\xe0ALPHA_IMAGE_DATA"
    saved_path = save_image(
        org_id="org_demo_alpha",
        unit_id="UNIT-ALPHA-01",
        image_bytes=alpha_bytes,
        filename="package.jpg",
        images_root=images_dir,
    )

    assert Path(saved_path).exists()
    assert "org_demo_alpha" in saved_path

    # Alpha can read its own image
    data = get_image_bytes("org_demo_alpha", "package.jpg", images_root=images_dir)
    assert data == alpha_bytes

    # Bravo cannot access alpha's image by name
    bravo_data = get_image_bytes("org_demo_bravo", "package.jpg", images_root=images_dir)
    assert bravo_data is None

    # Bravo cannot access alpha's image via path traversal
    traversal_data = get_image_bytes("org_demo_bravo", "../org_demo_alpha/package.jpg", images_root=images_dir)
    assert traversal_data is None

    # Path traversal in save_image org_id must be rejected
    with pytest.raises(ValueError):
        save_image("../../", "UNIT-01", b"data", images_root=images_dir)


def test_override_a_save_and_add_override(temp_storage):
    db_file, _ = temp_storage
    dummy_result = PrepResult(
        unit_id="UNIT-UNCERTAIN-01",
        checks=[],
        overall_status="UNCERTAIN",
        requires_manual_review=True,
    )
    result_id = save_result(
        org_id="org_demo_alpha",
        unit_id="UNIT-UNCERTAIN-01",
        image_path="data/images/org_demo_alpha/uncertain.jpg",
        result=dummy_result,
        db_path=db_file,
    )
    override_id = add_override(
        org_id="org_demo_alpha",
        result_id=result_id,
        original_verdict="UNCERTAIN",
        new_verdict="PASS",
        reason="Operator visually confirmed seal in person",
        operator_id="op_001",
        db_path=db_file,
    )
    assert isinstance(override_id, int)
    assert override_id > 0
    print("\na) PASS: Save result and add override succeeded, returned int id.")


def test_override_b_get_full_history(temp_storage):
    db_file, _ = temp_storage
    dummy_result = PrepResult(
        unit_id="UNIT-UNCERTAIN-01",
        checks=[],
        overall_status="UNCERTAIN",
        requires_manual_review=True,
    )
    result_id = save_result(
        org_id="org_demo_alpha",
        unit_id="UNIT-UNCERTAIN-01",
        image_path="data/images/org_demo_alpha/uncertain.jpg",
        result=dummy_result,
        db_path=db_file,
    )
    add_override(
        org_id="org_demo_alpha",
        result_id=result_id,
        original_verdict="UNCERTAIN",
        new_verdict="PASS",
        reason="Operator visually confirmed seal in person",
        operator_id="op_001",
        db_path=db_file,
    )
    history = get_full_history("org_demo_alpha", result_id, db_path=db_file)
    assert history is not None
    assert history["result"]["overall_status"] == "UNCERTAIN"
    assert len(history["overrides"]) == 1
    assert history["overrides"][0]["new_verdict"] == "PASS"
    assert history["overrides"][0]["reason"] == "Operator visually confirmed seal in person"
    print("\nb) PASS: get_full_history retained original verdict and contained 1 override entry with correct fields.")


def test_override_c_cross_tenant_override_raises_valueerror(temp_storage):
    db_file, _ = temp_storage
    dummy_result = PrepResult(
        unit_id="UNIT-UNCERTAIN-01",
        checks=[],
        overall_status="UNCERTAIN",
        requires_manual_review=True,
    )
    alpha_result_id = save_result(
        org_id="org_demo_alpha",
        unit_id="UNIT-UNCERTAIN-01",
        image_path="data/images/org_demo_alpha/uncertain.jpg",
        result=dummy_result,
        db_path=db_file,
    )
    with pytest.raises(ValueError, match="Result not found for this organization"):
        add_override(
            org_id="org_demo_bravo",
            result_id=alpha_result_id,
            original_verdict="UNCERTAIN",
            new_verdict="PASS",
            reason="Operator visually confirmed seal in person",
            operator_id="op_001",
            db_path=db_file,
        )
    print("\nc) PASS: add_override with mismatched org_id raised ValueError.")


def test_override_d_cross_tenant_get_overrides_returns_empty(temp_storage):
    db_file, _ = temp_storage
    dummy_result = PrepResult(
        unit_id="UNIT-UNCERTAIN-01",
        checks=[],
        overall_status="UNCERTAIN",
        requires_manual_review=True,
    )
    alpha_result_id = save_result(
        org_id="org_demo_alpha",
        unit_id="UNIT-UNCERTAIN-01",
        image_path="data/images/org_demo_alpha/uncertain.jpg",
        result=dummy_result,
        db_path=db_file,
    )
    add_override(
        org_id="org_demo_alpha",
        result_id=alpha_result_id,
        original_verdict="UNCERTAIN",
        new_verdict="PASS",
        reason="Operator visually confirmed seal in person",
        operator_id="op_001",
        db_path=db_file,
    )
    bravo_overrides = get_overrides_for_result("org_demo_bravo", alpha_result_id, db_path=db_file)
    assert bravo_overrides == []
    print("\nd) PASS: get_overrides_for_result for wrong org returned empty list.")


def test_tenant_isolation_comprehensive_guarantees(temp_storage):
    """
    Demonstrates actual multi-tenant isolation guarantees provided by the current
    parameterized SQLite and path-sanitizing storage implementation:
    1. org_demo_alpha can retrieve its own rows.
    2. org_demo_bravo cannot retrieve alpha rows.
    3. org_demo_bravo cannot retrieve an alpha result by ID.
    4. org_demo_bravo cannot retrieve alpha image bytes by guessing the filename/path.
    5. Path traversal attempts are rejected.
    """
    db_file, images_dir = temp_storage

    # Setup Alpha result and image
    alpha_result = PrepResult(
        unit_id="ALPHA-UNIT-100",
        checks=[],
        overall_status="PASS",
        requires_manual_review=False,
    )
    alpha_img_bytes = b"ALPHA_IMAGE_CONTENT"
    saved_img = save_image(
        org_id="org_demo_alpha",
        unit_id="ALPHA-UNIT-100",
        image_bytes=alpha_img_bytes,
        filename="alpha_capture.jpg",
        images_root=images_dir,
    )
    alpha_id = save_result(
        org_id="org_demo_alpha",
        unit_id="ALPHA-UNIT-100",
        image_path=saved_img,
        result=alpha_result,
        db_path=db_file,
    )

    # 1. org_demo_alpha can retrieve its own rows
    alpha_rows = get_results_for_org("org_demo_alpha", db_path=db_file)
    assert len(alpha_rows) == 1
    assert alpha_rows[0]["id"] == alpha_id
    assert alpha_rows[0]["unit_id"] == "ALPHA-UNIT-100"

    alpha_read_bytes = get_image_bytes("org_demo_alpha", "alpha_capture.jpg", images_root=images_dir)
    assert alpha_read_bytes == alpha_img_bytes

    # 2. org_demo_bravo cannot retrieve alpha rows
    bravo_rows = get_results_for_org("org_demo_bravo", db_path=db_file)
    assert bravo_rows == []

    # 3. org_demo_bravo cannot retrieve an alpha result by ID
    bravo_result_by_id = get_result_by_id("org_demo_bravo", alpha_id, db_path=db_file)
    assert bravo_result_by_id is None

    # 4. org_demo_bravo cannot retrieve alpha image bytes by guessing filename/path
    bravo_img_guess = get_image_bytes("org_demo_bravo", "alpha_capture.jpg", images_root=images_dir)
    assert bravo_img_guess is None

    # 5. Path traversal attempts are rejected
    traversal_img = get_image_bytes("org_demo_bravo", "../org_demo_alpha/alpha_capture.jpg", images_root=images_dir)
    assert traversal_img is None

    traversal_path = get_image_path("org_demo_bravo", "../../etc/passwd", images_root=images_dir)
    assert traversal_path is None

    with pytest.raises(ValueError):
        save_image("../../", "UNIT-01", b"data", images_root=images_dir)


def test_server_api_check_tenant_and_path_security(monkeypatch):
    """
    Issue 1 & Issue 2 Security Verification:
    1. Client-supplied org_id ("org_demo_bravo") is ignored; result is stored under TENANT_ORG_ID.
    2. Malicious client-supplied image_path ("../.env", "data/prep_manager.db") cannot cause
       arbitrary file access; server strictly evaluates fixed demo fixture for non-upload requests.
    """
    import http.client
    import threading
    import uuid
    from http.server import ThreadingHTTPServer
    from server import PrepManagerRequestHandler

    monkeypatch.setenv("TENANT_ORG_ID", "org_demo_alpha")
    monkeypatch.setenv("VISION_PROVIDER", "mock")

    unique_unit_id = f"TEST-TENANT-SPOOF-{uuid.uuid4().hex[:8]}"

    server = ThreadingHTTPServer(("127.0.0.1", 0), PrepManagerRequestHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        conn = http.client.HTTPConnection("127.0.0.1", port)

        # Send request with spoofed org_id and malicious traversal image_path
        payload = {
            "unit_id": unique_unit_id,
            "org_id": "org_demo_bravo",
            "image_path": "../.env",
        }
        body = json.dumps(payload).encode("utf-8")
        conn.request("POST", "/api/check", body=body, headers={"Content-Type": "application/json"})
        resp = conn.getresponse()
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))

        assert data["unit_id"] == unique_unit_id

        # Verify: Result was NOT stored under org_demo_bravo
        bravo_records = get_results_for_org("org_demo_bravo")
        assert not any(r["unit_id"] == unique_unit_id for r in bravo_records)

        # Verify: Result WAS stored under configured server-side tenant (org_demo_alpha)
        alpha_records = get_results_for_org("org_demo_alpha")
        stored_alpha = [r for r in alpha_records if r["unit_id"] == unique_unit_id]
        assert len(stored_alpha) == 1

        # Verify: Stored image path is the fixed demo fixture, NOT ../.env
        assert stored_alpha[0]["image_path"] == "fixtures/prep/a.jpg"
    finally:
        server.shutdown()
        server.server_close()
