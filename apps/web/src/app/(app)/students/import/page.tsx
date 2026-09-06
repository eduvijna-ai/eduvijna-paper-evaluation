"use client";

import { useMemo, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { PageHeader } from "@/components/layout/PageHeader";
import { api, isApiError } from "@/lib/api";
import { A1_PERMISSIONS } from "@/lib/api/a1-types";
import { getSession, hasPermission } from "@/lib/auth/session";
import {
  downloadCsvTemplate,
  importCommitErrorMessage,
  type ImportCommitResult,
  type ImportValidationView,
} from "@/lib/api/mappers/import";
import { ErrorState, LoadingState } from "@/components/ui/FeedbackStates";

type Step = "upload" | "validate" | "summary";

export default function StudentsImportPage() {
  const queryClient = useQueryClient();
  const session = useMemo(() => getSession(), []);
  const canImport = hasPermission(session, A1_PERMISSIONS.studentImport);

  const [step, setStep] = useState<Step>("upload");
  const [file, setFile] = useState<File | null>(null);
  const [validation, setValidation] = useState<ImportValidationView | null>(
    null,
  );
  const [error, setError] = useState<string | null>(null);
  const [commitResult, setCommitResult] = useState<ImportCommitResult | null>(
    null,
  );

  const validateMutation = useMutation({
    mutationFn: (f: File) => api.validateStudentImport(f),
    onSuccess: (result) => {
      setValidation(result);
      setStep("validate");
      setError(null);
    },
    onError: (err) => {
      setError(isApiError(err) ? err.userMessage() : "Validation failed");
    },
  });

  const commitMutation = useMutation({
    mutationFn: (sessionId: string) => api.commitStudentImport(sessionId),
    onSuccess: async (result) => {
      setCommitResult(result);
      setStep("summary");
      await queryClient.invalidateQueries({ queryKey: ["students"] });
    },
    onError: (err) => {
      if (isApiError(err)) {
        setError(importCommitErrorMessage(err));
      } else {
        setError("Commit failed");
      }
    },
  });

  if (!canImport) {
    return (
      <ErrorState
        title="Permission denied"
        message="student:import permission is required."
      />
    );
  }

  return (
    <div data-testid="students-import-page">
      <PageHeader
        title="Import students"
        description="Validate CSV against the live roster, then commit only VALID rows."
        breadcrumbs={[
          { label: "Students", href: "/students" },
          { label: "Import" },
        ]}
        actions={
          <button
            type="button"
            data-testid="download-csv-template"
            onClick={() => downloadCsvTemplate()}
            className="rounded-md border border-slate-200 bg-white px-3 py-2 text-sm hover:bg-slate-50"
          >
            Download CSV template
          </button>
        }
      />

      {error && (
        <p
          data-testid="import-error"
          className="mb-4 rounded-md bg-rose-50 px-3 py-2 text-sm text-rose-800 ring-1 ring-rose-200"
        >
          {error}
        </p>
      )}

      {step === "upload" && (
        <div className="max-w-lg space-y-4 rounded-md border border-slate-200 bg-white p-4">
          <label className="block text-sm">
            <span className="font-medium text-slate-800">Roster CSV</span>
            <input
              data-testid="import-file"
              type="file"
              accept=".csv,text/csv"
              className="mt-1 block w-full text-sm"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            />
          </label>
          <button
            type="button"
            data-testid="import-validate"
            disabled={!file || validateMutation.isPending}
            onClick={() => {
              if (!file) return;
              setError(null);
              validateMutation.mutate(file);
            }}
            className="rounded-md bg-teal-800 px-3 py-2 text-sm font-medium text-white disabled:opacity-60"
          >
            {validateMutation.isPending ? "Validating…" : "Validate CSV"}
          </button>
          {validateMutation.isPending && <LoadingState label="Validating…" />}
        </div>
      )}

      {step === "validate" && validation && (
        <div className="space-y-4" data-testid="import-validation-panel">
          <div className="grid gap-3 sm:grid-cols-4">
            <Stat label="Total rows" value={validation.totalRows} />
            <Stat label="Valid" value={validation.validRowCount} />
            <Stat label="Invalid" value={validation.invalidCount} />
            <Stat label="Duplicates" value={validation.duplicateCount} />
          </div>
          <div className="overflow-x-auto rounded-md border border-slate-200 bg-white">
            <table className="min-w-full text-left text-sm">
              <thead className="bg-slate-50 text-xs uppercase text-slate-500">
                <tr>
                  <th className="px-3 py-2">Row</th>
                  <th className="px-3 py-2">Code</th>
                  <th className="px-3 py-2">Name</th>
                  <th className="px-3 py-2">Outcome</th>
                </tr>
              </thead>
              <tbody>
                {validation.rowResults.map((row, idx) => (
                  <tr key={idx} className="border-t border-slate-100">
                    <td className="px-3 py-2">{row.rowNumber}</td>
                    <td className="px-3 py-2">{row.studentCode}</td>
                    <td className="px-3 py-2">{row.fullName}</td>
                    <td className="px-3 py-2">
                      <span data-testid={`import-outcome-${idx}`}>
                        {row.outcome}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => {
                setStep("upload");
                setValidation(null);
              }}
              className="rounded-md border border-slate-200 px-3 py-2 text-sm"
            >
              Back
            </button>
            <button
              type="button"
              data-testid="import-commit"
              disabled={
                validation.validRowCount < 1 || commitMutation.isPending
              }
              onClick={() => {
                setError(null);
                commitMutation.mutate(validation.importSessionId);
              }}
              className="rounded-md bg-teal-800 px-3 py-2 text-sm font-medium text-white disabled:opacity-60"
            >
              {commitMutation.isPending
                ? "Committing…"
                : `Commit ${validation.validRowCount} valid row(s)`}
            </button>
          </div>
        </div>
      )}

      {step === "summary" && (
        <div
          data-testid="import-success"
          className="rounded-md bg-teal-50 px-4 py-3 text-sm text-teal-900 ring-1 ring-teal-200"
        >
          {commitResult != null
            ? `Imported ${commitResult.committedCount} student(s).`
            : "Import committed."}
        </div>
      )}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-md border border-slate-200 bg-white px-3 py-2">
      <div className="text-xs text-slate-500">{label}</div>
      <div className="text-lg font-semibold text-slate-900">{value}</div>
    </div>
  );
}
