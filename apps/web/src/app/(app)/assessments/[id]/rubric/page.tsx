"use client";

import { use, useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { getApiCapabilities } from "@/lib/api/capabilities";
import { isApiError } from "@/lib/api/http/errors";
import { PageHeader } from "@/components/layout/PageHeader";
import { ErrorState, LoadingState } from "@/components/ui/FeedbackStates";
import type { Question, RubricCriterion } from "@/lib/types/domain";

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

function groupCriteria(criteria: RubricCriterion[]) {
  const map = new Map<string, RubricCriterion[]>();
  for (const row of criteria) {
    const list = map.get(row.question_id) ?? [];
    list.push(row);
    map.set(row.question_id, list);
  }
  return map;
}

function LiveRubricPage({ id }: { id: string }) {
  const queryClient = useQueryClient();
  const [activeRunId, setActiveRunId] = useState<string | null>(null);
  const [draftRubrics, setDraftRubrics] = useState<
    Record<string, { title: string; description: string }>
  >({});
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
  const rubricQuery = useQuery({
    queryKey: ["assessment-rubric", id],
    queryFn: () => api.getAssessmentRubric(id),
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
        queryKey: ["assessment-rubric", id],
      });
      void queryClient.invalidateQueries({ queryKey: ["assessment", id] });
      setActiveRunId(null);
    }
  }, [runQuery.data?.status, queryClient, id]);

  const leaves = useMemo(
    () => leafQuestions(questionsQuery.data ?? []),
    [questionsQuery.data],
  );
  const byQuestion = useMemo(
    () => groupCriteria(rubricQuery.data ?? []),
    [rubricQuery.data],
  );

  const createMutation = useMutation({
    mutationFn: (question: Question) => {
      const draft = draftRubrics[question.id] ?? {
        title: `Rubric ${question.code}`,
        description: "",
      };
      return api.createTeacherRubric!({
        assessmentId: id,
        questionVersionId: question.id,
        title: draft.title || `Rubric ${question.code}`,
        criteria: [
          {
            criterionCode: "C1",
            description: draft.description || `Teacher criterion for ${question.code}`,
            maxMarks: question.max_mark,
            sequence: 1,
            scoringMode: "ADDITIVE",
            partialCreditAllowed: true,
          },
        ],
      });
    },
    onSuccess: async () => {
      setActionError(null);
      await queryClient.invalidateQueries({
        queryKey: ["assessment-rubric", id],
      });
    },
    onError: (err) => {
      setActionError(isApiError(err) ? err.message : "Create failed");
    },
  });

  const proposeMutation = useMutation({
    mutationFn: (questionVersionId: string) =>
      api.prepareAiRubricProposal!({
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
        queryKey: ["assessment-rubric", id],
      });
      await queryClient.invalidateQueries({ queryKey: ["assessment", id] });
    },
    onError: (err) => {
      setActionError(isApiError(err) ? err.message : "AI proposal failed");
    },
  });

  const approveMutation = useMutation({
    mutationFn: (rubricVersionId: string) =>
      api.approveRubric!(rubricVersionId),
    onSuccess: async () => {
      setActionError(null);
      await queryClient.invalidateQueries({
        queryKey: ["assessment-rubric", id],
      });
      await queryClient.invalidateQueries({ queryKey: ["assessment", id] });
    },
    onError: (err) => {
      setActionError(isApiError(err) ? err.message : "Approve failed");
    },
  });

  if (
    assessmentQuery.isLoading ||
    rubricQuery.isLoading ||
    questionsQuery.isLoading ||
    versionQuery.isLoading
  ) {
    return <LoadingState />;
  }
  if (
    assessmentQuery.isError ||
    rubricQuery.isError ||
    questionsQuery.isError ||
    versionQuery.isError ||
    !assessmentQuery.data ||
    !rubricQuery.data ||
    !questionsQuery.data ||
    !versionQuery.data
  ) {
    return <ErrorState onRetry={() => void rubricQuery.refetch()} />;
  }

  const editable =
    assessmentQuery.data.workflow_state === "DRAFT" ||
    assessmentQuery.data.workflow_state === "RUBRIC_REVIEW";
  const generating = isActiveRunStatus(runQuery.data?.status);

  return (
    <div data-testid="assessment-rubric-page" data-authoring-mode="live">
      <PageHeader
        title="Rubric & answer key"
        description={assessmentQuery.data.title}
        breadcrumbs={[
          { label: "Assessments", href: "/assessments" },
          {
            label: assessmentQuery.data.code,
            href: `/assessments/${id}`,
          },
          { label: "Rubric" },
        ]}
      />

      <p
        data-testid="rubric-truth-notice"
        className="mb-4 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900"
      >
        AI proposals are not approved until a teacher explicitly approves them.
      </p>

      {actionError && (
        <p data-testid="rubric-error" className="mb-3 text-sm text-red-700">
          {actionError}
        </p>
      )}

      {generating && (
        <p data-testid="rubric-run-status" className="mb-3 text-sm text-slate-600">
          AI run status: {runQuery.data?.status}
        </p>
      )}

      <ul className="space-y-3">
        {leaves.map((question) => {
          const criteria = byQuestion.get(question.id) ?? [];
          const first = criteria[0];
          const status = first?.status;
          const source = first?.source_type;
          const needsApproval =
            source === "AI_PROPOSED" && status === "REVIEW_REQUIRED";
          return (
            <li
              key={question.id}
              data-testid={`rubric-question-${question.id}`}
              className="rounded-md border border-slate-200 bg-white p-4"
            >
              <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                {question.code} · {question.max_mark} marks
              </div>
              <p className="mt-1 text-sm text-slate-700">{question.prompt}</p>

              {criteria.length > 0 ? (
                <>
                  <p
                    data-testid={`rubric-provenance-${question.id}`}
                    className="mt-2 text-xs font-medium text-slate-600"
                  >
                    Provenance: {provenanceLabel(source)}
                  </p>
                  <p
                    data-testid={`rubric-status-${question.id}`}
                    className="mt-1 text-xs text-slate-500"
                  >
                    Status: {status}
                  </p>
                  <ul className="mt-3 space-y-2">
                    {criteria.map((criterion) => (
                      <li
                        key={criterion.id}
                        className="rounded border border-slate-100 bg-slate-50 p-3"
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div>
                            <div className="text-sm font-semibold text-slate-900">
                              {criterion.label}
                            </div>
                            <p className="mt-1 text-sm text-slate-600">
                              {criterion.description}
                            </p>
                          </div>
                          <div className="text-sm font-semibold tabular-nums">
                            {criterion.max_marks} marks
                          </div>
                        </div>
                      </li>
                    ))}
                  </ul>
                </>
              ) : editable ? (
                <div className="mt-3 space-y-2">
                  <input
                    data-testid={`rubric-title-${question.id}`}
                    className="w-full rounded border border-slate-300 px-2 py-1 text-sm"
                    placeholder="Rubric title"
                    value={
                      draftRubrics[question.id]?.title ??
                      `Rubric ${question.code}`
                    }
                    onChange={(e) =>
                      setDraftRubrics((prev) => ({
                        ...prev,
                        [question.id]: {
                          title: e.target.value,
                          description: prev[question.id]?.description ?? "",
                        },
                      }))
                    }
                  />
                  <textarea
                    data-testid={`rubric-draft-${question.id}`}
                    className="w-full rounded border border-slate-300 px-2 py-1 text-sm"
                    rows={2}
                    placeholder="Teacher criterion description"
                    value={draftRubrics[question.id]?.description ?? ""}
                    onChange={(e) =>
                      setDraftRubrics((prev) => ({
                        ...prev,
                        [question.id]: {
                          title:
                            prev[question.id]?.title ??
                            `Rubric ${question.code}`,
                          description: e.target.value,
                        },
                      }))
                    }
                  />
                </div>
              ) : (
                <p className="mt-2 text-sm text-slate-500">No rubric</p>
              )}

              {editable && (
                <div className="mt-3 flex flex-wrap gap-2">
                  {criteria.length === 0 && (
                    <button
                      type="button"
                      data-testid={`add-teacher-rubric-${question.id}`}
                      className="rounded-md border border-slate-300 px-3 py-1.5 text-sm hover:bg-slate-50"
                      disabled={createMutation.isPending}
                      onClick={() => createMutation.mutate(question)}
                    >
                      Add teacher rubric
                    </button>
                  )}
                  {criteria.length === 0 && (
                    <button
                      type="button"
                      data-testid={`generate-ai-rubric-${question.id}`}
                      className="rounded-md bg-teal-800 px-3 py-1.5 text-sm font-medium text-white hover:bg-teal-900 disabled:opacity-50"
                      disabled={proposeMutation.isPending || generating}
                      onClick={() => proposeMutation.mutate(question.id)}
                    >
                      Generate AI proposal
                    </button>
                  )}
                  {needsApproval && first?.rubric_version_id && (
                    <button
                      type="button"
                      data-testid={`approve-rubric-${question.id}`}
                      className="rounded-md bg-teal-800 px-3 py-1.5 text-sm font-medium text-white hover:bg-teal-900"
                      disabled={approveMutation.isPending}
                      onClick={() =>
                        approveMutation.mutate(first.rubric_version_id!)
                      }
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

function MockRubricPage({ id }: { id: string }) {
  const assessmentQuery = useQuery({
    queryKey: ["assessment", id],
    queryFn: () => api.getAssessment(id),
  });
  const rubricQuery = useQuery({
    queryKey: ["assessment-rubric", id],
    queryFn: () => api.getAssessmentRubric(id),
  });

  if (assessmentQuery.isLoading || rubricQuery.isLoading)
    return <LoadingState />;
  if (
    assessmentQuery.isError ||
    rubricQuery.isError ||
    !assessmentQuery.data ||
    !rubricQuery.data
  ) {
    return <ErrorState onRetry={() => void rubricQuery.refetch()} />;
  }

  return (
    <div data-testid="assessment-rubric-page" data-authoring-mode="mock">
      <PageHeader
        title="Rubric & answer key"
        description={assessmentQuery.data.title}
        breadcrumbs={[
          { label: "Assessments", href: "/assessments" },
          { label: assessmentQuery.data.code, href: `/assessments/${id}` },
          { label: "Rubric" },
        ]}
      />
      <ul className="space-y-3">
        {rubricQuery.data.map((criterion) => (
          <li
            key={criterion.id}
            className="rounded-md border border-slate-200 bg-white p-4"
          >
            <div className="flex items-start justify-between gap-3">
              <div>
                <div className="text-sm font-semibold text-slate-900">
                  {criterion.label}
                </div>
                <p className="mt-1 text-sm text-slate-600">
                  {criterion.description}
                </p>
                <p className="mt-2 text-xs text-slate-400">
                  Question {criterion.question_id}
                </p>
              </div>
              <div className="text-sm font-semibold tabular-nums">
                {criterion.max_marks} marks
              </div>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

export default function AssessmentRubricPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const live = getApiCapabilities().assessments === "live";
  return live ? <LiveRubricPage id={id} /> : <MockRubricPage id={id} />;
}
