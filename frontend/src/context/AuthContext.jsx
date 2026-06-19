import { createContext, useContext, useEffect, useState } from "react";
import api from "../api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    const raw = localStorage.getItem("pg_user");
    return raw ? JSON.parse(raw) : null;
  });
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    // Validate any stored token on first load.
    const token = localStorage.getItem("pg_token");
    if (token && !user) {
      api.get("/api/auth/me").then(
        (res) => setUser(res.data),
        () => logout()
      );
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function login(email, password) {
    setLoading(true);
    try {
      const res = await api.post("/api/auth/login", { email, password });
      localStorage.setItem("pg_token", res.data.access_token);
      localStorage.setItem("pg_user", JSON.stringify(res.data.user));
      setUser(res.data.user);
      return res.data.user;
    } finally {
      setLoading(false);
    }
  }

  function logout() {
    localStorage.removeItem("pg_token");
    localStorage.removeItem("pg_user");
    setUser(null);
  }

  const isAnalyst = user && (user.role === "analyst" || user.role === "admin");

  return (
    <AuthContext.Provider value={{ user, loading, login, logout, isAnalyst }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
