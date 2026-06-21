import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { useAuth } from '@/contexts/AuthContext';
import { teamsApi, evaluationsApi, submissionsApi, chatApi, settingsApi } from '@/api/client';
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
  Copy,
  Check,
} from 'lucide-react';
import {
  Radar,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
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
    fullMark: 5,
  }));
};

const CRITERIA_COLORS = [
  '#34d399', // グリーン
  '#f59e0b', // オレンジ
  '#ec4899', // ピンク
  '#3b82f6', // ブルー
  '#a855f7', // パープル
  '#06b6d4', // シアン
  '#10b981', // エメラルド
  '#f43f5e', // ローズ
];

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
  const [copied, setCopied] = useState(false);

  // Evaluation & History States
  const [evaluations, setEvaluations] = useState<EvaluationItem[]>([]);
  const [selectedEval, setSelectedEval] = useState<EvaluationItem | null>(null);
  const [evalLoading, setEvalLoading] = useState(true);

  // Q&A Chat States
  const [chatMessages, setChatMessages] = useState<ChatMessageItem[]>([]);
  const [newQuestion, setNewQuestion] = useState('');
  const [chatLoading, setChatLoading] = useState(false);
  const [chatError, setChatError] = useState('');

  // Configured Hackathon States (Criteria, Languages)
  const [aiLanguages, setAiLanguages] = useState<string[]>(['English', 'Japanese']);
  const [criteria, setCriteria] = useState<any[]>([]);
  const [selectedAiLang, setSelectedAiLang] = useState<string>('en');

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

  // Fetch criteria & language settings
  useEffect(() => {
    const fetchConfig = async () => {
      if (!user) return;
      try {
        const langData = await settingsApi.getLanguages();
        if (langData && langData.languages) {
          setAiLanguages(langData.languages);
          // Set default AI language based on current UI locale if it matches
          const currentUiLocale = i18n.language === 'ja' ? 'japanese' : 'english';
          const match = langData.languages.find(
            (l: string) => normalizeLangToKey(l) === normalizeLangToKey(currentUiLocale)
          );
          if (match) {
            setSelectedAiLang(normalizeLangToKey(match));
          } else if (langData.languages.length > 0) {
            setSelectedAiLang(normalizeLangToKey(langData.languages[0]));
          }
        }
      } catch (err) {
        console.error('Failed to fetch languages config:', err);
      }

      try {
        const critData = await settingsApi.getCriteria();
        if (Array.isArray(critData)) {
          setCriteria(critData);
        }
      } catch (err) {
        console.error('Failed to fetch criteria config:', err);
      }
    };

    fetchConfig();
  }, [user, i18n.language]);

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
        setSelectedEval((prev) => {
          if (!prev) return sorted[0];
          const current = sorted.find((e) => e.id === prev.id);
          return current || sorted[0];
        });
      } else {
        setSelectedEval(null);
      }
    } catch (err) {
      console.error('Failed to fetch evaluations:', err);
    } finally {
      setEvalLoading(false);
    }
  }, [user]);

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

  // Calculate 100-point total score considering criteria weights
  const calculateTotalScore = useCallback((evaluation: EvaluationItem) => {
    if (!evaluation) return 0;
    const scores = parseJson(evaluation.scores_json);
    const totalWeight = criteria.reduce((sum, c) => sum + (c.weight || 0), 0) || 1;
    return criteria.reduce((sum, crit) => {
      const score = Number(scores[crit.name] || 0);
      return sum + score * 20.0 * ((crit.weight || 0) / totalWeight);
    }, 0);
  }, [criteria]);

  // Generate unique display names for each evaluation based on chronological order
  const evalNames = useMemo(() => {
    const chrono = [...evaluations].sort((a, b) => a.id - b.id);
    const names: Record<number, string> = {};
    let consultationCount = 0;

    chrono.forEach((ev) => {
      if (ev.is_final) {
        names[ev.id] = t('team.final_eval');
      } else {
        consultationCount++;
        names[ev.id] = t('team.consultation_num', { number: consultationCount });
      }
    });
    return names;
  }, [evaluations, t]);

  // Generate trend line chart data
  const trendData = useMemo(() => {
    const chrono = [...evaluations].sort((a, b) => a.id - b.id);
    let consultationCount = 0;
    return chrono.map((ev) => {
      let name = '';
      if (ev.is_final) {
        name = i18n.language === 'ja' ? '最終' : 'Final';
      } else {
        consultationCount++;
        name = `#${consultationCount}`;
      }

      const totalScore = calculateTotalScore(ev);
      const scores = parseJson(ev.scores_json);

      const criteriaScores: Record<string, number> = {};
      criteria.forEach((crit) => {
        // Convert 5-point max score to 100-point max score (score * 20.0)
        criteriaScores[crit.name] = Math.round(Number(scores[crit.name] || 0) * 20.0 * 10) / 10;
      });

      return {
        name,
        score: Math.round(totalScore * 10) / 10,
        date: ev.evaluated_at ? new Date(ev.evaluated_at).toLocaleDateString() : '',
        ...criteriaScores,
      };
    });
  }, [evaluations, calculateTotalScore, criteria, i18n.language]);

  const [hiddenSeries, setHiddenSeries] = useState<string[]>([]);

  const handleLegendClick = useCallback((o: any) => {
    const { dataKey } = o;
    setHiddenSeries((prev) =>
      prev.includes(dataKey)
        ? prev.filter((item) => item !== dataKey)
        : [...prev, dataKey]
    );
  }, []);

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

  // Handle Copy ZIP Command
  const handleCopyCommand = () => {
    const cmd = t('team.zip_hint_command');
    navigator.clipboard.writeText(cmd).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
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
      await refreshUser();
      setTimeout(() => setUploadSuccess(false), 5000);
    } catch (err: any) {
      console.error('Upload failed:', err);
      if (err.status === 429) {
        setUploadError(t('team.api_limit_error'));
      } else {
        setUploadError(err.message || 'File upload and evaluation failed.');
      }
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

  // Render criteria breakdown
  const renderCriteriaBreakdown = () => {
    if (!selectedEval) return null;

    const scores = parseJson(selectedEval.scores_json);

    // Find previous evaluation to calculate deltas
    const currentIdx = evaluations.findIndex(e => e.id === selectedEval.id);
    const prevEval = currentIdx !== -1 && currentIdx < evaluations.length - 1 ? evaluations[currentIdx + 1] : null;
    const prevScores = prevEval ? parseJson(prevEval.scores_json) : null;

    // Calculate total weight and contributions
    const totalWeight = criteria.reduce((sum, c) => sum + (c.weight || 0), 0) || 1;
    const isJa = i18n.language === 'ja';

    return (
      <div className="dash-card criteria-breakdown-card" style={{ marginTop: '24px' }}>
        <h3>{isJa ? '評価項目内訳' : 'Criteria Breakdown'}</h3>
        
        {/* Criteria Grid Cards */}
        <div className="criteria-cards-grid" style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
          gap: '12px',
          marginBottom: '20px',
          marginTop: '16px'
        }}>
          {criteria.map((crit) => {
            const score = Number(scores[crit.name] || 0);
            const contribution = score * 20.0 * ((crit.weight || 0) / totalWeight);
            const maxContrib = 100.0 * ((crit.weight || 0) / totalWeight);
            
            let deltaText = '';
            let deltaColor = '';
            if (prevScores) {
              const prevScore = Number(prevScores[crit.name] || 0);
              const diff = score - prevScore;
              if (diff > 0) {
                deltaText = `+${diff.toFixed(1)}`;
                deltaColor = '#10b981';
              } else if (diff < 0) {
                deltaText = `${diff.toFixed(1)}`;
                deltaColor = '#ef4444';
              } else {
                deltaText = '±0';
                deltaColor = '#9ca3af';
              }
            }

            return (
              <div key={crit.name} className="criteria-score-card" style={{
                padding: '12px',
                borderRadius: '8px',
                background: '#111827',
                border: '1px solid #374151',
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'space-between',
              }}>
                <div>
                  <span style={{ fontSize: '0.8em', color: '#9ca3af', fontWeight: '500' }}>{crit.name}</span>
                  <div style={{ display: 'flex', alignItems: 'baseline', gap: '6px', marginTop: '2px' }}>
                    <span style={{ fontSize: '1.5em', fontWeight: 'bold', color: '#ffffff' }}>{score.toFixed(1)}</span>
                    <span style={{ fontSize: '0.8em', color: '#6b7280' }}>/ 5.0</span>
                    {deltaText && (
                      <span style={{ fontSize: '0.8em', color: deltaColor, fontWeight: '600', marginLeft: 'auto' }}>
                        {deltaText}
                      </span>
                    )}
                  </div>
                </div>
                <div style={{ marginTop: '8px', fontSize: '0.75em', color: '#9ca3af', borderTop: '1px solid #374151', paddingTop: '6px' }}>
                  {t('team.contribution_score', { contribution: contribution.toFixed(1), max: maxContrib.toFixed(1) })}
                </div>
              </div>
            );
          })}
        </div>


      </div>
    );
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

    const strengthsRisks = parseJson(selectedEval.strengths_risks_json);

    // Dynamic localization summary
    const isJa = i18n.language === 'ja';
    const summary = strengthsRisks[`summary_${selectedAiLang}`] ||
                    strengthsRisks[`summary_japanese`] ||
                    strengthsRisks[`summary_english`] ||
                    strengthsRisks[`summary_default`] ||
                    '';

    const judgesFeedback = strengthsRisks.judges_feedback || [];
    const chartData = getChartData(selectedEval.scores_json);

    // Count the number of turns submitted by the team
    const teamMessageCount = chatMessages.filter((msg) => msg.sender === 'team').length;
    const maxQaTurns = user?.max_qa_turns ?? 1;
    const isQaLimitReached = maxQaTurns !== -1 && teamMessageCount >= maxQaTurns;

    return (
      <div className="evaluation-detail">
        {/* AI Language Selection Tabs */}
        {aiLanguages.length > 1 && (
          <div className="ai-language-tabs" style={{
            display: 'flex',
            gap: '8px',
            marginBottom: '16px',
            borderBottom: '1px solid #374151',
            paddingBottom: '8px'
          }}>
            {aiLanguages.map((lang) => {
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

        <div className="eval-detail-header">
          <div className="eval-meta">
            <span className={`status-badge ${selectedEval.is_final ? 'status-final' : 'status-progress'}`}>
              {evalNames[selectedEval.id] || (selectedEval.is_final ? t('leaderboard.final') : 'Consultation')}
            </span>
            <span className="eval-date">
              <Clock size={14} />
              {selectedEval.evaluated_at ? new Date(selectedEval.evaluated_at).toLocaleString() : ''}
            </span>
          </div>
          <div className="eval-impact">
            <span className="impact-label">Overall Impact Score</span>
            <span className="impact-value">{calculateTotalScore(selectedEval).toFixed(1)}</span>
          </div>
        </div>

        {/* Charts Section */}
        <div className="eval-charts-container" style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
          gap: '16px',
          marginBottom: '24px',
          marginTop: '16px'
        }}>
          {/* Radar Chart */}
          {chartData.length > 0 && (
            <div className="radar-chart-card" style={{
              background: '#111827',
              borderRadius: '8px',
              padding: '16px',
              border: '1px solid #374151',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center'
            }}>
              <h5 style={{ margin: '0 0 12px 0', fontSize: '0.95em', color: '#9ca3af', fontWeight: '600' }}>
                {t('team.evaluation_balance')}
              </h5>
              <ResponsiveContainer width="100%" height={200}>
                <RadarChart cx="50%" cy="50%" outerRadius="70%" data={chartData}>
                  <PolarGrid stroke="#374151" />
                  <PolarAngleAxis dataKey="subject" tick={{ fill: '#9ca3af', fontSize: 9 }} />
                  <PolarRadiusAxis angle={30} domain={[0, 5]} tick={{ fill: '#6b7280', fontSize: 8 }} />
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

          {/* Trend Line Chart */}
          {trendData.length > 0 && (
            <div className="trend-chart-card" style={{
              background: '#111827',
              borderRadius: '8px',
              padding: '16px',
              border: '1px solid #374151',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center'
            }}>
              <h5 style={{ margin: '0 0 12px 0', fontSize: '0.95em', color: '#9ca3af', fontWeight: '600' }}>
                {t('team.score_trend')}
              </h5>
              <ResponsiveContainer width="100%" height={200}>
                <LineChart data={trendData} margin={{ top: 10, right: 5, left: -25, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                  <XAxis dataKey="name" stroke="#9ca3af" tick={{ fontSize: 9 }} />
                  <YAxis domain={[0, 100]} stroke="#9ca3af" tick={{ fontSize: 9 }} />
                  <Tooltip
                    contentStyle={{ backgroundColor: '#1f2937', borderColor: '#374151', borderRadius: '4px' }}
                    labelStyle={{ color: '#ffffff', fontSize: '10px' }}
                    itemStyle={{ fontSize: '10px' }}
                  />
                  <Legend
                    onClick={handleLegendClick}
                    wrapperStyle={{ fontSize: '8px', paddingTop: '10px', cursor: 'pointer' }}
                  />
                  <Line
                    type="monotone"
                    dataKey="score"
                    stroke="#818cf8"
                    activeDot={{ r: 6 }}
                    strokeWidth={3}
                    name={t('team.total_score_label')}
                    hide={hiddenSeries.includes('score')}
                  />
                  {criteria.map((crit, idx) => {
                    const color = CRITERIA_COLORS[idx % CRITERIA_COLORS.length];
                    return (
                      <Line
                        key={crit.name}
                        type="monotone"
                        dataKey={crit.name}
                        stroke={color}
                        strokeDasharray="4 4"
                        strokeWidth={1.5}
                        dot={{ r: 3 }}
                        name={crit.name}
                        hide={hiddenSeries.includes(crit.name)}
                      />
                    );
                  })}
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>

        {/* Evaluation Summary */}
        {summary && (
          <div className="eval-section summary-section">
            <h4><Sparkles size={18} /> {isJa ? 'AI要約' : 'AI Summary'}</h4>
            <p className="summary-text">{summary}</p>
          </div>
        )}

        <div className="eval-grid" style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
          {/* Judges Feedback */}
          <div className="eval-section feedback-section" style={{ width: '100%' }}>
            <h4>{isJa ? 'AI審査員からのフィードバック' : 'AI Judges Feedback'}</h4>
            <div className="judges-list" style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              {judgesFeedback.map((feedback: any, idx: number) => {
                const feedbackText = feedback[`feedback_${selectedAiLang}`] ||
                                     feedback[`feedback_japanese`] ||
                                     feedback[`feedback_english`] ||
                                     Object.entries(feedback).find(([k]) => k.startsWith('feedback_'))?.[1] ||
                                     'No feedback available.';

                return (
                  <div key={idx} className="judge-card" style={{ padding: '20px', background: '#111827', border: '1px solid #374151', borderRadius: '8px' }}>
                    <div className="judge-card-header" style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '16px' }}>
                      {feedback.judge_avatar_image ? (
                        <img 
                          src={feedback.judge_avatar_image} 
                          alt={feedback.judge_name} 
                          style={{ width: '40px', height: '40px', borderRadius: '50%', objectFit: 'cover', border: '1px solid rgba(255,255,255,0.1)' }} 
                        />
                      ) : (
                        <span className="judge-emoji" style={{ fontSize: '2.5em' }}>{feedback.judge_emoji || '🤖'}</span>
                      )}
                      <div>
                        <h5 style={{ margin: '0', fontSize: '1.1em', fontWeight: 'bold' }}>{feedback.judge_name}</h5>
                        <span className="judge-role" style={{ fontSize: '0.85em', color: '#9ca3af' }}>{feedback.judge_role}</span>
                      </div>
                    </div>

                    {/* Individual Judge Scores */}
                    {feedback.judge_scores && feedback.judge_scores.length > 0 && (
                      <div style={{
                        display: 'flex',
                        flexWrap: 'wrap',
                        gap: '12px',
                        marginBottom: '16px',
                        padding: '12px',
                        background: 'rgba(255, 255, 255, 0.03)',
                        borderRadius: '6px',
                        border: '1px solid rgba(255, 255, 255, 0.05)'
                      }}>
                        {feedback.judge_scores.map((scoreItem: any, idxS: number) => {
                          const sVal = Number(scoreItem.score);
                          const color = sVal >= 4 ? '#10b981' : sVal >= 3 ? '#f59e0b' : '#ef4444';
                          return (
                            <div key={idxS} style={{ flex: '1', minWidth: '110px' }}>
                              <div style={{ fontSize: '0.7em', color: '#9ca3af', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                                {scoreItem.criteria_name}
                              </div>
                              <div style={{ fontSize: '0.9em', fontWeight: 'bold', color }}>
                                {sVal.toFixed(1)} / 5.0
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    )}

                    <div className="judge-feedback-content">
                      <p style={{ fontSize: '0.95em', color: '#d1d5db', lineHeight: '1.6', margin: '0' }}>
                        {feedbackText}
                      </p>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        {/* Q&A / Objections Thread */}
        <div className="eval-section qa-section">
          <h4>
            <MessageSquare size={18} />
            {isJa ? '審査員パネルとの対話・反論' : 'Q&A / Objection Thread with Judges'}
          </h4>
          <p className="section-hint" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span>
              {isJa
                ? 'AI評価に対して質問や異議申し立てができます。審査員が回答します。'
                : 'Ask clarifying questions or present objections to the judges panel based on this evaluation.'}
            </span>
            {maxQaTurns !== -1 && (
              <span style={{
                fontSize: '0.85em',
                color: '#9ca3af',
                background: 'rgba(255, 255, 255, 0.05)',
                padding: '4px 8px',
                borderRadius: '4px',
                border: '1px solid rgba(255, 255, 255, 0.1)'
              }}>
                {isJa ? '残りQ&A回数' : 'Q&A Remaining'}:{' '}
                <strong style={{ color: isQaLimitReached ? '#ef4444' : '#ffffff' }}>
                  {Math.max(0, maxQaTurns - teamMessageCount)} / {maxQaTurns}
                </strong>
              </span>
            )}
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
                  let parsed: any = null;
                  if (typeof msg.message_json === 'string') {
                    try {
                      parsed = JSON.parse(msg.message_json);
                    } catch {
                      parsed = msg.message_json;
                    }
                  } else {
                    parsed = msg.message_json;
                  }

                  if (isTeam) {
                    let content = '';
                    if (parsed && typeof parsed === 'object') {
                      content = parsed[`user_objection_${selectedAiLang}`] ||
                                parsed[`user_objection_${selectedAiLang === 'ja' ? 'japanese' : 'english'}`] ||
                                parsed.user_objection ||
                                parsed.objection ||
                                parsed.message ||
                                JSON.stringify(parsed);
                    } else {
                      content = String(parsed || '');
                    }

                    return (
                      <div key={index} className="chat-message-bubble msg-team">
                        <div className="msg-header">
                          <span className="msg-sender">Team</span>
                          {msg.created_at && (
                            <span className="msg-time">{new Date(msg.created_at).toLocaleTimeString()}</span>
                          )}
                        </div>
                        <p className="msg-content">{content}</p>
                      </div>
                    );
                  } else {
                    let summaryText = '';
                    let judgesResponses: any[] = [];
                    if (parsed && typeof parsed === 'object') {
                      summaryText = parsed[`qa_summary_${selectedAiLang}`] ||
                                    parsed[`qa_summary_${selectedAiLang === 'ja' ? 'japanese' : 'english'}`] ||
                                    parsed.qa_summary_ja ||
                                    parsed.qa_summary_en ||
                                    parsed.qa_summary ||
                                    '';
                      judgesResponses = parsed.judges_responses || [];
                    } else {
                      summaryText = String(parsed || '');
                    }

                    return (
                      <div key={index} className="chat-message-bubble msg-judges" style={{ maxWidth: '85%' }}>
                        <div className="msg-header">
                          <span className="msg-sender">{isJa ? 'AI審査員パネル' : 'AI Judges Panel'}</span>
                          {msg.created_at && (
                            <span className="msg-time">{new Date(msg.created_at).toLocaleTimeString()}</span>
                          )}
                        </div>
                        <div className="msg-content">
                          {summaryText && (
                            <div className="qa-summary-section" style={{ marginBottom: judgesResponses.length > 0 ? '16px' : '0' }}>
                              <p style={{ fontWeight: '600', color: '#818cf8', margin: '0 0 6px 0', fontSize: '0.85em', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                                {isJa ? 'パネル総括サマリー' : 'Panel Consensus Summary'}
                              </p>
                              <p style={{ margin: '0', fontSize: '0.95em', lineHeight: '1.5', color: '#ffffff' }}>{summaryText}</p>
                            </div>
                          )}
                          
                          {judgesResponses.length > 0 && (
                            <div className="judges-chat-responses" style={{
                              display: 'flex',
                              flexDirection: 'column',
                              gap: '12px',
                              borderTop: '1px solid rgba(255, 255, 255, 0.1)',
                              paddingTop: '12px',
                              marginTop: '12px'
                            }}>
                              {judgesResponses.map((jResp: any, jIdx: number) => {
                                const responseText = jResp[`response_${selectedAiLang}`] ||
                                                     jResp[`response_${selectedAiLang === 'ja' ? 'japanese' : 'english'}`] ||
                                                     jResp.response_ja ||
                                                     jResp.response_en ||
                                                     '';
                                return (
                                  <div key={jIdx} className="judge-response-item" style={{
                                    background: 'rgba(255, 255, 255, 0.03)',
                                    border: '1px solid rgba(255, 255, 255, 0.05)',
                                    borderRadius: '6px',
                                    padding: '10px 12px'
                                  }}>
                                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
                                      {jResp.judge_avatar_image ? (
                                        <img 
                                          src={jResp.judge_avatar_image} 
                                          alt={jResp.judge_name} 
                                          style={{ width: '24px', height: '24px', borderRadius: '50%', objectFit: 'cover', border: '1px solid rgba(255,255,255,0.1)' }} 
                                        />
                                      ) : (
                                        <span style={{ fontSize: '1.2em' }}>{jResp.judge_emoji || '🤖'}</span>
                                      )}
                                      <div>
                                        <strong style={{ fontSize: '0.9em', color: '#ffffff' }}>{jResp.judge_name}</strong>
                                        {jResp.judge_role && (
                                          <span style={{ fontSize: '0.75em', color: '#9ca3af', marginLeft: '6px' }}>
                                            ({jResp.judge_role})
                                          </span>
                                        )}
                                      </div>
                                    </div>
                                    <p style={{ margin: '0', fontSize: '0.9em', color: '#d1d5db', lineHeight: '1.4' }}>
                                      {responseText}
                                    </p>
                                  </div>
                                );
                              })}
                            </div>
                          )}
                        </div>
                      </div>
                    );
                  }
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
                placeholder={
                  isQaLimitReached
                    ? (isJa ? 'Q&A対話の回数制限に達しました。' : 'Maximum Q&A discussion turns reached.')
                    : (isJa ? '審査員に質問や反論を送信...' : 'Type your question or objection here...')
                }
                disabled={chatLoading || isQaLimitReached}
              />
              <button type="submit" className="btn btn-primary" disabled={chatLoading || isQaLimitReached || !newQuestion.trim()}>
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
            
            <details className="zip-hint-details">
              <summary className="zip-hint-summary">
                {t('team.zip_hint_title')}
              </summary>
              <div className="zip-hint-content">
                <p>{t('team.zip_hint_desc')}</p>
                <div className="zip-hint-example">
                  <span>{t('team.zip_hint_example')}</span>
                  <div className="code-block-container">
                    <pre>
                      <code>{t('team.zip_hint_command')}</code>
                    </pre>
                    <button
                      type="button"
                      className="copy-code-btn"
                      onClick={handleCopyCommand}
                      title="Copy to clipboard"
                    >
                      {copied ? <Check size={14} className="text-success" /> : <Copy size={14} />}
                    </button>
                  </div>
                </div>
              </div>
            </details>

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

              {user.max_consultations !== undefined && (
                <div className="consultations-remaining-info" style={{
                  marginBottom: '12px',
                  padding: '8px 12px',
                  borderRadius: '6px',
                  background: 'rgba(255, 255, 255, 0.05)',
                  border: '1px solid rgba(255, 255, 255, 0.1)',
                  fontSize: '0.9em',
                  color: '#9ca3af',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center'
                }}>
                  <span>{t('team.consultations_remaining')}</span>
                  <strong style={{ color: '#ffffff' }}>
                    {user.max_consultations === -1
                      ? (i18n.language === 'ja' ? '無制限' : 'Unlimited')
                      : `${Math.max(0, user.max_consultations - (user.consultation_count || 0))} / ${user.max_consultations}`}
                  </strong>
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
          {renderCriteriaBreakdown()}
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
                        {ev.is_final ? '🏆 ' : '💡 '}
                        {evalNames[ev.id]} ({ev.evaluated_at ? new Date(ev.evaluated_at).toLocaleDateString() : ''})
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
