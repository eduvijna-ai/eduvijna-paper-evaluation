"use client";

import Link from "next/link";
import { use, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, isApiError } from "@/lib/api";
import { getApiCapabilities } from "@/lib/api/capabilities";
import { PageHeader, StatusBadge } from "@/components/layout/PageHeader";
import { ErrorState, LoadingState } from "@/components/ui/FeedbackStates";
import type { PublicationArtifactType } from "@/lib/types/domain";

const LIVE_UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

function isLiveUuid(id: string): boolean {
  return LIVE_UUID_RE.test(id) && !id.toLowerCase().includes("demo");
}

const ARTIFACTS: Array<{ type: PublicationArtifactType; label: string }> = [
  { type: "ANNOTATED_PDF", label: "Evaluated paper PDF" },
  { type: "STUDENT_REPORT_PDF", label: "Student report PDF" },
  { type: "PARENT_REPORT_PDF", label: "Parent report PDF" },
  { type: "TEACHER_REPORT_PDF", label: "Teacher report PDF" },
];

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export default function PublicationWorkspacePage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const publicationLive = getApiCapabilities().publication === "live";
  const liveMode = publicationLive && isLiveUuid(id);
  const queryClient = useQueryClient();
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);

  const submissionQuery = useQuery({
    queryKey: ["submission", id],
    queryFn: () => api.getSubmission(id),
    enabled: liveMode,
  });

  const workspaceQuery = useQuery({
    queryKey: ["publication", id],
    queryFn: () => api.getPublicationWorkspace!(id),
    enabled: liveMode,
    refetchInterval: (query) => {
      const status = query.state.data?.latest?.status;
      if (status === "GENERATING" || status === "READY") return 2000;
      return false;
    },
  });

  const prepareMutation = useMutation({
    mutationFn: () => api.preparePublication!(id),
    onSuccess: async () => {
      setActionError(null);
      setActionMessage("Publication package generation started.");
      await queryClient.invalidateQueries({ queryKey: ["publication", id] });
      await queryClient.invalidateQueries({ queryKey: ["submission", id] });
    },
    onError: (err) => {
      setActionMessage(null);
      setActionError(
        isApiError(err) ? err.message : "Failed to prepare publication.",
      );
    },
  });

  const publishMutation = useMutation({
    mutationFn: (publishedResultId: string) =>
      api.publishPublication!(publishedResultId),
    onSuccess: async () => {
      setActionError(null);
      setActionMessage("Results published.");
      await queryClient.invalidateQueries({ queryKey: ["publication", id] });
      await queryClient.invalidateQueries({ queryKey: ["submission", id] });
    },
    onError: (err) => {
      setActionMessage(null);
      setActionError(
        isApiError(err) ? err.message : "Failed to publish results.",
      );
    },
  });

  const regenerateMutation = useMutation({
    mutationFn: (publishedResultId: string) =>
      api.regeneratePublication!(publishedResultId),
    onSuccess: async () => {
      setActionError(null);
      setActionMessage("Regeneration queued.");
      await queryClient.invalidateQueries({ queryKey: ["publication", id] });
    },
    onError: (err) => {
      setActionMessage(null);
      setActionError(
        isApiError(err) ? err.message : "Failed to regenerate publication.",
      );
    },
  });

  if (!liveMode) {
    return (
      <div data-testid="publication-workspace-page">
        <PageHeader
          title="Publication"
          description="Publication workspace is available for live submissions in hybrid mode."
          breadcrumbs={[
            { label: "Submissions", href: "/submissions" },
            { label: id, href: `/submissions/${id}` },
            { label: "Publication" },
          ]}
        />
        <ErrorState message="Publication is not available for this submission identity." />
      </div>
    );
  }

  if (submissionQuery.isLoading || workspaceQuery.isLoading) {
    return <LoadingState />;
  }
  if (submissionQuery.isError || !submissionQuery.data) {
    return <ErrorState onRetry={() => void submissionQuery.refetch()} />;
  }
  if (workspaceQuery.isError) {
    return <ErrorState onRetry={() => void workspaceQuery.refetch()} />;
  }

  const submission = submissionQuery.data;
  const workspace = workspaceQuery.data;
  const latest = workspace?.latest ?? null;
  const status = latest?.status;
  const studentId = submission.student_id;
  const assessmentId = submission.assessment_id;
  const generating = status === "GENERATING" || status === "READY";
  const generated = status === "GENERATED";
  const published = status === "PUBLISHED" || submission.workflow_state === "PUBLISHED";
  const canPrepare =
    submission.workflow_state === "APPROVED" &&
    (!latest || status === "FAILED");
  const canPrepareWhenNone =
    submission.workflow_state === "APPROVED" && !latest;

  return (
    <div data-testid="publication-workspace-page">
      <PageHeader
        title="Publication workspace"
        description={`${submission.assessment_title} · ${submission.student_display_name ?? "Unresolved student"}`}
        breadcrumbs={[
          { label: "Submissions", href: "/submissions" },
          { label: id, href: `/submissions/${id}` },
          { label: "Publication" },
        ]}
      />

      <div className="mb-4 flex flex-wrap gap-2">
        <span data-testid="publication-submission-state">
          <StatusBadge kind="submission" state={submission.workflow_state} />
        </span>
        {status && (
          <span
            data-testid="publication-result-status"
            className="rounded-md bg-slate-900 px-2.5 py-1 text-xs font-semibold uppercase tracking-wide text-white"
          >
            {status}
          </span>
        )}
      </div>

      {latest?.ledger_snapshot_hash && (
        <p
          data-testid="publication-snapshot-hash"
          className="mb-4 break-all font-mono text-xs text-slate-600"
          title={latest.ledger_snapshot_hash}
        >
          Snapshot {latest.ledger_snapshot_hash.slice(0, 16)}…
        </p>
      )}

      {actionError && (
        <p
          data-testid="publication-action-error"
          className="mb-3 rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-900"
        >
          {actionError}
        </p>
      )}
      {actionMessage && (
        <p
          data-testid="publication-action-message"
          className="mb-3 rounded-md border border-teal-200 bg-teal-50 px-3 py-2 text-sm text-teal-950"
        >
          {actionMessage}
        </p>
      )}

      {(canPrepare || canPrepareWhenNone) && (
        <div className="mb-6 rounded-md border border-slate-200 bg-white p-4">
          <h2 className="text-sm font-semibold text-slate-900">
            Ready to generate
          </h2>
          <p className="mt-1 text-sm text-slate-600">
            Evaluation is approved. Generate the publication package (annotated
            paper + audience reports). Publishing is a separate explicit step.
          </p>
          <button
            type="button"
            data-testid="generate-publication-package"
            disabled={prepareMutation.isPending}
            onClick={() => prepareMutation.mutate()}
            className="mt-3 rounded-md bg-teal-800 px-3 py-2 text-sm font-medium text-white hover:bg-teal-900 disabled:opacity-50"
          >
            Generate publication package
          </button>
        </div>
      )}

      {generating && (
        <p
          data-testid="publication-generating"
          className="mb-6 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-950"
        >
          Generating… building annotated paper and audience reports.
        </p>
      )}

      {latest?.status === "FAILED" && (
        <div className="mb-6 rounded-md border border-rose-200 bg-rose-50 p-4 text-sm text-rose-950">
          <p data-testid="publication-failed">
            Generation failed
            {latest.failure_code ? ` (${latest.failure_code})` : ""}.
            {latest.failure_detail ? ` ${latest.failure_detail}` : ""}
          </p>
          <button
            type="button"
            data-testid="retry-publication-prepare"
            className="mt-2 rounded-md bg-rose-800 px-3 py-1.5 text-xs font-medium text-white"
            onClick={() => prepareMutation.mutate()}
          >
            Retry generate
          </button>
        </div>
      )}

      {(generated || published) && latest && (
        <div className="space-y-4">
          <div className="rounded-md border border-slate-200 bg-white p-4">
            <h2 className="text-sm font-semibold text-slate-900">
              {published ? "Published results" : "Generated package"}
            </h2>
            <p className="mt-1 text-sm text-slate-600">
              Total{" "}
              <span data-testid="publication-total-score" className="font-semibold tabular-nums">
                {latest.total_score ?? "—"} / {latest.max_total_score ?? "—"}
              </span>
              {published && latest.published_at
                ? ` · published ${new Date(latest.published_at).toLocaleString()}`
                : null}
            </p>

            <div className="mt-3 flex flex-wrap gap-2">
              <Link
                href={`/submissions/${id}/annotated-paper`}
                data-testid="preview-annotated-paper"
                className="rounded-md border border-slate-200 px-3 py-1.5 text-sm hover:border-teal-300"
              >
                Annotated paper
              </Link>
              {published && studentId && assessmentId && (
                <>
                  <Link
                    href={`/reports/student/${studentId}/assessment/${assessmentId}`}
                    data-testid="preview-student-report"
                    className="rounded-md border border-slate-200 px-3 py-1.5 text-sm hover:border-teal-300"
                  >
                    Student report
                  </Link>
                  <Link
                    href={`/reports/parent/${studentId}/assessment/${assessmentId}`}
                    data-testid="preview-parent-report"
                    className="rounded-md border border-slate-200 px-3 py-1.5 text-sm hover:border-teal-300"
                  >
                    Parent report
                  </Link>
                  <Link
                    href={`/reports/teacher/${studentId}/assessment/${assessmentId}`}
                    data-testid="preview-teacher-report"
                    className="rounded-md border border-slate-200 px-3 py-1.5 text-sm hover:border-teal-300"
                  >
                    Teacher report
                  </Link>
                </>
              )}
              {generated && !published && (
                <p
                  data-testid="publication-preview-hint"
                  className="w-full text-xs text-slate-500"
                >
                  Download PDF artifacts below to preview audience reports before
                  the explicit publish step. Consumer report URLs resolve only
                  after publish.
                </p>
              )}
            </div>

            <div className="mt-4 space-y-2">
              <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                Download artifacts
              </h3>
              <div className="flex flex-wrap gap-2">
                {ARTIFACTS.map((art) => {
                  const info = latest.artifacts[art.type];
                  const available = Boolean(info?.available);
                  return (
                    <button
                      key={art.type}
                      type="button"
                      data-testid={`download-artifact-${art.type}`}
                      disabled={!available}
                      className="rounded-md border border-slate-200 px-3 py-1.5 text-sm disabled:opacity-40 hover:border-teal-300"
                      onClick={async () => {
                        try {
                          const blob = await api.getPublicationArtifactBlob!(
                            latest.id,
                            art.type,
                          );
                          downloadBlob(
                            blob,
                            `${art.type.toLowerCase().replace(/_/g, "-")}.pdf`,
                          );
                        } catch (err) {
                          setActionError(
                            isApiError(err)
                              ? err.message
                              : "Download failed.",
                          );
                        }
                      }}
                    >
                      {art.label}
                    </button>
                  );
                })}
              </div>
            </div>

            {generated && !published && (
              <div className="mt-4 flex flex-wrap gap-2">
                <button
                  type="button"
                  data-testid="publish-results"
                  disabled={publishMutation.isPending}
                  onClick={() => {
                    if (
                      window.confirm(
                        "Publish results to student/parent/teacher consumers? This cannot be undone from the UI.",
                      )
                    ) {
                      publishMutation.mutate(latest.id);
                    }
                  }}
                  className="rounded-md bg-teal-800 px-3 py-2 text-sm font-medium text-white hover:bg-teal-900 disabled:opacity-50"
                >
                  Publish results
                </button>
                <button
                  type="button"
                  data-testid="regenerate-publication"
                  disabled={regenerateMutation.isPending}
                  onClick={() => regenerateMutation.mutate(latest.id)}
                  className="rounded-md border border-slate-300 px-3 py-2 text-sm font-medium text-slate-800 hover:bg-slate-50 disabled:opacity-50"
                >
                  Regenerate
                </button>
              </div>
            )}

            {published && (
              <p
                data-testid="publication-published-status"
                className="mt-4 rounded-md border border-teal-200 bg-teal-50 px-3 py-2 text-sm text-teal-950"
              >
                Published. Consumer report links above resolve live published
                data. Analytics and adaptive learning remain unavailable for
                this live identity.
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
