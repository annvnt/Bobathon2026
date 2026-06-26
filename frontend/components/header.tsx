"use client";

import { Loader2, RefreshCw } from "lucide-react";
import { useState } from "react";
import { api } from "@/lib/api";
import { useApp } from "@/lib/app-context";
import { ThemeToggle } from "./theme-toggle";

/** Floating controls pill (top-right): company selector, scan trigger, theme. */
export function Header() {
  const { users, selectedUserId, setSelectedUserId, selectedCompany, bumpRefresh } =
    useApp();
  const [scanning, setScanning] = useState(false);
  const [toast, setToast] = useState<string | null>(null);

  const runScan = async () => {
    setScanning(true);
    setToast(null);
    try {
      const res = await api.scan();
      setToast(res.message);
      bumpRefresh();
    } catch {
      setToast("Scan failed — check OPENROUTER_API_KEY / backend.");
    } finally {
      setScanning(false);
      setTimeout(() => setToast(null), 7000);
    }
  };

  return (
    <div className="flex flex-col items-end gap-2">
      <div className="flex items-center gap-1.5 rounded-full border border-border bg-elevated/80 p-1.5 shadow-lg shadow-black/20 backdrop-blur-xl">
        <select
          value={selectedUserId ?? "all"}
          onChange={(e) =>
            setSelectedUserId(e.target.value === "all" ? null : e.target.value)
          }
          className="max-w-[130px] cursor-pointer truncate rounded-full bg-transparent px-3 py-1.5 text-sm text-fg outline-none sm:max-w-[200px]"
        >
          <option value="all">All companies (admin)</option>
          {users.map((u) => (
            <option key={u.id} value={u.id}>
              {u.company_name}
            </option>
          ))}
        </select>
        <button onClick={runScan} disabled={scanning} className="btn-primary rounded-full">
          {scanning ? (
            <Loader2 size={15} className="animate-spin" />
          ) : (
            <RefreshCw size={15} />
          )}
          Scan
        </button>
        <ThemeToggle />
        <div className="hidden h-9 w-9 items-center justify-center rounded-full border border-border bg-surface text-xs font-medium sm:flex">
          {selectedCompany.slice(0, 2).toUpperCase()}
        </div>
      </div>
      {toast && (
        <span className="max-w-xs rounded-lg border border-border bg-elevated/90 px-3 py-1.5 text-xs text-muted shadow-lg backdrop-blur">
          {toast}
        </span>
      )}
    </div>
  );
}
