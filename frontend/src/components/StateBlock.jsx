import { AlertTriangle, Loader2, RefreshCw } from "lucide-react";

/**
 * Shared loading / error placeholders.
 *
 * Every page that loads data uses these so a failed request produces a visible,
 * retryable message. Previously a failed load left the page rendering its empty
 * state, which was indistinguishable from "there is genuinely no data".
 */

export function LoadingBlock({ label = "Loading…" }) {
  return (
    <div
      role="status"
      aria-live="polite"
      className="flex flex-col items-center justify-center gap-3 px-6 py-16 text-slate-400"
    >
      <Loader2 className="h-6 w-6 animate-spin" />
      <span className="text-sm">{label}</span>
    </div>
  );
}

export function ErrorBlock({ message, onRetry, requestId }) {
  return (
    <div
      role="alert"
      className="flex flex-col items-center justify-center gap-3 px-6 py-14 text-center"
    >
      <div className="grid h-12 w-12 place-items-center rounded-full bg-red-50 text-red-600">
        <AlertTriangle className="h-6 w-6" />
      </div>
      <div>
        <div className="text-sm font-semibold text-navy-900">Could not load this data</div>
        <p className="mt-1 max-w-md text-sm text-slate-500">{message}</p>
        {requestId && (
          <p className="mt-2 font-mono text-[11px] text-slate-400">Reference: {requestId}</p>
        )}
      </div>
      {onRetry && (
        <button className="btn-outline btn-sm mt-1" onClick={onRetry}>
          <RefreshCw className="h-3.5 w-3.5" /> Try again
        </button>
      )}
    </div>
  );
}

export function EmptyBlock({ message }) {
  return (
    <div className="px-6 py-14 text-center text-sm text-slate-400">{message}</div>
  );
}
