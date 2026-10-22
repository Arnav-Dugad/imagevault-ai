import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import type { SystemStatus } from "../types";
import { api } from "./api";

const SystemContext = createContext<{ system: SystemStatus | null; refresh: () => Promise<void> }>({
  system: null, refresh: async () => {},
});

/** Loads the live status of the cloud services once, for the sidebar and the Cloud page. */
export function SystemProvider({ children }: { children: ReactNode }) {
  const [system, setSystem] = useState<SystemStatus | null>(null);
  const refresh = useCallback(() => api<SystemStatus>("/system").then(setSystem).catch(() => {}), []);
  useEffect(() => { refresh(); }, [refresh]);
  return <SystemContext.Provider value={{ system, refresh }}>{children}</SystemContext.Provider>;
}

export function useSystem() {
  const { system, refresh } = useContext(SystemContext);
  const storage = system?.services.find((s) => s.id === "storage");
  return { system, refresh, onAzureStorage: storage?.active ?? false };
}
