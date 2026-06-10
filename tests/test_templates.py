from core.templates import TEMPLATES


def test_templates_load():
    assert "hackathon" in TEMPLATES
    assert "startup_pitch" in TEMPLATES
    assert "hiring" in TEMPLATES
    assert "architecture" in TEMPLATES

    for tpl_id, tpl in TEMPLATES.items():
        assert "name" in tpl
        assert "description" in tpl
        assert "re_evaluation_context_mode" in tpl
        assert "max_qa_turns" in tpl
        assert "criteria" in tpl
        assert "personas" in tpl

        # Verify criteria structure
        for c in tpl["criteria"]:
            assert "name" in c
            assert "weight" in c
            assert "description" in c

        # Verify personas structure
        for p in tpl["personas"]:
            assert "id" in p
            assert "name" in p
            assert "avatar" in p
            assert "prompt" in p


def test_is_safe_url(mocker):
    from core.security import is_safe_url


    # Mock DNS resolution to keep test offline and robust.
    # We mock socket.getaddrinfo to simulate various IP resolutions.
    mocker.patch('socket.getaddrinfo', return_value=[(None, None, None, None, ('93.184.216.34', 80))])  # example.com IP
    assert is_safe_url("http://example.com/template.json") is True

    # Mocking a private IP resolution
    mocker.patch('socket.getaddrinfo', return_value=[(None, None, None, None, ('192.168.1.1', 80))])
    assert is_safe_url("http://example.com/template.json") is False

    # Test direct IPs (no DNS lookup needed)
    assert is_safe_url("http://127.0.0.1/template.json") is False
    assert is_safe_url("http://10.0.0.1/template.json") is False
    assert is_safe_url("http://169.254.169.254/metadata") is False

    # Test invalid schemes
    assert is_safe_url("ftp://example.com/template.json") is False
    assert is_safe_url("file:///etc/passwd") is False
