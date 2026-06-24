import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';
import { authApi } from '@/api/client';

interface User {
  team_id: string;
  role: string;
  product_name?: string;
  team_name?: string;
  one_liner?: string;
  max_consultations?: number;
  consultation_count?: number;
  max_qa_turns?: number;
}

interface AuthContextType {
  user: User | null;
  loading: boolean;
  login: (teamId: string, passcode: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  const refreshUser = async () => {
    try {
      const data = await authApi.me();
      setUser(data);
    } catch {
      setUser(null);
    }
  };

  useEffect(() => {
    refreshUser().finally(() => setLoading(false));
  }, []);

  const login = async (teamId: string, passcode: string) => {
    await authApi.login({
      team_id: teamId,
      passcode,
    });
    await refreshUser();
  };

  const logout = async () => {
    await authApi.logout();
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, logout, refreshUser }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
