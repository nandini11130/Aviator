"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";

export default function LoginPage() {
  const router = useRouter();
  const {
    signInWithGoogle,
    signInWithEmailPassword,
    createEmailAccount,
    sendPasswordReset,
    continueAsDemoUser,
    userId,
    loading,
  } = useAuth();
  const isProduction = process.env.NODE_ENV === "production";
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [mode, setMode] = useState<"signin" | "signup">("signin");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  if (!loading && userId) {
    router.replace("/dashboard");
  }

  const handleGoogleSignIn = async () => {
    try {
      setError(null);
      const redirecting = await signInWithGoogle();
      if (!redirecting) {
        router.push("/dashboard");
      }
    } catch (err) {
      const authError = err as Error & { code?: string };
      const details = authError.code
        ? `${authError.code}: ${authError.message}`
        : authError.message;
      const guidance =
        authError.code === "auth/unauthorized-domain"
          ? "Add aviator-1bbab.web.app to Firebase Authentication's Authorized domains."
          : "Please try again or contact support if the problem continues.";
      setError(`Google sign-in failed${details ? ` (${details})` : ""}. ${guidance}`);
    }
  };

  const handleEmailAuth = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    setNotice(null);
    setBusy(true);
    try {
      if (mode === "signup") {
        await createEmailAccount(email.trim(), password);
      } else {
        await signInWithEmailPassword(email.trim(), password);
      }
      router.push("/dashboard");
    } catch (err) {
      const code = (err as { code?: string }).code;
      const messages: Record<string, string> = {
        "auth/email-already-in-use": "An account already exists for this email. Sign in instead.",
        "auth/invalid-email": "Enter a valid email address.",
        "auth/invalid-credential": "Email or password is incorrect.",
        "auth/weak-password": "Choose a password with at least 6 characters.",
        "auth/too-many-requests": "Too many attempts. Please wait a little and try again.",
        "auth/operation-not-allowed":
          "Email/password sign-in is not enabled for this Firebase project.",
        "auth/network-request-failed": "Network error. Check your connection and try again.",
      };
      setError(
        code && messages[code]
          ? messages[code]
          : `Email ${mode === "signup" ? "sign-up" : "sign-in"} failed: ${
              (err as Error).message
            }`
      );
    } finally {
      setBusy(false);
    }
  };

  const handlePasswordReset = async () => {
    setError(null);
    setNotice(null);
    if (!email.trim()) {
      setError("Enter your email address first, then choose Forgot password.");
      return;
    }
    setBusy(true);
    try {
      await sendPasswordReset(email.trim());
      setNotice("If an account exists for that address, Firebase will send a password-reset email.");
    } catch (err) {
      const code = (err as { code?: string }).code;
      setError(
        code === "auth/invalid-email"
          ? "Enter a valid email address."
          : `Could not send password reset email: ${(err as Error).message}`
      );
    } finally {
      setBusy(false);
    }
  };

  const handleDemo = () => {
    continueAsDemoUser(name || "guest");
    router.push("/dashboard");
  };

  return (
    <main className="mx-auto flex min-h-screen max-w-md flex-col justify-center px-6">
      <h1 className="mb-2 text-2xl font-bold">Welcome to Aviator</h1>
      <p className="mb-8 text-sm text-blue-100/70">
        Sign in to subscribe and try demo bookings on flight schedules.
      </p>

      <button
        onClick={handleGoogleSignIn}
        disabled={busy}
        className="mb-4 rounded-xl bg-white px-4 py-3 font-semibold text-aviator-midnight hover:bg-blue-50 disabled:opacity-50"
      >
        Continue with Google
      </button>

      <div className="my-4 flex items-center gap-3 text-xs uppercase tracking-wide text-blue-100/50">
        <span className="h-px flex-1 bg-white/10" />
        or use email
        <span className="h-px flex-1 bg-white/10" />
      </div>

      <form onSubmit={handleEmailAuth} className="flex flex-col gap-3">
        <label htmlFor="email" className="text-sm text-blue-100/80">
          Email
        </label>
        <input
          id="email"
          type="email"
          autoComplete="email"
          required
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          placeholder="you@example.com"
          className="rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-sm placeholder:text-blue-100/40"
        />
        <label htmlFor="password" className="text-sm text-blue-100/80">
          Password
        </label>
        <input
          id="password"
          type="password"
          autoComplete={mode === "signup" ? "new-password" : "current-password"}
          minLength={6}
          required
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          placeholder={mode === "signup" ? "At least 6 characters" : "Your password"}
          className="rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-sm placeholder:text-blue-100/40"
        />
        <button
          type="submit"
          disabled={busy}
          className="mt-2 rounded-xl bg-aviator-sky px-4 py-3 font-semibold text-white disabled:opacity-50"
        >
          {busy
            ? "Please wait..."
            : mode === "signup"
              ? "Create account"
              : "Sign in with email"}
        </button>
      </form>

      <div className="mt-3 flex items-center justify-between text-sm">
        <button
          type="button"
          onClick={() => {
            setMode(mode === "signin" ? "signup" : "signin");
            setError(null);
            setNotice(null);
          }}
          className="text-blue-200 hover:text-white"
        >
          {mode === "signin" ? "Create an account" : "Already have an account? Sign in"}
        </button>
        {mode === "signin" && (
          <button
            type="button"
            disabled={busy}
            onClick={handlePasswordReset}
            className="text-blue-100/60 hover:text-white disabled:opacity-50"
          >
            Forgot password?
          </button>
        )}
      </div>

      {error && <p role="alert" className="mt-4 text-sm text-red-300">{error}</p>}
      {notice && <p role="status" className="mt-4 text-sm text-emerald-200">{notice}</p>}

      {!isProduction && (
        <>
          <div className="my-5 text-center text-xs uppercase tracking-wide text-blue-100/50">
            or try it instantly
          </div>

          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Your name (demo mode)"
            className="mb-3 rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-sm placeholder:text-blue-100/40"
          />
          <button
            onClick={handleDemo}
            className="rounded-xl bg-aviator-gold px-4 py-3 font-semibold text-aviator-midnight hover:brightness-95"
          >
            Continue as demo user
          </button>
        </>
      )}
    </main>
  );
}
