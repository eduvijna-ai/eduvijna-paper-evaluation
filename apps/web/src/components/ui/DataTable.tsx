"use client";

import { cn } from "@/lib/utils/cn";

export interface DataTableColumn<T> {
  key: string;
  header: string;
  className?: string;
  cell: (row: T) => React.ReactNode;
}

export function DataTable<T extends { id: string }>({
  columns,
  rows,
  onRowClick,
  emptyMessage = "No rows",
  "data-testid": testId,
}: {
  columns: DataTableColumn<T>[];
  rows: T[];
  onRowClick?: (row: T) => void;
  emptyMessage?: string;
  "data-testid"?: string;
}) {
  if (rows.length === 0) {
    return (
      <div
        data-testid={testId ?? "data-table-empty"}
        className="rounded-md border border-dashed border-slate-200 px-4 py-10 text-center text-sm text-slate-500"
      >
        {emptyMessage}
      </div>
    );
  }

  return (
    <div
      data-testid={testId ?? "data-table"}
      className="overflow-x-auto rounded-md border border-slate-200 bg-white"
    >
      <table className="min-w-full text-left text-sm">
        <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
          <tr>
            {columns.map((col) => (
              <th
                key={col.key}
                className={cn("px-3 py-2.5 font-medium", col.className)}
              >
                {col.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {rows.map((row) => (
            <tr
              key={row.id}
              data-testid={`data-table-row-${row.id}`}
              onClick={onRowClick ? () => onRowClick(row) : undefined}
              className={cn(
                onRowClick && "cursor-pointer hover:bg-slate-50/80",
              )}
            >
              {columns.map((col) => (
                <td
                  key={col.key}
                  className={cn("px-3 py-2.5 text-slate-800", col.className)}
                >
                  {col.cell(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function ConfirmDialog({
  open,
  title,
  description,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  tone = "default",
  onConfirm,
  onCancel,
}: {
  open: boolean;
  title: string;
  description?: string;
  confirmLabel?: string;
  cancelLabel?: string;
  tone?: "default" | "danger";
  onConfirm: () => void;
  onCancel: () => void;
}) {
  if (!open) return null;

  return (
    <div
      data-testid="confirm-dialog"
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="confirm-dialog-title"
    >
      <div className="w-full max-w-md rounded-lg border border-slate-200 bg-white p-5 shadow-lg">
        <h2
          id="confirm-dialog-title"
          className="text-base font-semibold text-slate-900"
        >
          {title}
        </h2>
        {description && (
          <p className="mt-2 text-sm text-slate-600">{description}</p>
        )}
        <div className="mt-5 flex justify-end gap-2">
          <button
            type="button"
            data-testid="confirm-dialog-cancel"
            onClick={onCancel}
            className="rounded-md border border-slate-200 px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-50"
          >
            {cancelLabel}
          </button>
          <button
            type="button"
            data-testid="confirm-dialog-confirm"
            onClick={onConfirm}
            className={cn(
              "rounded-md px-3 py-1.5 text-sm text-white",
              tone === "danger"
                ? "bg-rose-700 hover:bg-rose-800"
                : "bg-teal-800 hover:bg-teal-900",
            )}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
