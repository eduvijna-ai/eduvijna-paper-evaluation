"use client";

import { PageHeader } from "@/components/layout/PageHeader";
import { getApiMode } from "@/lib/api";

export default function AdminPage() {
  const mode = getApiMode();

  return (
    <div data-testid="admin-page">
      <PageHeader
        title="Admin"
        description="Demo tenant settings for the Client Validation Build."
        breadcrumbs={[{ label: "Admin" }]}
      />
      <div className="grid gap-4 lg:grid-cols-2">
        <section className="rounded-md border border-slate-200 bg-white p-4">
          <h2 className="text-sm font-semibold text-slate-800">Tenant</h2>
          <dl className="mt-3 space-y-2 text-sm">
            <div className="flex justify-between gap-3">
              <dt className="text-slate-500">Tenant</dt>
              <dd>tenant-demo-001</dd>
            </div>
            <div className="flex justify-between gap-3">
              <dt className="text-slate-500">Institution</dt>
              <dd>inst-demo-001</dd>
            </div>
            <div className="flex justify-between gap-3">
              <dt className="text-slate-500">API mode</dt>
              <dd data-testid="api-mode">{mode}</dd>
            </div>
          </dl>
        </section>
        <section className="rounded-md border border-slate-200 bg-white p-4">
          <h2 className="text-sm font-semibold text-slate-800">
            Feature flags (demo)
          </h2>
          <ul className="mt-3 space-y-2 text-sm text-slate-700">
            <li>Teacher review workspace · enabled</li>
            <li>Parent plain-language reports · enabled</li>
            <li>Adaptive learning priorities · enabled</li>
            <li>Real OCR / PDF ingestion · deferred (mock only)</li>
          </ul>
        </section>
      </div>
    </div>
  );
}
