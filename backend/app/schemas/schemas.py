"""
Pydantic schemas for request/response validation.
"""


from pydantic import BaseModel

# ──────────────────────────────────────────────
# Auth
# ──────────────────────────────────────────────

class LoginRequest(BaseModel):
    team_id: str
    passcode: str


class LoginResponse(BaseModel):
    team_id: str
    role: str


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
    team_id: str
    role: str
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
# Team
# ──────────────────────────────────────────────

class TeamCreate(BaseModel):
    team_id: str
    passcode: str
    role: str = "team"
    product_name: str | None = None
    team_name: str | None = None
    one_liner: str | None = None


class TeamBulkCreate(BaseModel):
    csv_content: str


class TeamProfileUpdate(BaseModel):
    product_name: str | None = None
    team_name: str | None = None
    one_liner: str | None = None


class PasscodeChange(BaseModel):
    current_passcode: str | None = None
    new_passcode: str


class RoleUpdate(BaseModel):
    new_role: str


class TeamActiveUpdate(BaseModel):
    is_active: bool


class TeamResponse(BaseModel):
    team_id: str
    role: str
    product_name: str | None = None
    team_name: str | None = None
    one_liner: str | None = None
    is_active: bool = True


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

class CriteriaUpdate(BaseModel):
    criteria: list[dict]


class PersonasUpdate(BaseModel):
    personas: list[dict]


class GeminiConfig(BaseModel):
    api_key: str | None = None
    model: str | None = None
    api_tier: str | None = None


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
