"use client";

import { BatteryCharging, Plus, Radio, Trash2 } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { Badge, EmptyState } from "@/components/ui";
import { api } from "@/lib/api";
import { useApp } from "@/lib/app-context";
import type { Product } from "@/lib/types";

export default function ProductsPage() {
  const { selectedUserId, refreshKey, bumpRefresh } = useApp();
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");

  useEffect(() => {
    setLoading(true);
    api
      .listProducts(selectedUserId ?? undefined)
      .then(setProducts)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [selectedUserId, refreshKey]);

  const remove = async (id: string) => {
    if (!confirm("Delete this product?")) return;
    await api.deleteProduct(id);
    bumpRefresh();
  };

  const filtered = products.filter(
    (p) =>
      p.name.toLowerCase().includes(query.toLowerCase()) ||
      p.category.toLowerCase().includes(query.toLowerCase()),
  );

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="label-mono">Portfolio</p>
          <h1 className="mt-1 text-3xl font-semibold tracking-tight">Products</h1>
        </div>
        <Link href="/products/add" className="btn-primary">
          <Plus size={15} /> Add product
        </Link>
      </div>

      <input
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Search products…"
        className="input max-w-sm"
      />

      {loading ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="card h-48 animate-pulse" />
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <EmptyState title="No products" hint="Add a product to start monitoring it." />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {filtered.map((p) => (
            <ProductCard key={p.id} product={p} onDelete={() => remove(p.id)} />
          ))}
        </div>
      )}
    </div>
  );
}

function ProductCard({
  product: p,
  onDelete,
}: {
  product: Product;
  onDelete: () => void;
}) {
  const risk = p.open_alerts > 0;
  return (
    <Link
      href={`/products/${p.id}`}
      className="card group relative flex flex-col p-5 card-hover"
    >
      <button
        onClick={(e) => {
          e.preventDefault();
          e.stopPropagation();
          onDelete();
        }}
        className="absolute right-4 top-4 text-muted opacity-0 transition-opacity hover:text-red-500 group-hover:opacity-100"
        aria-label="Delete"
      >
        <Trash2 size={15} />
      </button>

      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="truncate pr-6 font-medium">{p.name}</h3>
          <p className="mt-0.5 text-sm text-muted">{p.category.replace(/_/g, " ")}</p>
        </div>
      </div>

      {/* risk indicator */}
      <div className="mt-4 flex items-center gap-2">
        {risk ? (
          <Badge tone="high">
            {p.open_alerts} open gap{p.open_alerts > 1 ? "s" : ""}
          </Badge>
        ) : (
          <Badge tone="low">compliant</Badge>
        )}
        {p.has_battery && (
          <span className="flex items-center gap-1 text-xs text-muted">
            <BatteryCharging size={13} /> {p.battery_capacity_wh}Wh
          </span>
        )}
        {p.has_radio && (
          <span className="flex items-center gap-1 text-xs text-muted">
            <Radio size={13} /> radio
          </span>
        )}
      </div>

      <div className="mt-4 flex flex-wrap gap-1">
        {p.compliance_streams.slice(0, 6).map((s) => (
          <Badge key={s} tone="outline">
            {s}
          </Badge>
        ))}
        {p.compliance_streams.length > 6 && (
          <Badge tone="outline">+{p.compliance_streams.length - 6}</Badge>
        )}
      </div>

      {p.substances.length > 0 && (
        <p className="mt-4 border-t border-border pt-3 text-xs text-muted">
          Substances: {p.substances.join(", ")}
        </p>
      )}
    </Link>
  );
}
