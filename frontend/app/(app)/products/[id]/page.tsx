"use client";

import {
  ArrowLeft,
  BatteryCharging,
  CalendarClock,
  Euro,
  Radio,
  ShieldCheck,
  TrendingUp,
} from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { Orb, SectionCard } from "@/components/charts";
import { Badge, EmptyState, severityTone } from "@/components/ui";
import { api } from "@/lib/api";
import type { Alert, ProductAnalytics } from "@/lib/types";

function eur(n: number): string {
  if (n >= 1_000_000) return `€${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `€${Math.round(n / 1_000)}k`;
  return `€${n}`;
}

export default function ProductDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [a, setA] = useState<ProductAnalytics | null>(null);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    Promise.all([api.productAnalytics(id), api.listAlerts({ product_id: id })])
      .then(([pa, al]) => {
        setA(pa);
        setAlerts(al);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [id]);

  if (loading)
    return <div className="card h-72 animate-pulse" />;
  if (!a) return <EmptyState title="Product not found" />;

  const p = a.product;

  return (
    <div className="space-y-6">
      <Link
        href="/products"
        className="inline-flex items-center gap-1.5 text-sm text-muted hover:text-fg"
      >
        <ArrowLeft size={15} /> Products
      </Link>

      <div>
        <p className="label-mono">{a.company}</p>
        <h1 className="mt-1 text-3xl font-semibold tracking-tight">{p.name}</h1>
        <p className="mt-2 text-sm text-muted">{p.description}</p>
        <div className="mt-3 flex flex-wrap gap-1.5">
          <Badge tone="outline">{p.category.replace(/_/g, " ")}</Badge>
          <Badge tone="outline">{p.intended_use}</Badge>
          {p.has_battery && (
            <Badge tone="outline">
              <BatteryCharging size={11} className="mr-1" />
              {p.battery_type} · {p.battery_capacity_wh}Wh
            </Badge>
          )}
          {p.has_radio && (
            <Badge tone="outline">
              <Radio size={11} className="mr-1" /> radio
            </Badge>
          )}
          {p.markets.map((m) => (
            <Badge key={m} tone="outline">
              {m}
            </Badge>
          ))}
          {p.substances.map((s) => (
            <Badge key={s} tone="outline">
              {s}
            </Badge>
          ))}
        </div>
      </div>

      {/* product orbs */}
      <div className="grid gap-4 sm:grid-cols-3">
        <SectionCard title="Product risk" icon={TrendingUp}>
          <div className="flex justify-center py-1">
            <Orb value={a.orbs.risk} label="risk" />
          </div>
        </SectionCard>
        <SectionCard title="Compliance health" icon={ShieldCheck}>
          <div className="flex justify-center py-1">
            <Orb
              value={a.orbs.health}
              label="health"
              color={a.orbs.health >= 66 ? "#10b981" : a.orbs.health >= 33 ? "#f59e0b" : "#ef4444"}
            />
          </div>
        </SectionCard>
        <SectionCard title="Fine exposure" icon={Euro}>
          <div className="flex justify-center py-1">
            <Orb
              value={Math.min(100, (a.orbs.fine_exposure_eur / 500_000) * 100)}
              display={eur(a.orbs.fine_exposure_eur)}
              label="at risk"
              color="#ef4444"
            />
          </div>
        </SectionCard>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        {/* coverage */}
        <SectionCard title="Regulation coverage" icon={ShieldCheck}>
          <div className="space-y-2">
            {a.coverage.map((c) => (
              <div
                key={c.label}
                className="flex items-center gap-3 rounded-lg border border-border bg-surface px-3 py-2"
              >
                <span className="w-24 font-mono text-xs">{c.label}</span>
                <span className="min-w-0 flex-1 truncate text-sm text-muted">
                  {c.regulation}
                </span>
                {c.open_gaps > 0 ? (
                  <Badge tone="high">{c.open_gaps} gap</Badge>
                ) : (
                  <Badge tone="low">ok</Badge>
                )}
              </div>
            ))}
          </div>
        </SectionCard>

        {/* timeline */}
        <SectionCard title="Deadlines" icon={CalendarClock}>
          {a.timeline.length === 0 ? (
            <p className="text-sm text-muted">No active deadlines.</p>
          ) : (
            <div className="space-y-2">
              {a.timeline.map((t) => {
                const urgent = t.days_remaining !== null && t.days_remaining < 90;
                return (
                  <div
                    key={t.alert_id}
                    className="flex items-center gap-3 rounded-lg border border-border bg-surface px-3 py-2"
                  >
                    <Badge tone={t.severity as any}>{t.label}</Badge>
                    <span className="min-w-0 flex-1 truncate text-sm">{t.title}</span>
                    <span className={`font-mono text-xs ${urgent ? "text-red-500" : "text-muted"}`}>
                      {t.days_remaining !== null ? `${t.days_remaining}d` : "—"}
                    </span>
                  </div>
                );
              })}
            </div>
          )}
        </SectionCard>
      </div>

      {/* this product's alerts */}
      <SectionCard title={`Compliance gaps (${alerts.length})`}>
        {alerts.length === 0 ? (
          <p className="text-sm text-muted">No gaps detected for this product.</p>
        ) : (
          <div className="space-y-2">
            {alerts.map((al) => (
              <Link
                key={al.id}
                href={`/alerts?focus=${al.id}`}
                className="flex items-center gap-3 rounded-lg border border-border bg-surface px-3 py-2 transition-colors hover:border-fg/20"
              >
                <Badge tone={severityTone(al.severity)}>{al.severity}</Badge>
                <span className="min-w-0 flex-1 truncate text-sm">{al.gap}</span>
                <span className="hidden font-mono text-xs text-muted sm:inline">
                  {al.deadline ?? "—"}
                </span>
              </Link>
            ))}
          </div>
        )}
      </SectionCard>
    </div>
  );
}
