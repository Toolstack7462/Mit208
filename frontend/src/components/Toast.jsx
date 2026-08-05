import { useCallback, useEffect, useRef, useState } from "react";
import { AlertTriangle, CheckCircle2 } from "lucide-react";

/**
 * Transient notification, shared by the pages that report the outcome of an
 * action.
 *
 * It carries a tone because the previous per-page toast always showed a green
 * tick — so a refusal such as "You already have a pending release request"
 * was presented with a success icon, which contradicts the message.
 */
export function Toast({ message, tone = "success" }) {
  if (!message) return null;
  const isError = tone === "error";
  return (
    <div
      role={isError ? "alert" : "status"}
      aria-live={isError ? "assertive" : "polite"}
      className={`fixed right-8 top-6 z-50 flex max-w-md items-start gap-2 rounded-lg px-4 py-2.5 text-sm font-medium shadow-lg ${
        isError ? "bg-red-600 text-white" : "bg-navy-900 text-white"
      }`}
    >
      {isError ? (
        <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
      ) : (
        <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-400" />
      )}
      <span>{message}</span>
    </div>
  );
}

/** Manages toast text, tone and auto-dismissal. */
export function useToast(timeoutMs = 3000) {
  const [toast, setToast] = useState({ message: "", tone: "success" });
  const timerRef = useRef(null);

  const show = useCallback((message, tone = "success") => {
    // Cancel any dismissal still pending from an earlier toast. Without this, a
    // quick success-then-error sequence let the success timer fire and wipe the
    // error message off the screen before the user had read it.
    if (timerRef.current) clearTimeout(timerRef.current);
    setToast({ message, tone });
    // Errors linger a little longer — they usually need reading, not just noting.
    const delay = tone === "error" ? timeoutMs + 2500 : timeoutMs;
    timerRef.current = setTimeout(() => {
      timerRef.current = null;
      setToast({ message: "", tone: "success" });
    }, delay);
  }, [timeoutMs]);

  // Clear the pending timer if the page unmounts, so it cannot fire against a
  // component that no longer exists.
  useEffect(() => () => {
    if (timerRef.current) clearTimeout(timerRef.current);
  }, []);

  return { toast, show };
}
