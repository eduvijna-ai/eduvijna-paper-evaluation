"use client";

import Link from "next/link";
import { use } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { PageHeader, StatusBadge } from "@/components/layout/PageHeader";
import { ConfidenceIndicator, ErrorState, LoadingState } from "@/components/ui/FeedbackStates";

function stageHref(id: string, state: string): string {
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
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["submission", id],
    queryFn: () => api.getSubmission(id),
  });

  if (isLoading) return <LoadingState />;
  if (isError || !data) return <ErrorState onRetry={() => void refetch()} />;

  const links = [
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
            href={stageHref(id, data.workflow_state)}
            data-testid="open-current-stage"
            className="rounded-md bg-teal-800 px-3 py-2 text-sm font-medium text-white hover:bg-teal-900"
          >
            Open current stage
          </Link>
        }
      />

      <div className="mb-4 flex flex-wrap gap-2">
        <StatusBadge kind="submission" state={data.workflow_state} />
        <StatusBadge kind="identity" state={data.student_match_state} />
      </div>

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
          <dd className="mt-1 font-semibold tabular-nums">{data.page_count}</dd>
        </div>
        <div>
          <dt className="text-slate-500">Updated</dt>
          <dd className="mt-1 text-slate-800">
            {new Date(data.updated_at).toLocaleString()}
          </dd>
        </div>
      </dl>

      <div className="mb-6 grid gap-3 sm:grid-cols-2">
        <div className="rounded-md border border-slate-200 bg-white p-4">
          <ConfidenceIndicator
            value={data.identity_confidence}
            label="Identity confidence"
          />
        </div>
        <div className="rounded-md border border-slate-200 bg-white p-4">
          <ConfidenceIndicator
            value={data.mapping_confidence}
            label="Mapping confidence"
          />
        </div>
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
