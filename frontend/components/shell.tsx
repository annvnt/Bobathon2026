"use client";

import { AppProvider } from "@/lib/app-context";
import { DynamicIsland } from "./dynamic-island";
import { Header } from "./header";

export function Shell({ children }: { children: React.ReactNode }) {
  return (
    <AppProvider>
      <div className="fixed inset-x-0 top-4 z-50 flex items-start justify-between gap-3 px-4">
        <DynamicIsland />
        <Header />
      </div>
      <main className="mx-auto w-full max-w-6xl px-6 pb-20 pt-28">{children}</main>
    </AppProvider>
  );
}
