import base64
import os
import streamlit as st

def encode_image_to_base64(file_bytes: bytes, mime_type: str) -> str:
    """
    Encodes image bytes to a Base64 data URL string.
    """
    encoded = base64.b64encode(file_bytes).decode('utf-8')
    return f"data:{mime_type};base64,{encoded}"

def get_avatar_html(persona_name, default_avatar="🧑‍⚖️", size=60):
    """
    Returns an HTML snippet to display the persona's avatar image.
    If default_avatar is a Base64 data URI, it uses it directly.
    Otherwise, looks for a PNG/JPG file in assets/avatars/{persona_name_lowercase}.png.
    Falls back to the DiceBear API if the file doesn't exist.
    """
    # Check if default_avatar is a Base64 data URI
    if isinstance(default_avatar, str) and default_avatar.startswith("data:image/"):
        return f'<img src="{default_avatar}" style="width: {size}px; height: {size}px; border-radius: 50%; object-fit: cover; box-shadow: 0 4px 6px rgba(0,0,0,0.3); vertical-align: middle; margin-right: 10px;">'

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    avatars_dir = os.path.join(base_dir, "assets", "avatars")
    
    avatar_path = None
    for ext in ['.png', '.jpg', '.jpeg']:
        temp_path = os.path.join(avatars_dir, f"{persona_name.lower()}{ext}")
        if os.path.exists(temp_path):
            avatar_path = temp_path
            break
    
    if avatar_path:
        try:
            with open(avatar_path, "rb") as f:
                encoded = base64.b64encode(f.read()).decode()
            mime_type = "image/jpeg" if avatar_path.endswith((".jpg", ".jpeg")) else "image/png"
            img_src = f"data:{mime_type};base64,{encoded}"
            return f'<img src="{img_src}" style="width: {size}px; height: {size}px; border-radius: 50%; object-fit: cover; box-shadow: 0 4px 6px rgba(0,0,0,0.3); vertical-align: middle; margin-right: 10px;">'
        except Exception:
            pass
            
    # Fallback to high-quality external avatar API (DiceBear Micah style)
    # Using the persona name as a seed generates a consistent, beautiful avatar
    seed_name = persona_name.replace(" ", "")
    fallback_url = f"https://api.dicebear.com/7.x/micah/svg?seed={seed_name}&backgroundColor=transparent"
    
    return f'<img src="{fallback_url}" style="width: {size}px; height: {size}px; border-radius: 50%; object-fit: cover; box-shadow: 0 4px 6px rgba(0,0,0,0.3); vertical-align: middle; margin-right: 10px;">'

