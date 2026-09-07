"use client";

import Link from "next/link";
import { use } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { getApiCapabilities } from "@/lib/api/capabilities";
import { PageHeader, StatusBadge } from "@/components/layout/PageHeader";
import { ConfidenceIndicator, ErrorState, LoadingState } from "@/components/ui/FeedbackStates";

const POLL_STATES = new Set(["UPLOADED", "PROCESSING", "EVALUATING"]);
const TERMINAL_AFTER_IDENTITY = new Set([
  "MAPPING_REVIEW",
  "READY_FOR_EVALUATION",
  "EVALUATION_REVIEW",
  "APPROVED",
  "PUBLISHED",
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
  evaluationLive?: boolean,
  publicationLive?: boolean,
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
    if (
      publicationLive &&
      (state === "APPROVED" || state === "PUBLISHED")
    ) {
      return `/submissions/${id}/publication`;
    }
    if (
      evaluationLive &&
      (state === "READY_FOR_EVALUATION" ||
        state === "EVALUATING" ||
        state === "EVALUATION_REVIEW" ||
        state === "APPROVED")
    ) {
      return `/submissions/${id}/evaluation`;
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
  const evaluationLive = getApiCapabilities().evaluation === "live";
  const publicationLive = getApiCapabilities().publication === "live";
  const reportsLive = getApiCapabilities().reports === "live";
  const analyticsLive = getApiCapabilities().analytics === "live";
  const learningLive = getApiCapabilities().learning === "live";
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["submission", id],
    queryFn: () => api.getSubmission(id),
    refetchInterval: (query) => {
      if (!live) return false;
      const submission = query.state.data;
      if (!submission) return false;
      if (submission.workflow_state === "FAILED") return false;
      if (submission.workflow_state === "EVALUATING") return 2000;
      if (TERMINAL_AFTER_IDENTITY.has(submission.workflow_state)) return false;
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

  const published = data.workflow_state === "PUBLISHED";
  const approved = data.workflow_state === "APPROVED";

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
      data.workflow_state === "READY_FOR_EVALUATION" ||
      data.workflow_state === "EVALUATING" ||
      data.workflow_state === "EVALUATION_REVIEW" ||
      data.workflow_state === "APPROVED" ||
      data.workflow_state === "PUBLISHED")
  ) {
    liveLinks.push({
      href: `/submissions/${id}/mapping`,
      label: "Mapping",
      testId: "link-mapping",
    });
  }
  if (
    transcriptionLive &&
    (data.workflow_state === "READY_FOR_EVALUATION" ||
      data.workflow_state === "EVALUATING" ||
      data.workflow_state === "EVALUATION_REVIEW" ||
      data.workflow_state === "APPROVED" ||
      data.workflow_state === "PUBLISHED")
  ) {
    liveLinks.push({
      href: `/submissions/${id}/transcription`,
      label: "Transcription",
      testId: "link-transcription",
    });
  }
  if (
    evaluationLive &&
    data.transcription_state === "READY" &&
    (data.workflow_state === "READY_FOR_EVALUATION" ||
      data.workflow_state === "EVALUATING" ||
      data.workflow_state === "EVALUATION_REVIEW" ||
      data.workflow_state === "APPROVED" ||
      data.workflow_state === "PUBLISHED")
  ) {
    liveLinks.push({
      href: `/submissions/${id}/evaluation`,
      label: "Evaluation",
      testId: "link-evaluation",
    });
  }
  if (
    publicationLive &&
    (approved || published)
  ) {
    liveLinks.push({
      href: `/submissions/${id}/publication`,
      label: "Publication",
      testId: "link-publication",
    });
    liveLinks.push({
      href: `/submissions/${id}/annotated-paper`,
      label: "Annotated paper",
      testId: "link-annotated",
    });
  }
  if (
    reportsLive &&
    published &&
    data.student_id &&
    data.assessment_id
  ) {
    liveLinks.push({
      href: `/reports/student/${data.student_id}/assessment/${data.assessment_id}`,
      label: "Student report",
      testId: "link-student-report",
    });
    liveLinks.push({
      href: `/reports/parent/${data.student_id}/assessment/${data.assessment_id}`,
      label: "Parent report",
      testId: "link-parent-report",
    });
    liveLinks.push({
      href: `/reports/teacher/${data.student_id}/assessment/${data.assessment_id}`,
      label: "Teacher report",
      testId: "link-teacher-report",
    });
  }

  const links = live ? liveLinks : mockLinks;
  const identityConfirmedProcessing =
    live &&
    data.student_match_state === "CONFIRMED" &&
    data.workflow_state === "PROCESSING";

  const downstreamBoundary =
    live &&
    (published
      ? analyticsLive
        ? learningLive
          ? "Results are published. Reports, analytics, and learning are live."
          : "Results are published. Reports and analytics are live. Adaptive learning remains unavailable for this live identity."
        : "Results are published. Student, parent, and teacher reports are live. Analytics and adaptive learning remain unavailable for this live identity."
      : approved
        ? publicationLive
          ? analyticsLive
            ? "Evaluation approved. Open publication to generate the package, then explicitly publish results. Learning remains mock."
            : "Evaluation approved. Open publication to generate the package, then explicitly publish results. Analytics and learning remain mock."
          : "Evaluation approved. Result publication, reports, analytics, and learning are not live yet."
        : data.workflow_state === "EVALUATION_REVIEW" ||
            data.workflow_state === "EVALUATING"
          ? "Live evaluation review is available. Publication and reports unlock after approval."
          : data.workflow_state === "MAPPING_REVIEW"
            ? "Question mapping is live for this submission. Open mapping to continue."
            : data.workflow_state === "READY_FOR_EVALUATION" &&
                data.transcription_state === "READY"
              ? evaluationLive
                ? "Evidence mapping and transcription are ready. Open evaluation to start scoring review."
                : "Evidence mapping and transcription are ready. Live evaluation is not enabled yet."
              : data.workflow_state === "READY_FOR_EVALUATION"
                ? "Mapping is complete. Open transcription review to confirm evidence text before evaluation."
                : mappingLive
                  ? "Identity review and mapping are available when ready."
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
              evaluationLive,
              publicationLive,
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

      {published && (
        <p
          data-testid="submission-published-immutable"
          className="mb-4 rounded-md border border-teal-200 bg-teal-50 px-3 py-2 text-sm text-teal-950"
        >
          Published results are immutable. Evaluation mutations, remapping, and
          republication from this screen are disabled.
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
