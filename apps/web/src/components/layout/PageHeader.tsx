import Link from "next/link";
import { cn } from "@/lib/utils/cn";
import type { StatusTone } from "@/lib/helpers/status";
import {
  resolveStatusVisual,
  type DomainStatusKind,
} from "@/lib/helpers/status";

const toneClasses: Record<StatusTone, string> = {
  neutral: "bg-slate-100 text-slate-700 ring-slate-200",
  info: "bg-sky-50 text-sky-800 ring-sky-200",
  success: "bg-teal-50 text-teal-800 ring-teal-200",
  warning: "bg-amber-50 text-amber-900 ring-amber-200",
  danger: "bg-rose-50 text-rose-800 ring-rose-200",
};

interface StatusBadgeProps {
  kind: DomainStatusKind;
  state: string;
  className?: string;
  "data-testid"?: string;
}

export function StatusBadge({
  kind,
  state,
  className,
  "data-testid": testId,
}: StatusBadgeProps) {
  const visual = resolveStatusVisual(kind, state);
  return (
    <span
      data-testid={testId ?? `status-badge-${kind}-${state}`}
      className={cn(
        "inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium ring-1 ring-inset",
        toneClasses[visual.tone],
        className,
      )}
    >
      {visual.label}
    </span>
  );
}

export function Breadcrumbs({
  items,
}: {
  items: Array<{ label: string; href?: string }>;
}) {
  return (
    <nav aria-label="Breadcrumb" data-testid="breadcrumbs" className="text-sm">
      <ol className="flex flex-wrap items-center gap-1.5 text-slate-500">
        {items.map((item, index) => {
          const isLast = index === items.length - 1;
          return (
            <li key={`${item.label}-${index}`} className="flex items-center gap-1.5">
              {index > 0 && <span className="text-slate-300">/</span>}
              {item.href && !isLast ? (
                <Link
                  href={item.href}
                  className="hover:text-teal-800 transition-colors"
                >
                  {item.label}
                </Link>
              ) : (
                <span className={cn(isLast && "text-slate-800 font-medium")}>
                  {item.label}
                </span>
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}

export function PageHeader({
  title,
  description,
  breadcrumbs,
  actions,
}: {
  title: string;
  description?: string;
  breadcrumbs?: Array<{ label: string; href?: string }>;
  actions?: React.ReactNode;
}) {
  return (
    <header
      data-testid="page-header"
      className="mb-6 flex flex-col gap-3 border-b border-slate-200 pb-4 sm:flex-row sm:items-start sm:justify-between"
    >
      <div className="space-y-2 min-w-0">
        {breadcrumbs && breadcrumbs.length > 0 && (
          <Breadcrumbs items={breadcrumbs} />
        )}
        <h1 className="text-2xl font-semibold tracking-tight text-slate-900">
          {title}
        </h1>
        {description && (
          <p className="text-sm text-slate-600 max-w-2xl">{description}</p>
        )}
      </div>
      {actions && <div className="flex shrink-0 flex-wrap gap-2">{actions}</div>}
    </header>
  );
}
