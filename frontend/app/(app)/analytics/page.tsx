"use client";

import {
  AlertTriangle,
  CalendarClock,
  Euro,
  Layers,
  PieChart,
  ShieldCheck,
  TrendingUp,
} from "lucide-react";
import { useEffect, useState } from "react";
import { BarChart, Donut, Orb, SectionCard, SEV_COLOR, colorAt } from "@/components/charts";
import { Badge, EmptyState } from "@/components/ui";
import { api } from "@/lib/api";
import { useApp } from "@/lib/app-context";
import type { Analytics } from "@/lib/types";

function eur(n: number): string {
  if (n >= 1_000_000) return `€${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `€${Math.round(n / 1_000)}k`;
  return `€${n}`;
}

export default function AnalyticsPage() {
  const { selectedUserId, selectedCompany, refreshKey } = useApp();
  const [a, setA] = useState<Analytics | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    api
      .analytics(selectedUserId ?? undefined)
      .then(setA)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [selectedUserId, refreshKey]);

  if (loading)
    return (
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="card h-56 animate-pulse" />
        ))}
      </div>
    );

  if (!a || a.totals.open_alerts === 0)
    return (
      <div className="space-y-6">
        <Header company={selectedCompany} />
        <EmptyState
          title="No analytics yet"
          hint="Run the daily scan from the header to generate compliance insights."
        />
      </div>
    );

  const severitySegments = [
    { label: "high", value: a.by_severity.high || 0, color: SEV_COLOR.high },
    { label: "medium", value: a.by_severity.medium || 0, color: SEV_COLOR.medium },
    { label: "low", value: a.by_severity.low || 0, color: SEV_COLOR.low },
  ].filter((s) => s.value > 0);

  const byLabel = Object.entries(a.by_label)
    .map(([label, value]) => ({ label, value }))
    .sort((x, y) => y.value - x.value);

  const byCategory = Object.entries(a.by_category)
    .map(([label, value]) => ({ label: label.replace(/_/g, " "), value }))
    .sort((x, y) => y.value - x.value);

  return (
    <div className="space-y-6">
      <Header company={selectedCompany} />

      {/* Impact orbs */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <SectionCard title="Portfolio risk" icon={TrendingUp}>
          <div className="flex justify-center py-1">
            <Orb value={a.orbs.portfolio_risk} label="risk" />
          </div>
        </SectionCard>
        <SectionCard title="Compliance health" icon={ShieldCheck}>
          <div className="flex justify-center py-1">
            <Orb
              value={a.orbs.compliance_health}
              label="health"
              color={a.orbs.compliance_health >= 66 ? "#10b981" : a.orbs.compliance_health >= 33 ? "#f59e0b" : "#ef4444"}
            />
          </div>
        </SectionCard>
        <SectionCard title="Fine exposure" icon={Euro}>
          <div className="flex justify-center py-1">
            <Orb
              value={Math.min(100, (a.orbs.fine_exposure_eur / 2_000_000) * 100)}
              display={eur(a.orbs.fine_exposure_eur)}
              label="at risk"
              color="#ef4444"
            />
          </div>
        </SectionCard>
        <SectionCard title="Deadline pressure" icon={CalendarClock}>
          <div className="flex justify-center py-1">
            <Orb value={a.orbs.deadline_pressure} label="pressure" />
          </div>
        </SectionCard>
      </div>

      {/* totals strip */}
      <div className="grid gap-4 sm:grid-cols-4">
        <Mini label="Products" value={a.totals.products} />
        <Mini label="Open gaps" value={a.totals.open_alerts} />
        <Mini label="Flagged products" value={a.totals.flagged_products} />
        <Mini label="Clean products" value={a.totals.clean_products} />
      </div>

      {/* charts */}
      <div className="grid gap-4 lg:grid-cols-2">
        <SectionCard title="Gaps by severity" icon={PieChart}>
          {severitySegments.length ? (
            <Donut segments={severitySegments} centerSub="gaps" />
          ) : (
            <p className="text-sm text-muted">No gaps.</p>
          )}
        </SectionCard>

        <SectionCard title="Gaps by regulation" icon={AlertTriangle}>
          <BarChart data={byLabel} />
        </SectionCard>

        <SectionCard title="Gaps by product category" icon={Layers}>
          <BarChart data={byCategory} />
        </SectionCard>

        <SectionCard title="Upcoming deadlines" icon={CalendarClock}>
          <div className="space-y-2">
            {a.timeline.slice(0, 7).map((t) => {
              const urgent = t.days_remaining !== null && t.days_remaining < 90;
              return (
                <div
                  key={t.alert_id}
                  className="flex items-center gap-3 rounded-lg border border-border bg-surface px-3 py-2"
                >
                  <Badge tone={t.severity as any}>{t.label}</Badge>
                  <span className="min-w-0 flex-1 truncate text-sm">{t.product}</span>
                  <span
                    className={`font-mono text-xs ${urgent ? "text-red-500" : "text-muted"}`}
                  >
                    {t.days_remaining !== null ? `${t.days_remaining}d` : "—"}
                  </span>
                  <span className="hidden font-mono text-xs text-muted sm:inline">
                    {t.deadline ?? ""}
                  </span>
                </div>
              );
            })}
          </div>
        </SectionCard>
      </div>

      {/* company risk ranking (admin / multi-company) */}
      {a.company_risk.length > 1 && (
        <SectionCard title="Company risk ranking" icon={TrendingUp}>
          <BarChart
            data={a.company_risk.map((c) => ({
              label: c.company,
              value: c.risk,
            }))}
            colorFn={(i) => (a.company_risk[i].risk >= 67 ? "#ef4444" : a.company_risk[i].risk >= 34 ? "#f59e0b" : "#10b981")}
          />
        </SectionCard>
      )}

      {/* label coverage */}
      <SectionCard title="Regulation coverage" icon={ShieldCheck}>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left">
                <th className="py-2 label-mono font-normal">Label</th>
                <th className="py-2 label-mono font-normal">Regulation</th>
                <th className="py-2 label-mono font-normal">In scope</th>
                <th className="py-2 label-mono font-normal">Open gaps</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {a.label_coverage.map((l, i) => (
                <tr key={l.label}>
                  <td className="py-2">
                    <span
                      className="mr-2 inline-block h-2.5 w-2.5 rounded-full align-middle"
                      style={{ background: colorAt(i) }}
                    />
                    {l.label}
                  </td>
                  <td className="py-2 text-muted">{l.regulation}</td>
                  <td className="py-2 tabular-nums">{l.products_in_scope}</td>
                  <td className="py-2">
                    {l.open_gaps > 0 ? (
                      <Badge tone="high">{l.open_gaps}</Badge>
                    ) : (
                      <span className="text-muted">0</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </SectionCard>
    </div>
  );
}

function Header({ company }: { company: string }) {
  return (
    <div>
      <p className="label-mono">Impact analysis</p>
      <h1 className="mt-1 text-3xl font-semibold tracking-tight">Analytics</h1>
      <p className="mt-2 max-w-xl text-sm text-muted">
        Compliance intelligence for {company} — risk, exposure, deadlines and where the
        gaps concentrate.
      </p>
    </div>
  );
}

function Mini({ label, value }: { label: string; value: number }) {
  return (
    <div className="card p-4">
      <div className="label-mono">{label}</div>
      <div className="mt-2 text-2xl font-semibold tabular-nums">{value}</div>
    </div>
  );
}
