import io
import zipfile

from core.file_handler import extract_text_from_zip


def create_mock_zip(files_dict):
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'a', zipfile.ZIP_DEFLATED, False) as zip_file:
        for file_name, data in files_dict.items():
            zip_file.writestr(file_name, data)
    zip_buffer.seek(0)
    return zip_buffer

def test_extract_text_from_zip_success():
    files = {
        "src/main.py": "print('hello')",
        "src/index.js": "console.log('test')",
        "README.md": "# Project Title"
    }
    zip_data = create_mock_zip(files)

    result = extract_text_from_zip(zip_data)

    assert "--- FILE: src/main.py ---" in result
    assert "print('hello')" in result
    assert "--- FILE: src/index.js ---" in result
    assert "console.log('test')" in result
    assert "--- FILE: README.md ---" in result
    assert "# Project Title" in result

def test_extract_text_from_zip_ignore_patterns():
    files = {
        "src/main.py": "print('hello')",
        "node_modules/package/index.js": "module.exports = {}",
        ".git/config": "[core]",
        "package-lock.json": "{}",
        "image.png": "binary_data_here"  # extension mismatch
    }
    zip_data = create_mock_zip(files)

    result = extract_text_from_zip(zip_data)

    assert "--- FILE: src/main.py ---" in result
    assert "node_modules" not in result
    assert ".git/config" not in result
    assert "package-lock.json" not in result
    assert "image.png" not in result

def test_extract_text_from_zip_decoding_error():
    # Python file containing binary data that cannot be decoded as UTF-8
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'a', zipfile.ZIP_DEFLATED, False) as zip_file:
        zip_file.writestr("binary.py", b'\x80\x81\x82\xff')
        zip_file.writestr("valid.py", "print('valid')")
    zip_buffer.seek(0)

    result = extract_text_from_zip(zip_buffer)

    # binary.py is ignored due to decoding errors, but valid.py is processed normally
    assert "valid.py" in result
    assert "print('valid')" in result
    assert "binary.py" not in result

def test_extract_text_from_zip_truncation():
    # Verify truncation warning occurs when files are too large
    # MAX_CHARS = 800000, so we create a file exceeding this limit.
    # Since the check is performed at the beginning of the loop iteration,
    # we name files alphabetically so the large file is processed first,
    # followed by the dummy file which triggers the break.
    large_content = "a" * 800010
    files = {
        "a_large.py": large_content,
        "b_dummy.py": "print('hello')"
    }
    zip_data = create_mock_zip(files)

    result = extract_text_from_zip(zip_data)

    assert "[SYSTEM WARNING: Codebase too large. Truncated to fit within AI limits.]" in result

def test_extract_text_from_zip_empty_or_none():
    assert extract_text_from_zip(None) == ""

    # ZIP archive containing only directory entries
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'a', zipfile.ZIP_DEFLATED, False) as zip_file:
        zip_file.writestr("empty_dir/", "")
    zip_buffer.seek(0)

    assert extract_text_from_zip(zip_buffer) == ""
