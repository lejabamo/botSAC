import React, { createContext, useState, useContext, type ReactNode } from 'react';

export interface User {
  username: string;
  name: string;
  role: string;
  rol_principal: string;
  token?: string;
}

interface AuthContextType {
  user: User | null;
  login: (username: string, password?: string) => Promise<User>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(() => {
    try {
      const saved = localStorage.getItem('botsac_user');
      return saved ? JSON.parse(saved) : null;
    } catch {
      return null;
    }
  });

  const login = async (username: string, password?: string): Promise<User> => {
    const cleanUser = username.trim().toLowerCase();
    const response = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: cleanUser, password: password || '' })
    });

    if (!response.ok) {
      let detail = 'Error de autenticación.';
      try {
        const errJson = await response.json();
        if (errJson && errJson.detail) detail = errJson.detail;
      } catch {
        // Fallback detail
      }
      throw new Error(detail);
    }

    const data = await response.json();
    const verifiedUser: User = {
      username: data.username,
      name: data.name,
      role: data.role,
      rol_principal: data.rol_principal || 'FUNCIONARIO',
      token: data.token
    };

    localStorage.setItem('botsac_user', JSON.stringify(verifiedUser));
    setUser(verifiedUser);
    return verifiedUser;
  };

  const logout = async () => {
    try {
      const saved = localStorage.getItem('botsac_user');
      const token = saved ? JSON.parse(saved)?.token : user?.token;
      if (token) {
        await fetch('/api/auth/logout', {
          method: 'POST',
          headers: { 'Authorization': `Bearer ${token}` }
        });
      }
    } catch (e) {
      console.warn('Error invalidando sesión en servidor', e);
    } finally {
      localStorage.removeItem('botsac_user');
      setUser(null);
    }
  };

  return (
    <AuthContext.Provider value={{ user, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used within an AuthProvider');
  return context;
};
