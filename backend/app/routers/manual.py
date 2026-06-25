"""
Manual router: retrieves user manuals (ja/en) from the docs directory.
"""

import os

from fastapi import APIRouter, Depends, HTTPException

from app.auth.deps import CurrentUser, require_role

router = APIRouter(prefix="/api/manual", tags=["manual"])


@router.get("")
def get_manual(
    lang: str = "ja",
    user: CurrentUser = Depends(require_role("admin", "observer", "team")),
):
    """Retrieve user manual content based on language."""
    is_ja = lang.lower().startswith("ja")
    filename = "user_manual_ja.md" if is_ja else "user_manual_en.md"

    # Define paths to search for the manual file
    possible_paths = [
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "docs", filename)),
        os.path.abspath(os.path.join(os.getcwd(), "docs", filename)),
        os.path.abspath(os.path.join(os.getcwd(), "..", "docs", filename)),
        f"/app/docs/{filename}",
    ]

    content_path = None
    for p in possible_paths:
        if os.path.exists(p):
            content_path = p
            break

    if not content_path:
        raise HTTPException(status_code=404, detail=f"Manual file '{filename}' not found.")

    try:
        with open(content_path, "r", encoding="utf-8") as f:
            content = f.read()
        return {"content": content}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read manual file: {str(e)}")
