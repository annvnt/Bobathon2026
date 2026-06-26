"use client";

import clsx from "clsx";
import type { LucideIcon } from "lucide-react";

export const SEV_COLOR: Record<string, string> = {
  high: "#ef4444",
  medium: "#f59e0b",
  low: "#10b981",
};

const PALETTE = [
  "#60a5fa", "#f59e0b", "#ef4444", "#10b981", "#a78bfa",
  "#f472b6", "#34d399", "#fbbf24", "#22d3ee", "#fb7185",
];
export const colorAt = (i: number) => PALETTE[i % PALETTE.length];

/* ----------------------------------------------------------------- card --- */
export function SectionCard({
  title,
  icon: Icon,
  action,
  className,
  children,
}: {
  title?: string;
  icon?: LucideIcon;
  action?: React.ReactNode;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <div className={clsx("card p-5", className)}>
      {(title || action) && (
        <div className="mb-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            {Icon && <Icon size={14} className="text-muted" />}
            <span className="label-mono">{title}</span>
          </div>
          {action}
        </div>
      )}
      {children}
    </div>
  );
}

/* ------------------------------------------------------------------ orb --- */
export function Orb({
  value,
  label,
  sublabel,
  color,
  size = 132,
  display,
}: {
  value: number; // 0–100 (controls arc fill)
  label: string;
  sublabel?: string;
  color?: string;
  size?: number;
  display?: string; // overrides centre text (e.g. "€1.4M")
}) {
  const stroke = 10;
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const pct = Math.max(0, Math.min(100, value));
  const dash = (pct / 100) * c;
  const arc =
    color ??
    (pct >= 67 ? "#ef4444" : pct >= 34 ? "#f59e0b" : "#10b981");

  return (
    <div className="flex flex-col items-center">
      <div className="relative" style={{ width: size, height: size }}>
        <svg width={size} height={size} className="-rotate-90">
          <circle
            cx={size / 2}
            cy={size / 2}
            r={r}
            fill="none"
            stroke="rgb(var(--border))"
            strokeWidth={stroke}
          />
          <circle
            cx={size / 2}
            cy={size / 2}
            r={r}
            fill="none"
            stroke={arc}
            strokeWidth={stroke}
            strokeLinecap="round"
            strokeDasharray={`${dash} ${c - dash}`}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-2xl font-semibold tabular-nums tracking-tight">
            {display ?? value}
          </span>
          <span className="label-mono mt-0.5">{label}</span>
        </div>
      </div>
      {sublabel && <p className="mt-2 text-xs text-muted">{sublabel}</p>}
    </div>
  );
}

/* ------------------------------------------------------------------ bar --- */
export function Bar({
  label,
  value,
  max = 100,
  color = "#60a5fa",
  valueLabel,
}: {
  label: string;
  value: number;
  max?: number;
  color?: string;
  valueLabel?: string;
}) {
  const pct = max > 0 ? Math.min(100, (value / max) * 100) : 0;
  return (
    <div>
      <div className="mb-1.5 flex items-center justify-between text-sm">
        <span className="text-fg/80">{label}</span>
        <span className="font-mono text-xs text-muted">{valueLabel ?? value}</span>
      </div>
      <div className="h-2 w-full overflow-hidden rounded-full bg-surface">
        <div
          className="h-full rounded-full transition-all"
          style={{ width: `${pct}%`, background: color }}
        />
      </div>
    </div>
  );
}

/* -------------------------------------------------------------- barchart --- */
export function BarChart({
  data,
  colorFn,
}: {
  data: { label: string; value: number; color?: string }[];
  colorFn?: (i: number) => string;
}) {
  const max = Math.max(1, ...data.map((d) => d.value));
  if (data.length === 0)
    return <p className="text-sm text-muted">No data yet.</p>;
  return (
    <div className="space-y-3">
      {data.map((d, i) => (
        <Bar
          key={d.label}
          label={d.label}
          value={d.value}
          max={max}
          color={d.color ?? (colorFn ? colorFn(i) : colorAt(i))}
        />
      ))}
    </div>
  );
}

/* ---------------------------------------------------------------- donut --- */
export function Donut({
  segments,
  size = 150,
  centerLabel,
  centerSub,
}: {
  segments: { label: string; value: number; color: string }[];
  size?: number;
  centerLabel?: string;
  centerSub?: string;
}) {
  const total = segments.reduce((s, x) => s + x.value, 0);
  const stroke = 16;
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  let offset = 0;

  return (
    <div className="flex items-center gap-5">
      <div className="relative" style={{ width: size, height: size }}>
        <svg width={size} height={size} className="-rotate-90">
          <circle cx={size / 2} cy={size / 2} r={r} fill="none"
            stroke="rgb(var(--border))" strokeWidth={stroke} />
          {total > 0 &&
            segments.map((seg) => {
              const len = (seg.value / total) * c;
              const el = (
                <circle
                  key={seg.label}
                  cx={size / 2}
                  cy={size / 2}
                  r={r}
                  fill="none"
                  stroke={seg.color}
                  strokeWidth={stroke}
                  strokeDasharray={`${len} ${c - len}`}
                  strokeDashoffset={-offset}
                />
              );
              offset += len;
              return el;
            })}
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-2xl font-semibold tabular-nums">{centerLabel ?? total}</span>
          {centerSub && <span className="label-mono mt-0.5">{centerSub}</span>}
        </div>
      </div>
      <div className="space-y-1.5">
        {segments.map((s) => (
          <div key={s.label} className="flex items-center gap-2 text-sm">
            <span className="h-2.5 w-2.5 rounded-full" style={{ background: s.color }} />
            <span className="capitalize text-fg/80">{s.label}</span>
            <span className="font-mono text-xs text-muted">{s.value}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
