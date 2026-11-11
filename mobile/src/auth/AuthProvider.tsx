import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import * as SecureStore from "expo-secure-store";
import { getIdentity, loginOwner, logoutOwner, registerOwner, type LoginInput, type OwnerSession, type RegisterInput } from "../api/auth.mjs";
import { getConnection } from "../connection";
import { restoreSession } from "./session.mjs";

const STORAGE_KEY = "leadlane.owner-session.v1";
type AuthState = {
  session: OwnerSession | null;
  restoring: boolean;
  restoreError: string | null;
  storageWarning: boolean;
  retryRestore: () => Promise<void>;
  retryStorage: () => Promise<void>;
  signIn: (input: LoginInput) => Promise<void>;
  signUp: (input: RegisterInput) => Promise<void>;
  signOut: () => Promise<boolean>;
  invalidate: (token: string) => void;
};
const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<OwnerSession | null>(null);
  const [restoring, setRestoring] = useState(true);
  const [restoreError, setRestoreError] = useState<string | null>(null);
  const [storageWarning, setStorageWarning] = useState(false);
  const tokenRef = useRef<string | null>(null);
  const generation = useRef(0);
  const storageQueue = useRef<Promise<unknown>>(Promise.resolve());

  function storage<T,>(operation: () => Promise<T>): Promise<T> {
    // Serialize keystore operations so a delayed "remember" cannot resurrect a
    // token after logout has deleted it.
    const result = storageQueue.current.then(operation);
    storageQueue.current = result.then(() => undefined, () => undefined);
    return result;
  }

  async function retryRestore() {
    const attempt = ++generation.current;
    setRestoring(true);
    setRestoreError(null);
    try {
      const restored = await restoreSession({
        readToken: () => storage(() => SecureStore.getItemAsync(STORAGE_KEY)),
        deleteToken: () => storage(() => SecureStore.deleteItemAsync(STORAGE_KEY)),
        loadIdentity: (token) => getIdentity(token, getConnection()),
      });
      if (attempt !== generation.current) return;
      tokenRef.current = restored?.access_token ?? null;
      setSession(restored);
    } catch {
      if (attempt === generation.current) setRestoreError("We couldn’t restore your session. Check your connection and try again.");
    } finally { if (attempt === generation.current) setRestoring(false); }
  }

  useEffect(() => {
    void retryRestore();
    return () => { generation.current += 1; };
  }, []);

  async function acceptSession(next: OwnerSession) {
    generation.current += 1;
    try { await storage(() => SecureStore.setItemAsync(STORAGE_KEY, next.access_token)); setStorageWarning(false); }
    catch { setStorageWarning(true); }
    tokenRef.current = next.access_token;
    setSession(next);
    setRestoreError(null);
  }

  async function signOut() {
    // If secure storage cannot be cleared, report failure instead of claiming
    // logout succeeded while a reusable credential remains on this device.
    const token = tokenRef.current ?? await storage(() => SecureStore.getItemAsync(STORAGE_KEY));
    await storage(() => SecureStore.deleteItemAsync(STORAGE_KEY));
    generation.current += 1;
    tokenRef.current = null;
    setSession(null);
    setRestoreError(null);
    setStorageWarning(false);
    if (!token) return true;
    try { await logoutOwner(token, getConnection()); return true; }
    catch { return false; }
  }

  function invalidate(token: string) {
    if (tokenRef.current !== token) return;
    tokenRef.current = null;
    generation.current += 1;
    setSession(null);
    setRestoreError(null);
    void storage(() => SecureStore.deleteItemAsync(STORAGE_KEY)).catch(() => setRestoreError("We couldn’t clear an expired session. Please retry."));
  }

  async function retryStorage() {
    if (!tokenRef.current) return;
    const token = tokenRef.current;
    await storage(() => SecureStore.setItemAsync(STORAGE_KEY, token));
    setStorageWarning(false);
  }

  return <AuthContext.Provider value={{ session, restoring, restoreError, storageWarning, retryRestore, retryStorage, signOut, invalidate,
    signIn: async (input) => acceptSession(await loginOwner(input, getConnection())),
    signUp: async (input) => acceptSession(await registerOwner(input, getConnection())),
  }}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("Authentication provider is missing");
  return context;
}

export function useAuthenticatedConnection() {
  const { session, invalidate } = useAuth();
  const token = session?.access_token;
  return {
    ...getConnection(), accessToken: token,
    fetchImpl: (async (url, options) => {
      const response = await fetch(url, options);
      if (response.status === 401 && token) invalidate(token);
      return response;
    }) as typeof fetch,
  };
}
