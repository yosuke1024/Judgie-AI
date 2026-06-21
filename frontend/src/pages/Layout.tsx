import { useState, useEffect } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { useTranslation } from 'react-i18next';
import { Outlet, NavLink, useNavigate } from 'react-router-dom';
import { LayoutDashboard, Trophy, Settings, Shield, LogOut, Zap, Globe } from 'lucide-react';

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
import { teamsApi, authApi } from '@/api/client';

export default function Layout() {
  const { user, logout, switchTenant } = useAuth();
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const [teams, setTeams] = useState<any[]>([]);
  const [myTenants, setMyTenants] = useState<any[]>([]);

  const showAdminCenter = user?.role === 'admin';
  const showTeamDashboards = user?.role === 'admin' || user?.role === 'observer';

  useEffect(() => {
    if (showTeamDashboards && user?.hackathon_id) {
      teamsApi.list(user.hackathon_id)
        .then((data) => {
          setTeams(data.filter((t) => t.role === 'team'));
        })
        .catch((err) => console.error('Failed to load teams for sidebar:', err));
    }
  }, [showTeamDashboards, user?.hackathon_id]);

  useEffect(() => {
    if (user) {
      authApi.getMyTenants()
        .then((data) => setMyTenants(data))
        .catch((err) => console.error('Failed to load my tenants for switcher:', err));
    }
  }, [user]);

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  const handleTenantChange = async (hackathonId: number, teamId: string) => {
    try {
      await switchTenant(hackathonId, teamId);
      navigate('/');
    } catch (err) {
      console.error('Failed to switch project:', err);
    }
  };

  const toggleLang = () => {
    i18n.changeLanguage(i18n.language === 'en' ? 'ja' : 'en');
  };

  if (!user) return null;


  return (
    <div className="app-layout">
      <aside className="sidebar">
        <div className="sidebar-brand">
          <Zap size={24} />
          <span>Judgie-AI</span>
        </div>

        <nav className="sidebar-nav">
          {user.role === 'team' && (
            <NavLink to="/dashboard" className="nav-link">
              <LayoutDashboard size={18} />
              <span>{t('nav.dashboard')}</span>
            </NavLink>
          )}

          {user.role !== 'superadmin' && (
            <NavLink to="/leaderboard" className="nav-link">
              <Trophy size={18} />
              <span>{t('nav.leaderboard')}</span>
            </NavLink>
          )}

          {showAdminCenter && (
            <NavLink to="/admin" className="nav-link">
              <Settings size={18} />
              <span>{t('nav.admin_center')}</span>
            </NavLink>
          )}

          {showTeamDashboards && (
            <>
              <div className="sidebar-section-header" style={{
                padding: '12px 16px 4px 16px',
                fontSize: '0.75rem',
                fontWeight: 600,
                color: '#6b7280',
                textTransform: 'uppercase',
                letterSpacing: '0.05em'
              }}>
                {t('nav.team_dashboards')}
              </div>
              <div className="sidebar-teams-list" style={{
                maxHeight: '200px',
                overflowY: 'auto',
                display: 'flex',
                flexDirection: 'column',
                gap: '2px',
                padding: '0 8px'
              }}>
                {teams.map((t) => (
                  <NavLink
                    key={t.team_id}
                    to={`/admin/teams/${t.team_id}`}
                    className="nav-link nav-link-sub"
                    style={({ isActive }) => ({
                      padding: '6px 12px',
                      fontSize: '0.85rem',
                      borderRadius: '4px',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '8px',
                      color: isActive ? '#ffffff' : '#9ca3af',
                      background: isActive ? 'rgba(255,255,255,0.08)' : 'transparent',
                      textDecoration: 'none'
                    })}
                  >
                    <div style={{
                      width: '6px',
                      height: '6px',
                      borderRadius: '50%',
                      background: '#10b981',
                      flexShrink: 0
                    }} />
                    <span style={{
                      whiteSpace: 'nowrap',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis'
                    }}>
                      {t.product_name || t.team_name || t.team_id}
                    </span>
                  </NavLink>
                ))}
                {teams.length === 0 && (
                  <div style={{ padding: '8px 12px', fontSize: '0.8rem', color: '#6b7280' }}>
                    No teams.
                  </div>
                )}
              </div>
            </>
          )}

          {user.role === 'superadmin' && (
            <NavLink to="/super-admin" className="nav-link">
              <Shield size={18} />
              <span>{t('nav.super_admin')}</span>
            </NavLink>
          )}
        </nav>

        {myTenants.length > 1 && (
          <div className="sidebar-tenant-switcher" style={{
            padding: '12px 16px',
            borderTop: '1px solid rgba(255,255,255,0.08)',
            display: 'flex',
            flexDirection: 'column',
            gap: '6px'
          }}>
            <label style={{ fontSize: '0.7rem', color: '#9ca3af', fontWeight: 600 }}>
              {t('login.select_project').toUpperCase()}
            </label>
            <select
              value={`${user.hackathon_id}-${user.team_id}`}
              onChange={(e) => {
                const [hId, tId] = e.target.value.split('-');
                handleTenantChange(Number(hId), tId);
              }}
              style={{
                width: '100%',
                padding: '6px 8px',
                fontSize: '0.85rem',
                background: '#1f2937',
                color: '#ffffff',
                border: '1px solid #374151',
                borderRadius: '4px',
                cursor: 'pointer'
              }}
            >
              {myTenants.map((t) => (
                <option key={`${t.hackathon_id}-${t.team_id}`} value={`${t.hackathon_id}-${t.team_id}`}>
                  {t.hackathon_name} - {t.team_name || t.team_id} ({t.role.toUpperCase()})
                </option>
              ))}
            </select>
          </div>
        )}

        <div className="sidebar-footer">
          <div className="user-badge">
            <span className="user-role">{user.role.toUpperCase()}</span>
            <span className="user-name">{user.team_id}</span>
          </div>
          <button className="btn btn-icon" onClick={toggleLang} title="Switch Language">
            <Globe size={16} />
          </button>
          <button className="btn btn-icon btn-danger" onClick={handleLogout} title={t('nav.logout')}>
            <LogOut size={16} />
          </button>
        </div>

        <div className="sidebar-credits" style={{
          marginTop: '12px',
          paddingTop: '12px',
          borderTop: '1px solid rgba(255,255,255,0.06)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          fontSize: '0.7rem',
          color: '#6b7280'
        }}>
          <a
            href="https://pixapps.ai/"
            target="_blank"
            rel="noopener noreferrer"
            style={{ color: '#6b7280', textDecoration: 'none', transition: 'color 0.2s' }}
            onMouseOver={(e) => (e.currentTarget.style.color = '#9ca3af')}
            onMouseOut={(e) => (e.currentTarget.style.color = '#6b7280')}
          >
            {t('credits.produced_by')}
          </a>
          <a
            href="https://github.com/yosuke1024/Judgie-AI"
            target="_blank"
            rel="noopener noreferrer"
            style={{ color: '#6b7280', display: 'flex', alignItems: 'center', gap: '4px', textDecoration: 'none', transition: 'color 0.2s' }}
            onMouseOver={(e) => (e.currentTarget.style.color = '#9ca3af')}
            onMouseOut={(e) => (e.currentTarget.style.color = '#6b7280')}
          >
            <GithubIcon size={12} />
            <span>{t('credits.github')}</span>
          </a>
        </div>
      </aside>

      <main className="main-content">
        <Outlet />
      </main>
    </div>
  );
}
