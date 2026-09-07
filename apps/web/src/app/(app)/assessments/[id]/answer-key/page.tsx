"use client";

import { use, useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { getApiCapabilities } from "@/lib/api/capabilities";
import { isApiError } from "@/lib/api/http/errors";
import { PageHeader } from "@/components/layout/PageHeader";
import { ErrorState, LoadingState } from "@/components/ui/FeedbackStates";
import type { Question } from "@/lib/types/domain";

function isActiveRunStatus(status: string | undefined): boolean {
  return status === "QUEUED" || status === "RUNNING";
}

function leafQuestions(nodes: Question[]): Question[] {
  return nodes.flatMap((node) => {
    if (node.is_leaf_scorable || !node.children?.length) {
      return [node];
    }
    return leafQuestions(node.children);
  });
}

function provenanceLabel(sourceType: string | undefined): string {
  if (sourceType === "AI_PROPOSED") {
    return "AI proposal — teacher approval required";
  }
  if (sourceType === "TEACHER") return "Teacher";
  if (sourceType === "IMPORTED") return "Imported";
  return sourceType ?? "Unknown";
}

function LiveAnswerKeyPage({ id }: { id: string }) {
  const queryClient = useQueryClient();
  const [activeRunId, setActiveRunId] = useState<string | null>(null);
  const [draftAnswers, setDraftAnswers] = useState<Record<string, string>>({});
  const [actionError, setActionError] = useState<string | null>(null);

  const assessmentQuery = useQuery({
    queryKey: ["assessment", id],
    queryFn: () => api.getAssessment(id),
  });
  const versionQuery = useQuery({
    queryKey: ["assessment-version", id],
    queryFn: () => api.getLatestAssessmentVersion!(id),
  });
  const questionsQuery = useQuery({
    queryKey: ["assessment-questions", id],
    queryFn: () => api.getAssessmentQuestions(id),
  });
  const answerKeyQuery = useQuery({
    queryKey: ["assessment-answer-key", id],
    queryFn: () => api.getAssessmentAnswerKey(id),
  });

  const runQuery = useQuery({
    queryKey: ["authoring-ai-run", activeRunId],
    queryFn: () => api.getAuthoringAiRun!(activeRunId!),
    enabled: Boolean(activeRunId),
    refetchInterval: (q) =>
      isActiveRunStatus(q.state.data?.status) ? 2000 : false,
  });

  useEffect(() => {
    const status = runQuery.data?.status;
    if (
      status === "REVIEW_REQUIRED" ||
      status === "SUCCEEDED" ||
      status === "FAILED" ||
      status === "UNAVAILABLE"
    ) {
      void queryClient.invalidateQueries({
        queryKey: ["assessment-answer-key", id],
      });
      void queryClient.invalidateQueries({ queryKey: ["assessment", id] });
      setActiveRunId(null);
    }
  }, [runQuery.data?.status, queryClient, id]);

  const leaves = useMemo(
    () => leafQuestions(questionsQuery.data ?? []),
    [questionsQuery.data],
  );

  const createMutation = useMutation({
    mutationFn: (questionVersionId: string) =>
      api.createTeacherAnswerKey!({
        assessmentId: id,
        assessmentVersionId: versionQuery.data!.id,
        questionVersionId,
        answerText: draftAnswers[questionVersionId] ?? "",
      }),
    onSuccess: async () => {
      setActionError(null);
      await queryClient.invalidateQueries({
        queryKey: ["assessment-answer-key", id],
      });
    },
    onError: (err) => {
      setActionError(isApiError(err) ? err.message : "Create failed");
    },
  });

  const proposeMutation = useMutation({
    mutationFn: (questionVersionId: string) =>
      api.prepareAiAnswerKeyProposal!({
        questionVersionId,
        assessmentVersionId: versionQuery.data!.id,
      }),
    onSuccess: async (run) => {
      setActionError(null);
      if (run.status === "QUEUED" || run.status === "RUNNING") {
        setActiveRunId(run.id);
        return;
      }
      await queryClient.invalidateQueries({
        queryKey: ["assessment-answer-key", id],
      });
      await queryClient.invalidateQueries({ queryKey: ["assessment", id] });
    },
    onError: (err) => {
      setActionError(isApiError(err) ? err.message : "AI proposal failed");
    },
  });

  const approveMutation = useMutation({
    mutationFn: (answerKeyVersionId: string) =>
      api.approveAnswerKey!(answerKeyVersionId),
    onSuccess: async () => {
      setActionError(null);
      await queryClient.invalidateQueries({
        queryKey: ["assessment-answer-key", id],
      });
      await queryClient.invalidateQueries({ queryKey: ["assessment", id] });
    },
    onError: (err) => {
      setActionError(isApiError(err) ? err.message : "Approve failed");
    },
  });

  if (
    assessmentQuery.isLoading ||
    answerKeyQuery.isLoading ||
    questionsQuery.isLoading ||
    versionQuery.isLoading
  ) {
    return <LoadingState />;
  }
  if (
    assessmentQuery.isError ||
    answerKeyQuery.isError ||
    questionsQuery.isError ||
    versionQuery.isError ||
    !assessmentQuery.data ||
    !answerKeyQuery.data ||
    !questionsQuery.data ||
    !versionQuery.data
  ) {
    return <ErrorState onRetry={() => void answerKeyQuery.refetch()} />;
  }

  const editable =
    assessmentQuery.data.workflow_state === "DRAFT" ||
    assessmentQuery.data.workflow_state === "RUBRIC_REVIEW";
  const byQuestion = new Map(
    answerKeyQuery.data.map((step) => [step.question_id, step]),
  );
  const generating = isActiveRunStatus(runQuery.data?.status);

  return (
    <div data-testid="assessment-answer-key-page" data-authoring-mode="live">
      <PageHeader
        title="Answer key"
        description={assessmentQuery.data.title}
        breadcrumbs={[
          { label: "Assessments", href: "/assessments" },
          {
            label: assessmentQuery.data.code,
            href: `/assessments/${id}`,
          },
          { label: "Answer key" },
        ]}
      />

      <p
        data-testid="answer-key-truth-notice"
        className="mb-4 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900"
      >
        AI proposals are not approved until a teacher explicitly approves them.
      </p>

      {actionError && (
        <p data-testid="answer-key-error" className="mb-3 text-sm text-red-700">
          {actionError}
        </p>
      )}

      {generating && (
        <p
          data-testid="answer-key-run-status"
          className="mb-3 text-sm text-slate-600"
        >
          AI run status: {runQuery.data?.status}
        </p>
      )}

      <ul className="space-y-3">
        {leaves.map((question) => {
          const step = byQuestion.get(question.id);
          const status = step?.status;
          const source = step?.source_type;
          const needsApproval =
            source === "AI_PROPOSED" && status === "REVIEW_REQUIRED";
          return (
            <li
              key={question.id}
              data-testid={`answer-key-step-${step?.id ?? question.id}`}
              className="rounded-md border border-slate-200 bg-white p-4"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0 flex-1">
                  <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                    {question.code} · {question.max_mark} marks
                  </div>
                  <p className="mt-1 text-sm text-slate-700">{question.prompt}</p>
                  {step ? (
                    <>
                      <p
                        data-testid={`answer-key-provenance-${question.id}`}
                        className="mt-2 text-xs font-medium text-slate-600"
                      >
                        Provenance: {provenanceLabel(source)}
                      </p>
                      <p
                        data-testid={`answer-key-status-${question.id}`}
                        className="mt-1 text-xs text-slate-500"
                      >
                        Status: {status}
                      </p>
                      <p className="mt-2 text-sm text-slate-800">{step.content}</p>
                    </>
                  ) : editable ? (
                    <textarea
                      data-testid={`answer-key-draft-${question.id}`}
                      className="mt-2 w-full rounded border border-slate-300 px-2 py-1 text-sm"
                      rows={3}
                      placeholder="Teacher answer"
                      value={draftAnswers[question.id] ?? ""}
                      onChange={(e) =>
                        setDraftAnswers((prev) => ({
                          ...prev,
                          [question.id]: e.target.value,
                        }))
                      }
                    />
                  ) : (
                    <p className="mt-2 text-sm text-slate-500">No answer key</p>
                  )}
                </div>
              </div>
              {editable && (
                <div className="mt-3 flex flex-wrap gap-2">
                  {!step && (
                    <button
                      type="button"
                      data-testid={`add-teacher-answer-${question.id}`}
                      className="rounded-md border border-slate-300 px-3 py-1.5 text-sm hover:bg-slate-50"
                      disabled={
                        createMutation.isPending ||
                        !(draftAnswers[question.id] ?? "").trim()
                      }
                      onClick={() => createMutation.mutate(question.id)}
                    >
                      Add teacher answer
                    </button>
                  )}
                  {!step && (
                    <button
                      type="button"
                      data-testid={`generate-ai-answer-${question.id}`}
                      className="rounded-md bg-teal-800 px-3 py-1.5 text-sm font-medium text-white hover:bg-teal-900 disabled:opacity-50"
                      disabled={proposeMutation.isPending || generating}
                      onClick={() => proposeMutation.mutate(question.id)}
                    >
                      Generate AI proposal
                    </button>
                  )}
                  {needsApproval && step && (
                    <button
                      type="button"
                      data-testid={`approve-answer-key-${question.id}`}
                      className="rounded-md bg-teal-800 px-3 py-1.5 text-sm font-medium text-white hover:bg-teal-900"
                      disabled={approveMutation.isPending}
                      onClick={() => approveMutation.mutate(step.id)}
                    >
                      Approve AI proposal
                    </button>
                  )}
                </div>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function MockAnswerKeyPage({ id }: { id: string }) {
  const assessmentQuery = useQuery({
    queryKey: ["assessment", id],
    queryFn: () => api.getAssessment(id),
  });
  const answerKeyQuery = useQuery({
    queryKey: ["assessment-answer-key", id],
    queryFn: () => api.getAssessmentAnswerKey(id),
  });

  if (assessmentQuery.isLoading || answerKeyQuery.isLoading)
    return <LoadingState />;
  if (
    assessmentQuery.isError ||
    answerKeyQuery.isError ||
    !assessmentQuery.data ||
    !answerKeyQuery.data
  ) {
    return <ErrorState onRetry={() => void answerKeyQuery.refetch()} />;
  }

  return (
    <div data-testid="assessment-answer-key-page" data-authoring-mode="mock">
      <PageHeader
        title="Answer key"
        description={assessmentQuery.data.title}
        breadcrumbs={[
          { label: "Assessments", href: "/assessments" },
          { label: assessmentQuery.data.code, href: `/assessments/${id}` },
          { label: "Answer key" },
        ]}
      />
      <ul className="space-y-3">
        {answerKeyQuery.data.map((step) => (
          <li
            key={step.id}
            data-testid={`answer-key-step-${step.id}`}
            className="rounded-md border border-slate-200 bg-white p-4"
          >
            <div className="flex items-start justify-between gap-3">
              <div>
                <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                  {step.question_id} · Step {step.step_index + 1}
                </div>
                <p className="mt-1 text-sm text-slate-800">{step.content}</p>
              </div>
              <div className="text-sm font-semibold tabular-nums text-slate-900">
                {step.marks} marks
              </div>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

export default function AssessmentAnswerKeyPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const live = getApiCapabilities().assessments === "live";
  return live ? <LiveAnswerKeyPage id={id} /> : <MockAnswerKeyPage id={id} />;
}
