import pytest
import json
from unittest.mock import MagicMock
from core.gemini import (
    configure_gemini, upload_to_gemini, wait_for_files_active,
    analyze_submission, object_to_judges, admin_chat_about_submission
)

def test_configure_gemini_success(mocker):
    # Case where API key is correctly configured
    mocker.patch("core.gemini.get_setting", return_value="test_api_key")
    mock_client_cls = mocker.patch("google.genai.Client")
    
    configure_gemini(1)
    
    mock_client_cls.assert_called_once_with(api_key="test_api_key")

def test_configure_gemini_missing_key(mocker):
    # Case where API key is missing
    mocker.patch("core.gemini.get_setting", return_value=None)
    
    with pytest.raises(ValueError) as excinfo:
        configure_gemini(1)
        
    assert "Gemini API Key has not been set" in str(excinfo.value)

def test_upload_to_gemini(mocker):
    mocker.patch("core.gemini.get_setting", return_value="test_api_key")
    
    # Mock Client instance and files.upload
    mock_client = MagicMock()
    mock_client.files.upload.return_value = "mock_file_obj"
    mocker.patch("core.gemini.get_gemini_client", return_value=mock_client)
    
    res = upload_to_gemini(1, "dummy_path.mp4", mime_type="video/mp4")
    
    assert res == "mock_file_obj"
    mock_client.files.upload.assert_called_once()

def test_wait_for_files_active_success(mocker):
    mocker.patch("core.gemini.get_setting", return_value="test_api_key")
    mocker.patch("time.sleep")  # Mock sleep to accelerate test runs
    
    mock_file_processing = MagicMock()
    mock_file_processing.state.name = "PROCESSING"
    mock_file_active = MagicMock()
    mock_file_active.state.name = "ACTIVE"
    
    mock_client = MagicMock()
    mock_client.files.get.side_effect = [mock_file_processing, mock_file_active]
    mocker.patch("core.gemini.get_gemini_client", return_value=mock_client)
    
    mock_file_input = MagicMock()
    mock_file_input.name = "files/testfile"
    
    wait_for_files_active(1, [mock_file_input])
    assert mock_client.files.get.call_count == 2

def test_wait_for_files_active_failed(mocker):
    mocker.patch("core.gemini.get_setting", return_value="test_api_key")
    mocker.patch("time.sleep")
    
    mock_file_failed = MagicMock()
    mock_file_failed.state.name = "FAILED"
    mock_file_failed.name = "files/testfile"
    
    mock_client = MagicMock()
    mock_client.files.get.return_value = mock_file_failed
    mocker.patch("core.gemini.get_gemini_client", return_value=mock_client)
    
    mock_file_input = MagicMock()
    mock_file_input.name = "files/testfile"
    
    with pytest.raises(ValueError) as excinfo:
        wait_for_files_active(1, [mock_file_input])
        
    assert "File processing failed" in str(excinfo.value)

def test_analyze_submission(mocker):
    mocker.patch("core.gemini.get_setting", return_value="test_api_key")
    
    # Mock criteria & personas settings
    mocker.patch("core.gemini.get_criteria", return_value=[{"name": "Innovation", "weight": 50, "description": "desc"}])
    mocker.patch("core.gemini.get_personas", return_value=[
        {"name": "Alex", "active": True, "prompt": "prompt1"},
        {"name": "David", "active": False, "prompt": "prompt2"} # Inactive judge
    ])
    
    # Mock Client instance and generate_content
    mock_response = MagicMock()
    mock_response.text = '{"scores": {"Innovation": 4.5}, "impact_score": 4.5}'
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response
    mocker.patch("core.gemini.get_gemini_client", return_value=mock_client)
    
    res = analyze_submission(
        hackathon_id=1,
        text_content="print('hello')",
        gemini_media_files=["media_mock"],
        previous_evaluations_json='{"prev": "data"}',
        is_final=True
    )
    
    assert res["scores"]["Innovation"] == 4.5
    assert res["impact_score"] == 4.5
    mock_client.models.generate_content.assert_called_once()

def test_object_to_judges(mocker):
    mocker.patch("core.gemini.get_setting", return_value="test_api_key")
    mocker.patch("core.gemini.get_personas", return_value=[{"name": "Alex", "active": True, "prompt": "prompt1"}])
    
    mock_response = MagicMock()
    mock_response.text = '{"qa_summary_en": "Objection rejected", "judges_responses": []}'
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response
    mocker.patch("core.gemini.get_gemini_client", return_value=mock_client)
    
    res = object_to_judges(
        hackathon_id=1,
        text_content="print('hello')",
        gemini_media_files=None,
        previous_evaluation_json="{}",
        objection_text="I objection"
    )
    
    assert res["qa_summary_en"] == "Objection rejected"

def test_admin_chat_about_submission(mocker):
    mocker.patch("core.gemini.get_setting", return_value="test_api_key")
    
    # Mock genai.Client instance and files.get
    mock_file = MagicMock()
    mock_file.name = "files/test"
    
    mock_response = MagicMock()
    mock_response.text = '{"question_en": "Q?", "question_ja": "Q_ja?", "answer_en": "Ans", "answer_ja": "Ans_ja"}'
    
    mock_client = MagicMock()
    mock_client.files.get.return_value = mock_file
    mock_client.models.generate_content.return_value = mock_response
    mocker.patch("core.gemini.get_gemini_client", return_value=mock_client)
    
    res = admin_chat_about_submission(
        hackathon_id=1,
        source_text="source",
        gemini_file_ids_json='["files/test"]',
        previous_evaluation_json="{}",
        admin_question="what is this?"
    )
    
    assert res["answer_en"] == "Ans"
    assert res["answer_ja"] == "Ans_ja"
