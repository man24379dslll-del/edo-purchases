import { createContext, useContext, useEffect, useState, useCallback } from "react";
import { api, setToken } from "../api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  const loadMe = useCallback(async () => {
    try {
      const u = await api.me();
      setUser(u);
    } catch (_) {
      setUser(null);
      setToken(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (localStorage.getItem("edo_token")) loadMe();
    else setLoading(false);
  }, [loadMe]);

  async function login(email, password) {
    const data = await api.login(email, password);
    setToken(data.access_token);
    setUser({ email: data.email, fio: data.fio, role: data.role, is_active: true });
  }

  function logout() {
    setToken(null);
    setUser(null);
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
