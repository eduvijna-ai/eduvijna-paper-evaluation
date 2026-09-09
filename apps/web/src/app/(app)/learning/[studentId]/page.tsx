"use client";

import Link from "next/link";
import { Suspense, use, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, isApiError } from "@/lib/api";
import { getApiCapabilities } from "@/lib/api/capabilities";
import { PageHeader } from "@/components/layout/PageHeader";
import {
  AssignResourcePanel,
  AssignedResourcesSection,
  ErrorDistribution,
  LearningPathStep,
  LiveLearningPathStepRow,
  LiveRecommendationCard,
  ReassessmentsSection,
  TopicPriorityCard,
} from "@/components/learning/LearningComponents";
import { ErrorState, LoadingState } from "@/components/ui/FeedbackStates";
import type {
  LiveLearningWorkspace,
  Reassessment,
  StudentResourceAssignment,
} from "@/lib/types/domain";
import {
  REASSESSMENT_ID,
  REASSESSMENT_ID_CREATED,
} from "@/lib/fixtures/b14-demo";

const DEMO_STUDENT_ID = "student-demo-001";

function evidenceReady(status: string): boolean {
  // B9 gate: only READY unlocks generation (PARTIAL/QUEUED/FAILED block).
  return status === "READY";
}

function LiveAdaptiveLearningPage({ studentId }: { studentId: string }) {
  const queryClient = useQueryClient();
  const searchParams = useSearchParams();
  const curriculumFromUrl = searchParams.get("curriculum_id") ?? undefined;
  const [curriculumId, setCurriculumId] = useState<string | undefined>(
    curriculumFromUrl,
  );
  const [activeRunId, setActiveRunId] = useState<string | null>(null);
  const [selectedResourceId, setSelectedResourceId] = useState("");
  const [selectedRecommendationId, setSelectedRecommendationId] = useState("");

  const workspaceQuery = useQuery({
    queryKey: ["live-learning-workspace", studentId, curriculumId ?? "auto"],
    queryFn: () => api.getLearningWorkspace!(studentId, curriculumId),
  });

  const workspace = workspaceQuery.data;

  useEffect(() => {
    if (curriculumFromUrl && curriculumFromUrl !== curriculumId) {
      setCurriculumId(curriculumFromUrl);
    }
  }, [curriculumFromUrl, curriculumId]);

  useEffect(() => {
    if (!workspace) return;
    if (!curriculumId && workspace.selected_curriculum?.id) {
      setCurriculumId(workspace.selected_curriculum.id);
    } else if (
      !curriculumId &&
      workspace.available_curricula.length === 1
    ) {
      setCurriculumId(workspace.available_curricula[0]!.id);
    }
  }, [workspace, curriculumId]);

  const selectedCurriculumId =
    curriculumId ??
    workspace?.selected_curriculum?.id ??
    workspace?.available_curricula[0]?.id;

  const activeResourcesQuery = useQuery({
    queryKey: [
      "b13-active-resources",
      selectedCurriculumId ?? "none",
    ],
    queryFn: () =>
      api.listCurriculumResources!({
        curriculumId: selectedCurriculumId,
        status: "ACTIVE",
      }),
    enabled: Boolean(selectedCurriculumId),
  });

  const runQuery = useQuery({
    queryKey: ["live-learning-plan-run", activeRunId],
    queryFn: () => api.getLearningPlanRun!(activeRunId!),
    enabled: Boolean(activeRunId),
    refetchInterval: (q) => {
      const status = q.state.data?.status;
      if (status === "QUEUED" || status === "RUNNING") return 2000;
      return false;
    },
  });

  useEffect(() => {
    const status = runQuery.data?.status;
    if (status === "READY" || status === "FAILED" || status === "SUPERSEDED") {
      void queryClient.invalidateQueries({
        queryKey: ["live-learning-workspace", studentId],
      });
      if (status === "READY") setActiveRunId(null);
    }
  }, [runQuery.data?.status, queryClient, studentId]);

  const prepareMutation = useMutation({
    mutationFn: () => {
      if (!selectedCurriculumId) {
        throw new Error("Select a curriculum first");
      }
      return api.prepareLearningPlan!(studentId, selectedCurriculumId);
    },
    onSuccess: (result) => {
      setActiveRunId(result.run_id);
      void queryClient.invalidateQueries({
        queryKey: ["live-learning-workspace", studentId],
      });
    },
  });

  const assignMutation = useMutation({
    mutationFn: () =>
      api.assignStudentResource!(studentId, {
        resource_id: selectedResourceId,
        learning_recommendation_id: selectedRecommendationId || null,
      }),
    onSuccess: () => {
      setSelectedResourceId("");
      setSelectedRecommendationId("");
      void queryClient.invalidateQueries({
        queryKey: ["live-learning-workspace", studentId],
      });
    },
  });

  const cancelMutation = useMutation({
    mutationFn: (assignmentId: string) =>
      api.cancelStudentResourceAssignment!(assignmentId),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: ["live-learning-workspace", studentId],
      });
    },
  });

  if (workspaceQuery.isLoading) return <LoadingState />;
  if (workspaceQuery.isError || !workspace) {
    return <ErrorState onRetry={() => void workspaceQuery.refetch()} />;
  }

  const assignments = workspace.resource_assignments ?? [];
  const reassessments = workspace.reassessments ?? [];
  const recommendations = workspace.latest_plan?.recommendations ?? [];
  const compatibleResources = (activeResourcesQuery.data?.items ?? []).filter(
    (resource) => {
      if (!selectedRecommendationId) return true;
      const rec = recommendations.find((r) => r.id === selectedRecommendationId);
      if (!rec) return true;
      return resource.curriculum_node_ids.includes(rec.curriculum_node_id);
    },
  );

  return (
    <LiveLearningWorkspaceView
      studentId={studentId}
      workspace={workspace}
      selectedCurriculumId={selectedCurriculumId}
      onSelectCurriculum={setCurriculumId}
      preparing={prepareMutation.isPending || Boolean(activeRunId)}
      prepareError={prepareMutation.error}
      runStatus={runQuery.data?.status ?? workspace.latest_run?.status ?? null}
      onGenerate={() => prepareMutation.mutate()}
      assignments={assignments}
      reassessments={reassessments}
      assignResources={compatibleResources}
      recommendations={recommendations.map((r) => ({
        id: r.id,
        code: r.code,
        title: r.title,
      }))}
      selectedResourceId={selectedResourceId}
      selectedRecommendationId={selectedRecommendationId}
      onSelectResource={setSelectedResourceId}
      onSelectRecommendation={setSelectedRecommendationId}
      onAssign={() => assignMutation.mutate()}
      assigning={assignMutation.isPending}
      assignError={
        assignMutation.error
          ? isApiError(assignMutation.error)
            ? assignMutation.error.message
            : "Failed to assign resource"
          : null
      }
      onCancelAssignment={(id) => cancelMutation.mutate(id)}
      cancelPending={cancelMutation.isPending}
    />
  );
}

function LiveLearningWorkspaceView({
  studentId,
  workspace,
  selectedCurriculumId,
  onSelectCurriculum,
  preparing,
  prepareError,
  runStatus,
  onGenerate,
  assignments,
  reassessments,
  assignResources,
  recommendations,
  selectedResourceId,
  selectedRecommendationId,
  onSelectResource,
  onSelectRecommendation,
  onAssign,
  assigning,
  assignError,
  onCancelAssignment,
  cancelPending,
}: {
  studentId: string;
  workspace: LiveLearningWorkspace;
  selectedCurriculumId: string | undefined;
  onSelectCurriculum: (id: string) => void;
  preparing: boolean;
  prepareError: unknown;
  runStatus: string | null;
  onGenerate: () => void;
  assignments: StudentResourceAssignment[];
  reassessments: Reassessment[];
  assignResources: Array<{
    id: string;
    code: string;
    title: string;
    status: string;
  }>;
  recommendations: Array<{ id: string; code: string; title: string }>;
  selectedResourceId: string;
  selectedRecommendationId: string;
  onSelectResource: (id: string) => void;
  onSelectRecommendation: (id: string) => void;
  onAssign: () => void;
  assigning: boolean;
  assignError: string | null;
  onCancelAssignment: (id: string) => void;
  cancelPending: boolean;
}) {
  const plan = workspace.latest_plan;
  const ready = evidenceReady(String(workspace.materialization_status));
  const generating =
    preparing ||
    runStatus === "QUEUED" ||
    runStatus === "RUNNING" ||
    workspace.latest_run?.status === "QUEUED" ||
    workspace.latest_run?.status === "RUNNING";
  const showPlan = plan && plan.status === "READY";
  const noGaps =
    showPlan &&
    plan.recommendations.length === 0 &&
    plan.path.length === 0;

  const studentLabel =
    workspace.student.external_ref ??
    workspace.student.student_code ??
    workspace.student.display_name;

  return (
    <div data-testid="adaptive-learning-page" data-learning-mode="live">
      <PageHeader
        title="Adaptive learning"
        description={`Evidence-backed priorities for ${workspace.student.display_name}`}
        breadcrumbs={[
          { label: "Learning" },
          { label: studentLabel },
        ]}
        actions={
          <div className="flex flex-wrap gap-2">
            <Link
              href="/learning/resources"
              data-testid="b13-resources-catalog-link"
              className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-800 hover:bg-slate-50"
            >
              Resource catalog
            </Link>
            {showPlan && plan.recommendations.length > 0 ? (
              <Link
                href={`/learning/${studentId}/improvement-assessment`}
                data-testid="improvement-assessment-link"
                className="rounded-md bg-teal-800 px-3 py-2 text-sm font-medium text-white hover:bg-teal-900"
              >
                Improvement assessment
              </Link>
            ) : null}
          </div>
        }
      />

      <p
        data-testid="curriculum-restriction-notice"
        className="mb-4 rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700"
      >
        Recommendations restricted to student&apos;s curriculum. No open-web
        resources.
      </p>

      {workspace.available_curricula.length > 1 && (
        <label className="mb-4 block text-sm text-slate-700">
          Curriculum
          <select
            data-testid="learning-curriculum-select"
            className="mt-1 block w-full max-w-md rounded-md border border-slate-300 px-2 py-1.5"
            value={selectedCurriculumId ?? ""}
            onChange={(e) => onSelectCurriculum(e.target.value)}
          >
            {workspace.available_curricula.map((c) => (
              <option key={c.id} value={c.id}>
                {c.code} · {c.name}
              </option>
            ))}
          </select>
        </label>
      )}

      <div
        data-testid="learning-materialization-status"
        className="mb-4 rounded-md border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700"
      >
        Materialization:{" "}
        <span className="font-semibold">
          {workspace.materialization_status}
        </span>
        {" · "}
        Evidence nodes: {workspace.evidence_coverage.curriculum_node_count},
        rows: {workspace.evidence_coverage.evidence_row_count}
      </div>

      {!ready && (
        <p
          data-testid="learning-evidence-not-ready"
          className="mb-4 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900"
        >
          Published mastery evidence is still processing (
          {workspace.materialization_status}). Generate learning plan is
          disabled until materialization is READY.
        </p>
      )}

      {(workspace.is_stale || plan?.is_stale) && showPlan && (
        <p
          data-testid="learning-plan-stale"
          className="mb-4 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900"
        >
          New published evidence is available. Regenerate the learning plan.
        </p>
      )}

      {generateErrorMessage(prepareError) && (
        <p className="mb-4 text-sm text-rose-700">
          {generateErrorMessage(prepareError)}
        </p>
      )}

      {(!showPlan || workspace.is_stale || plan?.is_stale) && (
        <div className="mb-6">
          <button
            type="button"
            data-testid="generate-learning-plan"
            disabled={!ready || !selectedCurriculumId || generating}
            onClick={onGenerate}
            className="rounded-md bg-teal-800 px-3 py-2 text-sm font-medium text-white hover:bg-teal-900 disabled:opacity-50"
          >
            {generating
              ? "Generating…"
              : showPlan
                ? "Regenerate learning plan"
                : "Generate learning plan"}
          </button>
        </div>
      )}

      {generating && !showPlan && (
        <p
          data-testid="learning-plan-generating"
          className="mb-4 text-sm text-slate-600"
        >
          Generating…
        </p>
      )}

      {noGaps && (
        <p
          data-testid="learning-no-gaps"
          className="mb-4 rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700"
        >
          No evidence-backed learning gaps were identified from currently
          published results.
        </p>
      )}

      {showPlan && plan.recommendations.length > 0 && (
        <section
          data-testid="live-recommendations"
          className="grid gap-3 lg:grid-cols-3"
        >
          {plan.recommendations.map((rec) => (
            <LiveRecommendationCard key={rec.id} recommendation={rec} />
          ))}
        </section>
      )}

      <AssignResourcePanel
        resources={assignResources}
        recommendations={recommendations}
        selectedResourceId={selectedResourceId}
        selectedRecommendationId={selectedRecommendationId}
        onSelectResource={onSelectResource}
        onSelectRecommendation={onSelectRecommendation}
        onAssign={onAssign}
        assigning={assigning}
        errorMessage={assignError}
      />

      <AssignedResourcesSection
        assignments={assignments}
        onCancel={onCancelAssignment}
        cancelPending={cancelPending}
      />

      <ReassessmentsSection reassessments={reassessments} />

      {showPlan && plan.path.length > 0 && (
        <section className="mt-6">
          <h2 className="mb-3 text-sm font-semibold text-slate-800">
            Learning path
          </h2>
          <ol data-testid="live-learning-path" className="space-y-2">
            {plan.path.map((step, index) => (
              <LiveLearningPathStepRow
                key={step.id}
                step={step}
                index={index}
              />
            ))}
          </ol>
        </section>
      )}
    </div>
  );
}

function generateErrorMessage(error: unknown): string | null {
  if (!error) return null;
  if (typeof error === "object" && error && "message" in error) {
    return String((error as { message: unknown }).message);
  }
  return "Failed to generate learning plan";
}

function MockAdaptiveLearningPage({ studentId }: { studentId: string }) {
  const queryClient = useQueryClient();
  const [selectedResourceId, setSelectedResourceId] = useState("");
  const [selectedRecommendationId, setSelectedRecommendationId] = useState("");

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["adaptive-learning", studentId],
    queryFn: () => api.getAdaptiveLearning(studentId),
  });

  const assignmentsQuery = useQuery({
    queryKey: ["b13-student-assignments", studentId],
    queryFn: () => api.listStudentResourceAssignments!(studentId),
  });

  const activeResourcesQuery = useQuery({
    queryKey: ["b13-active-resources-mock"],
    queryFn: () => api.listCurriculumResources!({ status: "ACTIVE" }),
  });

  const assignMutation = useMutation({
    mutationFn: () =>
      api.assignStudentResource!(studentId, {
        resource_id: selectedResourceId,
        learning_recommendation_id: selectedRecommendationId || null,
      }),
    onSuccess: () => {
      setSelectedResourceId("");
      setSelectedRecommendationId("");
      void queryClient.invalidateQueries({
        queryKey: ["b13-student-assignments", studentId],
      });
    },
  });

  const cancelMutation = useMutation({
    mutationFn: (assignmentId: string) =>
      api.cancelStudentResourceAssignment!(assignmentId),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: ["b13-student-assignments", studentId],
      });
    },
  });

  const reassessmentsQuery = useQuery({
    queryKey: ["b14-reassessments-mock", studentId],
    queryFn: async () => {
      if (studentId !== DEMO_STUDENT_ID) return [] as Reassessment[];
      const rows = await Promise.all([
        api.getReassessment(REASSESSMENT_ID),
        api.getReassessment(REASSESSMENT_ID_CREATED),
      ]);
      return rows;
    },
  });

  const assignedIds = useMemo(
    () =>
      new Set(
        (assignmentsQuery.data?.items ?? [])
          .filter((a) => a.status === "ASSIGNED")
          .map((a) => a.resource_id),
      ),
    [assignmentsQuery.data],
  );

  const assignableResources = (activeResourcesQuery.data?.items ?? []).filter(
    (r) => !assignedIds.has(r.id),
  );

  if (isLoading) return <LoadingState />;
  if (isError || !data) return <ErrorState onRetry={() => void refetch()} />;

  return (
    <div data-testid="adaptive-learning-page" data-learning-mode="mock">
      <PageHeader
        title="Adaptive learning"
        description={`Priority topics and sequenced path for ${data.student.display_name}`}
        breadcrumbs={[
          { label: "Learning" },
          { label: data.student.external_ref },
        ]}
        actions={
          <div className="flex flex-wrap gap-2">
            <Link
              href="/learning/resources"
              data-testid="b13-resources-catalog-link"
              className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-800 hover:bg-slate-50"
            >
              Resource catalog
            </Link>
            <Link
              href={`/learning/${studentId}/improvement-assessment`}
              data-testid="improvement-assessment-link"
              className="rounded-md bg-teal-800 px-3 py-2 text-sm font-medium text-white hover:bg-teal-900"
            >
              Improvement assessment
            </Link>
          </div>
        }
      />

      <p
        data-testid="curriculum-restriction-notice"
        className="mb-4 rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700"
      >
        Recommendations restricted to student&apos;s curriculum.
      </p>

      <section className="grid gap-3 lg:grid-cols-3">
        {data.priorities.map((topic) => (
          <TopicPriorityCard key={topic.id} topic={topic} />
        ))}
      </section>

      <AssignResourcePanel
        resources={assignableResources}
        selectedResourceId={selectedResourceId}
        selectedRecommendationId={selectedRecommendationId}
        onSelectResource={setSelectedResourceId}
        onSelectRecommendation={setSelectedRecommendationId}
        onAssign={() => assignMutation.mutate()}
        assigning={assignMutation.isPending}
        errorMessage={
          assignMutation.error
            ? isApiError(assignMutation.error)
              ? assignMutation.error.message
              : "Failed to assign resource"
            : null
        }
      />

      <AssignedResourcesSection
        assignments={assignmentsQuery.data?.items ?? []}
        loading={assignmentsQuery.isLoading}
        error={assignmentsQuery.isError}
        onRetry={() => void assignmentsQuery.refetch()}
        onCancel={(id) => cancelMutation.mutate(id)}
        cancelPending={cancelMutation.isPending}
      />

      <ReassessmentsSection
        reassessments={reassessmentsQuery.data ?? []}
        loading={reassessmentsQuery.isLoading}
        error={reassessmentsQuery.isError}
        onRetry={() => void reassessmentsQuery.refetch()}
      />

      <div className="mt-6 grid gap-6 lg:grid-cols-[1.2fr_0.8fr]">
        <section>
          <h2 className="mb-3 text-sm font-semibold text-slate-800">
            Learning path
          </h2>
          <ol className="space-y-2">
            {data.path.map((step, index) => (
              <LearningPathStep key={step.id} step={step} index={index} />
            ))}
          </ol>
        </section>
        <section className="rounded-md border border-slate-200 bg-white p-4">
          <h2 className="mb-3 text-sm font-semibold text-slate-800">
            Error distribution
          </h2>
          <ErrorDistribution items={data.error_distribution} />
        </section>
      </div>
    </div>
  );
}

export default function AdaptiveLearningPage({
  params,
}: {
  params: Promise<{ studentId: string }>;
}) {
  const { studentId } = use(params);
  const live = getApiCapabilities().learning === "live";
  return live ? (
    <Suspense fallback={<LoadingState />}>
      <LiveAdaptiveLearningPage studentId={studentId} />
    </Suspense>
  ) : (
    <MockAdaptiveLearningPage studentId={studentId} />
  );
}
