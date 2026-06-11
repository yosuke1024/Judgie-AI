import os
import json
import pytest
from core.templates import TEMPLATES, TEMPLATES_DIR


def test_templates_load_dynamic():
    """Verify that all JSON template files load correctly and match the required schema."""
    assert len(TEMPLATES) > 0, "No templates loaded from the directory."

    # Validate that each file in the templates directory is loaded
    json_files = [f for f in os.listdir(TEMPLATES_DIR) if f.endswith(".json")]
    assert len(TEMPLATES) == len(json_files), "Mismatch between directory JSON count and TEMPLATES registry."

    for tpl_id, tpl in TEMPLATES.items():
        assert "name" in tpl, f"Template '{tpl_id}' is missing 'name'"
        assert "description" in tpl, f"Template '{tpl_id}' is missing 'description'"
        assert "criteria" in tpl, f"Template '{tpl_id}' is missing 'criteria'"
        assert "personas" in tpl, f"Template '{tpl_id}' is missing 'personas'"

        # Verify criteria structure & weights
        criteria = tpl["criteria"]
        assert isinstance(criteria, list), f"Criteria in '{tpl_id}' must be a list"
        total_weight = 0

        for c in criteria:
            assert "name" in c, f"Criteria in '{tpl_id}' is missing 'name'"
            assert "weight" in c, f"Criteria '{c.get('name')}' in '{tpl_id}' is missing 'weight'"
            assert "description" in c, f"Criteria '{c.get('name')}' in '{tpl_id}' is missing 'description'"
            total_weight += c["weight"]

        assert total_weight == 100, f"Total weight of criteria in '{tpl_id}' must equal 100, got {total_weight}"

        # Verify personas structure
        personas = tpl["personas"]
        assert isinstance(personas, list), f"Personas in '{tpl_id}' must be a list"
        seen_persona_ids = set()

        for p in personas:
            assert "id" in p, f"Persona in '{tpl_id}' is missing 'id'"
            assert p["id"] not in seen_persona_ids, f"Duplicate persona ID '{p['id']}' in '{tpl_id}'"
            seen_persona_ids.add(p["id"])

            assert "name" in p, f"Persona ID '{p.get('id')}' in '{tpl_id}' is missing 'name'"
            assert "role" in p, f"Persona ID '{p.get('id')}' in '{tpl_id}' is missing 'role'"
            assert "avatar" in p, f"Persona ID '{p.get('id')}' in '{tpl_id}' is missing 'avatar'"
            assert "prompt" in p, f"Persona ID '{p.get('id')}' in '{tpl_id}' is missing 'prompt'"
            assert "active" in p, f"Persona ID '{p.get('id')}' in '{tpl_id}' is missing 'active'"
            assert isinstance(p["active"], bool), f"Persona 'active' state in '{tpl_id}' must be a boolean"


def test_is_safe_url(mocker):
    """Ported from test_templates.py. Verifies safe url validation logic."""
    from core.security import is_safe_url

    # Mock DNS resolution to keep test offline and robust.
    mocker.patch('socket.getaddrinfo', return_value=[(None, None, None, None, ('93.184.216.34', 80))])  # public IP
    assert is_safe_url("https://raw.githubusercontent.com/yosuke1024/Judgie-AI/main/template.json") is True
    assert is_safe_url("https://github.com/yosuke1024/Judgie-AI/main/template.json") is True

    # Not allowed domains should fail
    assert is_safe_url("http://example.com/template.json") is False

    # Mocking a private IP resolution for a whitelisted domain
    mocker.patch('socket.getaddrinfo', return_value=[(None, None, None, None, ('192.168.1.1', 80))])
    assert is_safe_url("https://raw.githubusercontent.com/yosuke1024/Judgie-AI/main/template.json") is False

    # Test direct IPs (no DNS lookup needed) - should fail because they are not in the whitelist
    assert is_safe_url("http://127.0.0.1/template.json") is False
    assert is_safe_url("http://10.0.0.1/template.json") is False
    assert is_safe_url("http://169.254.169.254/metadata") is False

    # Test invalid schemes
    assert is_safe_url("ftp://github.com/template.json") is False
    assert is_safe_url("file:///etc/passwd") is False
