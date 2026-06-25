import logging

from app.core.llm import get_llm_provider

# Maintained for backward compatibility and test mock compatibility
from app.models.db import (
    get_ai_response_languages,  # noqa: F401
    get_criteria,  # noqa: F401
    get_personas,  # noqa: F401
    get_setting,
    normalize_lang_to_key,  # noqa: F401
)

logger = logging.getLogger(__name__)


def get_gemini_client(api_key_override=None):
    """
    Returns an initialized Gemini client using the database or key override.
    Maintained for backward compatibility and model diagnostics.
    """
    provider = get_llm_provider("gemini")
    return provider._get_client(api_key_override=api_key_override)


def list_available_llm_models(provider_name: str, api_key_override=None):
    """
    Fetches available models for the specified provider.
    """
    provider = get_llm_provider(provider_name)
    return provider.list_models(api_key_override=api_key_override)


def list_available_gemini_models(api_key_override=None):
    # Maintained for backward compatibility and test mock compatibility
    return list_available_llm_models("gemini", api_key_override)


def upload_to_gemini(file_path, mime_type=None):
    """Uploads the given file to the active provider (usually Gemini)."""
    provider = get_llm_provider()
    return provider.upload_file(file_path, mime_type)


def wait_for_files_active(files):
    """Waits for the given files to be active in the active provider (usually Gemini)."""
    provider = get_llm_provider()
    provider.wait_for_files(files)


def analyze_submission(text_content, gemini_media_files=None, previous_evaluations_json=None, is_final=False):
    """Calls the active LLM provider to evaluate the submission and returns structured JSON."""
    provider = get_llm_provider()

    # Resolve provider-specific model setting, e.g. openai_model or anthropic_model, fallback to gemini_model
    current_provider = get_setting("llm_provider") or "gemini"
    model_setting_key = f"{current_provider.lower()}_model"
    model_name = get_setting(model_setting_key) or get_setting("gemini_model")

    return provider.analyze_submission(
        model_name=model_name,
        text_content=text_content,
        media_files=gemini_media_files,
        previous_evaluations_json=previous_evaluations_json,
        is_final=is_final,
    )


def object_to_judges(text_content, gemini_media_files, previous_evaluation_json, chat_history_list):
    """Handles Q&A debate turn with the team using the active LLM provider."""
    provider = get_llm_provider()

    current_provider = get_setting("llm_provider") or "gemini"
    model_setting_key = f"{current_provider.lower()}_model"
    model_name = get_setting(model_setting_key) or get_setting("gemini_model")

    return provider.object_to_judges(
        model_name=model_name,
        text_content=text_content,
        media_files=gemini_media_files,
        previous_evaluation_json=previous_evaluation_json,
        chat_history_list=chat_history_list,
    )


def admin_chat_about_submission(source_text, gemini_file_ids_json, previous_evaluation_json, admin_question):
    """Allows Hackathon Admin to ask a specific question using the active LLM provider."""
    provider = get_llm_provider()

    current_provider = get_setting("llm_provider") or "gemini"
    model_setting_key = f"{current_provider.lower()}_model"
    model_name = get_setting(model_setting_key) or get_setting("gemini_model")

    return provider.admin_chat(
        model_name=model_name,
        source_text=source_text,
        file_ids_json=gemini_file_ids_json,
        previous_evaluation_json=previous_evaluation_json,
        admin_question=admin_question,
    )


def translate_text(text, target_languages):
    """Translates the given text using the active LLM provider."""
    provider = get_llm_provider()
    return provider.translate(text, target_languages)
