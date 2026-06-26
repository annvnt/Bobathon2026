"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Orb, SectionCard } from "@/components/charts";
import { Badge, EmptyState, Stat, severityTone } from "@/components/ui";
import { ShieldCheck, TrendingUp } from "lucide-react";
import { api } from "@/lib/api";
import { useApp } from "@/lib/app-context";
import type { Alert, Analytics, DashboardMetrics } from "@/lib/types";

export default function DashboardPage() {
  const { selectedUserId, selectedCompany, refreshKey } = useApp();
  const [metrics, setMetrics] = useState<DashboardMetrics | null>(null);
  const [analytics, setAnalytics] = useState<Analytics | null>(null);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    Promise.all([
      api.metrics(selectedUserId ?? undefined),
      api.analytics(selectedUserId ?? undefined),
      api.listAlerts({ is_read: false, user_id: selectedUserId ?? undefined }),
    ])
      .then(([m, an, a]) => {
        setMetrics(m);
        setAnalytics(an);
        setAlerts(a);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [selectedUserId, refreshKey]);

  return (
    <div className="space-y-8">
      <div>
        <p className="label-mono">Overview</p>
        <h1 className="mt-1 text-3xl font-semibold tracking-tight">
          {selectedCompany}
        </h1>
        <p className="mt-2 max-w-xl text-sm text-muted">
          Live compliance posture across your portfolio. Run the daily scan to
          pull the latest regulation updates and re-assess every product.
        </p>
      </div>

      <div className="grid gap-4 lg:grid-cols-5">
        <SectionCard title="Portfolio risk" icon={TrendingUp} className="lg:col-span-1">
          <div className="flex justify-center">
            <Orb value={analytics?.orbs.portfolio_risk ?? 0} label="risk" size={116} />
          </div>
        </SectionCard>
        <SectionCard title="Compliance health" icon={ShieldCheck} className="lg:col-span-1">
          <div className="flex justify-center">
            <Orb
              value={analytics?.orbs.compliance_health ?? 0}
              label="health"
              size={116}
              color={
                (analytics?.orbs.compliance_health ?? 0) >= 66
                  ? "#10b981"
                  : (analytics?.orbs.compliance_health ?? 0) >= 33
                  ? "#f59e0b"
                  : "#ef4444"
              }
            />
          </div>
        </SectionCard>
        <div className="grid gap-4 lg:col-span-3 sm:grid-cols-3">
          <Stat
            label="Total products"
            value={loading ? "—" : metrics?.total_products ?? 0}
            hint="Monitored in portfolio"
          />
          <Stat
            label="Active alerts"
            value={loading ? "—" : metrics?.active_alerts ?? 0}
            hint="Unread compliance gaps"
          />
          <Stat
            label="Monitored regulations"
            value={loading ? "—" : metrics?.monitored_regulations ?? 0}
            hint="Regulation families tracked"
          />
        </div>
      </div>

      <div>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-lg font-semibold tracking-tight">Recent alerts</h2>
          <Link href="/alerts" className="text-sm text-muted hover:text-fg">
            View all →
          </Link>
        </div>

        {loading ? (
          <div className="card h-40 animate-pulse" />
        ) : alerts.length === 0 ? (
          <EmptyState
            title="No unread alerts"
            hint="Run the daily scan to assess products against current regulations."
          />
        ) : (
          <div className="card divide-y divide-border overflow-hidden">
            {alerts.slice(0, 6).map((a) => (
              <Link
                key={a.id}
                href={`/alerts?focus=${a.id}`}
                className="flex items-center gap-4 px-5 py-4 transition-colors hover:bg-surface"
              >
                <Badge tone={severityTone(a.severity)}>{a.severity}</Badge>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium">
                    {a.product_name} · {a.regulation_label}
                  </p>
                  <p className="truncate text-sm text-muted">{a.gap}</p>
                </div>
                <span className="hidden shrink-0 font-mono text-xs text-muted sm:block">
                  {a.deadline ?? "—"}
                </span>
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
