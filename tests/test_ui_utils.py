import os

import pytest

from core.ui_utils import encode_image_to_base64, get_avatar_html


@pytest.fixture
def setup_temp_avatar():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    avatars_dir = os.path.join(base_dir, "assets", "avatars")

    # Create temp directory
    os.makedirs(avatars_dir, exist_ok=True)

    test_avatar_path = os.path.join(avatars_dir, "test judge.png")
    with open(test_avatar_path, "wb") as f:
        f.write(b"fake_png_image_data")

    yield "Test Judge", test_avatar_path

    # Cleanup files
    if os.path.exists(test_avatar_path):
        os.remove(test_avatar_path)

    # Clean up empty parent directories
    try:
        os.rmdir(avatars_dir)
        os.rmdir(os.path.join(base_dir, "assets"))
    except OSError:
        pass # Do not delete if other files exist inside the directory

def test_get_avatar_html_with_file(setup_temp_avatar):
    persona_name, _ = setup_temp_avatar

    html = get_avatar_html(persona_name, size=50)

    # Verify that the generated HTML contains Base64 encoded PNG image data
    assert "data:image/png;base64," in html
    assert "width: 50px" in html

def test_get_avatar_html_fallback():
    # Test fallback with a non-existent persona name
    html = get_avatar_html("Non Existent Judge", default_avatar="🧑‍⚖️", size=60)

    # Verify fallback to DiceBear API url
    assert "https://api.dicebear.com/7.x/micah/svg?seed=NonExistentJudge" in html
    assert "width: 60px" in html

def test_get_avatar_html_with_base64_data_uri():
    # Test when default_avatar is a Base64 data URI
    base64_avatar = "data:image/png;base64,ZmFrZV9wbmc="
    html = get_avatar_html("Test Judge", default_avatar=base64_avatar, size=45)

    # Verify that it uses the Base64 data URI directly
    assert f'src="{base64_avatar}"' in html
    assert "width: 45px" in html

def test_encode_image_to_base64():
    # Test encoding helper function
    fake_data = b"hello world"
    mime = "image/png"
    result = encode_image_to_base64(fake_data, mime)

    assert result == "data:image/png;base64,aGVsbG8gd29ybGQ="

