import { createContext, useCallback, useContext, useState, type ReactNode } from "react";
import { CheckCircle2, XCircle } from "lucide-react";
import { cn } from "./utils";

interface Toast { id: number; message: string; error?: boolean }

const ToastContext = createContext<(message: string, error?: boolean) => void>(() => {});

/** Small messages in the corner ("3 photos deleted") that disappear by themselves. */
export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const show = useCallback((message: string, error = false) => {
    const id = Date.now() + Math.random();
    setToasts((all) => [...all.slice(-2), { id, message, error }]);
    setTimeout(() => setToasts((all) => all.filter((t) => t.id !== id)), error ? 6000 : 3500);
  }, []);
  return (
    <ToastContext.Provider value={show}>
      {children}
      <div className="pointer-events-none fixed bottom-5 left-1/2 z-[70] flex -translate-x-1/2 flex-col items-center gap-2" aria-live="polite">
        {toasts.map((toast) => (
          <div key={toast.id} className={cn("pop-in flex items-center gap-2 rounded-xl border px-4 py-2.5 text-sm shadow-2xl backdrop-blur",
            toast.error ? "border-coral/40 bg-[#2a1512]/95 text-coral" : "border-line bg-raised/95 text-ink")}>
            {toast.error ? <XCircle className="h-4 w-4 shrink-0" /> : <CheckCircle2 className="h-4 w-4 shrink-0 text-acid" />}
            {toast.message}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export const useToast = () => useContext(ToastContext);
