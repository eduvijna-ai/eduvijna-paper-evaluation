"use client";

import Link from "next/link";
import { use } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { getApiCapabilities } from "@/lib/api/capabilities";
import { PageHeader, StatusBadge } from "@/components/layout/PageHeader";
import { ErrorState, LoadingState } from "@/components/ui/FeedbackStates";

export default function AssessmentDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const capabilities = getApiCapabilities();
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["assessment", id],
    queryFn: () => api.getAssessment(id),
  });

  if (isLoading) return <LoadingState />;
  if (isError || !data) return <ErrorState onRetry={() => void refetch()} />;

  const navLinks = [
    {
      href: `/assessments/${id}/questions`,
      label: "Questions",
      testId: "link-questions",
    },
    {
      href: `/assessments/${id}/answer-key`,
      label: "Answer key",
      testId: "link-answer-key",
    },
    {
      href: `/assessments/${id}/rubric`,
      label: "Rubric",
      testId: "link-rubric",
    },
    {
      href: `/assessments/${id}/curriculum-map`,
      label: "Curriculum map",
      testId: "link-curriculum-map",
    },
  ];
  const analyticsIsCompatible =
    capabilities.assessments === "mock" || capabilities.analytics === "live";

  return (
    <div data-testid="assessment-detail-page">
      <PageHeader
        title={data.title}
        description={`${data.code} · ${data.subject} · Version ${data.grade}`}
        breadcrumbs={[
          { label: "Assessments", href: "/assessments" },
          { label: data.code },
        ]}
        actions={
          <div className="flex flex-wrap gap-2">
            <StatusBadge kind="assessment" state={data.workflow_state} />
            {navLinks.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                data-testid={link.testId}
                className="rounded-md border border-slate-200 px-3 py-2 text-sm hover:bg-slate-50"
              >
                {link.label}
              </Link>
            ))}
            {analyticsIsCompatible && (
              <Link
                href={`/analytics/assessments/${id}`}
                data-testid="link-analytics"
                className="rounded-md bg-teal-800 px-3 py-2 text-sm font-medium text-white hover:bg-teal-900"
              >
                Analytics
              </Link>
            )}
          </div>
        }
      />
      <dl className="grid gap-3 rounded-md border border-slate-200 bg-white p-4 sm:grid-cols-3 text-sm">
        <div>
          <dt className="text-slate-500">Max marks</dt>
          <dd className="mt-1 font-semibold tabular-nums">{data.max_marks}</dd>
        </div>
        <div>
          <dt className="text-slate-500">Questions</dt>
          <dd className="mt-1 font-semibold tabular-nums">
            {data.question_count}
          </dd>
        </div>
        <div>
          <dt className="text-slate-500">Submissions</dt>
          <dd className="mt-1 font-semibold tabular-nums">
            {capabilities.assessments === "live" && capabilities.submissions === "mock"
              ? "Not live yet"
              : data.submission_count}
          </dd>
        </div>
      </dl>

      {capabilities.assessments === "live" &&
        capabilities.analytics === "mock" && (
        <p
          data-testid="assessment-downstream-boundary"
          className="mt-3 rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-600"
        >
          {capabilities.evaluation === "live" && capabilities.reports === "live"
            ? "Analytics and adaptive learning remain on the mock provider and are hidden for live assessment identities."
            : capabilities.evaluation === "live"
            ? "Analytics, reports, and learning remain on the mock provider and are hidden for live assessment identities."
            : capabilities.submissions === "live"
              ? "Analytics, mapping, and evaluation remain on the mock provider and are hidden for live assessment identities."
              : "Analytics and submission workflows remain on the mock provider and are hidden for live A2 assessment identities."}
        </p>
      )}

      {capabilities.assessments === "live" &&
        capabilities.analytics === "live" &&
        capabilities.learning === "mock" && (
        <p
          data-testid="assessment-learning-boundary"
          className="mt-3 rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-600"
        >
          Adaptive learning remains on the mock provider and is hidden for live
          assessment identities.
        </p>
      )}

      <nav
        data-testid="assessment-subnav"
        className="mt-4 flex flex-wrap gap-2 border-t border-slate-200 pt-4"
        aria-label="Assessment sections"
      >
        {navLinks.map((link) => (
          <Link
            key={`subnav-${link.href}`}
            href={link.href}
            className="rounded-md bg-slate-100 px-3 py-1.5 text-xs font-medium text-slate-800 hover:bg-slate-200"
          >
            {link.label}
          </Link>
        ))}
      </nav>
    </div>
  );
}
