import os
import json

TEMPLATES = {}

# Solve templates directory path relative to this file
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")

if os.path.exists(TEMPLATES_DIR):
    for filename in sorted(os.listdir(TEMPLATES_DIR)):
        if filename.endswith(".json"):
            template_id = os.path.splitext(filename)[0]
            file_path = os.path.join(TEMPLATES_DIR, filename)
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    TEMPLATES[template_id] = json.load(f)
            except Exception as e:
                raise RuntimeError(f"Failed to load template file '{filename}': {e}")

