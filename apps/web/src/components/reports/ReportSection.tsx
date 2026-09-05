import { cn } from "@/lib/utils/cn";

export function ReportSection({
  title,
  children,
  className,
}: {
  title: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section
      data-testid={`report-section-${title.toLowerCase().replace(/\s+/g, "-")}`}
      className={cn("border-b border-slate-200 py-5 last:border-b-0", className)}
    >
      <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">
        {title}
      </h2>
      <div className="mt-3">{children}</div>
    </section>
  );
}

export function ParentFriendlyInsight({
  title,
  items,
}: {
  title: string;
  items: string[];
}) {
  return (
    <div data-testid={`parent-insight-${title.toLowerCase().replace(/\s+/g, "-")}`}>
      <h3 className="text-sm font-semibold text-slate-900">{title}</h3>
      <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-slate-700">
        {items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </div>
  );
}
