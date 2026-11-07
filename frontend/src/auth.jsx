import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { api } from "./api";

const KEY = "shotsense_token";
const DEMO_KEY = "shotsense_demo_used";
const AuthContext = createContext(null);

export function demoUsedHere() {
  try {
    return localStorage.getItem(DEMO_KEY) === "1";
  } catch {
    return false;
  }
}

function markDemoUsed() {
  try {
    localStorage.setItem(DEMO_KEY, "1");
  } catch {
    /* the server-side cookie and IP checks still apply */
  }
}

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

  const startDemo = useCallback(async () => {
    try {
      const { access_token } = await api("/api/auth/guest", { method: "POST" });
      markDemoUsed();
      writeToken(access_token);
      setChecking(true);
      setToken(access_token);
    } catch (err) {
      if (err.status === 429) markDemoUsed();
      throw err;
    }
  }, []);

  const refreshUser = useCallback(() => {
    if (!token) return;
    api("/api/auth/me", { token })
      .then(setUser)
      .catch((err) => err.status === 401 && signOut());
  }, [token, signOut]);

  const value = useMemo(
    () => ({ token, user, checking, authenticate, startDemo, refreshUser, signOut }),
    [token, user, checking, authenticate, startDemo, refreshUser, signOut],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  return useContext(AuthContext);
}
