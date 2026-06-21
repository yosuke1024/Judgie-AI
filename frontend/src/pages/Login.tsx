import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuth } from '@/contexts/AuthContext';
import { hackathonsApi, ApiError } from '@/api/client';
import { Globe, LogIn, Zap } from 'lucide-react';

interface HackathonItem {
  id: number;
  name: string;
  template_id: string | null;
  admin_id: string | null;
  team_count: number;
}

export default function LoginPage() {
  const { t, i18n } = useTranslation();
  const { login, user } = useAuth();
  const navigate = useNavigate();

  const [hackathons, setHackathons] = useState<HackathonItem[]>([]);
  const [selectedHackathon, setSelectedHackathon] = useState<number | undefined>();
  const [teamId, setTeamId] = useState('');
  const [passcode, setPasscode] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [isSuperAdmin, setIsSuperAdmin] = useState(false);

  useEffect(() => {
    hackathonsApi.list().then(setHackathons).catch(() => {});
  }, []);

  useEffect(() => {
    if (user) {
      if (user.role === 'superadmin') navigate('/super-admin');
      else if (user.role === 'admin') navigate('/admin');
      else navigate('/dashboard');
    }
  }, [user, navigate]);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (!teamId || !passcode) {
      setError(t('login.all_fields_required'));
      return;
    }

    setLoading(true);
    try {
      await login(teamId, passcode, selectedHackathon);
    } catch (err: any) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError(t('login.invalid_credentials'));
      }
    } finally {
      setLoading(false);
    }
  };

  const toggleLang = () => {
    i18n.changeLanguage(i18n.language === 'en' ? 'ja' : 'en');
  };

  return (
    <div className="login-page">
      <div className="login-backdrop" />
      <div className="login-container">
        {/* Language toggle */}
        <button className="lang-toggle" onClick={toggleLang} title="Switch Language">
          <Globe size={18} />
          {i18n.language === 'en' ? '日本語' : 'English'}
        </button>

        {/* Logo */}
        <div className="login-logo">
          <Zap size={40} />
          <h1>{t('login.title')}</h1>
          <p className="login-subtitle">{t('login.subtitle')}</p>
        </div>

        {/* Error */}
        {error && <div className="login-error">{error}</div>}

        <form onSubmit={handleLogin} className="login-form">
          {/* Project Selector (non-superadmin) */}
          {!isSuperAdmin && hackathons.length > 0 && (
            <div className="form-group">
              <label>{t('login.select_project')}</label>
              <select
                value={selectedHackathon ?? ''}
                onChange={(e) => setSelectedHackathon(Number(e.target.value) || undefined)}
              >
                <option value="">—</option>
                {hackathons.map((h) => (
                  <option key={h.id} value={h.id}>
                    {h.name} ({h.team_count} teams)
                  </option>
                ))}
              </select>
            </div>
          )}

          <div className="form-group">
            <label>{t('login.team_id')}</label>
            <input
              type="text"
              value={teamId}
              onChange={(e) => setTeamId(e.target.value)}
              placeholder={isSuperAdmin ? 'superadmin' : ''}
              autoComplete="username"
            />
          </div>

          <div className="form-group">
            <label>{t('login.passcode')}</label>
            <input
              type="password"
              value={passcode}
              onChange={(e) => setPasscode(e.target.value)}
              autoComplete="current-password"
            />
          </div>

          <button type="submit" className="btn btn-primary login-btn" disabled={loading}>
            <LogIn size={18} />
            {loading ? t('common.loading') : t('login.login_btn')}
          </button>
        </form>

        <div className="login-footer">
          <button
            className="btn btn-ghost"
            onClick={() => {
              setIsSuperAdmin(!isSuperAdmin);
              setTeamId(isSuperAdmin ? '' : 'superadmin');
              setSelectedHackathon(undefined);
            }}
          >
            {isSuperAdmin ? '← Back' : t('login.super_admin_login')}
          </button>
        </div>
      </div>
    </div>
  );
}
