"use client";

import { useEffect, useState } from "react";
import { Badge } from "@/components/ui";
import { useTheme } from "@/lib/theme";
import type { Taxonomy } from "@/lib/types";
import { api } from "@/lib/api";

export default function SettingsPage() {
  const { theme, toggle } = useTheme();
  const [taxonomy, setTaxonomy] = useState<Taxonomy | null>(null);

  useEffect(() => {
    api.taxonomy().then(setTaxonomy).catch(() => {});
  }, []);

  return (
    <div className="max-w-2xl space-y-8">
      <div>
        <p className="label-mono">Configuration</p>
        <h1 className="mt-1 text-3xl font-semibold tracking-tight">Settings</h1>
      </div>

      <div className="card divide-y divide-border">
        <Row label="Appearance" hint="Light and dark themes.">
          <button onClick={toggle} className="btn-ghost capitalize">
            {theme} mode
          </button>
        </Row>
        <Row label="LLM provider" hint="OpenRouter (openai/gpt-4o-mini). Set OPENROUTER_API_KEY in backend/.env.">
          <Badge tone="outline">openrouter</Badge>
        </Row>
        <Row
          label="Alert delivery"
          hint="Set ALERTS_PROVIDER in backend/.env (mock · twilio)."
        >
          <Badge tone="outline">configurable</Badge>
        </Row>
        <Row label="Daily sync" hint="APScheduler runs the MCP sync each day at 00:00.">
          <Badge tone="low">enabled</Badge>
        </Row>
      </div>

      {taxonomy && (
        <div>
          <h2 className="mb-3 text-lg font-semibold tracking-tight">
            Monitored regulation families
          </h2>
          <div className="flex flex-wrap gap-1.5">
            {Object.keys(taxonomy.regulation_families).map((f) => (
              <Badge key={f} tone="outline">
                {f}
              </Badge>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function Row({
  label,
  hint,
  children,
}: {
  label: string;
  hint: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex items-center justify-between gap-4 px-5 py-4">
      <div>
        <p className="text-sm font-medium">{label}</p>
        <p className="text-xs text-muted">{hint}</p>
      </div>
      {children}
    </div>
  );
}
