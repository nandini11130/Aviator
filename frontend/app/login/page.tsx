"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";

export default function LoginPage() {
  const router = useRouter();
  const { signInWithGoogle, continueAsDemoUser, userId, loading } = useAuth();
  const isProduction = process.env.NODE_ENV === "production";
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);

  if (!loading && userId) {
    router.replace("/dashboard");
  }

  const handleGoogleSignIn = async () => {
    try {
      setError(null);
      await signInWithGoogle();
      router.push("/dashboard");
    } catch (err) {
      const authError = err as Error & { code?: string };
      const details = authError.code
        ? `${authError.code}: ${authError.message}`
        : authError.message;
      setError(
        `Google sign-in failed${details ? ` (${details})` : ""}. In Firebase Console, enable Authentication and the Google provider for project aviator-1bbab, and add aviator-1bbab.web.app to Authorized domains.`
      );
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
        Sign in to subscribe and book last-minute empty seats.
      </p>

      <button
        onClick={handleGoogleSignIn}
        className="mb-4 rounded-xl bg-white px-4 py-3 font-semibold text-aviator-midnight hover:bg-blue-50"
      >
        Continue with Google
      </button>

      {error && <p className="mb-4 text-sm text-red-300">{error}</p>}

      {!isProduction && (
        <>
          <div className="my-4 text-center text-xs uppercase tracking-wide text-blue-100/50">
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
