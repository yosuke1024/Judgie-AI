"""
Pydantic schemas for request/response validation.
"""

from pydantic import BaseModel

# ──────────────────────────────────────────────
# Auth
# ──────────────────────────────────────────────


class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    email: str
    role: str
    team_id: str | None = None


class OIDCLoginInitResponse(BaseModel):
    auth_url: str
    state: str


class OIDCCallbackRequest(BaseModel):
    code: str
    state: str


class OIDCCallbackResponse(BaseModel):
    status: str  # "success" or "failed"
    team_id: str | None = None
    role: str | None = None


class UserInfo(BaseModel):
    user_id: int
    email: str
    role: str
    team_id: str | None = None
    display_name: str | None = None
    product_name: str | None = None
    team_name: str | None = None
    one_liner: str | None = None
    max_consultations: int = -1
    consultation_count: int = 0
    max_qa_turns: int = 1


# ──────────────────────────────────────────────
# Project
# ──────────────────────────────────────────────


class ProjectInitialize(BaseModel):
    template_id: str
    custom_template_data: dict | None = None


# ──────────────────────────────────────────────
# User
# ──────────────────────────────────────────────


class UserCreate(BaseModel):
    email: str
    password: str | None = None  # NULL = SSO-only user
    display_name: str | None = None
    role: str = "team"
    team_id: str | None = None  # Required when role is 'team'


class UserUpdate(BaseModel):
    display_name: str | None = None
    role: str | None = None
    team_id: str | None = None
    is_active: bool | None = None


class UserResponse(BaseModel):
    user_id: int
    email: str
    display_name: str | None = None
    role: str
    team_id: str | None = None
    is_active: bool = True
    has_password: bool = False


class UserBulkCreate(BaseModel):
    csv_content: str


class PasswordReset(BaseModel):
    new_password: str


# ──────────────────────────────────────────────
# Team
# ──────────────────────────────────────────────


class TeamCreate(BaseModel):
    team_id: str
    product_name: str | None = None
    team_name: str | None = None
    one_liner: str | None = None


class TeamBulkCreate(BaseModel):
    csv_content: str


class TeamProfileUpdate(BaseModel):
    product_name: str | None = None
    team_name: str | None = None
    one_liner: str | None = None


class TeamActiveUpdate(BaseModel):
    is_active: bool


class TeamResponse(BaseModel):
    team_id: str
    product_name: str | None = None
    team_name: str | None = None
    one_liner: str | None = None
    is_active: bool = True
    members: list[UserResponse] = []


# ──────────────────────────────────────────────
# Evaluation
# ──────────────────────────────────────────────


class EvaluationResponse(BaseModel):
    id: int
    team_id: str
    scores_json: str
    impact_score: float
    strengths_risks_json: str
    qa_json: str | None = None
    is_final: bool
    source_text: str | None = None
    gemini_file_ids: str | None = None
    evaluated_at: str | None = None


class ScoreboardEntry(BaseModel):
    team_id: str
    product_name: str | None = None
    team_name: str | None = None
    one_liner: str | None = None
    total_score: float = 0.0
    status: str = "Not Submitted"
    consults: int = 0
    scores_json: str | None = None


# ──────────────────────────────────────────────
# Chat
# ──────────────────────────────────────────────


class TeamObjection(BaseModel):
    objection_text: str


class AdminQuestion(BaseModel):
    question: str


class ChatMessage(BaseModel):
    id: int
    sender: str
    message_json: dict | str
    created_at: str | None = None


class AdminChatResponse(BaseModel):
    id: int
    question_en: str | None = None
    question_ja: str | None = None
    answer_en: str | None = None
    answer_ja: str | None = None
    qa_json: dict | None = None
    created_at: str | None = None


# ──────────────────────────────────────────────
# Settings
# ──────────────────────────────────────────────


class OIDCSettings(BaseModel):
    oidc_enabled: bool
    oidc_issuer: str
    oidc_client_id: str
    has_client_secret: bool
    oidc_redirect_uri: str | None = None
    oidc_allowed_domains: str | None = None
    oidc_allowed_emails: str | None = None


class OIDCSettingsUpdate(BaseModel):
    oidc_enabled: bool | None = None
    oidc_issuer: str | None = None
    oidc_client_id: str | None = None
    oidc_client_secret: str | None = None
    oidc_redirect_uri: str | None = None
    oidc_allowed_domains: str | None = None
    oidc_allowed_emails: str | None = None


class CriteriaUpdate(BaseModel):
    criteria: list[dict]


class PersonasUpdate(BaseModel):
    personas: list[dict]


class GeminiConfig(BaseModel):
    api_key: str | None = None
    model: str | None = None
    api_tier: str | None = None


class LLMConfig(BaseModel):
    llm_provider: str
    gemini_model: str | None = None
    openai_model: str | None = None
    anthropic_model: str | None = None
    has_gemini_api_key: bool
    has_openai_api_key: bool
    has_anthropic_api_key: bool
    gemini_available_models: list[str] = []
    openai_available_models: list[str] = []
    anthropic_available_models: list[str] = []


class LLMConfigUpdate(BaseModel):
    llm_provider: str | None = None
    api_key: str | None = None
    model: str | None = None


class ProjectSettings(BaseModel):
    re_evaluation_context_mode: str | None = None
    max_qa_turns: int | None = None
    max_consultations: int | None = None
    video_upload_enabled: bool | None = None


class LanguageSettings(BaseModel):
    languages: list[str]


# ──────────────────────────────────────────────
# Export / Import
# ──────────────────────────────────────────────


class TemplateImport(BaseModel):
    url: str


class PasswordChange(BaseModel):
    current_password: str
    new_password: str


# ──────────────────────────────────────────────
# Async Tasks
# ──────────────────────────────────────────────


class AsyncTaskResponse(BaseModel):
    task_id: str
    status: str  # PENDING, PROCESSING, SUCCESS, FAILED
    result_id: int | None = None
    error_message: str | None = None
