import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import type { Settings } from "../types";
import { api } from "./api";

const SettingsContext = createContext<{ settings: Settings | null; refresh: () => void; update: (s: Settings) => void }>({
  settings: null, refresh: () => {}, update: () => {},
});

export function SettingsProvider({ children }: { children: ReactNode }) {
  const [settings, setSettings] = useState<Settings | null>(null);
  const refresh = useCallback(() => { api<Settings>("/settings").then(setSettings).catch(() => {}); }, []);
  useEffect(refresh, [refresh]);
  return <SettingsContext.Provider value={{ settings, refresh, update: setSettings }}>{children}</SettingsContext.Provider>;
}

export const useSettings = () => useContext(SettingsContext);
