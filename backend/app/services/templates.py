"""
Template loader for evaluation templates.
Adapted from core/templates.py (100% reuse, no Streamlit dependency).
"""

import json
import os

TEMPLATES = {}

# Resolve templates directory dynamically (works for both local dev and Docker container)
_HERE = os.path.abspath(__file__)
_DIR = _HERE
TEMPLATES_DIR = None
for _ in range(5):
    _DIR = os.path.dirname(_DIR)
    _potential = os.path.join(_DIR, "templates")
    if os.path.exists(_potential) and os.path.isdir(_potential):
        TEMPLATES_DIR = _potential
        break

if not TEMPLATES_DIR:
    # Fallback to local dev path structure
    _BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(_HERE)))
    _PROJECT_ROOT = os.path.dirname(_BACKEND_DIR)
    TEMPLATES_DIR = os.path.join(_PROJECT_ROOT, "templates")

if os.path.exists(TEMPLATES_DIR):
    for filename in sorted(os.listdir(TEMPLATES_DIR)):
        if filename.endswith(".json") and not filename.endswith(".sample.json"):
            template_id = os.path.splitext(filename)[0]
            file_path = os.path.join(TEMPLATES_DIR, filename)
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    TEMPLATES[template_id] = json.load(f)
            except Exception as e:
                raise RuntimeError(f"Failed to load template file '{filename}': {e}")
