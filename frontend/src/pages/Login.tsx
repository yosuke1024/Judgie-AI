import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuth } from '@/contexts/AuthContext';
import { hackathonsApi, authApi, ApiError } from '@/api/client';
import { Globe, LogIn, Zap } from 'lucide-react';

interface HackathonItem {
  id: number;
  name: string;
  template_id: string | null;
  admin_id: string | null;
  team_count: number;
}

interface TenantItem {
  hackathon_id: number;
  hackathon_name: string;
  team_id: string;
  team_name: string | null;
  role: string;
}

export default function LoginPage() {
  const { t, i18n } = useTranslation();
  const { login, user, oidcSelectTenant, refreshUser } = useAuth();
  const navigate = useNavigate();

  const [hackathons, setHackathons] = useState<HackathonItem[]>([]);
  const [selectedHackathon, setSelectedHackathon] = useState<number | undefined>();
  const [teamId, setTeamId] = useState('');
  const [passcode, setPasscode] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [isSuperAdmin, setIsSuperAdmin] = useState(false);

  // OIDC Specific State
  const [oidcTempToken, setOidcTempToken] = useState<string | null>(null);
  const [oidcTenants, setOidcTenants] = useState<TenantItem[]>([]);
  const [selectTenantMode, setSelectTenantMode] = useState(false);
  const [selectedTenantIndex, setSelectedTenantIndex] = useState<number | null>(null);

  useEffect(() => {
    hackathonsApi.list().then(setHackathons).catch(() => {});

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
      } else if (res.status === 'select_tenant') {
        setOidcTempToken(res.temp_token || null);
        setOidcTenants(res.tenants || []);
        setSelectTenantMode(true);
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

  const handleSelectTenant = async (e: React.FormEvent) => {
    e.preventDefault();
    if (selectedTenantIndex === null || !oidcTempToken) return;

    setLoading(true);
    setError('');
    const tenant = oidcTenants[selectedTenantIndex];
    try {
      await oidcSelectTenant(oidcTempToken, tenant.hackathon_id, tenant.team_id);
    } catch (err: any) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError('Failed to select workspace.');
      }
    } finally {
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

  if (selectTenantMode) {
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
            <h1>{t('login.select_tenant_title')}</h1>
            <p className="login-subtitle">{t('login.select_tenant_subtitle')}</p>
          </div>

          {/* Error */}
          {error && <div className="login-error">{error}</div>}

          <form onSubmit={handleSelectTenant} className="login-form">
            <div className="form-group">
              <label>{t('login.select_project')}</label>
              <select
                value={selectedTenantIndex ?? ''}
                onChange={(e) => setSelectedTenantIndex(e.target.value === '' ? null : Number(e.target.value))}
              >
                <option value="">—</option>
                {oidcTenants.map((t, idx) => (
                  <option key={`${t.hackathon_id}-${t.team_id}`} value={idx}>
                    {t.hackathon_name} - {t.team_name || t.team_id} ({t.role.toUpperCase()})
                  </option>
                ))}
              </select>
            </div>

            <button type="submit" className="btn btn-primary login-btn" disabled={loading || selectedTenantIndex === null}>
              <LogIn size={18} />
              {loading ? t('common.loading') : t('login.access_workspace_btn')}
            </button>
          </form>

          <div className="login-footer">
            <button
              className="btn btn-ghost"
              onClick={() => {
                setSelectTenantMode(false);
                setOidcTempToken(null);
                setOidcTenants([]);
                setSelectedTenantIndex(null);
              }}
            >
              ← Cancel
            </button>
          </div>
        </div>
      </div>
    );
  }

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

          {/* SSO Divider & Button */}
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
