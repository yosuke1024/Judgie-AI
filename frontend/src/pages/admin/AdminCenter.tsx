import React, { useState, useEffect, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { useAuth } from '@/contexts/AuthContext';
import {
  teamsApi,
  evaluationsApi,
  settingsApi,
  chatApi,
  exportApi,
} from '@/api/client';
import {
  Users,
  Sliders,
  Shield,
  BarChart3,
  Search,
  Languages,
  Settings as SettingsIcon,
  Download,
  Plus,
  Trash2,
  Lock,
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

interface TeamItem {
  team_id: string;
  role: string;
  product_name: string | null;
  team_name: string | null;
  one_liner: string | null;
  is_active?: boolean;
}

interface ScoreboardEntry {
  team_id: string;
  product_name: string | null;
  team_name: string | null;
  one_liner: string | null;
  total_score: number;
  status: string;
  consults: number;
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
  const [newTeamPass, setNewTeamPass] = useState('');
  const [newTeamRole, setNewTeamRole] = useState('team');
  const [bulkCsv, setBulkCsv] = useState('');
  const [editingPassTeam, setEditingPassTeam] = useState<string | null>(null);
  const [newPassVal, setNewPassVal] = useState('');

  // --- Tab 2: Criteria ---
  const [criteriaList, setCriteriaList] = useState<any[]>([]);

  // --- Tab 3: Personas ---
  const [personas, setPersonas] = useState<any[]>([]);

  // --- Tab 4: Scoreboard ---
  const [scores, setScores] = useState<ScoreboardEntry[]>([]);

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
  const [geminiConfig, setGeminiConfig] = useState({ api_key: '', model: '', api_tier: 'free' });
  const [hasApiKey, setHasApiKey] = useState(false);
  const [availableModels, setAvailableModels] = useState<string[]>([]);
  const [verifyingKey, setVerifyingKey] = useState(false);
  const [projectSettings, setProjectSettings] = useState({
    re_evaluation_context_mode: 'cumulative',
    max_qa_turns: 1,
    max_consultations: 3,
    video_upload_enabled: true,
  });
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

  const loadScoreboard = useCallback(async () => {
    try {
      const data = await evaluationsApi.getScoreboard();
      setScores(data);
    } catch (err: any) {
      console.error(err);
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
      const gemini = await settingsApi.getGemini() as { has_api_key?: boolean; model?: string; api_tier?: string; available_models?: string[] };
      const project = await settingsApi.getProject();
      setGeminiConfig({
        api_key: '',
        model: gemini.model || '',
        api_tier: gemini.api_tier || 'free',
      });
      setHasApiKey(!!gemini.has_api_key);
      setAvailableModels(gemini.available_models || []);
      setProjectSettings({
        re_evaluation_context_mode: (project.re_evaluation_context_mode as string) || 'cumulative',
        max_qa_turns: Number(project.max_qa_turns) || 1,
        max_consultations: Number(project.max_consultations) || 3,
        video_upload_enabled: project.video_upload_enabled !== false,
      });
    } catch (err: any) {
      console.error(err);
    }
  }, []);

  // Fetch initial tab data on mount or tab change
  useEffect(() => {
    setError('');
    if (activeTab === 'teams') loadTeams();
    else if (activeTab === 'criteria') loadCriteria();
    else if (activeTab === 'personas') loadPersonas();
    else if (activeTab === 'scoreboard') loadScoreboard();
    else if (activeTab === 'deep_dive') loadLanguages();
    else if (activeTab === 'languages') loadLanguages();
    else if (activeTab === 'settings') {
      loadSettings();
      loadTemplates();
    }
  }, [activeTab, loadTeams, loadCriteria, loadPersonas, loadScoreboard, loadLanguages, loadSettings, loadTemplates]);

  // --- Handlers: Teams Tab ---
  const handleCreateTeam = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTeamId || !newTeamPass) return;
    try {
      setError('');
      await teamsApi.create({
        team_id: newTeamId,
        passcode: newTeamPass,
        role: newTeamRole,
      });
      setNewTeamId('');
      setNewTeamPass('');
      showSuccess(`Team ${newTeamId} created successfully!`);
      loadTeams();
    } catch (err: any) {
      setError(err.message || 'Failed to create team.');
    }
  };

  const handleBulkCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!bulkCsv) return;
    try {
      setError('');
      const res: any = await teamsApi.bulkCreate(bulkCsv);
      setBulkCsv('');
      if (res && typeof res.created === 'number') {
        showSuccess(`CSV Bulk import complete! Created: ${res.created}, Skipped: ${res.skipped}`);
      } else {
        showSuccess('CSV Bulk import complete!');
      }
      loadTeams();
    } catch (err: any) {
      setError(err.message || 'Bulk creation failed.');
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

  const handleUpdateTeamRole = async (teamId: string, role: string) => {
    try {
      await teamsApi.updateRole(teamId, role);
      showSuccess(`Role updated for ${teamId}`);
      loadTeams();
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleUpdateTeamPasscode = async (teamId: string) => {
    if (!newPassVal.trim()) return;
    try {
      setError('');
      await teamsApi.updatePasscode(teamId, newPassVal.trim());
      showSuccess(`Passcode reset for team '${teamId}'`);
      setEditingPassTeam(null);
      setNewPassVal('');
    } catch (err: any) {
      setError(err.message || 'Failed to reset passcode.');
    }
  };

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
      await chatApi.submitAdminQuestion(selectedDiveEval.id, q);
      await fetchAdminChat(selectedDiveEval.id);
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
      await settingsApi.updateGemini(geminiConfig);
      showSuccess('Project settings updated.');
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleChangeAdminPass = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newAdminPass) return;
    if (newAdminPass !== confirmAdminPass) {
      setError('New passcodes do not match.');
      return;
    }
    try {
      setError('');
      await settingsApi.resetAdminPasscode(newAdminPass);
      setNewAdminPass('');
      setConfirmAdminPass('');
      showSuccess('Admin passcode changed successfully!');
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleVerifyKey = async () => {
    if (!geminiConfig.api_key.trim()) return;
    try {
      setError('');
      setVerifyingKey(true);
      await settingsApi.updateGemini({ api_key: geminiConfig.api_key.trim() });
      showSuccess('API key verified & saved successfully.');
      await loadSettings();
    } catch (err: any) {
      setError(err.message || 'Invalid API key or failed to verify.');
    } finally {
      setVerifyingKey(false);
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
          className={`tab-btn ${activeTab === 'scoreboard' ? 'active' : ''}`}
          onClick={() => setActiveTab('scoreboard')}
        >
          <BarChart3 size={16} />
          {t('admin.scoreboard_tab')}
        </button>
        <button
          className={`tab-btn ${activeTab === 'deep_dive' ? 'active' : ''}`}
          onClick={() => setActiveTab('deep_dive')}
        >
          <Search size={16} />
          {t('admin.deep_dive_tab')}
        </button>
        <button
          className={`tab-btn ${activeTab === 'languages' ? 'active' : ''}`}
          onClick={() => setActiveTab('languages')}
        >
          <Languages size={16} />
          {t('admin.languages_tab')}
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
                        required
                      />
                    </div>
                    <div className="form-group">
                      <label>Passcode</label>
                      <input
                        type="text"
                        value={newTeamPass}
                        onChange={(e) => setNewTeamPass(e.target.value)}
                        placeholder="Secret passcode"
                        disabled={isObserver}
                        required
                      />
                    </div>
                    <div className="form-group">
                      <label>Role</label>
                      <select value={newTeamRole} onChange={(e) => setNewTeamRole(e.target.value)} disabled={isObserver}>
                        <option value="team">Team (Participant)</option>
                        <option value="observer">Observer (Read-only)</option>
                      </select>
                    </div>
                    <button type="submit" className="btn btn-primary" disabled={isObserver}>
                      <Plus size={16} /> Add Team
                    </button>
                  </form>
                </div>

                <div className="card mt-4">
                  <h4>Bulk Import (CSV)</h4>
                  <form onSubmit={handleBulkCreate} className="vertical-form">
                    <div className="form-group">
                      <label>CSV Content (team_id,passcode,role)</label>
                      <textarea
                        value={bulkCsv}
                        onChange={(e) => setBulkCsv(e.target.value)}
                        placeholder="team-01,secret123,team&#10;team-02,abc456,observer"
                        rows={6}
                        disabled={isObserver}
                        required
                      />
                    </div>
                    <button type="submit" className="btn btn-primary" disabled={isObserver}>
                      <Upload size={16} /> Import Teams
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
                          <th>Role</th>
                          <th>Product Name</th>
                          <th>Passcode</th>
                          <th>Active</th>
                          <th>Actions</th>
                        </tr>
                      </thead>
                      <tbody>
                        {teams.map((t) => (
                          <tr key={t.team_id}>
                            <td><strong>{t.team_id}</strong></td>
                            <td>
                              <select
                                value={t.role}
                                onChange={(e) => handleUpdateTeamRole(t.team_id, e.target.value)}
                                className="table-select"
                                disabled={isObserver}
                              >
                                <option value="team">TEAM</option>
                                <option value="observer">OBSERVER</option>
                              </select>
                            </td>
                            <td>{t.product_name || <span className="dim-text">—</span>}</td>
                            <td>
                              {editingPassTeam === t.team_id ? (
                                <div className="inline-edit-passcode">
                                  <input
                                    type="text"
                                    value={newPassVal}
                                    onChange={(e) => setNewPassVal(e.target.value)}
                                    placeholder="New passcode"
                                    className="table-input"
                                  />
                                  <button
                                    onClick={() => handleUpdateTeamPasscode(t.team_id)}
                                    className="btn btn-success btn-xs"
                                  >
                                    Save
                                  </button>
                                  <button
                                    onClick={() => setEditingPassTeam(null)}
                                    className="btn btn-ghost btn-xs"
                                  >
                                    Cancel
                                  </button>
                                </div>
                              ) : (
                                <button
                                  onClick={() => {
                                    setEditingPassTeam(t.team_id);
                                    setNewPassVal('');
                                  }}
                                  className="btn btn-ghost btn-xs btn-lock"
                                  disabled={isObserver}
                                >
                                  <Lock size={12} /> Reset Passcode
                                </button>
                              )}
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
                            <td colSpan={6} className="text-center dim-text">
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
        {/* TAB: SCOREBOARD */}
        {/* ================================================================= */}
        {activeTab === 'scoreboard' && (
          <div className="tab-pane scoreboard-pane">
            <div className="card">
              <div className="card-header-flex">
                <h4>Scoreboard Dashboard</h4>
                <button onClick={loadScoreboard} className="btn btn-ghost btn-sm">
                  <RefreshCw size={14} /> Refresh Rankings
                </button>
              </div>

              <div className="table-wrapper mt-4">
                <table className="admin-table">
                  <thead>
                    <tr>
                      <th>Rank</th>
                      <th>Team ID</th>
                      <th>Product Info</th>
                      <th>Consultations</th>
                      <th>Status</th>
                      <th>Final Score</th>
                    </tr>
                  </thead>
                  <tbody>
                    {scores.map((s, idx) => (
                      <tr key={s.team_id}>
                        <td><strong>#{idx + 1}</strong></td>
                        <td><strong>{s.team_id}</strong></td>
                        <td>
                          <div>
                            <strong>{s.product_name || 'No Product Name'}</strong>
                            {s.team_name && <div className="text-xs dim-text">{s.team_name}</div>}
                          </div>
                        </td>
                        <td>{s.consults}</td>
                        <td>
                          <span
                            className={`status-badge ${
                              s.status.includes('Final') ? 'status-final' : 'status-progress'
                            }`}
                          >
                            {s.status}
                          </span>
                        </td>
                        <td className="score-cell">
                          <strong>{s.total_score.toFixed(1)}</strong>
                        </td>
                      </tr>
                    ))}
                    {scores.length === 0 && (
                      <tr>
                        <td colSpan={6} className="text-center dim-text">
                          No team submissions yet.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
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
                  {teams.filter((t) => t.role === 'team').map((t) => (
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
        {/* TAB: LANGUAGES */}
        {/* ================================================================= */}
        {activeTab === 'languages' && (
          <div className="tab-pane languages-pane">
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
        )}

        {/* ================================================================= */}
        {/* TAB: SETTINGS */}
        {/* ================================================================= */}
        {activeTab === 'settings' && (
          <div className="tab-pane settings-pane">
            <div className="settings-grid">
              {/* Import Panel */}
              <div className="card">
                <h4>{t('admin.import_template_title')}</h4>
                <p className="dim-text text-sm">{t('admin.import_template_desc')}</p>

                {/* 1. Preset Templates Import */}
                <form onSubmit={handleApplyPresetTemplate} className="vertical-form mt-4">
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

                <hr className="my-6" style={{ margin: '24px 0', border: 'none', borderTop: '1px solid var(--border-color)' }} />

                {/* 2. Custom JSON URL Import */}
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

              {/* Project settings */}
              <div className="card">
                <h4>Hackathon Rules & Rulesets</h4>
                <div className="vertical-form mt-4">
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

                <h4 className="mt-6">Gemini AI Configuration</h4>
                <div className="vertical-form mt-2">
                  <div className="form-group">
                    <label>Gemini API Key (Optional Override)</label>
                    <div className="api-key-input-row" style={{ display: 'flex', gap: '8px' }}>
                      <input
                        type="password"
                        value={geminiConfig.api_key}
                        onChange={(e) => setGeminiConfig({ ...geminiConfig, api_key: e.target.value })}
                        placeholder={isObserver ? "API Key hidden for observers" : (hasApiKey ? "API Key is set (Enter new key to change)" : "Leave blank to use server environment key")}
                        disabled={isObserver}
                        style={{ flexGrow: 1 }}
                      />
                      <button
                        type="button"
                        onClick={handleVerifyKey}
                        className="btn btn-secondary"
                        disabled={isObserver || verifyingKey || !geminiConfig.api_key.trim()}
                        style={{ whiteSpace: 'nowrap' }}
                      >
                        {verifyingKey ? (
                          <>
                            <Loader2 size={14} className="animate-spin inline" style={{ marginRight: '4px' }} />
                            Verifying...
                          </>
                        ) : 'Verify & Save Key'}
                      </button>
                    </div>
                    {hasApiKey && (
                      <p className="text-xs text-success mt-1" style={{ color: 'var(--success)', marginTop: '4px' }}>
                        ✓ Gemini API Key is configured.
                      </p>
                    )}
                  </div>

                  <div className="form-group">
                    <label>Gemini Model</label>
                    <select
                      value={geminiConfig.model}
                      onChange={(e) => setGeminiConfig({ ...geminiConfig, model: e.target.value })}
                      disabled={isObserver || !hasApiKey || availableModels.length === 0}
                    >
                      {availableModels.length === 0 ? (
                        <option value="">— Verify API Key First —</option>
                      ) : (
                        availableModels.map((m) => (
                          <option key={m} value={m}>
                            {m}
                          </option>
                        ))
                      )}
                    </select>
                  </div>
                </div>

                <div className="panel-actions mt-6">
                  <button onClick={handleSaveSettings} className="btn btn-primary" disabled={isObserver}>
                    <Save size={16} /> Save Configurations
                  </button>
                </div>
              </div>

              {/* Change Admin Password */}
              <div className="card">
                <h4>Change Admin Passcode</h4>
                <form onSubmit={handleChangeAdminPass} className="vertical-form mt-4">
                  <div className="form-group">
                    <label>New Passcode</label>
                    <input
                      type="password"
                      value={newAdminPass}
                      onChange={(e) => setNewAdminPass(e.target.value)}
                      disabled={isObserver}
                      required
                    />
                  </div>
                  <div className="form-group">
                    <label>Confirm New Passcode</label>
                    <input
                      type="password"
                      value={confirmAdminPass}
                      onChange={(e) => setConfirmAdminPass(e.target.value)}
                      disabled={isObserver}
                      required
                    />
                  </div>
                  <button type="submit" className="btn btn-primary" disabled={isObserver}>
                    Change Passcode
                  </button>
                </form>
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
