import { useAuth } from '@/contexts/AuthContext';
import { useTranslation } from 'react-i18next';
import { Outlet, NavLink, useNavigate } from 'react-router-dom';
import { LayoutDashboard, Trophy, Settings, Shield, LogOut, Zap, Globe } from 'lucide-react';

export default function Layout() {
  const { user, logout } = useAuth();
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  const toggleLang = () => {
    i18n.changeLanguage(i18n.language === 'en' ? 'ja' : 'en');
  };

  if (!user) return null;

  const showAdminCenter = user.role === 'admin' || user.role === 'observer';

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

          {user.role === 'superadmin' && (
            <NavLink to="/super-admin" className="nav-link">
              <Shield size={18} />
              <span>{t('nav.super_admin')}</span>
            </NavLink>
          )}
        </nav>

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
      </aside>

      <main className="main-content">
        <Outlet />
      </main>
    </div>
  );
}
