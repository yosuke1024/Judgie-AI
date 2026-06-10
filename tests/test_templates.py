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
