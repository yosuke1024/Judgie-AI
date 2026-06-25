import React, { useState, useEffect, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { useAuth } from '@/contexts/AuthContext';
import {
  teamsApi,
  usersApi,
  evaluationsApi,
  settingsApi,
  chatApi,
  exportApi,
  pollTaskUntilDone,
} from '@/api/client';
import {
  Users,
  User as UserIcon,
  Key,
  Sliders,
  Shield,
  Search,
  Settings as SettingsIcon,
  Download,
  Plus,
  Trash2,
  Save,
  CheckCircle,
  AlertTriangle,
  Loader2,
  Send,
  Sparkles,
  RefreshCw,
  FileText,
  Upload,
} from 'lucide-react';

interface MemberItem {
  user_id: number;
  email: string;
  username: string | null;
  display_name: string | null;
  role: string;
  team_id: string | null;
  is_active: boolean;
  has_password: boolean;
}

interface TeamItem {
  team_id: string;
  product_name: string | null;
  team_name: string | null;
  one_liner: string | null;
  is_active?: boolean;
  members: MemberItem[];
}



interface EvaluationItem {
  id: number;
  team_id: string;
  scores_json: string;
  impact_score: number;
  strengths_risks_json: string;
  qa_json: string | null;
  is_final: boolean;
  evaluated_at: string | null;
}

interface AdminChatResponse {
  id: number;
  question_en: string | null;
  question_ja: string | null;
  answer_en: string | null;
  answer_ja: string | null;
  qa_json: Record<string, any> | null;
  created_at: string | null;
}

const emojiMap: Record<string, string> = {
  'English': '🇺🇸',
  'Japanese': '🇯🇵',
  'Spanish': '🇪🇸',
  'French': '🇫🇷',
  'German': '🇩🇪',
  'Chinese (Simplified)': '🇨🇳',
  'Chinese (Traditional)': '🇹🇼',
  'Korean': '🇰🇷',
  'Vietnamese': '🇻🇳',
  'Thai': '🇹🇭',
  'Indonesian': '🇮🇩',
};

const normalizeLangToKey = (langName: string): string => {
  const cleaned = langName.replace(/-/g, ' ');
  const safeName = cleaned.replace(/[^\w\s\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff]/g, '');
  return safeName.replace(/\s+/g, '_').trim().toLowerCase();
};

export default function AdminCenter() {
  const { t, i18n } = useTranslation();
  const { user } = useAuth();
  const isObserver = user?.role === 'observer';
  const [activeTab, setActiveTab] = useState('teams');

  // --- Common States ---
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [loading, setLoading] = useState(false);

  // --- Tab 1: Teams ---
  const [teams, setTeams] = useState<TeamItem[]>([]);
  const [newTeamId, setNewTeamId] = useState('');

  // --- Tab: Members (New) ---
  const [members, setMembers] = useState<MemberItem[]>([]);
  const [newMemberEmail, setNewMemberEmail] = useState('');
  const [newMemberUsername, setNewMemberUsername] = useState('');
  const [newMemberDisplayName, setNewMemberDisplayName] = useState('');
  const [newMemberRole, setNewMemberRole] = useState('team');
  const [newMemberTeamId, setNewMemberTeamId] = useState('');
  const [newMemberPassword, setNewMemberPassword] = useState('');
  const [memberSearch, setMemberSearch] = useState('');
  const [memberRoleFilter, setMemberRoleFilter] = useState('all');
  const [memberBulkCsv, setMemberBulkCsv] = useState('');

  // --- Tab 2: Criteria ---
  const [criteriaList, setCriteriaList] = useState<any[]>([]);

  // --- Tab 3: Personas ---
  const [personas, setPersonas] = useState<any[]>([]);



  // --- Tab 5: Deep Dive ---
  const [diveTeamId, setDiveTeamId] = useState('');
  const [diveEvaluations, setDiveEvaluations] = useState<EvaluationItem[]>([]);
  const [selectedDiveEval, setSelectedDiveEval] = useState<EvaluationItem | null>(null);
  const [adminChats, setAdminChats] = useState<AdminChatResponse[]>([]);
  const [adminQuestion, setAdminQuestion] = useState('');
  const [diveLoading, setDiveLoading] = useState(false);
  const [chatLoading, setChatLoading] = useState(false);
  const [selectedAiLang, setSelectedAiLang] = useState<string>('en');

  // --- Tab 6: Languages ---
  const [languages, setLanguages] = useState<string[]>([]);
  const [newLang, setNewLang] = useState('');

  // --- Tab 7: Settings ---
  const [llmProvider, setLlmProvider] = useState<string>('gemini');
  const [geminiModel, setGeminiModel] = useState<string>('');
  const [openaiModel, setOpenaiModel] = useState<string>('');
  const [anthropicModel, setAnthropicModel] = useState<string>('');
  const [hasGeminiApiKey, setHasGeminiApiKey] = useState(false);
  const [hasOpenaiApiKey, setHasOpenaiApiKey] = useState(false);
  const [hasAnthropicApiKey, setHasAnthropicApiKey] = useState(false);
  const [geminiAvailableModels, setGeminiAvailableModels] = useState<string[]>([]);
  const [openaiAvailableModels, setOpenaiAvailableModels] = useState<string[]>([]);
  const [anthropicAvailableModels, setAnthropicAvailableModels] = useState<string[]>([]);
  const [apiKeyInput, setApiKeyInput] = useState<string>('');
  const [verifyingKey, setVerifyingKey] = useState(false);
  const [projectSettings, setProjectSettings] = useState({
    re_evaluation_context_mode: 'cumulative',
    max_qa_turns: 1,
    max_consultations: 3,
    video_upload_enabled: true,
  });
  const [oidcConfig, setOidcConfig] = useState({
    oidc_enabled: false,
    oidc_issuer: 'https://accounts.google.com',
    oidc_client_id: '',
    oidc_client_secret: '',
    oidc_redirect_uri: '',
    oidc_allowed_domains: '',
    oidc_allowed_emails: '',
    has_client_secret: false,
  });
  const [savingOidc, setSavingOidc] = useState(false);
  const [newAdminPass, setNewAdminPass] = useState('');
  const [confirmAdminPass, setConfirmAdminPass] = useState('');

  // --- Tab 8: Export ---
  const [importUrl, setImportUrl] = useState('');
  const [templates, setTemplates] = useState<Record<string, { name: string; description: string }>>({});
  const [selectedTemplate, setSelectedTemplate] = useState('');

  const showSuccess = (msg: string) => {
    setSuccess(msg);
    setTimeout(() => setSuccess(''), 4000);
  };

  // --- Data Loading Functions ---
  const loadTemplates = useCallback(async () => {
    try {
      const tpls = await settingsApi.getTemplates();
      setTemplates(tpls);
    } catch (err: any) {
      console.error('Failed to load templates:', err);
    }
  }, []);

  const loadTeams = useCallback(async () => {
    try {
      setLoading(true);
      const data = await teamsApi.list();
      setTeams(data);
    } catch (err: any) {
      setError(err.message || 'Failed to load teams.');
    } finally {
      setLoading(false);
    }
  }, []);

  const loadMembers = useCallback(async () => {
    try {
      setLoading(true);
      const data = await usersApi.list();
      setMembers(data);
    } catch (err: any) {
      setError(err.message || 'Failed to load members.');
    } finally {
      setLoading(false);
    }
  }, []);

  const loadCriteria = useCallback(async () => {
    try {
      const data = await settingsApi.getCriteria();
      setCriteriaList(data);
    } catch (err: any) {
      setError(err.message || 'Failed to load criteria.');
    }
  }, []);

  const loadPersonas = useCallback(async () => {
    try {
      const data = await settingsApi.getPersonas();
      setPersonas(data);
    } catch (err: any) {
      setError(err.message || 'Failed to load AI judges.');
    }
  }, []);



  const loadLanguages = useCallback(async () => {
    try {
      const data = await settingsApi.getLanguages();
      if (data && data.languages) {
        setLanguages(data.languages);
        // Set default AI language based on current UI locale if it matches
        const currentUiLocale = i18n.language === 'ja' ? 'japanese' : 'english';
        const match = data.languages.find(
          (l: string) => normalizeLangToKey(l) === normalizeLangToKey(currentUiLocale)
        );
        if (match) {
          setSelectedAiLang(normalizeLangToKey(match));
        } else if (data.languages.length > 0) {
          setSelectedAiLang(normalizeLangToKey(data.languages[0]));
        }
      }
    } catch (err: any) {
      console.error(err);
    }
  }, [i18n.language]);

  const loadSettings = useCallback(async () => {
    try {
      const llm = await settingsApi.getLlm() as any;
      const project = await settingsApi.getProject();
      const oidc = await settingsApi.getOidc() as any;

      setLlmProvider(llm.llm_provider || 'gemini');
      setGeminiModel(llm.gemini_model || '');
      setOpenaiModel(llm.openai_model || '');
      setAnthropicModel(llm.anthropic_model || '');
      setHasGeminiApiKey(!!llm.has_gemini_api_key);
      setHasOpenaiApiKey(!!llm.has_openai_api_key);
      setHasAnthropicApiKey(!!llm.has_anthropic_api_key);
      setGeminiAvailableModels(llm.gemini_available_models || []);
      setOpenaiAvailableModels(llm.openai_available_models || []);
      setAnthropicAvailableModels(llm.anthropic_available_models || []);
      setApiKeyInput('');

      setProjectSettings({
        re_evaluation_context_mode: (project.re_evaluation_context_mode as string) || 'cumulative',
        max_qa_turns: Number(project.max_qa_turns) || 1,
        max_consultations: Number(project.max_consultations) || 3,
        video_upload_enabled: project.video_upload_enabled !== false,
      });
      setOidcConfig({
        oidc_enabled: !!oidc.oidc_enabled,
        oidc_issuer: oidc.oidc_issuer || 'https://accounts.google.com',
        oidc_client_id: oidc.oidc_client_id || '',
        oidc_client_secret: '',
        oidc_redirect_uri: oidc.oidc_redirect_uri || '',
        oidc_allowed_domains: oidc.oidc_allowed_domains || '',
        oidc_allowed_emails: oidc.oidc_allowed_emails || '',
        has_client_secret: !!oidc.has_client_secret,
      });
    } catch (err: any) {
      console.error(err);
    }
  }, []);

  const handleSaveOidc = async (e: React.FormEvent) => {
    e.preventDefault();
    setSavingOidc(true);
    setError('');
    try {
      const payload: any = {
        oidc_enabled: oidcConfig.oidc_enabled,
        oidc_issuer: oidcConfig.oidc_issuer,
        oidc_client_id: oidcConfig.oidc_client_id,
        oidc_redirect_uri: oidcConfig.oidc_redirect_uri || null,
        oidc_allowed_domains: oidcConfig.oidc_allowed_domains || '',
        oidc_allowed_emails: oidcConfig.oidc_allowed_emails || '',
      };
      if (oidcConfig.oidc_client_secret.trim()) {
        payload.oidc_client_secret = oidcConfig.oidc_client_secret;
      }
      await settingsApi.updateOidc(payload);
      showSuccess('OIDC settings updated successfully!');
      
      const oidc = await settingsApi.getOidc() as any;
      setOidcConfig(prev => ({
        ...prev,
        oidc_client_secret: '',
        has_client_secret: !!oidc.has_client_secret,
      }));
    } catch (err: any) {
      setError(err.message || 'Failed to update OIDC settings.');
    } finally {
      setSavingOidc(false);
    }
  };

  // Fetch initial tab data on mount or tab change
  useEffect(() => {
    setError('');
    if (activeTab === 'teams') loadTeams();
    else if (activeTab === 'members') {
      loadMembers();
      loadTeams();
    }
    else if (activeTab === 'criteria') loadCriteria();
    else if (activeTab === 'personas') loadPersonas();
    else if (activeTab === 'deep_dive') loadLanguages();
    else if (activeTab === 'settings') {
      loadSettings();
      loadTemplates();
      loadLanguages();
    }
  }, [activeTab, loadTeams, loadMembers, loadCriteria, loadPersonas, loadLanguages, loadSettings, loadTemplates]);

  // --- Handlers: Members Tab ---
  const handleCreateMember = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newMemberEmail) return;

    try {
      setError('');
      setLoading(true);
      await usersApi.create({
        email: newMemberEmail,
        username: newMemberUsername || undefined,
        display_name: newMemberDisplayName || undefined,
        role: newMemberRole,
        team_id: newMemberRole === 'team' ? newMemberTeamId : undefined,
        password: newMemberPassword || undefined,
      });
      showSuccess(t('admin.members.update_success'));
      setNewMemberEmail('');
      setNewMemberUsername('');
      setNewMemberDisplayName('');
      setNewMemberRole('team');
      setNewMemberTeamId('');
      setNewMemberPassword('');
      loadMembers();
    } catch (err: any) {
      setError(err.message || 'Failed to create member.');
    } finally {
      setLoading(false);
    }
  };

  const handleUpdateMemberRole = async (userId: number, role: string) => {
    try {
      setError('');
      const payload: any = { role };
      if (role === 'team') {
        const firstTeam = teams[0]?.team_id || '';
        payload.team_id = firstTeam;
      } else {
        payload.team_id = '';
      }
      await usersApi.update(userId, payload);
      showSuccess(t('admin.members.update_success'));
      loadMembers();
    } catch (err: any) {
      setError(err.message || 'Failed to update user role.');
    }
  };

  const handleUpdateMemberTeam = async (userId: number, teamId: string) => {
    try {
      setError('');
      await usersApi.update(userId, { team_id: teamId });
      showSuccess(t('admin.members.update_success'));
      loadMembers();
    } catch (err: any) {
      setError(err.message || 'Failed to update user team.');
    }
  };

  const handleToggleMemberActive = async (userId: number, isActive: boolean) => {
    try {
      setError('');
      await usersApi.update(userId, { is_active: isActive });
      showSuccess(t('admin.members.update_success'));
      loadMembers();
    } catch (err: any) {
      setError(err.message || 'Failed to update active state.');
    }
  };

  const handleResetMemberPassword = async (userId: number) => {
    const newPass = prompt('Enter new password:');
    if (newPass === null) return;
    if (!newPass.trim()) {
      alert('Password cannot be empty.');
      return;
    }
    try {
      setError('');
      await usersApi.resetPassword(userId, newPass.trim());
      showSuccess(t('admin.members.reset_password_success'));
    } catch (err: any) {
      setError(err.message || 'Failed to reset password.');
    }
  };

  const handleDeleteMember = async (userId: number) => {
    if (!confirm(t('admin.members.delete_confirm'))) return;
    try {
      setError('');
      await usersApi.delete(userId);
      showSuccess(t('admin.members.delete_success'));
      loadMembers();
    } catch (err: any) {
      setError(err.message || 'Failed to delete member.');
    }
  };

  const handleMemberBulkImport = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!memberBulkCsv) return;
    try {
      setError('');
      setLoading(true);
      const res = await usersApi.bulkCreate(memberBulkCsv);
      showSuccess(t('admin.members.import_success', { created: res.created, skipped: res.skipped }));
      setMemberBulkCsv('');
      loadMembers();
    } catch (err: any) {
      setError(err.message || 'Failed to import members.');
    } finally {
      setLoading(false);
    }
  };

  // --- Handlers: Teams Tab ---
  const handleCreateTeam = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTeamId) return;

    try {
      setError('');
      await teamsApi.create({
        team_id: newTeamId,
      });
      setNewTeamId('');
      showSuccess(`Team ${newTeamId} created successfully!`);
      loadTeams();
    } catch (err: any) {
      setError(err.message || 'Failed to create team.');
    }
  };



  const handleDeleteTeam = async (teamId: string) => {
    if (!window.confirm(`Are you sure you want to delete team ${teamId} and all their evaluations?`)) return;
    try {
      setError('');
      await teamsApi.delete(teamId);
      showSuccess(`Team ${teamId} deleted.`);
      loadTeams();
    } catch (err: any) {
      setError(err.message);
    }
  };

  // Role management moved to users router

  const handleUpdateTeamActive = async (teamId: string, isActive: boolean) => {
    try {
      setError('');
      await teamsApi.updateActive(teamId, isActive);
      showSuccess(`Status updated for team '${teamId}'`);
      loadTeams();
    } catch (err: any) {
      setError(err.message || 'Failed to update team status.');
    }
  };

  // --- Handlers: Criteria Tab ---
  const handleSaveCriteria = async () => {
    try {
      setError('');
      await settingsApi.updateCriteria(criteriaList);
      showSuccess('Evaluation criteria updated successfully!');
    } catch (err: any) {
      setError(err.message);
    }
  };

  const updateCriteriaField = (index: number, key: string, value: any) => {
    const updated = [...criteriaList];
    updated[index] = { ...updated[index], [key]: value };
    setCriteriaList(updated);
  };

  const deleteCriteria = (index: number) => {
    setCriteriaList(criteriaList.filter((_, i) => i !== index));
  };

  const addCriteria = () => {
    setCriteriaList([...criteriaList, { name: 'New Criterion', description: 'Description', weight: 1.0 }]);
  };

  // --- Handlers: Personas Tab ---
  const handleSavePersonas = async () => {
    try {
      setError('');
      await settingsApi.updatePersonas(personas);
      showSuccess('AI Judges personas updated successfully!');
    } catch (err: any) {
      setError(err.message);
    }
  };

  const updatePersonaField = (index: number, key: string, value: any) => {
    const updated = [...personas];
    updated[index] = { ...updated[index], [key]: value };
    setPersonas(updated);
  };

  const deletePersona = (index: number) => {
    setPersonas(personas.filter((_, i) => i !== index));
  };

  const addPersona = () => {
    setPersonas([
      ...personas,
      {
        id: String(Date.now()),
        name: 'Judge Name',
        role: 'Judge Role',
        avatar: '🤖',
        prompt: 'Focus on technical execution.',
        active: true,
      },
    ]);
  };

  // --- Handlers: Deep Dive Tab ---
  useEffect(() => {
    const fetchDiveData = async () => {
      if (!diveTeamId) {
        setDiveEvaluations([]);
        setSelectedDiveEval(null);
        return;
      }
      try {
        setDiveLoading(true);
        const data = (await evaluationsApi.getTeamEvaluations(diveTeamId)) as EvaluationItem[];
        const sorted = [...data].sort((a, b) => b.id - a.id);
        setDiveEvaluations(sorted);
        if (sorted.length > 0) {
          setSelectedDiveEval(sorted[0]);
        } else {
          setSelectedDiveEval(null);
        }
      } catch (err) {
        console.error(err);
      } finally {
        setDiveLoading(false);
      }
    };
    fetchDiveData();
  }, [diveTeamId]);

  const fetchAdminChat = useCallback(async (evalId: number) => {
    try {
      setChatLoading(true);
      const chats = (await chatApi.getAdminChat(evalId)) as AdminChatResponse[];
      setAdminChats(chats);
    } catch (err) {
      console.error(err);
    } finally {
      setChatLoading(false);
    }
  }, []);

  useEffect(() => {
    if (selectedDiveEval) {
      fetchAdminChat(selectedDiveEval.id);
    } else {
      setAdminChats([]);
    }
  }, [selectedDiveEval, fetchAdminChat]);

  const handleSendAdminQuestion = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedDiveEval || !adminQuestion.trim()) return;

    const q = adminQuestion.trim();
    setAdminQuestion('');
    const previousChats = [...adminChats];
    try {
      // Optimistic locally
      setAdminChats((prev) => [
        ...prev,
        {
          id: Date.now(),
          question_en: q,
          question_ja: q,
          answer_en: '',
          answer_ja: '',
          qa_json: { question: q, answer: 'Thinking...' },
          created_at: new Date().toISOString(),
        },
      ]);
      const { task_id } = await chatApi.submitAdminQuestion(selectedDiveEval.id, q);
      // Poll until the background LLM call completes
      const result = await pollTaskUntilDone(task_id);
      if (result.status === 'FAILED') {
        setError(result.error_message || 'AI Judge failed to respond.');
        setAdminChats(previousChats);
      } else {
        await fetchAdminChat(selectedDiveEval.id);
      }
    } catch (err: any) {
      setError(err.message || 'Failed to ask AI Judge.');
      setAdminChats(previousChats);
    }
  };

  const handleDeleteEvaluation = async (evalId: number) => {
    if (!window.confirm('Are you sure you want to delete this evaluation history record?')) return;
    try {
      await evaluationsApi.delete(evalId);
      showSuccess('Evaluation record deleted.');
      if (diveTeamId) {
        // reload
        const data = (await evaluationsApi.getTeamEvaluations(diveTeamId)) as EvaluationItem[];
        setDiveEvaluations(data);
        setSelectedDiveEval(data.length > 0 ? data[0] : null);
      }
    } catch (err: any) {
      setError(err.message);
    }
  };

  // --- Handlers: Languages Tab ---
  const handleSaveLanguages = async () => {
    try {
      setError('');
      await settingsApi.updateLanguages(languages);
      showSuccess('AI output languages updated!');
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleAddLanguage = () => {
    if (!newLang.trim()) return;
    if (!languages.includes(newLang.trim())) {
      setLanguages([...languages, newLang.trim()]);
    }
    setNewLang('');
  };

  const handleRemoveLanguage = (lang: string) => {
    setLanguages(languages.filter((l) => l !== lang));
  };

  // --- Handlers: Settings Tab ---
  const handleSaveSettings = async () => {
    try {
      setError('');
      await settingsApi.updateProject(projectSettings);
      showSuccess('Project settings updated.');
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleChangeAdminPass = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newAdminPass) return;
    if (newAdminPass !== confirmAdminPass) {
      setError('New passwords do not match.');
      return;
    }
    try {
      setError('');
      await settingsApi.resetAdminPassword(newAdminPass);
      setNewAdminPass('');
      setConfirmAdminPass('');
      showSuccess('Admin password changed successfully!');
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleVerifyKey = async () => {
    if (!apiKeyInput.trim()) return;
    try {
      setError('');
      setVerifyingKey(true);
      await settingsApi.updateLlm({
        llm_provider: llmProvider,
        api_key: apiKeyInput.trim(),
      });
      showSuccess(`${llmProvider.toUpperCase()} API key verified & saved successfully.`);
      await loadSettings();
    } catch (err: any) {
      setError(err.message || 'Invalid API key or failed to verify.');
    } finally {
      setVerifyingKey(false);
    }
  };

  const handleProviderChange = async (provider: string) => {
    setLlmProvider(provider);
    setApiKeyInput('');
    try {
      await settingsApi.updateLlm({ llm_provider: provider });
      showSuccess(`LLM Provider switched to ${provider.toUpperCase()}`);
      await loadSettings();
    } catch (err: any) {
      setError(err.message || 'Failed to switch LLM provider.');
    }
  };

  const handleModelChange = async (model: string) => {
    if (llmProvider === 'gemini') setGeminiModel(model);
    else if (llmProvider === 'openai') setOpenaiModel(model);
    else if (llmProvider === 'anthropic') setAnthropicModel(model);

    try {
      await settingsApi.updateLlm({
        llm_provider: llmProvider,
        model: model,
      });
      showSuccess(`${llmProvider.toUpperCase()} model updated to ${model}.`);
      await loadSettings();
    } catch (err: any) {
      setError(err.message || 'Failed to update model.');
    }
  };

  // --- Handlers: Export Tab ---
  const handleApplyPresetTemplate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedTemplate) return;

    if (!window.confirm(t('admin.import_preset_confirm'))) return;

    try {
      setError('');
      setLoading(true);
      await settingsApi.initialize({ template_id: selectedTemplate });
      showSuccess(t('admin.import_preset_success'));
      setSelectedTemplate('');
    } catch (err: any) {
      setError(err.message || 'Failed to apply template.');
    } finally {
      setLoading(false);
    }
  };

  const handleImportTemplate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!importUrl) return;
    try {
      setError('');
      await exportApi.importTemplate(importUrl);
      setImportUrl('');
      showSuccess('Template imported successfully!');
    } catch (err: any) {
      setError(err.message);
    }
  };

  return (
    <div className="admin-center-page">
      <div className="page-header">
        <Shield size={32} />
        <div>
          <h1>{t('admin.title')}</h1>
          <p className="page-subtitle">Configure your hackathon, teams, criteria and AI settings.</p>
        </div>
      </div>

      {/* Global Alerts */}
      {error && (
        <div className="alert alert-error">
          <AlertTriangle size={18} />
          <span>{error}</span>
        </div>
      )}
      {success && (
        <div className="alert alert-success">
          <CheckCircle size={18} />
          <span>{success}</span>
        </div>
      )}

      {/* Admin Tab Navigation */}
      <div className="admin-tabs">
        <button
          className={`tab-btn ${activeTab === 'teams' ? 'active' : ''}`}
          onClick={() => setActiveTab('teams')}
        >
          <Users size={16} />
          {t('admin.teams_tab')}
        </button>
        <button
          className={`tab-btn ${activeTab === 'members' ? 'active' : ''}`}
          onClick={() => setActiveTab('members')}
        >
          <UserIcon size={16} />
          {t('admin.members_tab')}
        </button>
        <button
          className={`tab-btn ${activeTab === 'criteria' ? 'active' : ''}`}
          onClick={() => setActiveTab('criteria')}
        >
          <Sliders size={16} />
          {t('admin.criteria_tab')}
        </button>
        <button
          className={`tab-btn ${activeTab === 'personas' ? 'active' : ''}`}
          onClick={() => setActiveTab('personas')}
        >
          <Sparkles size={16} />
          {t('admin.personas_tab')}
        </button>
        <button
          className={`tab-btn ${activeTab === 'deep_dive' ? 'active' : ''}`}
          onClick={() => setActiveTab('deep_dive')}
        >
          <Search size={16} />
          {t('admin.deep_dive_tab')}
        </button>
        <button
          className={`tab-btn ${activeTab === 'settings' ? 'active' : ''}`}
          onClick={() => setActiveTab('settings')}
        >
          <SettingsIcon size={16} />
          {t('admin.settings_tab')}
        </button>
        <button
          className={`tab-btn ${activeTab === 'export' ? 'active' : ''}`}
          onClick={() => setActiveTab('export')}
        >
          <Download size={16} />
          {t('admin.export_tab')}
        </button>
      </div>

      <div className="tab-content-panel">
        {/* ================================================================= */}
        {/* TAB: TEAMS */}
        {/* ================================================================= */}
        {activeTab === 'teams' && (
          <div className="tab-pane teams-pane">
            <div className="teams-grid">
              {/* Team Registration Forms */}
              <div className="pane-form-column">
                <div className="card">
                  <h4>Register Single Team</h4>
                  <form onSubmit={handleCreateTeam} className="vertical-form">
                    <div className="form-group">
                      <label>Team ID / Name</label>
                      <input
                        type="text"
                        value={newTeamId}
                        onChange={(e) => setNewTeamId(e.target.value)}
                        placeholder="e.g. team-alpha"
                        disabled={isObserver}
                      />
                    </div>
                    <button type="submit" className="btn btn-primary" disabled={isObserver}>
                      <Plus size={16} /> Add Team
                    </button>
                  </form>
                </div>
              </div>

              {/* Team List Table */}
              <div className="pane-table-column">
                <div className="card h-full">
                  <div className="card-header-flex">
                    <h4>Registered Teams ({teams.length})</h4>
                    <button onClick={loadTeams} className="btn btn-ghost btn-sm">
                      <RefreshCw size={14} /> Refresh
                    </button>
                  </div>

                  <div className="table-wrapper mt-4">
                    <table className="admin-table">
                      <thead>
                        <tr>
                          <th>Team ID</th>
                          <th>Product Name</th>
                          <th>Members</th>
                          <th>Active</th>
                          <th>Actions</th>
                        </tr>
                      </thead>
                      <tbody>
                        {teams.map((t) => (
                          <tr key={t.team_id}>
                            <td><strong>{t.team_id}</strong></td>
                            <td>{t.product_name || <span className="dim-text">—</span>}</td>
                            <td>
                              <span style={{ fontSize: '0.9em', display: 'inline-flex', alignItems: 'center', gap: '6px', background: 'var(--bg-accent)', padding: '2px 8px', borderRadius: '12px', fontWeight: 'bold' }}>
                                {t.members ? t.members.length : 0}
                              </span>
                            </td>
                            <td>
                              <input
                                type="checkbox"
                                checked={t.is_active !== false}
                                onChange={(e) => handleUpdateTeamActive(t.team_id, e.target.checked)}
                                disabled={isObserver}
                                className="table-checkbox"
                                style={{ transform: 'scale(1.2)', cursor: isObserver ? 'default' : 'pointer' }}
                              />
                            </td>
                            <td>
                              <button
                                onClick={() => handleDeleteTeam(t.team_id)}
                                className="btn btn-danger btn-xs"
                                disabled={isObserver}
                              >
                                <Trash2 size={12} /> Delete
                              </button>
                            </td>
                          </tr>
                        ))}
                        {teams.length === 0 && (
                          <tr>
                            <td colSpan={5} className="text-center dim-text">
                              {loading ? (
                                <div className="inline-flex items-center gap-2" style={{ display: 'inline-flex', alignItems: 'center', gap: '8px', justifyContent: 'center' }}>
                                  <Loader2 size={16} className="animate-spin" />
                                  <span>Loading teams...</span>
                                </div>
                              ) : (
                                'No teams registered yet.'
                              )}
                            </td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ================================================================= */}
        {/* TAB: MEMBERS */}
        {/* ================================================================= */}
        {activeTab === 'members' && (
          <div className="tab-pane members-pane">
            <div className="members-grid" style={{ display: 'grid', gridTemplateColumns: '320px 1fr', gap: '24px', alignItems: 'start' }}>
              {/* Member Registration Forms */}
              <div className="pane-form-column" style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
                <div className="card">
                  <h4>{t('admin.members.add_member')}</h4>
                  <form onSubmit={handleCreateMember} className="vertical-form">
                    <div className="form-group">
                      <label>Email *</label>
                      <input
                        type="email"
                        value={newMemberEmail}
                        onChange={(e) => setNewMemberEmail(e.target.value)}
                        placeholder={t('admin.members.email_placeholder')}
                        required
                        disabled={isObserver}
                      />
                    </div>
                    <div className="form-group">
                      <label>{t('admin.members.username')}</label>
                      <input
                        type="text"
                        value={newMemberUsername}
                        onChange={(e) => setNewMemberUsername(e.target.value)}
                        placeholder={t('admin.members.username_placeholder')}
                        disabled={isObserver}
                      />
                    </div>
                    <div className="form-group">
                      <label>{t('admin.members.display_name')}</label>
                      <input
                        type="text"
                        value={newMemberDisplayName}
                        onChange={(e) => setNewMemberDisplayName(e.target.value)}
                        placeholder={t('admin.members.display_name_placeholder')}
                        disabled={isObserver}
                      />
                    </div>
                    <div className="form-group">
                      <label>{t('admin.members.password')}</label>
                      <input
                        type="password"
                        value={newMemberPassword}
                        onChange={(e) => setNewMemberPassword(e.target.value)}
                        placeholder={t('admin.members.password_placeholder')}
                        disabled={isObserver}
                      />
                    </div>
                    <div className="form-group">
                      <label>{t('admin.members.role')}</label>
                      <select
                        value={newMemberRole}
                        onChange={(e) => setNewMemberRole(e.target.value)}
                        disabled={isObserver}
                      >
                        <option value="team">Team Member</option>
                        <option value="observer">Observer</option>
                        <option value="admin">Administrator</option>
                      </select>
                    </div>
                    {newMemberRole === 'team' && (
                      <div className="form-group">
                        <label>{t('admin.members.team')} *</label>
                        <select
                          value={newMemberTeamId}
                          onChange={(e) => setNewMemberTeamId(e.target.value)}
                          required
                          disabled={isObserver}
                        >
                          <option value="">— Select Team —</option>
                          {teams.map((t) => (
                            <option key={t.team_id} value={t.team_id}>
                              {t.team_id}
                            </option>
                          ))}
                        </select>
                      </div>
                    )}
                    <button type="submit" className="btn btn-primary" disabled={isObserver || (newMemberRole === 'team' && !newMemberTeamId)}>
                      <Plus size={16} /> {t('admin.members.add_member')}
                    </button>
                  </form>
                </div>

                <div className="card">
                  <h4>{t('admin.members.bulk_import')}</h4>
                  <form onSubmit={handleMemberBulkImport} className="vertical-form">
                    <div className="form-group">
                      <label>{t('admin.members.csv_content_label')}</label>
                      <span style={{ fontSize: '0.75em', color: 'var(--text-muted)', display: 'block', marginBottom: '8px', lineHeight: '1.4' }}>
                        {t('admin.members.csv_help')}
                      </span>
                      <textarea
                        value={memberBulkCsv}
                        onChange={(e) => setMemberBulkCsv(e.target.value)}
                        placeholder="user1@example.com,team-alpha,team,User One,pass123,user_one"
                        rows={6}
                        disabled={isObserver}
                        required
                      />
                    </div>
                    <button type="submit" className="btn btn-primary" disabled={isObserver}>
                      <Upload size={16} /> {t('admin.members.import_btn')}
                    </button>
                  </form>
                </div>
              </div>

              {/* Members Table */}
              <div className="pane-table-column">
                <div className="card h-full">
                  <div className="card-header-flex" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px', gap: '16px', flexWrap: 'wrap' }}>
                    <div style={{ flex: 1, minWidth: '200px' }}>
                      <h4>{t('admin.members.title')} ({members.length})</h4>
                      <p className="dim-text" style={{ fontSize: '0.85em', marginTop: '4px' }}>
                        {t('admin.members.subtitle')}
                      </p>
                    </div>
                    <button onClick={loadMembers} className="btn btn-ghost btn-sm">
                      <RefreshCw size={14} /> Refresh
                    </button>
                  </div>

                  {/* Filters */}
                  <div className="filters-bar" style={{ display: 'flex', gap: '12px', marginBottom: '16px', flexWrap: 'wrap' }}>
                    <input
                      type="text"
                      className="form-control"
                      placeholder={t('admin.members.search_placeholder')}
                      value={memberSearch}
                      onChange={(e) => setMemberSearch(e.target.value)}
                      style={{ flex: 1, minWidth: '200px', height: '36px', padding: '0 12px', borderRadius: '4px', border: '1px solid var(--border-color)', background: 'var(--bg-card)' }}
                    />
                    <select
                      className="form-control"
                      value={memberRoleFilter}
                      onChange={(e) => setMemberRoleFilter(e.target.value)}
                      style={{ width: '160px', height: '36px', borderRadius: '4px', border: '1px solid var(--border-color)', background: 'var(--bg-card)' }}
                    >
                      <option value="all">All Roles</option>
                      <option value="team">Team Members</option>
                      <option value="observer">Observers</option>
                      <option value="admin">Administrators</option>
                    </select>
                  </div>

                  <div className="table-wrapper">
                    <table className="admin-table">
                      <thead>
                        <tr>
                          <th>Email</th>
                          <th>{t('admin.members.username')}</th>
                          <th>{t('admin.members.display_name')}</th>
                          <th>{t('admin.members.role')}</th>
                          <th>{t('admin.members.team')}</th>
                          <th>{t('admin.members.active')}</th>
                          <th>{t('admin.members.actions')}</th>
                        </tr>
                      </thead>
                      <tbody>
                        {members
                          .filter((m) => {
                            const matchSearch =
                              m.email.toLowerCase().includes(memberSearch.toLowerCase()) ||
                              (m.username || '').toLowerCase().includes(memberSearch.toLowerCase()) ||
                              (m.display_name || '').toLowerCase().includes(memberSearch.toLowerCase());
                            const matchRole =
                              memberRoleFilter === 'all' || m.role === memberRoleFilter;
                            return matchSearch && matchRole;
                          })
                          .map((m) => (
                            <tr key={m.user_id}>
                              <td style={{ fontSize: '0.9em' }}>
                                <strong>{m.email}</strong>
                              </td>
                              <td style={{ fontSize: '0.9em' }}>
                                {m.username || <span className="dim-text">—</span>}
                              </td>
                              <td style={{ fontSize: '0.9em' }}>
                                {m.display_name || <span className="dim-text">—</span>}
                              </td>
                              <td>
                                <select
                                  value={m.role}
                                  onChange={(e) => handleUpdateMemberRole(m.user_id, e.target.value)}
                                  disabled={isObserver}
                                  style={{ fontSize: '0.9em', padding: '2px 4px', borderRadius: '4px' }}
                                >
                                  <option value="team">team</option>
                                  <option value="observer">observer</option>
                                  <option value="admin">admin</option>
                                </select>
                              </td>
                              <td>
                                {m.role === 'team' ? (
                                  <select
                                    value={m.team_id || ''}
                                    onChange={(e) => handleUpdateMemberTeam(m.user_id, e.target.value)}
                                    disabled={isObserver}
                                    style={{ fontSize: '0.9em', padding: '2px 4px', borderRadius: '4px', maxWidth: '120px' }}
                                  >
                                    <option value="">{t('admin.members.no_team')}</option>
                                    {teams.map((t) => (
                                      <option key={t.team_id} value={t.team_id}>
                                        {t.team_id}
                                      </option>
                                    ))}
                                  </select>
                                ) : (
                                  <span className="dim-text">—</span>
                                )}
                              </td>
                              <td>
                                <input
                                  type="checkbox"
                                  checked={m.is_active !== false}
                                  onChange={(e) => handleToggleMemberActive(m.user_id, e.target.checked)}
                                  disabled={isObserver}
                                  className="table-checkbox"
                                />
                              </td>
                              <td>
                                <div style={{ display: 'flex', gap: '8px' }}>
                                  <button
                                    onClick={() => handleResetMemberPassword(m.user_id)}
                                    className="btn btn-ghost btn-xs"
                                    title={t('admin.members.reset_password')}
                                    disabled={isObserver}
                                    style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '4px' }}
                                  >
                                    <Key size={14} />
                                  </button>
                                  <button
                                    onClick={() => handleDeleteMember(m.user_id)}
                                    className="btn btn-danger btn-xs"
                                    disabled={isObserver}
                                    style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '4px' }}
                                  >
                                    <Trash2 size={14} />
                                  </button>
                                </div>
                              </td>
                            </tr>
                          ))}
                        {members.length === 0 && (
                          <tr>
                            <td colSpan={7} style={{ textAlign: 'center', padding: '24px' }} className="dim-text">
                              No members found.
                            </td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ================================================================= */}
        {/* TAB: CRITERIA */}
        {/* ================================================================= */}
        {activeTab === 'criteria' && (
          <div className="tab-pane criteria-pane">
            <div className="card">
              <div className="card-header-flex">
                <div>
                  <h4>Evaluation Criteria</h4>
                  <p className="dim-text text-sm">Define what elements of the projects are evaluated and their weights.</p>
                </div>
                <button onClick={addCriteria} className="btn btn-secondary btn-sm" disabled={isObserver}>
                  <Plus size={14} /> Add Criterion
                </button>
              </div>

              <div className="criteria-list mt-4">
                {criteriaList.map((crit, index) => (
                  <div key={index} className="criteria-item-card">
                    <div className="crit-item-inputs">
                      <div className="form-group flex-2">
                        <label>Criterion Name</label>
                        <input
                          type="text"
                          value={crit.name}
                          onChange={(e) => updateCriteriaField(index, 'name', e.target.value)}
                          disabled={isObserver}
                        />
                      </div>
                      <div className="form-group flex-1">
                        <label>Weight</label>
                        <input
                          type="number"
                          step="0.1"
                          value={crit.weight}
                          onChange={(e) => updateCriteriaField(index, 'weight', parseFloat(e.target.value) || 1)}
                          disabled={isObserver}
                        />
                      </div>
                      <div className="form-group" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minWidth: '60px' }}>
                        <label>Active</label>
                        <input
                          type="checkbox"
                          checked={crit.active !== false}
                          onChange={(e) => updateCriteriaField(index, 'active', e.target.checked)}
                          disabled={isObserver}
                          style={{ marginTop: '10px', transform: 'scale(1.2)' }}
                        />
                      </div>
                      <button onClick={() => deleteCriteria(index)} className="btn btn-danger btn-icon-only mt-6" disabled={isObserver}>
                        <Trash2 size={16} />
                      </button>
                    </div>
                    <div className="form-group mt-2">
                      <label>Description</label>
                      <textarea
                        value={crit.description}
                        onChange={(e) => updateCriteriaField(index, 'description', e.target.value)}
                        rows={2}
                        disabled={isObserver}
                      />
                    </div>
                  </div>
                ))}
              </div>

              <div className="panel-actions mt-6">
                <button onClick={handleSaveCriteria} className="btn btn-primary" disabled={isObserver}>
                  <Save size={16} /> Save Criteria Configuration
                </button>
              </div>
            </div>
          </div>
        )}

        {/* ================================================================= */}
        {/* TAB: PERSONAS */}
        {/* ================================================================= */}
        {activeTab === 'personas' && (
          <div className="tab-pane personas-pane">
            <div className="card">
              <div className="card-header-flex">
                <div>
                  <h4>AI Judges (Jury Panel)</h4>
                  <p className="dim-text text-sm">Configure personas that evaluate teams with their expertise and prompts.</p>
                </div>
                <button onClick={addPersona} className="btn btn-secondary btn-sm" disabled={isObserver}>
                  <Plus size={14} /> Add AI Judge
                </button>
              </div>

              <div className="personas-list mt-4">
                {personas.map((persona, index) => (
                  <div key={index} className="persona-item-card">
                    <div className="persona-header-inputs">
                      <div className="form-group flex-sm">
                        <label>Avatar / Emoji</label>
                        <input
                          type="text"
                          value={persona.avatar || '🤖'}
                          onChange={(e) => updatePersonaField(index, 'avatar', e.target.value)}
                          disabled={isObserver}
                        />
                      </div>
                      <div className="form-group flex-2">
                        <label>Name</label>
                        <input
                          type="text"
                          value={persona.name}
                          onChange={(e) => updatePersonaField(index, 'name', e.target.value)}
                          disabled={isObserver}
                        />
                      </div>
                      <div className="form-group flex-2">
                        <label>Role / Specialty</label>
                        <input
                          type="text"
                          value={persona.role}
                          onChange={(e) => updatePersonaField(index, 'role', e.target.value)}
                          disabled={isObserver}
                        />
                      </div>
                      <div className="form-group" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minWidth: '60px' }}>
                        <label>Active</label>
                        <input
                          type="checkbox"
                          checked={persona.active !== false}
                          onChange={(e) => updatePersonaField(index, 'active', e.target.checked)}
                          disabled={isObserver}
                          style={{ marginTop: '10px', transform: 'scale(1.2)' }}
                        />
                      </div>
                      <button onClick={() => deletePersona(index)} className="btn btn-danger btn-icon-only mt-6" disabled={isObserver}>
                        <Trash2 size={16} />
                      </button>
                    </div>

                    {/* Custom Avatar Image Uploader */}
                    <div style={{ display: 'flex', alignItems: 'center', gap: '16px', marginTop: '12px', padding: '12px', background: 'rgba(255,255,255,0.03)', borderRadius: '6px', border: '1px solid rgba(255,255,255,0.05)', marginBottom: '12px' }}>
                      <div className="persona-avatar-preview" style={{ width: '48px', height: '48px', borderRadius: '50%', background: 'rgba(255,255,255,0.05)', display: 'flex', alignItems: 'center', justifyContent: 'center', overflow: 'hidden', border: '1px solid rgba(255,255,255,0.1)', flexShrink: 0 }}>
                        {persona.avatar_image ? (
                          <img src={persona.avatar_image} alt={persona.name} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                        ) : (
                          <span style={{ fontSize: '1.8em' }}>{persona.avatar || '🤖'}</span>
                        )}
                      </div>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', flex: 1 }}>
                        <span style={{ fontSize: '0.85em', color: '#9ca3af', fontWeight: '500' }}>Custom Avatar Image (PNG/JPG, Max 500KB)</span>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap' }}>
                          <input
                            type="file"
                            accept="image/png, image/jpeg, image/jpg"
                            disabled={isObserver}
                            onChange={(e) => {
                              const file = e.target.files?.[0];
                              if (file) {
                                if (file.size > 500 * 1024) {
                                  alert("Image size exceeds 500KB limit. / 画像サイズが500KBの上限を超えています。");
                                  return;
                                }
                                const reader = new FileReader();
                                reader.onloadend = () => {
                                  updatePersonaField(index, 'avatar_image', reader.result as string);
                                };
                                reader.readAsDataURL(file);
                              }
                            }}
                            style={{ fontSize: '0.8em', maxWidth: '250px' }}
                          />
                          {persona.avatar_image && (
                            <button
                              type="button"
                              onClick={() => updatePersonaField(index, 'avatar_image', undefined)}
                              className="btn btn-danger btn-xs"
                              disabled={isObserver}
                            >
                              Remove Image
                            </button>
                          )}
                        </div>
                      </div>
                    </div>

                    <div className="form-group mt-2">
                      <label>Prompt Instruction / Evaluation Philosophy</label>
                      <textarea
                        value={persona.prompt || ''}
                        onChange={(e) => updatePersonaField(index, 'prompt', e.target.value)}
                        rows={4}
                        placeholder="Tell the AI how to act, what to focus on, and how to write criticism..."
                        disabled={isObserver}
                      />
                    </div>
                  </div>
                ))}
              </div>

              <div className="panel-actions mt-6">
                <button onClick={handleSavePersonas} className="btn btn-primary" disabled={isObserver}>
                  <Save size={16} /> Save Judges Configuration
                </button>
              </div>
            </div>
          </div>
        )}



        {/* ================================================================= */}
        {/* TAB: DEEP DIVE (Admin Private Q&A) */}
        {/* ================================================================= */}
        {activeTab === 'deep_dive' && (
          <div className="tab-pane deep-dive-pane">
            <div className="dive-selection-header">
              <div className="form-group select-team-group">
                <label>Select Team to Inspect</label>
                <select value={diveTeamId} onChange={(e) => setDiveTeamId(e.target.value)}>
                  <option value="">— Select Team —</option>
                  {teams.map((t) => (
                    <option key={t.team_id} value={t.team_id}>
                      {t.team_id} {t.product_name ? `(${t.product_name})` : ''}
                    </option>
                  ))}
                </select>
              </div>

              {diveTeamId && diveEvaluations.length > 0 && (
                <div className="form-group select-eval-group">
                  <label>Select Evaluation Record</label>
                  <select
                    value={selectedDiveEval?.id || ''}
                    onChange={(e) => {
                      const sel = diveEvaluations.find((ev) => ev.id === Number(e.target.value));
                      if (sel) setSelectedDiveEval(sel);
                    }}
                  >
                    {diveEvaluations.map((ev) => (
                      <option key={ev.id} value={ev.id}>
                        {ev.is_final ? '🏆 Final' : '💡 Consultation'} (
                        {ev.evaluated_at ? new Date(ev.evaluated_at).toLocaleString() : ''})
                      </option>
                    ))}
                  </select>
                </div>
              )}
            </div>

            {diveLoading ? (
              <div className="text-center py-8">
                <Loader2 size={32} className="animate-spin inline" />
                <p className="mt-2 dim-text">Loading evaluations...</p>
              </div>
            ) : diveTeamId && !selectedDiveEval ? (
              <div className="card text-center py-8">
                <FileText size={48} className="mx-auto dim-text" />
                <h4 className="mt-2">No Evaluations Records</h4>
                <p className="dim-text">This team has not submitted anything yet.</p>
              </div>
            ) : selectedDiveEval ? (
              <div className="dive-inspection-container mt-4">
                {/* AI Language Selection Tabs */}
                {languages.length > 1 && (
                  <div className="ai-language-tabs" style={{
                    display: 'flex',
                    gap: '8px',
                    marginBottom: '16px',
                    borderBottom: '1px solid #374151',
                    paddingBottom: '8px'
                  }}>
                    {languages.map((lang) => {
                      const key = normalizeLangToKey(lang);
                      const active = selectedAiLang === key;
                      return (
                        <button
                          key={lang}
                          type="button"
                          onClick={() => setSelectedAiLang(key)}
                          className={`ai-lang-tab-btn ${active ? 'active' : ''}`}
                          style={{
                            padding: '6px 12px',
                            borderRadius: '4px',
                            background: active ? '#4f46e5' : 'transparent',
                            color: active ? '#ffffff' : '#9ca3af',
                            border: active ? 'none' : '1px solid #4b5563',
                            fontSize: '0.85em',
                            cursor: 'pointer',
                          }}
                        >
                          {emojiMap[lang] || '🌐'} {lang}
                        </button>
                      );
                    })}
                  </div>
                )}

                <div className="dive-inspection-layout mt-4">
                  {/* Left Side: Score & Feedbacks */}
                  <div className="dive-score-feedback">
                    <div className="card">
                      <div className="card-header-flex">
                        <h4>Evaluation Score Details</h4>
                        <button
                          onClick={() => handleDeleteEvaluation(selectedDiveEval.id)}
                          className="btn btn-danger btn-sm"
                          disabled={isObserver}
                        >
                          <Trash2 size={14} /> Delete Record
                        </button>
                      </div>

                      <div className="dive-scores-meta mt-4">
                        <div className="meta-metric">
                          <span className="label">Overall Score</span>
                          <span className="value">{selectedDiveEval.impact_score.toFixed(1)}</span>
                        </div>
                        <div className="meta-metric">
                          <span className="label">Type</span>
                          <span className="value">
                            {selectedDiveEval.is_final ? 'Final' : 'Consultation'}
                          </span>
                        </div>
                      </div>

                      <h5 className="mt-6">Scores Breakdown</h5>
                      <div className="scores-list mt-2">
                        {Object.entries(JSON.parse(selectedDiveEval.scores_json || '{}')).map(([k, v]) => (
                          <div key={k} className="score-row">
                            <span className="criteria-name">
                              {k.split('_').map((w) => w.charAt(0).toUpperCase() + w.slice(1)).join(' ')}
                            </span>
                            <span className="score-value">{Number(v).toFixed(1)}/10</span>
                          </div>
                        ))}
                      </div>

                      <h5 className="mt-6">AI Summary</h5>
                      <p className="summary-text mt-2">
                        {
                          (() => {
                            const strengthsRisks = JSON.parse(selectedDiveEval.strengths_risks_json || '{}');
                            return strengthsRisks[`summary_${selectedAiLang}`] ||
                                   strengthsRisks[`summary_japanese`] ||
                                   strengthsRisks[`summary_english`] ||
                                   strengthsRisks[`summary_default`] ||
                                   'No summary available.';
                          })()
                        }
                      </p>
                    </div>
                  </div>

                  {/* Right Side: Private Admin chat with AI panel */}
                  <div className="dive-private-chat">
                    <div className="card h-full flex flex-column">
                      <div className="chat-header">
                        <h4>Jury Private Consultation</h4>
                        <p className="dim-text text-sm">
                          Discuss details of this evaluation with the AI judges. Teams cannot see this chat.
                        </p>
                      </div>

                      <div className="chat-thread-container mt-4 flex-grow">
                        <div className="chat-messages">
                          {adminChats.length === 0 ? (
                            <p className="dim-text text-center py-6">
                              No private discussion history. Ask questions below.
                            </p>
                          ) : (
                            adminChats.map((c) => {
                              const qa = c.qa_json || {};
                              const q = qa[`question_${selectedAiLang}`] ||
                                        qa[`question_japanese`] ||
                                        qa[`question_english`] ||
                                        c.question_ja ||
                                        c.question_en ||
                                        '';
                              const a = qa[`answer_${selectedAiLang}`] ||
                                        qa[`answer_japanese`] ||
                                        qa[`answer_english`] ||
                                        c.answer_ja ||
                                        c.answer_en ||
                                        '';

                              return (
                                <div key={c.id} className="chat-qa-pair">
                                  <div className="chat-message-bubble msg-team">
                                    <div className="msg-header">Admin (Private)</div>
                                    <p className="msg-content">{q}</p>
                                  </div>
                                  <div className="chat-message-bubble msg-judges">
                                    <div className="msg-header">AI Jury Panel</div>
                                    <p className="msg-content">{a || 'Jury is generating reply...'}</p>
                                  </div>
                                </div>
                              );
                            })
                          )}
                          {chatLoading && (
                            <div className="chat-message-bubble msg-judges chat-typing">
                              <Loader2 size={16} className="animate-spin" />
                              <span>Jury panel is discussing in secret...</span>
                            </div>
                          )}
                        </div>
                      </div>

                      <form onSubmit={handleSendAdminQuestion} className="chat-input-form mt-4">
                        <input
                          type="text"
                          value={adminQuestion}
                          onChange={(e) => setAdminQuestion(e.target.value)}
                          placeholder={isObserver ? "Private consult chat is read-only for observers" : "Ask the judges about their scores or reasoning..."}
                          disabled={chatLoading || isObserver}
                        />
                        <button type="submit" className="btn btn-primary" disabled={chatLoading || !adminQuestion.trim() || isObserver}>
                          <Send size={16} />
                        </button>
                      </form>
                    </div>
                  </div>
                </div>
              </div>
            ) : (
              <div className="card text-center py-8">
                <Search size={48} className="mx-auto dim-text" />
                <h4 className="mt-2">Select a Team</h4>
                <p className="dim-text">Please pick a team above to review evaluations and chat with judges.</p>
              </div>
            )}
          </div>
        )}



        {/* ================================================================= */}
        {/* TAB: SETTINGS */}
        {/* ================================================================= */}
        {activeTab === 'settings' && (
          <div className="tab-pane settings-pane">
            <div className="settings-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(350px, 1fr))', gap: '24px', alignItems: 'start' }}>
              
              {/* 左カラム (AI System Group) */}
              <div className="settings-col-left" style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
                
                {/* 🤖 AI Jury Engine Configuration */}
                <div className="card">
                  <h4>{t('admin.ai_jury_engine_title')}</h4>
                  <p className="dim-text text-sm">{t('admin.ai_jury_engine_desc')}</p>
                  
                  <div className="vertical-form mt-4">
                    {/* LLM Provider */}
                    <div className="form-group">
                      <label>{t('admin.llm_provider_label')}</label>
                      <select
                        value={llmProvider}
                        onChange={(e) => handleProviderChange(e.target.value)}
                        disabled={isObserver}
                      >
                        <option value="gemini">Google Gemini</option>
                        <option value="openai">OpenAI</option>
                        <option value="anthropic">Anthropic</option>
                      </select>
                    </div>

                    {/* API Key Form */}
                    <div className="form-group mt-2">
                      <label>
                        {t('admin.api_key_label', { provider: llmProvider.toUpperCase() })} (Optional Override)
                      </label>
                      <div className="api-key-input-row" style={{ display: 'flex', gap: '8px' }}>
                        <input
                          type="password"
                          value={apiKeyInput}
                          onChange={(e) => setApiKeyInput(e.target.value)}
                          placeholder={
                            isObserver
                              ? "API Key hidden for observers"
                              : (llmProvider === 'gemini' && hasGeminiApiKey) ||
                                (llmProvider === 'openai' && hasOpenaiApiKey) ||
                                (llmProvider === 'anthropic' && hasAnthropicApiKey)
                              ? "API Key is set (Enter new key to change)"
                              : "Leave blank to use server environment key"
                          }
                          disabled={isObserver}
                          style={{ flexGrow: 1 }}
                        />
                        <button
                          type="button"
                          onClick={handleVerifyKey}
                          className="btn btn-secondary"
                          disabled={isObserver || verifyingKey || !apiKeyInput.trim()}
                          style={{ whiteSpace: 'nowrap' }}
                        >
                          {verifyingKey ? (
                            <>
                              <Loader2 size={14} className="animate-spin inline" style={{ marginRight: '4px' }} />
                              {t('admin.verifying')}
                            </>
                          ) : t('admin.verify_save_key')}
                        </button>
                      </div>
                      
                      {/* Key Configured Badge */}
                      {((llmProvider === 'gemini' && hasGeminiApiKey) ||
                        (llmProvider === 'openai' && hasOpenaiApiKey) ||
                        (llmProvider === 'anthropic' && hasAnthropicApiKey)) && (
                        <p className="text-xs text-success mt-1" style={{ color: 'var(--success)', marginTop: '4px' }}>
                          {t('admin.key_configured', { provider: llmProvider.toUpperCase() })}
                        </p>
                      )}
                    </div>

                    {/* Model Selector */}
                    <div className="form-group mt-2">
                      <label>{t('admin.model_label', { provider: llmProvider.toUpperCase() })}</label>
                      <select
                        value={
                          llmProvider === 'gemini'
                            ? geminiModel
                            : llmProvider === 'openai'
                            ? openaiModel
                            : anthropicModel
                        }
                        onChange={(e) => handleModelChange(e.target.value)}
                        disabled={
                          isObserver ||
                          (llmProvider === 'gemini' && !hasGeminiApiKey && geminiAvailableModels.length === 0) ||
                          (llmProvider === 'openai' && !hasOpenaiApiKey && openaiAvailableModels.length === 0) ||
                          (llmProvider === 'anthropic' && !hasAnthropicApiKey && anthropicAvailableModels.length === 0)
                        }
                      >
                        {llmProvider === 'gemini' ? (
                          geminiAvailableModels.length === 0 ? (
                            <option value="">— Verify API Key First —</option>
                          ) : (
                            geminiAvailableModels.map((m) => <option key={m} value={m}>{m}</option>)
                          )
                        ) : llmProvider === 'openai' ? (
                          openaiAvailableModels.length === 0 ? (
                            <option value="">— Verify API Key First —</option>
                          ) : (
                            openaiAvailableModels.map((m) => <option key={m} value={m}>{m}</option>)
                          )
                        ) : (
                          anthropicAvailableModels.length === 0 ? (
                            <option value="">— Verify API Key First —</option>
                          ) : (
                            anthropicAvailableModels.map((m) => <option key={m} value={m}>{m}</option>)
                          )
                        )}
                      </select>
                    </div>
                  </div>
                </div>

                {/* Configured AI Output Languages */}
                <div className="card">
                  <h4>Configured AI Output Languages</h4>
                  <p className="dim-text text-sm">
                    Add language formats in which the AI judges will respond. English and Japanese are built-in.
                  </p>

                  <div className="languages-setup mt-4">
                    <div className="languages-list">
                      {languages.map((l) => (
                        <div key={l} className="lang-tag">
                          <span>{l}</span>
                          <button onClick={() => handleRemoveLanguage(l)} className="btn-remove" disabled={isObserver}>
                            ×
                          </button>
                        </div>
                      ))}
                    </div>

                    <div className="add-language-form mt-4">
                      <div className="form-group inline-flex">
                        <input
                          type="text"
                          value={newLang}
                          onChange={(e) => setNewLang(e.target.value)}
                          placeholder="e.g. Thai, French, Spanish"
                          disabled={isObserver}
                        />
                        <button onClick={handleAddLanguage} className="btn btn-secondary" disabled={isObserver}>
                          Add Language
                        </button>
                      </div>
                    </div>
                  </div>

                  <div className="panel-actions mt-6">
                    <button onClick={handleSaveLanguages} className="btn btn-primary" disabled={isObserver}>
                      <Save size={16} /> Save Languages Settings
                    </button>
                  </div>
                </div>
              </div>
              
              {/* 右カラム (Rules & Security Group) */}
              <div className="settings-col-right" style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
                
                {/* ⚖️ Project Templates & Rules */}
                <div className="card">
                  <h4>{t('admin.rules_security_title')}</h4>
                  
                  {/* Configuration Template (Top) */}
                  <div className="template-import-section" style={{ marginTop: '16px', marginBottom: '24px' }}>
                    <h5 style={{ fontSize: '1em', fontWeight: '600', marginBottom: '8px' }}>{t('admin.import_template_title')}</h5>
                    <p className="dim-text text-xs" style={{ marginBottom: '12px' }}>{t('admin.import_template_desc')}</p>
                    
                    {/* Preset Templates */}
                    <form onSubmit={handleApplyPresetTemplate} className="vertical-form">
                      <div className="form-group">
                        <label>{t('admin.preset_template_label')}</label>
                        <select
                          value={selectedTemplate}
                          onChange={(e) => setSelectedTemplate(e.target.value)}
                          disabled={isObserver}
                        >
                          <option value="">{t('admin.select_preset_placeholder')}</option>
                          {Object.entries(templates).map(([key, tpl]) => (
                            <option key={key} value={key}>
                              {tpl.name}
                            </option>
                          ))}
                        </select>
                      </div>
                      {selectedTemplate && templates[selectedTemplate] && (
                        <p className="template-desc dim-text text-xs mt-1">
                          {templates[selectedTemplate].description}
                        </p>
                      )}
                      <button type="submit" className="btn btn-secondary mt-2" disabled={isObserver || !selectedTemplate}>
                        {t('admin.apply_preset_btn')}
                      </button>
                    </form>

                    <hr className="my-4" style={{ margin: '16px 0', border: 'none', borderTop: '1px solid var(--border-color)' }} />

                    {/* Custom Template URL */}
                    <form onSubmit={handleImportTemplate} className="vertical-form">
                      <div className="form-group">
                        <label>{t('admin.custom_url_label')}</label>
                        <input
                          type="url"
                          value={importUrl}
                          onChange={(e) => setImportUrl(e.target.value)}
                          placeholder="https://example.com/judgie-template.json"
                          disabled={isObserver}
                          required
                        />
                      </div>
                      <button type="submit" className="btn btn-primary mt-2" disabled={isObserver}>
                        {t('admin.import_url_btn')}
                      </button>
                    </form>
                  </div>

                  <hr style={{ margin: '24px 0', border: 'none', borderTop: '1px solid var(--border-color)' }} />

                  {/* Project Rules & Rulesets (Bottom) */}
                  <div className="rulesets-section">
                    <h5 style={{ fontSize: '1em', fontWeight: '600', marginBottom: '8px' }}>Hackathon Rules & Rulesets</h5>
                    
                    <div className="vertical-form mt-2">
                      <div className="form-group">
                        <label>Re-Evaluation Context Mode</label>
                        <select
                          value={projectSettings.re_evaluation_context_mode}
                          onChange={(e) =>
                            setProjectSettings({
                              ...projectSettings,
                              re_evaluation_context_mode: e.target.value,
                            })
                          }
                          disabled={isObserver}
                        >
                          <option value="cumulative">Cumulative (AI remembers previous uploads)</option>
                          <option value="single">Single (Each upload is evaluated independently)</option>
                        </select>
                      </div>

                      <div className="form-group">
                        <label>Max Q&A Discussion Turns per Evaluation</label>
                        <input
                          type="number"
                          value={projectSettings.max_qa_turns}
                          onChange={(e) =>
                            setProjectSettings({
                              ...projectSettings,
                              max_qa_turns: parseInt(e.target.value) || 1,
                            })
                          }
                          disabled={isObserver}
                        />
                      </div>

                      <div className="form-group">
                        <label>Max Consultations allowed per Team</label>
                        <input
                          type="number"
                          value={projectSettings.max_consultations}
                          onChange={(e) =>
                            setProjectSettings({
                              ...projectSettings,
                              max_consultations: parseInt(e.target.value) || 3,
                            })
                          }
                          disabled={isObserver}
                        />
                      </div>

                      <div className="form-checkbox">
                        <input
                          type="checkbox"
                          id="video-upload-chk"
                          checked={projectSettings.video_upload_enabled}
                          onChange={(e) =>
                            setProjectSettings({
                              ...projectSettings,
                              video_upload_enabled: e.target.checked,
                            })
                          }
                          disabled={isObserver}
                        />
                        <label htmlFor="video-upload-chk">Enable Video Upload (MP4/MOV)</label>
                      </div>
                    </div>

                    <div className="panel-actions mt-6">
                      <button onClick={handleSaveSettings} className="btn btn-primary" disabled={isObserver}>
                        <Save size={16} /> Save Rules Configurations
                      </button>
                    </div>
                  </div>
                </div>

                {/* 🔐 Security & Authentication */}
                <div className="card">
                  <h4>{t('admin.security_auth_title')}</h4>
                  
                  {/* OIDC Settings */}
                  <div className="oidc-section" style={{ marginBottom: '24px' }}>
                    <h5 style={{ fontSize: '1em', fontWeight: '600', marginBottom: '8px' }}>OIDC Authentication Settings (SSO)</h5>
                    <p className="dim-text text-xs" style={{ marginBottom: '12px' }}>
                      Configure Single Sign-On (SSO) for participants and admins. When enabled, local password login is disabled for teams (Initial admins can still log in using the password screen).
                    </p>
                    <form onSubmit={handleSaveOidc} className="vertical-form">
                      <div className="form-checkbox">
                        <input
                          type="checkbox"
                          id="oidc-enabled-chk"
                          checked={oidcConfig.oidc_enabled}
                          onChange={(e) =>
                            setOidcConfig({
                              ...oidcConfig,
                              oidc_enabled: e.target.checked,
                            })
                          }
                          disabled={isObserver}
                        />
                        <label htmlFor="oidc-enabled-chk">Enable OIDC (SSO) Authentication</label>
                      </div>

                      <div className="form-group">
                        <label>Issuer URL</label>
                        <input
                          type="url"
                          value={oidcConfig.oidc_issuer}
                          onChange={(e) => setOidcConfig({ ...oidcConfig, oidc_issuer: e.target.value })}
                          placeholder="https://accounts.google.com"
                          disabled={isObserver}
                          required
                        />
                      </div>

                      <div className="form-group">
                        <label>Client ID</label>
                        <input
                          type="text"
                          value={oidcConfig.oidc_client_id}
                          onChange={(e) => setOidcConfig({ ...oidcConfig, oidc_client_id: e.target.value })}
                          placeholder="Enter OIDC Client ID"
                          disabled={isObserver}
                          required
                        />
                      </div>

                      <div className="form-group">
                        <label>Client Secret</label>
                        <input
                          type="password"
                          value={oidcConfig.oidc_client_secret}
                          onChange={(e) => setOidcConfig({ ...oidcConfig, oidc_client_secret: e.target.value })}
                          placeholder={oidcConfig.has_client_secret ? "•••••••• (Saved. Enter new secret to change)" : "Enter OIDC Client Secret"}
                          disabled={isObserver}
                        />
                      </div>

                      <div className="form-group">
                        <label>Redirect URI (Callback)</label>
                        <input
                          type="text"
                          value={oidcConfig.oidc_redirect_uri}
                          onChange={(e) => setOidcConfig({ ...oidcConfig, oidc_redirect_uri: e.target.value })}
                          placeholder="Leave blank to use default (e.g. http://localhost:5173/login/callback)"
                          disabled={isObserver}
                        />
                      </div>

                      <div className="form-group">
                        <label>Allowed Email Domains (Comma-separated)</label>
                        <input
                          type="text"
                          value={oidcConfig.oidc_allowed_domains}
                          onChange={(e) => setOidcConfig({ ...oidcConfig, oidc_allowed_domains: e.target.value })}
                          placeholder="e.g. company.com, school.edu"
                          disabled={isObserver}
                        />
                      </div>

                      <div className="form-group">
                        <label>Allowed Individual Emails (Comma-separated)</label>
                        <input
                          type="text"
                          value={oidcConfig.oidc_allowed_emails}
                          onChange={(e) => setOidcConfig({ ...oidcConfig, oidc_allowed_emails: e.target.value })}
                          placeholder="e.g. admin@gmail.com, guest@company.com"
                          disabled={isObserver}
                        />
                      </div>

                      <button type="submit" className="btn btn-primary" disabled={isObserver || savingOidc}>
                        {savingOidc ? 'Saving...' : 'Save OIDC Settings'}
                      </button>
                    </form>
                  </div>

                  <hr style={{ margin: '24px 0', border: 'none', borderTop: '1px solid var(--border-color)' }} />

                  {/* Change Admin Password */}
                  <div className="change-admin-pass-section">
                    <h5 style={{ fontSize: '1em', fontWeight: '600', marginBottom: '8px' }}>Change Admin Password</h5>
                    <form onSubmit={handleChangeAdminPass} className="vertical-form mt-2">
                      <div className="form-group">
                        <label>New Password</label>
                        <input
                          type="password"
                          value={newAdminPass}
                          onChange={(e) => setNewAdminPass(e.target.value)}
                          disabled={isObserver}
                          required
                        />
                      </div>
                      <div className="form-group">
                        <label>Confirm New Password</label>
                        <input
                          type="password"
                          value={confirmAdminPass}
                          onChange={(e) => setConfirmAdminPass(e.target.value)}
                          disabled={isObserver}
                          required
                        />
                      </div>
                      <button type="submit" className="btn btn-primary" disabled={isObserver}>
                        Change Password
                      </button>
                    </form>
                  </div>
                </div>

              </div>

            </div>
          </div>
        )}

        {/* ================================================================= */}
        {/* TAB: EXPORT / DATA MANAGEMENT */}
        {/* ================================================================= */}
        {activeTab === 'export' && (
          <div className="tab-pane export-pane">
            <div className="settings-grid">
              {/* Export Panel */}
              <div className="card">
                <h4>Export Project Data</h4>
                <p className="dim-text text-sm">Download evaluating results and reports.</p>

                <div className="export-actions-list mt-4">
                  <div className="export-action-item">
                    <div>
                      <strong>{t('admin.export_all_markdown')}</strong>
                      <p className="dim-text text-xs">{t('admin.export_all_markdown_desc')}</p>
                    </div>
                    {isObserver ? (
                      <button className="btn btn-secondary btn-sm" disabled>
                        Admin Only
                      </button>
                    ) : (
                      <a
                        href="/api/export/markdown-zip/all"
                        download
                        className="btn btn-secondary btn-sm"
                      >
                        <Download size={14} /> {t('admin.download_zip')}
                      </a>
                    )}
                  </div>

                  <div className="export-action-item mt-4">
                    <div>
                      <strong>{t('admin.export_db')}</strong>
                      <p className="dim-text text-xs">{t('admin.export_db_desc')}</p>
                    </div>
                    {isObserver ? (
                      <button className="btn btn-secondary btn-sm" disabled>
                        Admin Only
                      </button>
                    ) : (
                      <a
                        href="/api/export/notebooklm-zip"
                        download
                        className="btn btn-secondary btn-sm"
                      >
                        <Download size={14} /> {t('admin.download_zip')}
                      </a>
                    )}
                  </div>

                  <div className="export-action-item mt-4">
                    <div>
                      <strong>{t('admin.export_template')}</strong>
                      <p className="dim-text text-xs">{t('admin.export_template_desc')}</p>
                    </div>
                    <a
                      href="/api/export/template"
                      download
                      className="btn btn-secondary btn-sm"
                    >
                      <Download size={14} /> {t('admin.export_json')}
                    </a>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
