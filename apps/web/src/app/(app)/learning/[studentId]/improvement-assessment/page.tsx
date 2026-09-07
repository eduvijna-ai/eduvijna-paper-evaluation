"use client";

import { use, useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { getApiCapabilities } from "@/lib/api/capabilities";
import { PageHeader } from "@/components/layout/PageHeader";
import {
  ImprovementAssessmentBlueprint,
  LiveImprovementBlueprintPanel,
} from "@/components/learning/LearningComponents";
import { ErrorState, LoadingState } from "@/components/ui/FeedbackStates";
import type {
  ImprovementAssessmentBlueprint as Blueprint,
  LiveImprovementAssessment,
} from "@/lib/types/domain";

function LiveImprovementAssessmentPage({ studentId }: { studentId: string }) {
  const queryClient = useQueryClient();
  const [rejectReason, setRejectReason] = useState("");
  const [pollingBlueprintId, setPollingBlueprintId] = useState<string | null>(
    null,
  );

  const workspaceQuery = useQuery({
    queryKey: ["live-learning-workspace", studentId, "auto"],
    queryFn: () => api.getLearningWorkspace!(studentId),
  });

  const workspace = workspaceQuery.data;
  const plan = workspace?.latest_plan;
  const runId = plan?.run_id ?? workspace?.latest_run?.id ?? null;
  const blueprintFromWorkspace = workspace?.latest_improvement_blueprint;

  const blueprintQuery = useQuery({
    queryKey: ["live-improvement-blueprint", pollingBlueprintId],
    queryFn: () => api.getImprovementAssessment!(pollingBlueprintId!),
    enabled: Boolean(pollingBlueprintId),
    refetchInterval: (q) => {
      const status = q.state.data?.status;
      if (status === "DRAFT" || status === "GENERATING") return 2000;
      return false;
    },
  });

  useEffect(() => {
    const status = blueprintQuery.data?.status;
    if (
      status === "PENDING_APPROVAL" ||
      status === "APPROVED" ||
      status === "REJECTED" ||
      status === "FAILED"
    ) {
      void queryClient.invalidateQueries({
        queryKey: ["live-learning-workspace", studentId],
      });
      if (status === "PENDING_APPROVAL" || status === "APPROVED") {
        setPollingBlueprintId(null);
      }
    }
  }, [blueprintQuery.data?.status, queryClient, studentId]);

  const prepareMutation = useMutation({
    mutationFn: () => {
      if (!runId) throw new Error("Learning plan run required");
      return api.prepareImprovementBlueprint!(runId);
    },
    onSuccess: (result) => {
      setPollingBlueprintId(result.improvement_assessment_id);
      void queryClient.invalidateQueries({
        queryKey: ["live-learning-workspace", studentId],
      });
    },
  });

  const approveMutation = useMutation({
    mutationFn: (id: string) => api.approveImprovementBlueprint(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: ["live-learning-workspace", studentId],
      });
    },
  });

  const rejectMutation = useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) =>
      api.rejectImprovementBlueprint!(id, reason),
    onSuccess: () => {
      setRejectReason("");
      void queryClient.invalidateQueries({
        queryKey: ["live-learning-workspace", studentId],
      });
    },
  });

  if (workspaceQuery.isLoading) return <LoadingState />;
  if (workspaceQuery.isError || !workspace) {
    return <ErrorState onRetry={() => void workspaceQuery.refetch()} />;
  }

  const blueprint: LiveImprovementAssessment | null =
    (approveMutation.data as LiveImprovementAssessment | undefined) ??
    (rejectMutation.data as LiveImprovementAssessment | undefined) ??
    blueprintQuery.data ??
    blueprintFromWorkspace ??
    null;

  const generating =
    prepareMutation.isPending ||
    Boolean(pollingBlueprintId) ||
    blueprint?.status === "DRAFT" ||
    blueprint?.status === "GENERATING";

  const planReady = plan?.status === "READY";
  const planStale = Boolean(workspace.is_stale || plan?.is_stale);
  const noGaps =
    planReady &&
    (plan?.recommendations.length ?? 0) === 0;

  return (
    <div data-testid="improvement-assessment-page" data-learning-mode="live">
      <PageHeader
        title="Improvement assessment blueprint"
        description="Teacher approval freezes the blueprint; reassessment release is not live."
        breadcrumbs={[
          { label: "Learning", href: `/learning/${studentId}` },
          { label: "Improvement assessment" },
        ]}
      />

      {!planReady && (
        <p
          data-testid="blueprint-need-plan"
          className="mb-4 rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700"
        >
          Generate a learning plan first.
        </p>
      )}

      {planReady && planStale && (
        <p
          data-testid="blueprint-need-regenerate"
          className="mb-4 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900"
        >
          Regenerate the learning plan first.
        </p>
      )}

      {planReady && !planStale && noGaps && (
        <p
          data-testid="blueprint-no-targets"
          className="mb-4 rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700"
        >
          No evidence-backed targets are available for an improvement
          blueprint.
        </p>
      )}

      {planReady &&
        !planStale &&
        !noGaps &&
        !blueprint &&
        !generating && (
          <button
            type="button"
            data-testid="generate-improvement-blueprint"
            onClick={() => prepareMutation.mutate()}
            className="mb-4 rounded-md bg-teal-800 px-3 py-2 text-sm font-medium text-white hover:bg-teal-900"
          >
            Generate improvement blueprint
          </button>
        )}

      {generating && (
        <p
          data-testid="blueprint-generating"
          className="mb-4 text-sm text-slate-600"
        >
          Generating…
        </p>
      )}

      {blueprint &&
        blueprint.status !== "DRAFT" &&
        blueprint.status !== "GENERATING" && (
          <LiveImprovementBlueprintPanel
            blueprint={blueprint}
            onApprove={() => approveMutation.mutate(blueprint.id)}
            onReject={() =>
              rejectMutation.mutate({
                id: blueprint.id,
                reason: rejectReason.trim(),
              })
            }
            rejectReason={rejectReason}
            onRejectReasonChange={setRejectReason}
          />
        )}
    </div>
  );
}

function MockImprovementAssessmentPage({ studentId }: { studentId: string }) {
  const [local, setLocal] = useState<Blueprint | null>(null);

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["improvement-blueprint", studentId],
    queryFn: () => api.getImprovementBlueprint(studentId),
  });

  const approveMutation = useMutation({
    mutationFn: (blueprintId: string) =>
      api.approveImprovementBlueprint(blueprintId),
    onSuccess: (result) => setLocal(result as Blueprint),
  });

  if (isLoading) return <LoadingState />;
  if (isError || !data) return <ErrorState onRetry={() => void refetch()} />;

  const blueprint = local ?? data;

  return (
    <div data-testid="improvement-assessment-page" data-learning-mode="mock">
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

export default function ImprovementAssessmentPage({
  params,
}: {
  params: Promise<{ studentId: string }>;
}) {
  const { studentId } = use(params);
  const live = getApiCapabilities().learning === "live";
  return live ? (
    <LiveImprovementAssessmentPage studentId={studentId} />
  ) : (
    <MockImprovementAssessmentPage studentId={studentId} />
  );
}
