import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuth } from '@/contexts/AuthContext';
import { authApi, ApiError } from '@/api/client';
import { Globe, LogIn, Zap } from 'lucide-react';

const GithubIcon = ({ size = 16 }: { size?: number }) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 24 24"
    fill="currentColor"
  >
    <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/>
  </svg>
);

export default function LoginPage() {
  const { t, i18n } = useTranslation();
  const { login, user, refreshUser } = useAuth();
  const navigate = useNavigate();

  const [teamId, setTeamId] = useState('');
  const [passcode, setPasscode] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [isSuperAdmin, setIsSuperAdmin] = useState(false);
  const [oidcEnabled, setOidcEnabled] = useState(false);

  useEffect(() => {
    const fetchConfig = async () => {
      try {
        const config = await authApi.getConfig();
        setOidcEnabled(config.oidc_enabled);
      } catch (err) {
        console.error('Failed to load auth config:', err);
      }
    };
    fetchConfig();
  }, []);

  useEffect(() => {
    // Check OIDC callback parameters in URL
    const params = new URLSearchParams(window.location.search);
    const code = params.get('code');
    const state = params.get('state');

    if (code && state) {
      handleOidcCallback(code, state);
    }
  }, []);

  useEffect(() => {
    if (user) {
      if (user.role === 'superadmin') navigate('/super-admin');
      else if (user.role === 'admin') navigate('/admin');
      else navigate('/dashboard');
    }
  }, [user, navigate]);

  const handleOidcCallback = async (code: string, state: string) => {
    window.history.replaceState({}, document.title, window.location.pathname);
    setLoading(true);
    setError('');
    try {
      const res = await authApi.oidcCallback({ code, state });
      if (res.status === 'success') {
        await refreshUser();
      }
    } catch (err: any) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError(t('login.csrf_error') || 'SSO authentication failed.');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleOidcLogin = async () => {
    setLoading(true);
    setError('');
    try {
      const { auth_url } = await authApi.oidcLogin();
      window.location.href = auth_url;
    } catch (err: any) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError('Failed to initiate SSO login.');
      }
      setLoading(false);
    }
  };

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (!teamId || !passcode) {
      setError(t('login.all_fields_required'));
      return;
    }

    setLoading(true);
    try {
      await login(teamId, passcode);
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

        {oidcEnabled && !isSuperAdmin ? (
          <div className="sso-only-container" style={{ textAlign: 'center', marginTop: '1.5rem', width: '100%' }}>
            <p style={{ color: 'var(--text-secondary)', marginBottom: '1.5rem', fontSize: '0.95rem', lineHeight: '1.5' }}>
              {t('login.sso_required_message')}
            </p>
            <button
              type="button"
              className="btn btn-primary login-btn sso-btn"
              onClick={handleOidcLogin}
              disabled={loading}
              style={{ width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem', height: '44px' }}
            >
              <Globe size={18} />
              {t('login.sso_login_btn')}
            </button>
          </div>
        ) : (
          <form onSubmit={handleLogin} className="login-form">
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

            {oidcEnabled && (
              <>
                <div className="sso-divider" style={{
                  display: 'flex',
                  alignItems: 'center',
                  textAlign: 'center',
                  margin: '1.5rem 0 1rem 0',
                  color: 'var(--text-muted, #888)',
                  fontSize: '0.875rem'
                }}>
                  <div style={{ flex: 1, height: '1px', backgroundColor: 'var(--border-color, #e0e0e0)' }}></div>
                  <span style={{ padding: '0 0.75rem' }}>or</span>
                  <div style={{ flex: 1, height: '1px', backgroundColor: 'var(--border-color, #e0e0e0)' }}></div>
                </div>
                <button
                  type="button"
                  className="btn btn-secondary login-btn sso-btn"
                  onClick={handleOidcLogin}
                  disabled={loading}
                  style={{ width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem' }}
                >
                  <Globe size={18} />
                  {t('login.sso_login_btn')}
                </button>
              </>
            )}
          </form>
        )}

        <div className="login-footer">
          <button
            className="btn btn-ghost"
            onClick={() => {
              setIsSuperAdmin(!isSuperAdmin);
              setTeamId(isSuperAdmin ? '' : 'superadmin');
            }}
          >
            {isSuperAdmin ? '← Back' : t('login.super_admin_login')}
          </button>
        </div>

        <div className="login-credits" style={{
          marginTop: '24px',
          paddingTop: '16px',
          borderTop: '1px solid var(--card-border)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          fontSize: '0.75rem',
          color: 'var(--text-muted)'
        }}>
          <a
            href="https://pixapps.ai/"
            target="_blank"
            rel="noopener noreferrer"
            style={{ color: 'var(--text-muted)', textDecoration: 'none', transition: 'color 0.2s' }}
            onMouseOver={(e) => (e.currentTarget.style.color = 'var(--text-secondary)')}
            onMouseOut={(e) => (e.currentTarget.style.color = 'var(--text-muted)')}
          >
            {t('credits.produced_by')}
          </a>
          <a
            href="https://github.com/yosuke1024/Judgie-AI"
            target="_blank"
            rel="noopener noreferrer"
            style={{ color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '4px', textDecoration: 'none', transition: 'color 0.2s' }}
            onMouseOver={(e) => (e.currentTarget.style.color = 'var(--text-secondary)')}
            onMouseOut={(e) => (e.currentTarget.style.color = 'var(--text-muted)')}
          >
            <GithubIcon size={14} />
            <span>{t('credits.github')}</span>
          </a>
        </div>
      </div>
    </div>
  );
}
