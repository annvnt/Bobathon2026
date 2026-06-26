"use client";

import { Check, Loader2, Sparkles } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Badge } from "@/components/ui";
import { api } from "@/lib/api";
import { useApp } from "@/lib/app-context";
import type { ClassifyResult, LabelDef, Taxonomy } from "@/lib/types";

const EXAMPLE =
  "Portable Bluetooth speaker with a 30Wh rechargeable lithium-ion battery and Wi-Fi streaming. Housing uses PVC with DEHP plasticizer. Sold to consumers across the EU in a cardboard box.";

const BATTERY_TYPES = ["none", "portable", "button_cell", "lmt", "industrial"];
const USES = ["consumer", "toy", "industrial", "medical"];

export default function AddProductPage() {
  const router = useRouter();
  const { selectedUserId, bumpRefresh } = useApp();
  const [taxonomy, setTaxonomy] = useState<Taxonomy | null>(null);
  const [labels, setLabels] = useState<LabelDef[]>([]);
  const [description, setDescription] = useState("");
  const [analyzing, setAnalyzing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [draft, setDraft] = useState<ClassifyResult | null>(null);

  useEffect(() => {
    api.taxonomy().then(setTaxonomy).catch(() => {});
    api.labels().then(setLabels).catch(() => {});
  }, []);

  const analyze = async () => {
    if (description.trim().length < 5) return;
    setAnalyzing(true);
    try {
      const res = await api.classify(description);
      setDraft(res);
    } catch {
      alert("Classification failed — is the backend running?");
    } finally {
      setAnalyzing(false);
    }
  };

  const toggleArray = (key: keyof ClassifyResult, value: string) => {
    if (!draft) return;
    const arr = (draft[key] as string[]) || [];
    const next = arr.includes(value)
      ? arr.filter((v) => v !== value)
      : [...arr, value];
    setDraft({ ...draft, [key]: next });
  };

  const save = async () => {
    if (!draft) return;
    setSaving(true);
    try {
      await api.createProduct({
        name: draft.name || description.slice(0, 48),
        description,
        category: draft.category,
        substances: draft.substances,
        markets: draft.markets,
        compliance_streams: draft.compliance_streams,
        has_battery: draft.has_battery,
        battery_type: draft.battery_type,
        battery_capacity_wh: draft.battery_capacity_wh,
        has_radio: draft.has_radio,
        intended_use: draft.intended_use,
        ...(selectedUserId ? { user_id: selectedUserId } : {}),
      } as any);
      bumpRefresh();
      router.push("/products");
    } catch {
      alert("Save failed.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <p className="label-mono">Workflow · Add product</p>
        <h1 className="mt-1 text-3xl font-semibold tracking-tight">
          Describe it. We label it.
        </h1>
        <p className="mt-2 max-w-xl text-sm text-muted">
          Paste a free-text product description. The AI classifies it against the
          regulatory taxonomy — then you verify and correct before saving.
        </p>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Left — description input */}
        <div className="space-y-3">
          <label className="label-mono">Product description</label>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={12}
            placeholder="e.g. LED desk lamp with USB-C charging…"
            className="input resize-none font-mono text-[13px] leading-relaxed"
          />
          <div className="flex items-center gap-2">
            <button
              onClick={analyze}
              disabled={analyzing || description.trim().length < 5}
              className="btn-primary"
            >
              {analyzing ? (
                <Loader2 size={15} className="animate-spin" />
              ) : (
                <Sparkles size={15} />
              )}
              Analyze with AI
            </button>
            <button
              onClick={() => setDescription(EXAMPLE)}
              className="btn-ghost"
            >
              Use example
            </button>
          </div>
        </div>

        {/* Right — generated, editable form */}
        <div className="card min-h-[360px] p-5">
          {!draft ? (
            <div className="flex h-full flex-col items-center justify-center text-center text-sm text-muted">
              <Sparkles size={20} className="mb-3 opacity-50" />
              The AI’s draft labels appear here. You can correct any field before
              saving.
            </div>
          ) : (
            <div className="space-y-5">
              <div className="rounded-lg border border-border bg-surface p-3 text-xs text-muted">
                <span className="label-mono">AI reasoning</span>
                <p className="mt-1 text-fg/80">{draft.reasoning}</p>
              </div>

              <Field label="Name">
                <input
                  className="input"
                  value={draft.name}
                  placeholder="Product name"
                  onChange={(e) => setDraft({ ...draft, name: e.target.value })}
                />
              </Field>

              <Field label="Category">
                <select
                  className="input"
                  value={draft.category}
                  onChange={(e) =>
                    setDraft({ ...draft, category: e.target.value })
                  }
                >
                  {taxonomy &&
                    Object.entries(taxonomy.product_categories).map(([k, v]) => (
                      <option key={k} value={k}>
                        {v}
                      </option>
                    ))}
                </select>
              </Field>

              <Field label="Substances">
                <ChipPicker
                  options={taxonomy ? Object.keys(taxonomy.substances) : []}
                  selected={draft.substances}
                  onToggle={(v) => toggleArray("substances", v)}
                />
              </Field>

              <Field label="Compliance streams (auto-mapped from labels.md)">
                <ChipPicker
                  options={labels.map((l) => l.label)}
                  selected={draft.compliance_streams}
                  onToggle={(v) => toggleArray("compliance_streams", v)}
                />
              </Field>

              <div className="grid grid-cols-2 gap-4">
                <Field label="Battery">
                  <select
                    className="input"
                    value={draft.battery_type}
                    onChange={(e) =>
                      setDraft({
                        ...draft,
                        battery_type: e.target.value,
                        has_battery: e.target.value !== "none",
                      })
                    }
                  >
                    {BATTERY_TYPES.map((t) => (
                      <option key={t} value={t}>
                        {t}
                      </option>
                    ))}
                  </select>
                </Field>
                <Field label="Capacity (Wh)">
                  <input
                    type="number"
                    className="input"
                    value={draft.battery_capacity_wh}
                    onChange={(e) =>
                      setDraft({
                        ...draft,
                        battery_capacity_wh: Number(e.target.value),
                      })
                    }
                  />
                </Field>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <Field label="Intended use">
                  <select
                    className="input"
                    value={draft.intended_use}
                    onChange={(e) =>
                      setDraft({ ...draft, intended_use: e.target.value })
                    }
                  >
                    {USES.map((u) => (
                      <option key={u} value={u}>
                        {u}
                      </option>
                    ))}
                  </select>
                </Field>
                <Field label="Has radio">
                  <button
                    onClick={() =>
                      setDraft({ ...draft, has_radio: !draft.has_radio })
                    }
                    className={`btn w-full ${
                      draft.has_radio
                        ? "bg-accent text-accent-fg"
                        : "border border-border"
                    }`}
                  >
                    {draft.has_radio ? "Yes" : "No"}
                  </button>
                </Field>
              </div>

              <button
                onClick={save}
                disabled={saving}
                className="btn-primary w-full"
              >
                {saving ? (
                  <Loader2 size={15} className="animate-spin" />
                ) : (
                  <Check size={15} />
                )}
                Save product
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="space-y-2">
      <label className="label-mono">{label}</label>
      {children}
    </div>
  );
}

function ChipPicker({
  options,
  selected,
  onToggle,
}: {
  options: string[];
  selected: string[];
  onToggle: (v: string) => void;
}) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {options.map((opt) => {
        const on = selected.includes(opt);
        return (
          <button
            key={opt}
            onClick={() => onToggle(opt)}
            className={`rounded-md border px-2 py-1 font-mono text-[11px] uppercase tracking-wider transition-colors ${
              on
                ? "border-accent bg-accent text-accent-fg"
                : "border-border text-muted hover:text-fg"
            }`}
          >
            {opt}
          </button>
        );
      })}
    </div>
  );
}
