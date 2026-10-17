"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { onAuthStateChanged, signInWithPopup, signOut, type User } from "firebase/auth";
import { auth, googleProvider } from "./firebase";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8080";
const DEMO_USER_STORAGE_KEY = "aviator_demo_user";

interface AuthState {
  firebaseUser: User | null;
  demoUserId: string | null;
  userId: string | null;
  loading: boolean;
  signInWithGoogle: () => Promise<void>;
  continueAsDemoUser: (name: string) => void;
  signOutUser: () => Promise<void>;
  callApi: <T>(path: string, init?: RequestInit) => Promise<T>;
}

const AuthContext = createContext<AuthState | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [firebaseUser, setFirebaseUser] = useState<User | null>(null);
  const [demoUserId, setDemoUserId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (process.env.NODE_ENV === "production") {
      window.localStorage.removeItem(DEMO_USER_STORAGE_KEY);
    } else {
      setDemoUserId(window.localStorage.getItem(DEMO_USER_STORAGE_KEY));
    }
    const unsubscribe = onAuthStateChanged(auth, (user) => {
      setFirebaseUser(user);
      setLoading(false);
    });
    return unsubscribe;
  }, []);

  const signInWithGoogle = useCallback(async () => {
    await signInWithPopup(auth, googleProvider);
  }, []);

  const continueAsDemoUser = useCallback((name: string) => {
    const slug = name.trim().toLowerCase().replace(/\s+/g, "-") || "guest";
    const id = `demo-${slug}`;
    window.localStorage.setItem(DEMO_USER_STORAGE_KEY, id);
    setDemoUserId(id);
  }, []);

  const signOutUser = useCallback(async () => {
    window.localStorage.removeItem(DEMO_USER_STORAGE_KEY);
    setDemoUserId(null);
    await signOut(auth);
  }, []);

  const callApi = useCallback(
    async <T,>(path: string, init: RequestInit = {}): Promise<T> => {
      const headers: Record<string, string> = {
        "Content-Type": "application/json",
        ...((init.headers as Record<string, string>) ?? {}),
      };
      if (firebaseUser) {
        headers.Authorization = `Bearer ${await firebaseUser.getIdToken()}`;
      } else if (demoUserId) {
        headers["X-User-Id"] = demoUserId;
      } else {
        throw new Error("Sign in (or continue as a demo user) first.");
      }

      const response = await fetch(`${API_BASE}${path}`, { ...init, headers });
      if (!response.ok) {
        const body = await response.text();
        throw new Error(body || `Request to ${path} failed (${response.status}).`);
      }
      if (response.status === 204) {
        return undefined as T;
      }
      return (await response.json()) as T;
    },
    [firebaseUser, demoUserId]
  );

  const userId = firebaseUser?.uid ?? demoUserId;

  return (
    <AuthContext.Provider
      value={{
        firebaseUser,
        demoUserId,
        userId,
        loading,
        signInWithGoogle,
        continueAsDemoUser,
        signOutUser,
        callApi,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return ctx;
}
