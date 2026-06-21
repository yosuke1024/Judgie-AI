import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from '@/contexts/AuthContext';
import Layout from '@/pages/Layout';
import LoginPage from '@/pages/Login';
import Leaderboard from '@/pages/Leaderboard';
import TeamDashboard from '@/pages/TeamDashboard';
import AdminCenter from '@/pages/admin/AdminCenter';
import SuperAdminConsole from '@/pages/SuperAdminConsole';

function ProtectedRoute({
  children,
  allowedRoles,
}: {
  children: React.ReactNode;
  allowedRoles?: string[];
}) {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="page-loading">
        <div className="spinner" />
        <p>Loading session...</p>
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  if (allowedRoles && !allowedRoles.includes(user.role)) {
    // Redirect unauthorized users to their default safe pages
    if (user.role === 'team') {
      return <Navigate to="/dashboard" replace />;
    } else if (user.role === 'admin' || user.role === 'observer') {
      return <Navigate to="/admin" replace />;
    } else if (user.role === 'superadmin') {
      return <Navigate to="/super-admin" replace />;
    }
    return <Navigate to="/leaderboard" replace />;
  }

  return <>{children}</>;
}

function AppRoutes() {
  const { user } = useAuth();

  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      
      {/* Protected Main App Shell */}
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <Layout />
          </ProtectedRoute>
        }
      >
        {/* Default Route based on user role */}
        <Route
          index
          element={
            user ? (
              user.role === 'team' ? (
                <Navigate to="/dashboard" replace />
              ) : user.role === 'superadmin' ? (
                <Navigate to="/super-admin" replace />
              ) : (
                <Navigate to="/admin" replace />
              )
            ) : (
              <Navigate to="/login" replace />
            )
          }
        />

        <Route
          path="dashboard"
          element={
            <ProtectedRoute allowedRoles={['team']}>
              <TeamDashboard />
            </ProtectedRoute>
          }
        />

        <Route
          path="leaderboard"
          element={
            <ProtectedRoute allowedRoles={['admin', 'observer', 'team']}>
              <Leaderboard />
            </ProtectedRoute>
          }
        />

        <Route
          path="admin"
          element={
            <ProtectedRoute allowedRoles={['admin', 'observer']}>
              <AdminCenter />
            </ProtectedRoute>
          }
        />

        <Route
          path="super-admin"
          element={
            <ProtectedRoute allowedRoles={['superadmin']}>
              <SuperAdminConsole />
            </ProtectedRoute>
          }
        />
      </Route>

      {/* Fallback */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </BrowserRouter>
  );
}
