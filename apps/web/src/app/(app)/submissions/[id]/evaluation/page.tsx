"use client";

import { use, useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, isApiError } from "@/lib/api";
import { getApiCapabilities } from "@/lib/api/capabilities";
import { PageHeader } from "@/components/layout/PageHeader";
import { PaperViewerShell } from "@/components/paper/PaperViewerShell";
import { QuestionTree } from "@/components/evaluation/QuestionTree";
import { EvaluationDecisionPanel } from "@/components/evaluation/EvaluationDecisionPanel";
import { ErrorState, LoadingState } from "@/components/ui/FeedbackStates";
import type { TeacherReviewAction } from "@/lib/types/enums";
import type { EvaluationWorkflowState } from "@/lib/types/enums";
import type { Question } from "@/lib/types/domain";
import {
  canApproveEvaluation,
  countFinalizedQuestions,
} from "@/lib/helpers/teacher-actions";

const LIVE_UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

function isLiveUuid(id: string): boolean {
  return LIVE_UUID_RE.test(id) && !id.toLowerCase().includes("demo");
}

function findQuestion(
  nodes: Question[],
  id: string,
): Question | undefined {
  for (const node of nodes) {
    if (node.id === id || node.question_version_id === id) return node;
    if (node.children) {
      const found = findQuestion(node.children, id);
      if (found) return found;
    }
  }
  return undefined;
}

export default function EvaluationWorkspacePage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const evaluationLive = getApiCapabilities().evaluation === "live";
  const liveMode = evaluationLive && isLiveUuid(id);
  const queryClient = useQueryClient();
  const [activePageId, setActivePageId] = useState<string | null>(null);
  const [selectedRegionId, setSelectedRegionId] = useState<string | null>(null);
  const [selectedQuestionId, setSelectedQuestionId] = useState<string | null>(
    null,
  );
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [gateReady, setGateReady] = useState(!liveMode);

  const submissionQuery = useQuery({
    queryKey: ["submission", id],
    queryFn: () => api.getSubmission(id),
    enabled: liveMode,
  });

  const prepareMutation = useMutation({
    mutationFn: () => api.prepareEvaluation!(id),
    onSuccess: async () => {
      setGateReady(true);
      await queryClient.invalidateQueries({ queryKey: ["submission", id] });
    },
    onError: () => {
      // Already past prepare (e.g. EVALUATION_REVIEW) — still load workspace.
      setGateReady(true);
    },
  });

  useEffect(() => {
    if (!liveMode || gateReady || prepareMutation.isPending) return;
    const state = submissionQuery.data?.workflow_state;
    if (!state) return;
    if (state === "READY_FOR_EVALUATION") {
      prepareMutation.mutate();
      return;
    }
    if (
      state === "EVALUATING" ||
      state === "EVALUATION_REVIEW" ||
      state === "APPROVED" ||
      state === "PUBLISHED"
    ) {
      setGateReady(true);
    }
  }, [liveMode, gateReady, prepareMutation, submissionQuery.data?.workflow_state]);

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["evaluation", id, selectedQuestionId],
    queryFn: () =>
      api.getEvaluationWorkspace(id, selectedQuestionId ?? undefined),
    enabled: !liveMode || gateReady,
    refetchInterval: (query) => {
      const ws = query.state.data?.submission.workflow_state;
      if (ws === "EVALUATING") return 2000;
      const runPending =
        (query.state.data?.ledgers.length ?? 0) > 0 &&
        query.state.data?.ledgers.every((l) => l.workflow_state === "PENDING");
      if (runPending) return 2000;
      return false;
    },
  });

  useEffect(() => {
    if (!data) return;
    const qid = selectedQuestionId ?? data.selected_question_id;
    if (!selectedQuestionId && data.selected_question_id) {
      setSelectedQuestionId(data.selected_question_id);
    }
    const region =
      data.regions.find((r) => r.question_id === qid) ?? data.regions[0];
    if (region) {
      setSelectedRegionId((prev) => prev ?? region.id);
      setActivePageId((prev) => prev ?? region.page_id);
    } else if (data.pages[0]) {
      setActivePageId((prev) => prev ?? data.pages[0]!.id);
    }
  }, [data, selectedQuestionId]);

  const questionId =
    selectedQuestionId ?? data?.selected_question_id ?? "";

  const ledger = useMemo(
    () => data?.ledgers.find((l) => l.question_id === questionId),
    [data, questionId],
  );

  const statusByQuestionId = useMemo(() => {
    const map: Record<string, EvaluationWorkflowState> = {};
    data?.ledgers.forEach((l) => {
      map[l.question_id] = l.workflow_state;
    });
    return map;
  }, [data]);

  const progress = useMemo(() => {
    const states = data?.ledgers.map((l) => l.workflow_state) ?? [];
    return countFinalizedQuestions(states);
  }, [data]);

  const canFinalize = useMemo(() => {
    const states = data?.ledgers.map((l) => l.workflow_state) ?? [];
    return (
      canApproveEvaluation(states) &&
      data?.submission.workflow_state === "EVALUATION_REVIEW"
    );
  }, [data]);

  const approved =
    data?.submission.workflow_state === "APPROVED" ||
    data?.submission.workflow_state === "PUBLISHED";

  const published = data?.submission.workflow_state === "PUBLISHED";

  const actionMutation = useMutation({
    mutationFn: ({
      action,
      payload,
    }: {
      action: TeacherReviewAction;
      payload?: { newScore?: number; feedback?: string };
    }) => api.applyTeacherAction(id, ledger?.id ?? "", action, payload),
    onSuccess: (result) => {
      setActionError(null);
      setActionMessage(result.message);
      void queryClient.invalidateQueries({ queryKey: ["evaluation", id] });
      void queryClient.invalidateQueries({ queryKey: ["submission", id] });
    },
    onError: (err) => {
      setActionMessage(null);
      setActionError(
        isApiError(err) ? err.message : "Teacher action failed.",
      );
    },
  });

  const finalizeMutation = useMutation({
    mutationFn: () => api.finalizeEvaluation!(id),
    onSuccess: async () => {
      setActionError(null);
      setActionMessage("Evaluation approved.");
      await queryClient.invalidateQueries({ queryKey: ["evaluation", id] });
      await queryClient.invalidateQueries({ queryKey: ["submission", id] });
    },
    onError: (err) => {
      setActionError(
        isApiError(err) ? err.message : "Finalize evaluation failed.",
      );
    },
  });

  if (liveMode && (!gateReady || prepareMutation.isPending) && !data) {
    return <LoadingState />;
  }

  const relatedRegions =
    data?.regions.filter(
      (r) =>
        r.question_id === questionId ||
        r.question_id === questionId.split("-").slice(0, 2).join("-"),
    ) ?? [];

  const answerKey =
    data?.answer_keys.filter((a) => a.question_id === questionId) ?? [];
  const rubric =
    data?.rubrics.filter((r) => r.question_id === questionId) ?? [];

  if (isLoading && !data) return <LoadingState />;
  if ((isError || !data) && !ledger) {
    return (
      <ErrorState
        message={
          isApiError(error)
            ? error.message
            : isApiError(prepareMutation.error)
              ? prepareMutation.error.message
              : undefined
        }
        onRetry={() => {
          setGateReady(false);
          void submissionQuery.refetch();
          void refetch();
        }}
      />
    );
  }
  if (!data || !ledger) {
    return (
      <ErrorState
        title="Evaluation not ready"
        message="No question evaluation ledger rows yet. Wait for the evaluation run to finish."
        onRetry={() => void refetch()}
      />
    );
  }

  const question = findQuestion(data.questions, questionId);
  const pageId = activePageId ?? data.pages[0]?.id ?? "";

  return (
    <div
      data-testid="evaluation-workspace-page"
      data-evaluation-mode={liveMode ? "live" : "mock"}
      className="-m-2 sm:-m-3"
    >
      <div className="px-2 sm:px-3 pt-2">
        <PageHeader
          title="Evaluation workspace"
          description={`${data.assessment.title} · ${data.student?.display_name ?? "Unresolved student"}`}
          breadcrumbs={[
            { label: "Submissions", href: "/submissions" },
            { label: id, href: `/submissions/${id}` },
            { label: "Evaluation" },
          ]}
          actions={
            liveMode ? (
              <div className="flex flex-col items-end gap-2">
                <p
                  data-testid="evaluation-progress"
                  className="text-sm text-slate-600"
                >
                  {progress.finalized} of {progress.total} questions finalized
                </p>
                {canFinalize && (
                  <button
                    type="button"
                    data-testid="approve-evaluation"
                    disabled={finalizeMutation.isPending}
                    onClick={() => finalizeMutation.mutate()}
                    className="rounded-md bg-teal-800 px-3 py-2 text-sm font-medium text-white hover:bg-teal-900 disabled:opacity-50"
                  >
                    Approve evaluation
                  </button>
                )}
              </div>
            ) : undefined
          }
        />
      </div>

      {approved && (
        <p
          data-testid="evaluation-approved-boundary"
          className="mx-2 mb-3 rounded-md border border-teal-200 bg-teal-50 px-3 py-2 text-sm text-teal-950 sm:mx-3"
        >
          {getApiCapabilities().publication === "live" ? (
            <>
              Evaluation approved.{" "}
              <a
                href={`/submissions/${id}/publication`}
                data-testid="link-publication-from-evaluation"
                className="font-medium underline"
              >
                Open publication
              </a>{" "}
              to generate and publish results.
            </>
          ) : (
            <>Evaluation approved. Result publication and reports are not live yet.</>
          )}
        </p>
      )}

      {liveMode && approved && getApiCapabilities().publication !== "live" && (
        <p
          data-testid="evaluation-downstream-mock-boundary"
          className="mx-2 mb-3 rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-600 sm:mx-3"
        >
          Reports, analytics, and adaptive learning remain mock and are not
          linked for this live submission.
        </p>
      )}

      {liveMode && approved && getApiCapabilities().publication === "live" && (
        <p
          data-testid="evaluation-downstream-mock-boundary"
          className="mx-2 mb-3 rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-600 sm:mx-3"
        >
          Analytics and adaptive learning remain mock and are not linked for
          this live submission.
        </p>
      )}

      <div
        data-testid="evaluation-3col"
        className="grid min-h-[70vh] gap-3 xl:grid-cols-[minmax(280px,1.1fr)_minmax(280px,1fr)_minmax(300px,1fr)]"
      >
        <div className="min-h-[480px] px-2 sm:px-3">
          <PaperViewerShell
            pages={data.pages}
            regions={
              relatedRegions.length > 0 ? relatedRegions : data.regions
            }
            activePageId={pageId}
            selectedRegionId={selectedRegionId}
            onPageSelect={setActivePageId}
            onRegionSelect={setSelectedRegionId}
          />
        </div>

        <div className="flex min-h-[480px] flex-col gap-3 overflow-y-auto rounded-md border border-slate-200 bg-white p-4">
          <div>
            <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">
              Questions
            </h2>
            <div className="mt-2">
              <QuestionTree
                questions={data.questions}
                selectedId={questionId}
                onSelect={(qid) => {
                  setSelectedQuestionId(qid);
                  const region = data.regions.find((r) => r.question_id === qid);
                  if (region) {
                    setSelectedRegionId(region.id);
                    setActivePageId(region.page_id);
                  }
                }}
                statusByQuestionId={statusByQuestionId}
              />
            </div>
          </div>

          <div className="border-t border-slate-100 pt-3">
            <h2 className="text-sm font-semibold text-slate-800">
              {question?.code ?? "Question"} · prompt
            </h2>
            <p className="mt-1 text-sm text-slate-700">
              {question?.prompt ?? "—"}
            </p>
          </div>

          <div className="border-t border-slate-100 pt-3">
            <h2 className="text-sm font-semibold text-slate-800">
              Transcription
            </h2>
            <p
              data-testid="evaluation-transcription"
              className="mt-1 whitespace-pre-wrap text-sm text-slate-700"
            >
              {ledger.transcription_text || "—"}
            </p>
          </div>

          <div className="border-t border-slate-100 pt-3">
            <h2 className="text-sm font-semibold text-slate-800">Answer key</h2>
            <ul className="mt-2 space-y-2">
              {answerKey.length === 0 && (
                <li className="text-sm text-slate-500">No key steps for this node.</li>
              )}
              {answerKey.map((step) => (
                <li
                  key={step.id}
                  className="rounded-md bg-slate-50 px-3 py-2 text-sm text-slate-700"
                >
                  <span className="font-medium">Step {step.step_index + 1}:</span>{" "}
                  {step.content}
                </li>
              ))}
            </ul>
          </div>

          <div className="border-t border-slate-100 pt-3">
            <h2 className="text-sm font-semibold text-slate-800">Rubric</h2>
            <ul className="mt-2 space-y-2">
              {rubric.length === 0 && (
                <li className="text-sm text-slate-500">
                  See parent question criteria or ledger breakdown.
                </li>
              )}
              {rubric.map((c) => (
                <li key={c.id} className="text-sm text-slate-700">
                  <span className="font-medium">{c.label}</span> ({c.max_marks}m) —{" "}
                  {c.description}
                </li>
              ))}
            </ul>
          </div>

          <div className="border-t border-slate-100 pt-3">
            <h2 className="text-sm font-semibold text-slate-800">
              Curriculum links
            </h2>
            <p className="mt-1 text-sm text-slate-600">
              {(question?.curriculum_node_ids ?? []).join(", ") || "—"}
            </p>
          </div>

          <div className="border-t border-slate-100 pt-3">
            <h2 className="text-sm font-semibold text-slate-800">
              Evaluation method
            </h2>
            <p
              data-testid="evaluation-method"
              className="mt-1 text-sm text-slate-600"
            >
              Rubric-aligned scoring with optional deterministic math
              verification. AI proposals require teacher confirmation; human
              final scores are authoritative.
            </p>
          </div>

          {actionMessage && (
            <p
              data-testid="teacher-action-result"
              className="rounded-md bg-teal-50 px-3 py-2 text-sm text-teal-900 ring-1 ring-teal-200"
            >
              {actionMessage}
            </p>
          )}
          {actionError && (
            <p
              data-testid="teacher-action-error"
              className="rounded-md bg-rose-50 px-3 py-2 text-sm text-rose-900 ring-1 ring-rose-200"
            >
              {actionError}
            </p>
          )}
        </div>

        <div className="min-h-[480px] rounded-md border border-slate-200 bg-white p-4">
          <EvaluationDecisionPanel
            ledger={ledger}
            liveMode={liveMode}
            disabled={published}
            onAction={(action, payload) =>
              actionMutation.mutate({ action, payload })
            }
          />
          {published && (
            <p
              data-testid="evaluation-published-locked"
              className="mt-3 rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-600"
            >
              Published results are immutable — teacher review actions are
              disabled.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
