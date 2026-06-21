import React, { useState, useEffect, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { useAuth } from '@/contexts/AuthContext';
import { teamsApi, evaluationsApi, submissionsApi, chatApi } from '@/api/client';
import {
  Upload,
  FileText,
  MessageSquare,
  User as UserIcon,
  Save,
  CheckCircle,
  AlertTriangle,
  Send,
  Loader2,
  Clock,
  Sparkles,
} from 'lucide-react';
import {
  Radar,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  ResponsiveContainer,
} from 'recharts';

interface EvaluationItem {
  id: number;
  team_id: string;
  scores_json: string;
  impact_score: number;
  strengths_risks_json: string;
  qa_json: string | null;
  is_final: boolean;
  source_text: string | null;
  evaluated_at: string | null;
}

interface ChatMessageItem {
  sender: string;
  message_json: string | Record<string, any>;
  created_at?: string;
}

export default function TeamDashboard() {
  const { t, i18n } = useTranslation();
  const { user, refreshUser } = useAuth();

  // Profile Form States
  const [productName, setProductName] = useState(user?.product_name || '');
  const [teamName, setTeamName] = useState(user?.team_name || '');
  const [oneLiner, setOneLiner] = useState(user?.one_liner || '');
  const [profileSaving, setProfileSaving] = useState(false);
  const [profileSuccess, setProfileSuccess] = useState(false);

  // Upload States
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [isFinalUpload, setIsFinalUpload] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState('');
  const [uploadSuccess, setUploadSuccess] = useState(false);

  // Evaluation & History States
  const [evaluations, setEvaluations] = useState<EvaluationItem[]>([]);
  const [selectedEval, setSelectedEval] = useState<EvaluationItem | null>(null);
  const [evalLoading, setEvalLoading] = useState(true);

  // Q&A Chat States
  const [chatMessages, setChatMessages] = useState<ChatMessageItem[]>([]);
  const [newQuestion, setNewQuestion] = useState('');
  const [chatLoading, setChatLoading] = useState(false);
  const [chatError, setChatError] = useState('');

  // Local state update when user profile loads
  useEffect(() => {
    if (user) {
      setProductName(user.product_name || '');
      setTeamName(user.team_name || '');
      setOneLiner(user.one_liner || '');
    }
  }, [user]);

  // Fetch evaluation history
  const fetchHistory = useCallback(async () => {
    if (!user) return;
    try {
      setEvalLoading(true);
      const data = (await evaluationsApi.getTeamEvaluations(user.team_id)) as EvaluationItem[];
      // Sort evaluations: latest first
      const sorted = [...data].sort((a, b) => b.id - a.id);
      setEvaluations(sorted);
      
      // Auto-select the latest evaluation if none selected, or keep the currently selected one
      if (sorted.length > 0) {
        if (!selectedEval) {
          setSelectedEval(sorted[0]);
        } else {
          const current = sorted.find((e) => e.id === selectedEval.id);
          if (current) setSelectedEval(current);
        }
      } else {
        setSelectedEval(null);
      }
    } catch (err) {
      console.error('Failed to fetch evaluations:', err);
    } finally {
      setEvalLoading(false);
    }
  }, [user, selectedEval]);

  useEffect(() => {
    fetchHistory();
  }, [fetchHistory]);

  // Fetch Chat Messages for selected evaluation
  const fetchChat = useCallback(async (evalId: number) => {
    try {
      setChatLoading(true);
      setChatError('');
      const chatData = (await chatApi.getTeamChat(evalId)) as ChatMessageItem[];
      setChatMessages(chatData);
    } catch (err) {
      console.error('Failed to fetch chat messages:', err);
      setChatError('Could not load chat messages.');
    } finally {
      setChatLoading(false);
    }
  }, []);

  useEffect(() => {
    if (selectedEval) {
      fetchChat(selectedEval.id);
    } else {
      setChatMessages([]);
    }
  }, [selectedEval, fetchChat]);

  if (!user) return null;

  // Handle Profile Update
  const handleProfileSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setProfileSaving(true);
    setProfileSuccess(false);
    try {
      if (user.hackathon_id === null) return;
      await teamsApi.updateProfile(user.hackathon_id, user.team_id, {
        product_name: productName,
        team_name: teamName,
        one_liner: oneLiner,
      });
      await refreshUser();
      setProfileSuccess(true);
      setTimeout(() => setProfileSuccess(false), 3000);
    } catch (err) {
      console.error('Failed to update profile:', err);
    } finally {
      setProfileSaving(false);
    }
  };

  // Handle File Input Selection
  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      setSelectedFiles(Array.from(e.target.files));
    }
  };

  // Handle Drag & Drop Upload
  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    if (e.dataTransfer.files) {
      setSelectedFiles(Array.from(e.dataTransfer.files));
    }
  };

  // Handle Submit Upload
  const handleUploadSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (selectedFiles.length === 0) return;

    setUploading(true);
    setUploadError('');
    setUploadSuccess(false);

    try {
      await submissionsApi.upload(selectedFiles, isFinalUpload);
      setUploadSuccess(true);
      setSelectedFiles([]);
      await fetchHistory();
      setTimeout(() => setUploadSuccess(false), 5000);
    } catch (err: any) {
      console.error('Upload failed:', err);
      setUploadError(err.message || 'File upload and evaluation failed.');
    } finally {
      setUploading(false);
    }
  };

  // Handle Sending Objection/Question
  const handleSendQuestion = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedEval || !newQuestion.trim()) return;

    const msg = newQuestion.trim();
    setNewQuestion('');
    setChatError('');

    try {
      // Optimistic local update
      setChatMessages((prev) => [...prev, { sender: 'team', message_json: msg, created_at: new Date().toISOString() }]);
      await chatApi.submitObjection(selectedEval.id, msg);
      await fetchChat(selectedEval.id);
    } catch (err: any) {
      console.error('Failed to submit objection:', err);
      setChatError(err.message || 'Failed to submit message to the AI judges.');
    }
  };

  // Parse JSON data safely
  const parseJson = (str: string, fallback: any = {}) => {
    try {
      return JSON.parse(str);
    } catch {
      return fallback;
    }
  };

  // Parse Scores for Radar Chart
  const getChartData = (scoresJson: string) => {
    const scores = parseJson(scoresJson);
    return Object.entries(scores).map(([key, val]) => ({
      subject: key.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' '),
      score: Number(val),
      fullMark: 10,
    }));
  };

  // Render evaluation detail
  const renderEvaluationDetail = () => {
    if (!selectedEval) {
      return (
        <div className="empty-evaluation">
          <FileText size={48} />
          <h3>No Evaluations Yet</h3>
          <p>Submit your project files above to get evaluated by our AI Judge Panel.</p>
        </div>
      );
    }

    const scores = parseJson(selectedEval.scores_json);
    const strengthsRisks = parseJson(selectedEval.strengths_risks_json);
    const chartData = getChartData(selectedEval.scores_json);

    // Dynamic localization summary
    const isJa = i18n.language === 'ja';
    const summary = strengthsRisks[`summary_${isJa ? 'japanese' : 'english'}`] ||
                    strengthsRisks[`summary_ja`] ||
                    strengthsRisks[`summary_en`] ||
                    strengthsRisks[`summary_default`] ||
                    '';

    const judgesFeedback = strengthsRisks.judges_feedback || [];

    return (
      <div className="evaluation-detail">
        <div className="eval-detail-header">
          <div className="eval-meta">
            <span className={`status-badge ${selectedEval.is_final ? 'status-final' : 'status-progress'}`}>
              {selectedEval.is_final ? t('leaderboard.final') : 'Consultation'}
            </span>
            <span className="eval-date">
              <Clock size={14} />
              {selectedEval.evaluated_at ? new Date(selectedEval.evaluated_at).toLocaleString() : ''}
            </span>
          </div>
          <div className="eval-impact">
            <span className="impact-label">Overall Impact Score</span>
            <span className="impact-value">{selectedEval.impact_score.toFixed(1)}</span>
          </div>
        </div>

        {/* Evaluation Summary */}
        {summary && (
          <div className="eval-section summary-section">
            <h4><Sparkles size={18} /> {isJa ? 'AI要約' : 'AI Summary'}</h4>
            <p className="summary-text">{summary}</p>
          </div>
        )}

        <div className="eval-grid">
          {/* Scores Breakdown */}
          <div className="eval-section scores-section">
            <h4>{isJa ? '評価項目内訳' : 'Criteria Breakdown'}</h4>
            <div className="scores-list">
              {Object.entries(scores).map(([criteria, score]) => (
                <div key={criteria} className="score-row">
                  <span className="criteria-name">
                    {criteria.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ')}
                  </span>
                  <div className="score-bar-container">
                    <div className="score-bar-fill" style={{ width: `${(Number(score) / 10) * 100}%` }} />
                    <span className="score-num">{Number(score).toFixed(1)}/10</span>
                  </div>
                </div>
              ))}
            </div>

            {/* Radar Chart */}
            {chartData.length > 0 && (
              <div className="radar-chart-container">
                <ResponsiveContainer width="100%" height={260}>
                  <RadarChart cx="50%" cy="50%" outerRadius="70%" data={chartData}>
                    <PolarGrid stroke="#374151" />
                    <PolarAngleAxis dataKey="subject" tick={{ fill: '#9ca3af', fontSize: 10 }} />
                    <PolarRadiusAxis angle={30} domain={[0, 10]} tick={{ fill: '#6b7280' }} />
                    <Radar
                      name={user.team_id}
                      dataKey="score"
                      stroke="#818cf8"
                      fill="#818cf8"
                      fillOpacity={0.3}
                    />
                  </RadarChart>
                </ResponsiveContainer>
              </div>
            )}
          </div>

          {/* Judges Feedback */}
          <div className="eval-section feedback-section">
            <h4>{isJa ? 'AI審査員からのフィードバック' : 'AI Judges Feedback'}</h4>
            <div className="judges-list">
              {judgesFeedback.map((feedback: any, idx: number) => (
                <div key={idx} className="judge-card">
                  <div className="judge-card-header">
                    <span className="judge-emoji">{feedback.judge_emoji || '🤖'}</span>
                    <div>
                      <h5>{feedback.judge_name}</h5>
                      <span className="judge-role">{feedback.judge_role}</span>
                    </div>
                  </div>
                  <div className="judge-feedback-content">
                    <div className="feedback-block strengths">
                      <h6>🟢 {isJa ? '強み' : 'Strengths'}</h6>
                      <p>{feedback.strengths}</p>
                    </div>
                    <div className="feedback-block risks">
                      <h6>🔴 {isJa ? '懸念・リスク' : 'Risks & Mitigations'}</h6>
                      <p>{feedback.risks_or_mitigations || feedback.risks}</p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Q&A / Objections Thread */}
        <div className="eval-section qa-section">
          <h4>
            <MessageSquare size={18} />
            {isJa ? '審査員パネルとの対話・反論' : 'Q&A / Objection Thread with Judges'}
          </h4>
          <p className="section-hint">
            {isJa
              ? 'AI評価に対して質問や異議申し立てができます。審査員が回答します。'
              : 'Ask clarifying questions or present objections to the judges panel based on this evaluation.'}
          </p>

          <div className="chat-thread">
            {chatMessages.length === 0 && !chatLoading ? (
              <div className="chat-empty">
                <p>{isJa ? 'まだ対話はありません。最初の質問を送信してください。' : 'No chat history. Start the conversation by sending a question.'}</p>
              </div>
            ) : (
              <div className="chat-messages">
                {chatMessages.map((msg, index) => {
                  const isTeam = msg.sender === 'team';
                  // Parse message_json if it is a JSON string
                  let content = '';
                  if (typeof msg.message_json === 'string') {
                    try {
                      const parsed = JSON.parse(msg.message_json);
                      content = parsed.objection || parsed.message || msg.message_json;
                    } catch {
                      content = msg.message_json;
                    }
                  } else if (msg.message_json) {
                    content = msg.message_json.objection || msg.message_json.message || JSON.stringify(msg.message_json);
                  }

                  return (
                    <div key={index} className={`chat-message-bubble ${isTeam ? 'msg-team' : 'msg-judges'}`}>
                      <div className="msg-header">
                        <span className="msg-sender">{isTeam ? 'Team' : 'AI Judges Panel'}</span>
                        {msg.created_at && (
                          <span className="msg-time">{new Date(msg.created_at).toLocaleTimeString()}</span>
                        )}
                      </div>
                      <p className="msg-content">{content}</p>
                    </div>
                  );
                })}
                {chatLoading && (
                  <div className="chat-message-bubble msg-judges chat-typing">
                    <Loader2 size={16} className="animate-spin" />
                    <span>Jury panel is discussing...</span>
                  </div>
                )}
              </div>
            )}

            {chatError && (
              <div className="chat-error">
                <AlertTriangle size={16} />
                <span>{chatError}</span>
              </div>
            )}

            <form onSubmit={handleSendQuestion} className="chat-input-form">
              <input
                type="text"
                value={newQuestion}
                onChange={(e) => setNewQuestion(e.target.value)}
                placeholder={isJa ? '審査員に質問や反論を送信...' : 'Type your question or objection here...'}
                disabled={chatLoading}
              />
              <button type="submit" className="btn btn-primary" disabled={chatLoading || !newQuestion.trim()}>
                <Send size={16} />
              </button>
            </form>
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className="dashboard-page">
      <div className="page-header">
        <UserIcon size={32} />
        <div>
          <h1>{t('team.title')}</h1>
          <p className="page-subtitle">
            Welcome, <strong>{user.team_name || user.team_id}</strong>
          </p>
        </div>
      </div>

      <div className="dashboard-layout">
        {/* Left Side: Upload & Profile */}
        <div className="sidebar-cards">
          {/* Team Profile Edit */}
          <div className="dash-card">
            <h3>{t('team.profile')}</h3>
            <form onSubmit={handleProfileSave} className="profile-form">
              <div className="form-group">
                <label>{t('team.product_name')}</label>
                <input
                  type="text"
                  value={productName}
                  onChange={(e) => setProductName(e.target.value)}
                  placeholder="e.g. Judgie-AI"
                />
              </div>
              <div className="form-group">
                <label>{t('team.team_name')}</label>
                <input
                  type="text"
                  value={teamName}
                  onChange={(e) => setTeamName(e.target.value)}
                  placeholder="e.g. DeepMind Builders"
                />
              </div>
              <div className="form-group">
                <label>{t('team.one_liner_label')}</label>
                <textarea
                  value={oneLiner}
                  onChange={(e) => setOneLiner(e.target.value)}
                  placeholder="e.g. AI-powered hackathon evaluation platform"
                  rows={2}
                />
              </div>
              <button type="submit" className="btn btn-primary" disabled={profileSaving}>
                {profileSaving ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
                {t('common.save')}
              </button>
              {profileSuccess && (
                <div className="success-inline">
                  <CheckCircle size={16} />
                  <span>Saved profile!</span>
                </div>
              )}
            </form>
          </div>

          {/* Submission Form */}
          <div className="dash-card">
            <h3>{t('team.submit')}</h3>
            <form onSubmit={handleUploadSubmit} className="upload-form">
              <div
                className="drop-zone"
                onDragOver={handleDragOver}
                onDrop={handleDrop}
              >
                <Upload size={32} />
                <p>{t('team.upload_hint')}</p>
                <input
                  type="file"
                  multiple
                  onChange={handleFileChange}
                  style={{ display: 'none' }}
                  id="file-upload-input"
                />
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  onClick={() => document.getElementById('file-upload-input')?.click()}
                >
                  Browse Files
                </button>
              </div>

              {selectedFiles.length > 0 && (
                <div className="selected-files">
                  <h5>Selected Files ({selectedFiles.length}):</h5>
                  <ul>
                    {selectedFiles.map((f, i) => (
                      <li key={i}>{f.name} ({(f.size / 1024 / 1024).toFixed(2)} MB)</li>
                    ))}
                  </ul>
                </div>
              )}

              <div className="form-checkbox">
                <input
                  type="checkbox"
                  id="is-final-checkbox"
                  checked={isFinalUpload}
                  onChange={(e) => setIsFinalUpload(e.target.checked)}
                />
                <label htmlFor="is-final-checkbox">
                  <strong>{t('team.final_submission')}</strong>
                </label>
              </div>

              {uploadError && (
                <div className="error-box">
                  <AlertTriangle size={16} />
                  <span>{uploadError}</span>
                </div>
              )}

              {uploadSuccess && (
                <div className="success-box">
                  <CheckCircle size={16} />
                  <span>Upload successful! Evaluating project...</span>
                </div>
              )}

              <button
                type="submit"
                className="btn btn-primary w-full"
                disabled={uploading || selectedFiles.length === 0}
              >
                {uploading ? (
                  <>
                    <Loader2 size={16} className="animate-spin" />
                    Evaluating Project...
                  </>
                ) : (
                  <>
                    <Sparkles size={16} />
                    {t('team.consultation')}
                  </>
                )}
              </button>
            </form>
          </div>
        </div>

        {/* Right Side: Evaluation Results & History */}
        <div className="main-cards">
          <div className="dash-card eval-card">
            <div className="eval-header-wrapper">
              <h3>{t('team.results')}</h3>
              
              {/* History Dropdown */}
              {evaluations.length > 0 && (
                <div className="history-selector">
                  <label htmlFor="eval-history-select">History:</label>
                  <select
                    id="eval-history-select"
                    value={selectedEval?.id || ''}
                    onChange={(e) => {
                      const selected = evaluations.find((ev) => ev.id === Number(e.target.value));
                      if (selected) setSelectedEval(selected);
                    }}
                  >
                    {evaluations.map((ev) => (
                      <option key={ev.id} value={ev.id}>
                        {ev.is_final ? '🏆 Final' : '💡 Consultation'} (
                        {ev.evaluated_at ? new Date(ev.evaluated_at).toLocaleDateString() : ''})
                      </option>
                    ))}
                  </select>
                </div>
              )}
            </div>

            {evalLoading ? (
              <div className="eval-loading-state">
                <Loader2 size={32} className="animate-spin" />
                <p>Loading evaluation details...</p>
              </div>
            ) : (
              renderEvaluationDetail()
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
