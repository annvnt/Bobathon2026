"use client";

import { ArrowRight, Loader2 } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { ThemeToggle } from "@/components/theme-toggle";
import { api } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [partnerId, setPartnerId] = useState("P001");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    const pid = partnerId.trim();
    if (!pid) {
      // blank → admin (all companies)
      localStorage.setItem("selectedUserId", "all");
      router.push("/dashboard");
      return;
    }
    setBusy(true);
    try {
      const user = await api.login(pid);
      localStorage.setItem("selectedUserId", user.id);
      router.push("/dashboard");
    } catch {
      setError(`No company found for partner ID "${pid}".`);
    } finally {
      setBusy(false);
    }
  };

  const enterAdmin = () => {
    localStorage.setItem("selectedUserId", "all");
    router.push("/dashboard");
  };

  return (
    <div className="relative flex min-h-screen items-center justify-center px-6">
      <div className="absolute right-6 top-6">
        <ThemeToggle />
      </div>

      <div className="w-full max-w-sm">
        <div className="mb-8 flex items-center gap-2">
          <span className="h-6 w-6 rounded-md bg-accent" />
          <span className="text-lg font-semibold tracking-tight">EcoComply</span>
        </div>

        <h1 className="text-3xl font-semibold tracking-tight">Sign in</h1>
        <p className="mt-2 text-sm text-muted">
          Continuous EU compliance for electronics SMEs.
        </p>

        <form onSubmit={submit} className="mt-8 space-y-4">
          <div>
            <label className="label-mono">Partner ID</label>
            <input
              value={partnerId}
              onChange={(e) => setPartnerId(e.target.value)}
              className="input mt-2 font-mono"
              placeholder="P001 (or 1)"
              autoFocus
            />
            <p className="mt-1.5 text-xs text-muted">
              Your company login is your partner ID, e.g. <code>P001</code>…<code>P022</code>.
            </p>
          </div>
          {error && <p className="text-sm text-red-500">{error}</p>}
          <button type="submit" disabled={busy} className="btn-primary w-full">
            {busy ? <Loader2 size={15} className="animate-spin" /> : <ArrowRight size={15} />}
            Continue
          </button>
        </form>

        <p className="mt-6 text-center text-xs text-muted">
          EcoComply staff?{" "}
          <button onClick={enterAdmin} className="underline underline-offset-2">
            Enter admin view
          </button>
          .
        </p>
        <p className="mt-1 text-center text-xs text-muted">
          <Link href="/dashboard" className="underline underline-offset-2">
            Skip to dashboard
          </Link>
        </p>
      </div>
    </div>
  );
}
