import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { api } from "./api";

const KEY = "shotsense_token";
const AuthContext = createContext(null);

function readToken() {
  try {
    return localStorage.getItem(KEY);
  } catch {
    return null;
  }
}

function writeToken(token) {
  try {
    if (token) localStorage.setItem(KEY, token);
    else localStorage.removeItem(KEY);
  } catch {
    /* storage unavailable: session lasts until the tab closes */
  }
}

export function AuthProvider({ children }) {
  const [token, setToken] = useState(readToken);
  const [user, setUser] = useState(null);
  const [checking, setChecking] = useState(Boolean(readToken()));

  const signOut = useCallback(() => {
    writeToken(null);
    setToken(null);
    setUser(null);
  }, []);

  useEffect(() => {
    if (!token) {
      setChecking(false);
      return;
    }
    let cancelled = false;
    api("/api/auth/me", { token })
      .then((u) => !cancelled && setUser(u))
      .catch((err) => {
        if (!cancelled && err.status === 401) signOut();
      })
      .finally(() => !cancelled && setChecking(false));
    return () => {
      cancelled = true;
    };
  }, [token, signOut]);

  const authenticate = useCallback(async (mode, email, password) => {
    const path = mode === "register" ? "/api/auth/register" : "/api/auth/login";
    const { access_token } = await api(path, { method: "POST", body: { email, password } });
    writeToken(access_token);
    setChecking(true);
    setToken(access_token);
  }, []);

  const value = useMemo(
    () => ({ token, user, checking, authenticate, signOut }),
    [token, user, checking, authenticate, signOut],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  return useContext(AuthContext);
}
