import React, { createContext, useContext, useEffect, useState } from "react";
import { api } from "@/lib/api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null); // null=checking, false=guest, obj=user
  const [companies, setCompanies] = useState([]);

  const loadCompanies = async () => {
    try {
      const { data } = await api.get("/companies");
      setCompanies(data);
    } catch (e) {}
  };

  useEffect(() => {
    api
      .get("/auth/me")
      .then(({ data }) => {
        setUser(data);
        loadCompanies();
      })
      .catch(() => setUser(false));
  }, []);

  const login = async (email, password) => {
    const { data } = await api.post("/auth/login", { email, password });
    setUser(data);
    loadCompanies();
    return data;
  };

  const logout = async () => {
    await api.post("/auth/logout");
    setUser(false);
  };

  return (
    <AuthContext.Provider value={{ user, setUser, login, logout, companies, reloadCompanies: loadCompanies }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
