"use client";

import Link from "next/link";
import { use } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { getApiCapabilities } from "@/lib/api/capabilities";
import { PageHeader, StatusBadge } from "@/components/layout/PageHeader";
import { ConfidenceIndicator, ErrorState, LoadingState } from "@/components/ui/FeedbackStates";

const POLL_STATES = new Set(["UPLOADED", "PROCESSING"]);
const TERMINAL_AFTER_IDENTITY = new Set([
  "MAPPING_REVIEW",
  "READY_FOR_EVALUATION",
  "FAILED",
]);
const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

function isLiveSubmissionContext(id: string): boolean {
  const caps = getApiCapabilities();
  if (caps.submissions === "live") return true;
  return UUID_RE.test(id) && !id.toLowerCase().includes("demo");
}

function stageHref(
  id: string,
  state: string,
  live: boolean,
  transcriptionState?: string,
): string {
  if (live) {
    if (state === "IDENTITY_REVIEW" || state === "UPLOADED" || state === "PROCESSING") {
      return `/submissions/${id}/identity`;
    }
    if (state === "MAPPING_REVIEW") {
      return `/submissions/${id}/mapping`;
    }
    if (state === "READY_FOR_EVALUATION" && transcriptionState !== "READY") {
      return `/submissions/${id}/transcription`;
    }
    return `/submissions/${id}`;
  }
  switch (state) {
    case "IDENTITY_REVIEW":
      return `/submissions/${id}/identity`;
    case "MAPPING_REVIEW":
      return `/submissions/${id}/mapping`;
    case "EVALUATION_REVIEW":
    case "READY_FOR_EVALUATION":
    case "EVALUATING":
    case "APPROVED":
    case "PUBLISHED":
      return `/submissions/${id}/evaluation`;
    default:
      return `/submissions/${id}/review`;
  }
}

export default function SubmissionDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const live = isLiveSubmissionContext(id);
  const mappingLive = getApiCapabilities().mapping === "live";
  const transcriptionLive = getApiCapabilities().transcription === "live";
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["submission", id],
    queryFn: () => api.getSubmission(id),
    refetchInterval: (query) => {
      if (!live) return false;
      const submission = query.state.data;
      if (!submission) return false;
      if (submission.workflow_state === "FAILED") return false;
      if (TERMINAL_AFTER_IDENTITY.has(submission.workflow_state)) return false;
      // After identity confirm, keep polling PROCESSING until mapping prepare lands.
      if (
        submission.student_match_state === "CONFIRMED" &&
        POLL_STATES.has(submission.workflow_state)
      ) {
        return 2000;
      }
      if (submission.workflow_state === "IDENTITY_REVIEW") return false;
      if (!POLL_STATES.has(submission.workflow_state)) return false;
      return 2000;
    },
  });

  if (isLoading) return <LoadingState />;
  if (isError || !data) return <ErrorState onRetry={() => void refetch()} />;

  const mockLinks = [
    { href: `/submissions/${id}/identity`, label: "Identity", testId: "link-identity" },
    { href: `/submissions/${id}/mapping`, label: "Mapping", testId: "link-mapping" },
    { href: `/submissions/${id}/evaluation`, label: "Evaluation", testId: "link-evaluation" },
    {
      href: `/submissions/${id}/annotated-paper`,
      label: "Annotated paper",
      testId: "link-annotated",
    },
    { href: `/submissions/${id}/review`, label: "Review hub", testId: "link-review" },
  ];
  const liveLinks = [
    { href: `/submissions/${id}/identity`, label: "Identity", testId: "link-identity" },
  ];
  if (
    mappingLive &&
    (data.workflow_state === "MAPPING_REVIEW" ||
      data.workflow_state === "READY_FOR_EVALUATION")
  ) {
    liveLinks.push({
      href: `/submissions/${id}/mapping`,
      label: "Mapping",
      testId: "link-mapping",
    });
  }
  if (
    transcriptionLive &&
    data.workflow_state === "READY_FOR_EVALUATION"
  ) {
    liveLinks.push({
      href: `/submissions/${id}/transcription`,
      label: "Transcription",
      testId: "link-transcription",
    });
  }
  const links = live ? liveLinks : mockLinks;
  const identityConfirmedProcessing =
    live &&
    data.student_match_state === "CONFIRMED" &&
    POLL_STATES.has(data.workflow_state);

  const downstreamBoundary =
    live &&
    (data.workflow_state === "MAPPING_REVIEW"
      ? "Question mapping is live for this submission. Evaluation, annotated paper, and review hub remain mock."
      : data.workflow_state === "READY_FOR_EVALUATION" &&
          data.transcription_state === "READY"
        ? "Evidence mapping and transcription are ready. Live evaluation is not enabled yet."
        : data.workflow_state === "READY_FOR_EVALUATION"
          ? "Mapping is complete. Open transcription review to confirm evidence text before evaluation."
          : mappingLive
            ? "Identity review and mapping are available when ready. Evaluation, annotated paper, and review hub remain mock."
            : "Mapping, evaluation, annotated paper, and review hub are not live for B3 ingestion. Identity review is available; downstream stages remain on the mock provider.");

  return (
    <div data-testid="submission-detail-page">
      <PageHeader
        title="Submission detail"
        description={data.assessment_title}
        breadcrumbs={[
          { label: "Submissions", href: "/submissions" },
          { label: id },
        ]}
        actions={
          <Link
            href={stageHref(
              id,
              data.workflow_state,
              live,
              data.transcription_state,
            )}
            data-testid="open-current-stage"
            className="rounded-md bg-teal-800 px-3 py-2 text-sm font-medium text-white hover:bg-teal-900"
          >
            Open current stage
          </Link>
        }
      />

      <div className="mb-4 flex flex-wrap gap-2">
        <span data-testid="submission-workflow-state">
          <StatusBadge kind="submission" state={data.workflow_state} />
        </span>
        <span data-testid="submission-identity-state">
          <StatusBadge kind="identity" state={data.student_match_state} />
        </span>
      </div>

      {live && (
        <p
          data-testid="submission-downstream-boundary"
          className="mb-4 rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-600"
        >
          {downstreamBoundary}
        </p>
      )}

      {identityConfirmedProcessing && (
        <p
          data-testid="identity-confirmed-boundary"
          className="mb-4 rounded-md border border-teal-200 bg-teal-50 px-3 py-2 text-sm text-teal-950"
        >
          Identity confirmed. Preparing mapping review — this page will update
          when the submission reaches mapping review.
        </p>
      )}

      <dl className="mb-6 grid gap-3 rounded-md border border-slate-200 bg-white p-4 sm:grid-cols-2 lg:grid-cols-4 text-sm">
        <div>
          <dt className="text-slate-500">Student</dt>
          <dd className="mt-1 font-semibold text-slate-900">
            {data.student_display_name ?? "Unresolved"}
          </dd>
        </div>
        <div>
          <dt className="text-slate-500">Roll detected</dt>
          <dd className="mt-1 font-semibold text-slate-900">
            {data.roll_number_detected ?? "—"}
          </dd>
        </div>
        <div>
          <dt className="text-slate-500">Pages</dt>
          <dd
            data-testid="submission-page-count"
            className="mt-1 font-semibold tabular-nums"
          >
            {data.page_count}
          </dd>
        </div>
        <div>
          <dt className="text-slate-500">Updated</dt>
          <dd className="mt-1 text-slate-800">
            {new Date(data.updated_at).toLocaleString()}
          </dd>
        </div>
        {live && data.original_filename && (
          <div>
            <dt className="text-slate-500">Source file</dt>
            <dd
              data-testid="submission-source-filename"
              className="mt-1 break-all font-semibold text-slate-900"
            >
              {data.original_filename}
            </dd>
          </div>
        )}
        {live && data.source_content_sha256 && (
          <div className="sm:col-span-2 lg:col-span-3">
            <dt className="text-slate-500">Source SHA-256</dt>
            <dd
              data-testid="submission-source-hash"
              className="mt-1 break-all font-mono text-xs text-slate-800"
            >
              {data.source_content_sha256}
            </dd>
          </div>
        )}
      </dl>

      <div className="mb-6 grid gap-3 sm:grid-cols-2">
        <div className="rounded-md border border-slate-200 bg-white p-4">
          <ConfidenceIndicator
            value={data.identity_confidence}
            label="Identity confidence"
          />
        </div>
        {(!live || mappingLive) && (
          <div className="rounded-md border border-slate-200 bg-white p-4">
            <ConfidenceIndicator
              value={data.mapping_confidence}
              label="Mapping confidence"
            />
          </div>
        )}
      </div>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {links.map((link) => (
          <Link
            key={link.href}
            href={link.href}
            data-testid={link.testId}
            className="rounded-md border border-slate-200 bg-white p-4 text-sm font-medium text-slate-900 hover:border-teal-300"
          >
            {link.label}
          </Link>
        ))}
      </div>
    </div>
  );
}
