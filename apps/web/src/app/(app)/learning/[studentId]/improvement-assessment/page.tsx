"use client";

import { use, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { PageHeader } from "@/components/layout/PageHeader";
import { ImprovementAssessmentBlueprint } from "@/components/learning/LearningComponents";
import { ErrorState, LoadingState } from "@/components/ui/FeedbackStates";
import type { ImprovementAssessmentBlueprint as Blueprint } from "@/lib/types/domain";

export default function ImprovementAssessmentPage({
  params,
}: {
  params: Promise<{ studentId: string }>;
}) {
  const { studentId } = use(params);
  const [local, setLocal] = useState<Blueprint | null>(null);

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["improvement-blueprint", studentId],
    queryFn: () => api.getImprovementBlueprint(studentId),
  });

  const approveMutation = useMutation({
    mutationFn: (blueprintId: string) =>
      api.approveImprovementBlueprint(blueprintId),
    onSuccess: (result) => setLocal(result),
  });

  if (isLoading) return <LoadingState />;
  if (isError || !data) return <ErrorState onRetry={() => void refetch()} />;

  const blueprint = local ?? data;

  return (
    <div data-testid="improvement-assessment-page">
      <PageHeader
        title="Improvement assessment blueprint"
        description="Teacher approval gate before releasing a targeted follow-up assessment."
        breadcrumbs={[
          { label: "Learning", href: `/learning/${studentId}` },
          { label: "Improvement assessment" },
        ]}
      />
      <ImprovementAssessmentBlueprint
        blueprint={blueprint}
        onApprove={() => approveMutation.mutate(blueprint.id)}
      />
    </div>
  );
}
