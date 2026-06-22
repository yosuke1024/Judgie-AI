import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useAuth } from '@/contexts/AuthContext';
import { evaluationsApi, settingsApi } from '@/api/client';
import { Trophy, Flame, Award, Users, BookOpen, ChevronDown, ChevronUp } from 'lucide-react';

interface ScoreEntry {
  team_id: string;
  product_name: string | null;
  team_name: string | null;
  one_liner: string | null;
  total_score: number;
  status: string;
  consults: number;
  scores_json: string | null;
}

interface CriteriaEntry {
  name: string;
  weight: number;
  description: string;
  active?: boolean;
}

interface PersonaEntry {
  name: string;
  role: string;
  avatar?: string;
  avatar_image?: string;
  prompt: string;
  active?: boolean;
}

export default function Leaderboard() {
  const { t } = useTranslation();
  const { user } = useAuth();
  const [entries, setEntries] = useState<ScoreEntry[]>([]);
  const [criteria, setCriteria] = useState<CriteriaEntry[]>([]);
  const [personas, setPersonas] = useState<PersonaEntry[]>([]);
  const [activeCategoryTab, setActiveCategoryTab] = useState<string>('');
  const [expandedPersona, setExpandedPersona] = useState<Record<string, boolean>>({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    Promise.all([
      evaluationsApi.getScoreboard().catch((err) => {
        console.error('Failed to load scoreboard', err);
        return [] as ScoreEntry[];
      }),
      settingsApi.getCriteria().catch((err) => {
        console.error('Failed to load criteria', err);
        return [] as CriteriaEntry[];
      }),
      settingsApi.getPersonas().catch((err) => {
        console.error('Failed to load personas', err);
        return [] as PersonaEntry[];
      }),
    ])
      .then(([scoreboardData, criteriaData, personasData]) => {
        setEntries(scoreboardData);
        
        const typedCriteria = (criteriaData || []) as CriteriaEntry[];
        setCriteria(typedCriteria);
        if (typedCriteria.length > 0) {
          setActiveCategoryTab(typedCriteria[0].name);
        }
        
        setPersonas((personasData || []) as PersonaEntry[]);
      })
      .finally(() => setLoading(false));
  }, []);

  const togglePersona = (name: string) => {
    setExpandedPersona((prev) => ({
      ...prev,
      [name]: !prev[name],
    }));
  };

  if (loading) {
    return (
      <div className="page-loading">
        <div className="spinner" />
        <p>{t('common.loading')}</p>
      </div>
    );
  }

  const maxScore = entries.length > 0 ? Math.max(...entries.map((e) => e.total_score), 1) : 100;

  return (
    <div className="leaderboard-page">
      <div className="page-header">
        <Flame size={32} />
        <div>
          <h1>{t('leaderboard.title')}</h1>
          <p className="page-subtitle">{t('leaderboard.subtitle')}</p>
        </div>
      </div>

      <section className="rankings-section">
        <h2>
          <Trophy size={20} />
          {t('leaderboard.current_rankings')}
        </h2>

        {entries.length === 0 ? (
          <p className="empty-state">{t('leaderboard.no_teams')}</p>
        ) : (
          <div className="rankings-table-wrapper">
            <table className="rankings-table">
              <thead>
                <tr>
                  <th>#</th>
                  <th>{t('leaderboard.product_team')}</th>
                  <th>{t('leaderboard.one_liner')}</th>
                  <th>{t('leaderboard.status')}</th>
                  <th>{t('leaderboard.consults')}</th>
                  <th>{t('leaderboard.total_score')}</th>
                </tr>
              </thead>
              <tbody>
                {entries.map((entry, idx) => (
                  <tr
                    key={entry.team_id}
                    className={user?.team_id === entry.team_id ? 'highlight-row' : ''}
                  >
                    <td className="rank-cell">
                      {idx === 0 ? '🥇' : idx === 1 ? '🥈' : idx === 2 ? '🥉' : idx + 1}
                    </td>
                    <td className="team-cell">
                      <strong>{entry.product_name || entry.team_id}</strong>
                      {entry.team_name && (
                        <span className="team-name-sub">{entry.team_name}</span>
                      )}
                    </td>
                    <td className="oneliner-cell">{entry.one_liner || '—'}</td>
                    <td>
                      <span
                        className={`status-badge ${
                          entry.status.includes('Final') ? 'status-final' : 'status-progress'
                        }`}
                      >
                        {entry.status === 'Not Submitted'
                          ? t('leaderboard.not_submitted')
                          : entry.status.includes('Final')
                          ? t('leaderboard.final')
                          : entry.status}
                      </span>
                    </td>
                    <td className="consult-cell">{entry.consults}</td>
                    <td className="score-cell">
                      <div className="score-bar-wrapper">
                        <div
                          className="score-bar"
                          style={{ width: `${(entry.total_score / maxScore) * 100}%` }}
                        />
                        <span className="score-value">{entry.total_score.toFixed(1)}</span>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* Category Leaders Section */}
      {criteria.filter((c) => c.active !== false).length > 0 && entries.length > 0 && (
        <section className="category-leaders-section">
          <h2>
            <Award size={20} />
            {t('leaderboard.category_leaders')}
          </h2>
          
          <div className="category-tabs">
            {criteria.filter((c) => c.active !== false).map((c) => (
              <button
                key={c.name}
                className={`category-tab-btn ${activeCategoryTab === c.name ? 'active' : ''}`}
                onClick={() => setActiveCategoryTab(c.name)}
              >
                {c.name}
              </button>
            ))}
          </div>

          <div className="category-leaderboard-content">
            {(() => {
              const currentCriterion = criteria.find((c) => c.name === activeCategoryTab);
              if (!currentCriterion) return null;

              const catData = entries.map((entry) => {
                let score = 0;
                if (entry.scores_json) {
                  try {
                    const parsed = JSON.parse(entry.scores_json);
                    score = Number(parsed[currentCriterion.name]) || 0;
                  } catch (e) {
                    // Ignore
                  }
                }
                const displayName = entry.product_name || entry.team_name || entry.team_id;
                return {
                  team_id: entry.team_id,
                  displayName,
                  score,
                };
              });

              catData.sort((a, b) => {
                if (b.score !== a.score) return b.score - a.score;
                return a.displayName.localeCompare(b.displayName);
              });

              const top5 = catData.slice(0, 5);

              return (
                <div className="cat-rankings-wrapper">
                  <table className="rankings-table">
                    <thead>
                      <tr>
                        <th style={{ width: '60px' }}>#</th>
                        <th>{t('leaderboard.product_team')}</th>
                        <th style={{ width: '220px' }}>{t('common.score')}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {top5.map((team, idx) => (
                        <tr
                          key={team.team_id}
                          className={user?.team_id === team.team_id ? 'highlight-row' : ''}
                        >
                          <td className="rank-cell">
                            {idx === 0 ? '🥇' : idx === 1 ? '🥈' : idx === 2 ? '🥉' : idx + 1}
                          </td>
                          <td className="team-cell">
                            <strong>{team.displayName}</strong>
                          </td>
                          <td className="score-cell">
                            <div className="score-bar-wrapper" style={{ width: '100%' }}>
                              <div
                                className="score-bar"
                                style={{
                                  width: `${(team.score / 5.0) * 100}%`,
                                  background: 'linear-gradient(90deg, var(--warning), var(--accent))',
                                }}
                              />
                              <span className="score-value">{team.score.toFixed(1)} / 5.0</span>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              );
            })()}
          </div>
        </section>
      )}

      {/* AI Jury Panel Section */}
      {personas.length > 0 && (
        <section className="jury-section">
          <h2>
            <Users size={20} />
            {t('leaderboard.jury_panel')}
          </h2>
          <p className="section-subtitle">{t('leaderboard.jury_subtitle')}</p>
          
          <div className="jury-grid">
            {personas
              .filter((p) => p.active !== false)
              .map((p) => {
                const isExpanded = !!expandedPersona[p.name];
                return (
                  <div key={p.name} className="jury-card">
                    <div className="jury-card-header" onClick={() => togglePersona(p.name)}>
                      <div className="jury-avatar-wrapper">
                        {p.avatar_image ? (
                          <img src={p.avatar_image} alt={p.name} className="jury-avatar-img" />
                        ) : (
                          <span className="jury-avatar-emoji">{p.avatar || '🧑‍⚖️'}</span>
                        )}
                      </div>
                      <div className="jury-meta">
                        <h3>{p.name}</h3>
                        <span className="jury-role">{p.role}</span>
                      </div>
                      <button className="jury-toggle-btn">
                        {isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                      </button>
                    </div>
                    {isExpanded && (
                      <div className="jury-card-content">
                        <pre className="persona-prompt-preview">{p.prompt}</pre>
                      </div>
                    )}
                  </div>
                );
              })}
          </div>
        </section>
      )}

      {/* Rules of the Game Section */}
      {criteria.filter((c) => c.active !== false).length > 0 && (
        <section className="rules-section">
          <h2>
            <BookOpen size={20} />
            {t('leaderboard.rules')}
          </h2>
          <div className="criteria-grid">
            {criteria.filter((c) => c.active !== false).map((c) => (
              <div key={c.name} className="criteria-card">
                <div className="criteria-card-header">
                  <h3>{c.name}</h3>
                  <span className="criteria-weight">{t('common.weight')}: {c.weight}%</span>
                </div>
                <p className="criteria-desc">{c.description}</p>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
