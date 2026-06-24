from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class BaseLLMProvider(ABC):
    @property
    @abstractmethod
    def supports_video(self) -> bool:
        """Return True if the provider natively supports large video input files."""
        pass

    @abstractmethod
    def list_models(self, api_key_override: Optional[str] = None) -> List[str]:
        """Return list of supported models available for this provider."""
        pass

    @abstractmethod
    def upload_file(self, file_path: str, mime_type: Optional[str] = None) -> Any:
        """Upload or process media files. Return file handle/metadata."""
        pass

    @abstractmethod
    def wait_for_files(self, files: List[Any]) -> None:
        """Wait for processed media files to become active (e.g. Gemini File API)."""
        pass

    @abstractmethod
    def analyze_submission(
        self,
        model_name: str,
        text_content: str,
        media_files: Optional[List[Any]] = None,
        previous_evaluations_json: Optional[str] = None,
        is_final: bool = False,
    ) -> Dict[str, Any]:
        """Perform evaluation of submission content and return structured scores/feedback JSON."""
        pass

    @abstractmethod
    def object_to_judges(
        self,
        model_name: str,
        text_content: str,
        media_files: Optional[List[Any]] = None,
        previous_evaluation_json: Optional[str] = None,
        chat_history_list: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Handle Q&A thread turn with the team and return structured feedback JSON."""
        pass

    @abstractmethod
    def admin_chat(
        self,
        model_name: str,
        source_text: str,
        file_ids_json: Optional[str] = None,
        previous_evaluation_json: Optional[str] = None,
        admin_question: str = "",
    ) -> Dict[str, Any]:
        """Allow admin to query details of submission and return bilingual Q&A JSON."""
        pass

    @abstractmethod
    def translate(self, text: str, target_languages: List[str]) -> Dict[str, str]:
        """Translate given text to target languages and return translated strings map."""
        pass
