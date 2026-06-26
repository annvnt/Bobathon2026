"use client";

import { createContext, useContext, useEffect, useState } from "react";
import { api } from "./api";
import type { User } from "./types";

interface AppState {
  users: User[];
  selectedUserId: string | null; // null = all companies (admin view)
  setSelectedUserId: (id: string | null) => void;
  selectedCompany: string;
  refreshKey: number;
  bumpRefresh: () => void;
}

const Ctx = createContext<AppState>({
  users: [],
  selectedUserId: null,
  setSelectedUserId: () => {},
  selectedCompany: "All companies",
  refreshKey: 0,
  bumpRefresh: () => {},
});

export function AppProvider({ children }: { children: React.ReactNode }) {
  const [users, setUsers] = useState<User[]>([]);
  const [selectedUserId, setSelected] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    api.users().then(setUsers).catch(() => {});
    const stored = localStorage.getItem("selectedUserId");
    if (stored) setSelected(stored === "all" ? null : stored);
  }, []);

  const setSelectedUserId = (id: string | null) => {
    setSelected(id);
    localStorage.setItem("selectedUserId", id ?? "all");
  };

  const selectedCompany =
    users.find((u) => u.id === selectedUserId)?.company_name ?? "All companies";

  return (
    <Ctx.Provider
      value={{
        users,
        selectedUserId,
        setSelectedUserId,
        selectedCompany,
        refreshKey,
        bumpRefresh: () => setRefreshKey((k) => k + 1),
      }}
    >
      {children}
    </Ctx.Provider>
  );
}

export const useApp = () => useContext(Ctx);
