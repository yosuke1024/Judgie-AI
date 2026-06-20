import zipfile


def extract_text_from_zip(uploaded_zip):
    """
    Extracts text from code files within an uploaded ZIP archive.
    Ignores binary files and images to optimize Gemini token usage.
    """
    if not uploaded_zip:
        return ""

    allowed_extensions = (".py", ".js", ".ts", ".jsx", ".tsx", ".html", ".css", ".md", ".txt", ".json", ".yml", ".yaml")
    ignore_dirs = (
        "node_modules/",
        ".git/",
        "venv/",
        ".venv/",
        "env/",
        ".next/",
        "dist/",
        "build/",
        "out/",
        ".expo/",
        "android/",
        "ios/",
    )
    ignore_files = ("package-lock.json", "yarn.lock", "pnpm-lock.yaml")

    text_content = ""
    MAX_CHARS = 800000  # Approx 200,000 tokens to stay well within the 250k Free Tier limit

    with zipfile.ZipFile(uploaded_zip, "r") as z:
        for filename in z.namelist():
            if len(text_content) > MAX_CHARS:
                text_content += "\n\n[SYSTEM WARNING: Codebase too large. Truncated to fit within AI limits.]"
                break

            if filename.endswith("/"):
                continue

            # Check if file is in an ignored directory or is an ignored file
            if any(ign in filename for ign in ignore_dirs):
                continue
            if any(filename.endswith(ign) for ign in ignore_files):
                continue

            if filename.endswith(allowed_extensions):
                try:
                    content = z.read(filename).decode("utf-8")
                    text_content += f"\n\n--- FILE: {filename} ---\n{content}"
                except Exception:
                    # Ignore decode errors for binary files masquerading as text
                    pass

    return text_content
