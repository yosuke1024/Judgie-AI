"""
Template loader for evaluation templates.
Adapted from core/templates.py (100% reuse, no Streamlit dependency).
"""

import json
import os

TEMPLATES = {}

# Resolve templates directory relative to project root
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
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
