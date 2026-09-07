"use client";

import { cn } from "@/lib/utils/cn";
import {
  formatConfidence,
  getConfidenceLevel,
  isUnresolvedConfidence,
} from "@/lib/helpers/confidence";
import type { Confidence } from "@/lib/types/domain";
import { AlertCircle, Inbox, Loader2 } from "lucide-react";

export function ConfidenceIndicator({
  value,
  label = "Confidence",
  className,
}: {
  value: Confidence | null | undefined;
  label?: string;
  className?: string;
}) {
  const missing = value === null || value === undefined;
  const safeValue = missing ? 0 : value;
  const level = missing ? "critical" : getConfidenceLevel(safeValue);
  const unresolved = missing || isUnresolvedConfidence(safeValue);
  const barColor =
    level === "high"
      ? "bg-teal-600"
      : level === "medium"
        ? "bg-sky-500"
        : level === "low"
          ? "bg-amber-500"
          : "bg-rose-600";

  return (
    <div
      data-testid="confidence-indicator"
      data-level={level}
      data-unresolved={unresolved ? "true" : "false"}
      className={cn("space-y-1", className)}
    >
      <div className="flex items-center justify-between text-xs">
        <span className="text-slate-600">{label}</span>
        <span
          className={cn(
            "font-medium tabular-nums",
            unresolved ? "text-rose-700" : "text-slate-800",
          )}
        >
          {missing ? "—" : formatConfidence(safeValue)}
          {unresolved && " · unresolved"}
        </span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-slate-200">
        <div
          className={cn("h-full rounded-full transition-all", barColor)}
          style={{ width: `${missing ? 0 : Math.round(safeValue * 100)}%` }}
        />
      </div>
    </div>
  );
}

export function EmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description?: string;
  action?: React.ReactNode;
}) {
  return (
    <div
      data-testid="empty-state"
      className="flex flex-col items-center justify-center gap-3 py-16 text-center"
    >
      <Inbox className="h-8 w-8 text-slate-300" aria-hidden />
      <div>
        <h3 className="text-sm font-semibold text-slate-800">{title}</h3>
        {description && (
          <p className="mt-1 text-sm text-slate-500 max-w-sm">{description}</p>
        )}
      </div>
      {action}
    </div>
  );
}

export function LoadingState({ label = "Loading…" }: { label?: string }) {
  return (
    <div
      data-testid="loading-state"
      className="flex items-center justify-center gap-2 py-16 text-sm text-slate-600"
    >
      <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
      {label}
    </div>
  );
}

export function ErrorState({
  title = "Something went wrong",
  message,
  onRetry,
}: {
  title?: string;
  message?: string;
  onRetry?: () => void;
}) {
  return (
    <div
      data-testid="error-state"
      className="flex flex-col items-center justify-center gap-3 py-16 text-center"
    >
      <AlertCircle className="h-8 w-8 text-rose-500" aria-hidden />
      <div>
        <h3 className="text-sm font-semibold text-slate-800">{title}</h3>
        {message && (
          <p className="mt-1 text-sm text-slate-500 max-w-md">{message}</p>
        )}
      </div>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="rounded-md bg-slate-900 px-3 py-1.5 text-sm text-white hover:bg-slate-800"
        >
          Retry
        </button>
      )}
    </div>
  );
}
