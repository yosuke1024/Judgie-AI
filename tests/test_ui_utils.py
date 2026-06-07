import os
import shutil
import pytest
from core.ui_utils import get_avatar_html

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
