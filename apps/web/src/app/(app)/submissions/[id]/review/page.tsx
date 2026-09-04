"use client";

import Link from "next/link";
import { use } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { PageHeader, StatusBadge } from "@/components/layout/PageHeader";
import { ErrorState, LoadingState } from "@/components/ui/FeedbackStates";

export default function SubmissionReviewPage({
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
    { href: `/submissions/${id}/identity`, label: "Identity" },
    { href: `/submissions/${id}/mapping`, label: "Mapping" },
    { href: `/submissions/${id}/evaluation`, label: "Evaluation" },
    { href: `/submissions/${id}/annotated-paper`, label: "Annotated paper" },
  ];

  return (
    <div data-testid="submission-review-page">
      <PageHeader
        title="Submission review hub"
        description={data.assessment_title}
        breadcrumbs={[
          { label: "Submissions", href: "/submissions" },
          { label: id },
          { label: "Review" },
        ]}
      />
      <div className="mb-4 flex flex-wrap gap-2">
        <StatusBadge kind="submission" state={data.workflow_state} />
        <StatusBadge kind="identity" state={data.student_match_state} />
      </div>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {links.map((link) => (
          <Link
            key={link.href}
            href={link.href}
            className="rounded-md border border-slate-200 bg-white p-4 text-sm font-medium text-slate-900 hover:border-teal-300"
          >
            {link.label}
          </Link>
        ))}
      </div>
    </div>
  );
}
