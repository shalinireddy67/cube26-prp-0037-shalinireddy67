"""
Prep Manager Storage Module.

Provides persistent storage for PrepResult records (SQLite) and uploaded images,
enforcing strict multi-tenant organization-level isolation.
"""

from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Any, List, Optional

from src.schemas import PrepResult

DB_PATH = Path("data/prep_manager.db")
IMAGES_ROOT = Path("data/images")


def _sanitize_id(value: str) -> str:
    """
    Strips and rejects any of '/', '\\', '..', and whitespace-only values.
    Raises ValueError on an empty, non-string, or fully-invalid result.
    Used for both org_id and unit_id everywhere they touch a filesystem or database boundary.
    """
    if not isinstance(value, str):
        raise ValueError("Identifier must be a string")

    val = value.strip()
    if not val:
        raise ValueError("Identifier cannot be empty or whitespace-only")

    # Strip any occurrences of '..', '/', '\'
    prev = None
    while prev != val:
        prev = val
        val = val.replace("..", "").replace("/", "").replace("\\", "").strip()

    if not val:
        raise ValueError(f"Identifier '{value}' is empty or fully-invalid")

    return val


def init_db(db_path: Path | str = DB_PATH) -> None:
    """
    Creates the SQLite file and the `results` table with an index on org_id if not present.
    Safe to call repeatedly (idempotent).
    """
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                org_id TEXT NOT NULL,
                unit_id TEXT NOT NULL,
                image_path TEXT,
                overall_status TEXT NOT NULL,
                requires_manual_review INTEGER NOT NULL,
                checks_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_results_org_id ON results (org_id);
        """)
        conn.commit()


def save_result(
    org_id: str,
    unit_id: str,
    image_path: str,
    result: PrepResult,
    db_path: Path | str = DB_PATH,
) -> int:
    """
    Saves a PrepResult for a specific org_id into the SQLite database.
    Serializes result.checks via dataclasses.asdict into JSON for checks_json.
    Calls init_db() to ensure the database schema exists, then inserts the row.
    Returns the newly inserted row id.
    """
    clean_org = _sanitize_id(org_id)
    clean_unit = _sanitize_id(unit_id)

    init_db(db_path)

    checks_data: List[dict] = []
    if isinstance(result.checks, list):
        for c in result.checks:
            if hasattr(c, "__dataclass_fields__"):
                checks_data.append(asdict(c))
            elif isinstance(c, dict):
                checks_data.append(c)

    checks_json = json.dumps(checks_data)
    requires_manual_review_int = 1 if result.requires_manual_review else 0
    created_at = datetime.now(timezone.utc).isoformat()

    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO results (
                org_id, unit_id, image_path, overall_status,
                requires_manual_review, checks_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                clean_org,
                clean_unit,
                str(image_path),
                result.overall_status,
                requires_manual_review_int,
                checks_json,
                created_at,
            ),
        )
        conn.commit()
        return cursor.lastrowid


def get_results_for_org(org_id: str, db_path: Path | str = DB_PATH) -> list[dict]:
    """
    Retrieves all results belonging to the given org_id using a parameterized query.
    Returns only rows matching that exact org_id.
    """
    clean_org = _sanitize_id(org_id)
    init_db(db_path)

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM results WHERE org_id = ?", (clean_org,))
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


def get_result_by_id(org_id: str, record_id: int, db_path: Path | str = DB_PATH) -> dict | None:
    """
    Retrieves a result by its id and org_id using bound parameters in the same query.
    A record belonging to another organization is structurally unreachable.
    """
    clean_org = _sanitize_id(org_id)
    init_db(db_path)

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM results WHERE id = ? AND org_id = ?",
            (record_id, clean_org),
        )
        row = cursor.fetchone()
        return dict(row) if row else None


def save_image(
    org_id: str,
    unit_id: str,
    image_bytes: bytes,
    filename: Optional[str] = None,
    images_root: Path | str = IMAGES_ROOT,
) -> str:
    """
    Stores an uploaded image in data/images/{org_id}/ with strict path sanitization.
    Prevents path traversal and returns the path to the saved file as a string.
    """
    clean_org = _sanitize_id(org_id)
    clean_unit = _sanitize_id(unit_id)

    root_path = Path(images_root)
    org_dir = (root_path / clean_org).resolve()
    root_resolved = root_path.resolve()

    if not org_dir.is_relative_to(root_resolved) or org_dir == root_resolved:
        raise ValueError(f"Path traversal detected in org_id: {org_id}")

    org_dir.mkdir(parents=True, exist_ok=True)

    if filename:
        clean_filename = _sanitize_id(Path(filename).name)
    else:
        clean_filename = f"{clean_unit}.jpg"

    dest_path = (org_dir / clean_filename).resolve()
    if not dest_path.is_relative_to(org_dir):
        raise ValueError(f"Path traversal detected in filename: {filename}")

    dest_path.write_bytes(image_bytes)
    return str(dest_path)


def get_image_path(
    org_id: str,
    filename: str,
    images_root: Path | str = IMAGES_ROOT,
) -> Optional[Path]:
    """
    Returns the resolved Path for an image strictly within data/images/{org_id}/.
    Returns None if the image does not exist or if path traversal is attempted.
    """
    try:
        clean_org = _sanitize_id(org_id)
        clean_filename = _sanitize_id(Path(filename).name)
    except ValueError:
        return None

    root_path = Path(images_root)
    org_dir = (root_path / clean_org).resolve()
    root_resolved = root_path.resolve()

    if not org_dir.is_relative_to(root_resolved) or org_dir == root_resolved:
        return None

    dest_path = (org_dir / clean_filename).resolve()
    if not dest_path.is_relative_to(org_dir):
        return None

    if dest_path.is_file():
        return dest_path
    return None


def get_image_bytes(
    org_id: str,
    filename: str,
    images_root: Path | str = IMAGES_ROOT,
) -> Optional[bytes]:
    """
    Reads image bytes strictly from data/images/{org_id}/.
    Returns None if the file is not found or access across org boundaries is attempted.
    """
    path = get_image_path(org_id, filename, images_root=images_root)
    if path is not None:
        return path.read_bytes()
    return None
