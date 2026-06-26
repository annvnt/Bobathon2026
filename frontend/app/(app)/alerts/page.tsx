"use client";

import { Check, ChevronDown, ExternalLink } from "lucide-react";
import { useEffect, useState } from "react";
import { Badge, EmptyState, severityTone } from "@/components/ui";
import { api } from "@/lib/api";
import { useApp } from "@/lib/app-context";
import type { Alert } from "@/lib/types";

export default function AlertsPage() {
  const { selectedUserId, refreshKey, bumpRefresh } = useApp();
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [loading, setLoading] = useState(true);
  const [onlyUnread, setOnlyUnread] = useState(false);
  const [open, setOpen] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    api
      .listAlerts({
        user_id: selectedUserId ?? undefined,
        is_read: onlyUnread ? false : undefined,
      })
      .then(setAlerts)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [selectedUserId, onlyUnread, refreshKey]);

  useEffect(() => {
    const focus = new URLSearchParams(window.location.search).get("focus");
    if (focus) setOpen(focus);
  }, []);

  const markRead = async (id: string) => {
    const updated = await api.markAlertRead(id);
    setAlerts((prev) => prev.map((a) => (a.id === id ? updated : a)));
    bumpRefresh();
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="label-mono">Compliance gaps</p>
          <h1 className="mt-1 text-3xl font-semibold tracking-tight">Alerts</h1>
        </div>
        <label className="flex cursor-pointer items-center gap-2 text-sm text-muted">
          <input
            type="checkbox"
            checked={onlyUnread}
            onChange={(e) => setOnlyUnread(e.target.checked)}
            className="accent-current"
          />
          Unread only
        </label>
      </div>

      {loading ? (
        <div className="card h-64 animate-pulse" />
      ) : alerts.length === 0 ? (
        <EmptyState
          title="No alerts"
          hint="Run the daily scan from the header to assess your portfolio."
        />
      ) : (
        <div className="space-y-3">
          {alerts.map((a) => (
            <div
              key={a.id}
              className={`card overflow-hidden ${a.is_read ? "opacity-60" : ""}`}
            >
              <button
                onClick={() => setOpen(open === a.id ? null : a.id)}
                className="flex w-full items-center gap-4 px-5 py-4 text-left transition-colors hover:bg-surface"
              >
                <Badge tone={severityTone(a.severity)}>{a.severity}</Badge>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium">
                    {a.product_name} · {a.regulation_label}
                    {a.company_name && (
                      <span className="text-muted"> — {a.company_name}</span>
                    )}
                  </p>
                  <p className="truncate text-sm text-muted">{a.gap}</p>
                </div>
                <span className="hidden shrink-0 font-mono text-xs text-muted sm:block">
                  {a.deadline ?? "—"}
                </span>
                <ChevronDown
                  size={16}
                  className={`shrink-0 text-muted transition-transform ${
                    open === a.id ? "rotate-180" : ""
                  }`}
                />
              </button>

              {open === a.id && (
                <div className="space-y-4 border-t border-border px-5 py-5 text-sm">
                  <Section title="Regulation">
                    {a.regulation_title || a.regulation_label}
                  </Section>
                  <Section title="What is required">{a.requirement}</Section>
                  <Section title="The gap">{a.gap}</Section>
                  <Section title="Recommended action">
                    {a.recommended_action}
                  </Section>

                  {(a.product_impact || a.business_impact) && (
                    <div className="grid gap-3 sm:grid-cols-2">
                      {a.product_impact && (
                        <div className="rounded-lg border border-border bg-surface p-3">
                          <p className="label-mono">Product impact</p>
                          <p className="mt-1 text-fg/90">{a.product_impact}</p>
                        </div>
                      )}
                      {a.business_impact && (
                        <div className="rounded-lg border border-border bg-surface p-3">
                          <p className="label-mono">Business impact</p>
                          <p className="mt-1 text-fg/90">{a.business_impact}</p>
                        </div>
                      )}
                    </div>
                  )}

                  {a.key_dates.length > 0 && (
                    <div>
                      <p className="label-mono">Key dates</p>
                      <div className="mt-1.5 flex flex-wrap gap-1.5">
                        {a.key_dates.map((d) => (
                          <Badge key={d} tone="medium">
                            {d}
                          </Badge>
                        ))}
                      </div>
                    </div>
                  )}

                  {a.citations.length > 0 && (
                    <div>
                      <p className="label-mono">
                        Cited regulation lines · cause &amp; effect
                      </p>
                      <div className="mt-2 space-y-2">
                        {a.citations.map((c) => (
                          <div
                            key={c.line_no}
                            className="rounded-lg border border-border bg-surface p-3"
                          >
                            <div className="flex items-start gap-2">
                              <span className="mt-0.5 font-mono text-[11px] text-muted">
                                L{c.line_no}
                              </span>
                              <p className="flex-1 font-mono text-[12px] leading-relaxed text-fg/80">
                                “{c.text}”
                              </p>
                            </div>
                            <div className="mt-2 grid gap-1 pl-7 text-[13px]">
                              <p>
                                <span className="text-muted">Cause → </span>
                                {c.cause.replace(/^The regulation requires:\s*/, "")}
                              </p>
                              <p>
                                <span className="text-muted">Effect → </span>
                                {c.effect}
                              </p>
                              {c.dates.length > 0 && (
                                <p className="text-muted">
                                  Dates: {c.dates.join(", ")}
                                </p>
                              )}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  <div className="flex flex-wrap items-center gap-4">
                    <Badge tone="outline">confidence {a.confidence}%</Badge>
                    <Badge tone="outline">delivery: {a.delivery_status}</Badge>
                    {a.source_url && (
                      <a
                        href={a.source_url}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex items-center gap-1 text-muted underline-offset-2 hover:text-fg hover:underline"
                      >
                        Source <ExternalLink size={13} />
                      </a>
                    )}
                    <div className="ml-auto">
                      {!a.is_read && (
                        <button
                          onClick={() => markRead(a.id)}
                          className="btn-ghost"
                        >
                          <Check size={15} /> Mark read
                        </button>
                      )}
                    </div>
                  </div>
                  <div className="rounded-lg border border-border bg-surface p-3 font-mono text-xs text-muted">
                    {a.alert_message}
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <p className="label-mono">{title}</p>
      <p className="mt-1 text-fg/90">{children}</p>
    </div>
  );
}
