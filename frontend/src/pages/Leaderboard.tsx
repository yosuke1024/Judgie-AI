import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useAuth } from '@/contexts/AuthContext';
import { evaluationsApi } from '@/api/client';
import { Trophy, Flame } from 'lucide-react';

interface ScoreEntry {
  team_id: string;
  product_name: string | null;
  team_name: string | null;
  one_liner: string | null;
  total_score: number;
  status: string;
  consults: number;
}

export default function Leaderboard() {
  const { t } = useTranslation();
  const { user } = useAuth();
  const [entries, setEntries] = useState<ScoreEntry[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    evaluationsApi
      .getScoreboard()
      .then(setEntries)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

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
    </div>
  );
}
