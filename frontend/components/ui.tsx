import clsx from "clsx";

export function Badge({
  children,
  tone = "default",
  className,
}: {
  children: React.ReactNode;
  tone?: "default" | "high" | "medium" | "low" | "outline";
  className?: string;
}) {
  const tones: Record<string, string> = {
    default: "bg-surface text-fg border-border",
    outline: "bg-transparent text-muted border-border",
    high: "bg-red-500/10 text-red-500 border-red-500/30",
    medium: "bg-amber-500/10 text-amber-500 border-amber-500/30",
    low: "bg-emerald-500/10 text-emerald-500 border-emerald-500/30",
  };
  return (
    <span
      className={clsx(
        "inline-flex items-center rounded-md border px-2 py-0.5 font-mono text-[11px] uppercase tracking-wider",
        tones[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}

export function severityTone(sev: string): "high" | "medium" | "low" {
  if (sev === "high") return "high";
  if (sev === "low") return "low";
  return "medium";
}

export function Stat({
  label,
  value,
  hint,
}: {
  label: string;
  value: React.ReactNode;
  hint?: string;
}) {
  return (
    <div className="card p-5">
      <div className="label-mono">{label}</div>
      <div className="mt-3 text-4xl font-semibold tracking-tight tabular-nums">{value}</div>
      {hint && <div className="mt-1 text-sm text-muted">{hint}</div>}
    </div>
  );
}

export function EmptyState({ title, hint }: { title: string; hint?: string }) {
  return (
    <div className="card flex flex-col items-center justify-center gap-1 px-6 py-16 text-center">
      <p className="font-medium">{title}</p>
      {hint && <p className="text-sm text-muted">{hint}</p>}
    </div>
  );
}
