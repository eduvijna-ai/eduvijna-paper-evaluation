"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { A1_PERMISSIONS } from "@/lib/api/a1-types";
import { api, isApiError } from "@/lib/api";
import { getSession, hasPermission } from "@/lib/auth/session";
import { PageHeader } from "@/components/layout/PageHeader";
import { ErrorState, LoadingState } from "@/components/ui/FeedbackStates";

function actionErrorMessage(error: unknown): string {
  if (isApiError(error)) return error.message;
  if (error && typeof error === "object" && "message" in error) {
    return String((error as { message: unknown }).message);
  }
  return "Request failed";
}

export default function ClusteringPage() {
  const queryClient = useQueryClient();
  const session = getSession();
  const canManage = hasPermission(session, A1_PERMISSIONS.clusteringManage);
  const canReview = hasPermission(session, A1_PERMISSIONS.clusteringReview);
  const [versionId, setVersionId] = useState("assess-ver-demo-001");
  const [questionId, setQuestionId] = useState("q-demo-001");
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [selectedClusterId, setSelectedClusterId] = useState<string | null>(null);
  const [observation, setObservation] = useState(
    "Students omit the constant factor after differentiation.",
  );
  const [formError, setFormError] = useState<string | null>(null);

  const runsQuery = useQuery({
    queryKey: ["b18-cluster-runs", versionId, questionId],
    queryFn: () =>
      api.listAnswerClusterRuns!(
        versionId || undefined,
        questionId || undefined,
      ),
  });

  const runs = runsQuery.data?.items ?? [];
  const activeRunId = selectedRunId ?? runs[0]?.id ?? null;

  const clustersQuery = useQuery({
    queryKey: ["b18-cluster-list", activeRunId],
    queryFn: () => api.listAnswerClusters!(activeRunId!),
    enabled: Boolean(activeRunId),
  });

  const clusters = clustersQuery.data?.items ?? [];
  const activeClusterId = selectedClusterId ?? clusters[0]?.id ?? null;

  const clusterDetailQuery = useQuery({
    queryKey: ["b18-cluster-detail", activeClusterId],
    queryFn: () => api.getAnswerCluster!(activeClusterId!),
    enabled: Boolean(activeClusterId),
  });

  const createMutation = useMutation({
    mutationFn: () =>
      api.createAnswerClusterRun!({
        assessment_version_id: versionId,
        question_id: questionId,
      }),
    onSuccess: (run) => {
      setFormError(null);
      setSelectedRunId(run.id);
      void queryClient.invalidateQueries({ queryKey: ["b18-cluster-runs"] });
    },
    onError: (err) => setFormError(actionErrorMessage(err)),
  });

  const reviewMutation = useMutation({
    mutationFn: () =>
      api.submitAnswerClusterReview!(activeClusterId!, {
        observation,
      }),
    onSuccess: () => {
      setFormError(null);
      void queryClient.invalidateQueries({
        queryKey: ["b18-cluster-detail", activeClusterId],
      });
    },
    onError: (err) => setFormError(actionErrorMessage(err)),
  });

  if (runsQuery.isLoading) {
    return <LoadingState label="Loading answer clusters…" />;
  }
  if (runsQuery.isError) {
    return <ErrorState message={actionErrorMessage(runsQuery.error)} />;
  }

  return (
    <div className="space-y-6" data-testid="b18-clustering-workspace">
      <PageHeader
        title="Answer clustering"
        description="Semantic grouping of student responses for rubric QA (PEV-050)."
      />

      <section className="flex flex-wrap items-end gap-3">
        <label className="flex flex-col gap-1 text-sm">
          Assessment version ID
          <input
            data-testid="b18-cluster-version-input"
            className="rounded border px-2 py-1"
            value={versionId}
            onChange={(e) => setVersionId(e.target.value)}
          />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          Question ID
          <input
            data-testid="b18-cluster-question-input"
            className="rounded border px-2 py-1"
            value={questionId}
            onChange={(e) => setQuestionId(e.target.value)}
          />
        </label>
        {canManage ? (
          <button
            type="button"
            data-testid="b18-cluster-run"
            className="rounded bg-slate-900 px-3 py-2 text-sm text-white"
            onClick={() => createMutation.mutate()}
            disabled={createMutation.isPending || !versionId || !questionId}
          >
            Run clustering
          </button>
        ) : null}
      </section>
      {formError ? (
        <p className="text-sm text-red-700" data-testid="b18-cluster-error">
          {formError}
        </p>
      ) : null}

      <section data-testid="b18-cluster-run-list" className="space-y-2">
        <h2 className="text-lg font-medium">Runs</h2>
        {runs.length === 0 ? (
          <p className="text-sm text-slate-600">No cluster runs yet.</p>
        ) : (
          <ul className="divide-y rounded border">
            {runs.map((run) => (
              <li key={run.id}>
                <button
                  type="button"
                  data-testid="b18-cluster-run-row"
                  className={`flex w-full items-center justify-between px-3 py-2 text-left text-sm ${
                    activeRunId === run.id ? "bg-slate-100" : ""
                  }`}
                  onClick={() => {
                    setSelectedRunId(run.id);
                    setSelectedClusterId(null);
                  }}
                >
                  <span>{run.id.slice(0, 16)}…</span>
                  <span data-testid="b18-cluster-run-status">{run.status}</span>
                  <span>clusters={run.cluster_count}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>

      {activeRunId ? (
        <section data-testid="b18-cluster-list" className="space-y-2">
          <h2 className="text-lg font-medium">Clusters</h2>
          {clustersQuery.isLoading ? (
            <LoadingState label="Loading clusters…" />
          ) : clusters.length === 0 ? (
            <p className="text-sm text-slate-600">No clusters in this run.</p>
          ) : (
            <ul className="divide-y rounded border">
              {clusters.map((cluster) => (
                <li key={cluster.id}>
                  <button
                    type="button"
                    data-testid="b18-cluster-row"
                    className={`flex w-full justify-between px-3 py-2 text-left text-sm ${
                      activeClusterId === cluster.id ? "bg-slate-100" : ""
                    }`}
                    onClick={() => setSelectedClusterId(cluster.id)}
                  >
                    <span>{cluster.label ?? `Cluster ${cluster.cluster_index}`}</span>
                    <span data-testid="b18-cluster-member-count">
                      n={cluster.member_count}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>
      ) : null}

      {activeClusterId && clusterDetailQuery.data ? (
        <section data-testid="b18-cluster-detail" className="space-y-3">
          <h2 className="text-lg font-medium">Cluster detail</h2>
          <div data-testid="b18-cluster-members" className="space-y-1">
            {clusterDetailQuery.data.members.map((member) => (
              <div
                key={member.id}
                data-testid="b18-cluster-member-row"
                className="rounded border px-3 py-2 text-sm"
              >
                <p className="font-medium">
                  Score: {member.final_human_approved_score ?? "—"}
                </p>
                <p className="text-slate-600">
                  {member.transcription_text ?? "No transcription"}
                </p>
              </div>
            ))}
          </div>
          {canReview ? (
            <div data-testid="b18-cluster-review" className="space-y-2">
              <textarea
                data-testid="b18-cluster-observation-input"
                className="w-full rounded border px-2 py-1 text-sm"
                rows={3}
                value={observation}
                onChange={(e) => setObservation(e.target.value)}
              />
              <button
                type="button"
                data-testid="b18-cluster-review-submit"
                className="rounded bg-slate-900 px-3 py-1 text-sm text-white"
                onClick={() => reviewMutation.mutate()}
                disabled={reviewMutation.isPending || !observation.trim()}
              >
                Submit advisory review
              </button>
            </div>
          ) : null}
          {(clusterDetailQuery.data.reviews ?? []).length > 0 ? (
            <ul data-testid="b18-cluster-reviews" className="text-sm">
              {clusterDetailQuery.data.reviews.map((review) => (
                <li key={review.id} data-testid="b18-cluster-review-row">
                  {review.observation}
                </li>
              ))}
            </ul>
          ) : null}
        </section>
      ) : null}
    </div>
  );
}
