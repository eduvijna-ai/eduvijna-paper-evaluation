"use client";

import { use, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { PageHeader } from "@/components/layout/PageHeader";
import { PaperViewerShell } from "@/components/paper/PaperViewerShell";
import { QuestionTree } from "@/components/evaluation/QuestionTree";
import { EvaluationDecisionPanel } from "@/components/evaluation/EvaluationDecisionPanel";
import { ErrorState, LoadingState } from "@/components/ui/FeedbackStates";
import type { TeacherReviewAction } from "@/lib/types/enums";
import type { EvaluationWorkflowState } from "@/lib/types/enums";
import type { Question } from "@/lib/types/domain";

function findQuestion(
  nodes: Question[],
  id: string,
): Question | undefined {
  for (const node of nodes) {
    if (node.id === id) return node;
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
  const queryClient = useQueryClient();
  const [activePageId, setActivePageId] = useState("page-1");
  const [selectedRegionId, setSelectedRegionId] = useState<string | null>(
    "reg-2",
  );
  const [selectedQuestionId, setSelectedQuestionId] = useState<string | null>(
    null,
  );
  const [actionMessage, setActionMessage] = useState<string | null>(null);

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["evaluation", id, selectedQuestionId],
    queryFn: () =>
      api.getEvaluationWorkspace(id, selectedQuestionId ?? undefined),
  });

  const questionId = selectedQuestionId ?? data?.selected_question_id ?? "q-1b";

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

  const relatedRegions =
    data?.regions.filter(
      (r) => r.question_id === questionId || r.question_id === questionId.split("-").slice(0, 2).join("-"),
    ) ?? [];

  const answerKey =
    data?.answer_keys.filter((a) => a.question_id === questionId) ?? [];
  const rubric =
    data?.rubrics.filter((r) => r.question_id === questionId) ?? [];

  const actionMutation = useMutation({
    mutationFn: ({
      action,
      payload,
    }: {
      action: TeacherReviewAction;
      payload?: { newScore?: number; feedback?: string };
    }) =>
      api.applyTeacherAction(id, ledger?.id ?? "", action, payload),
    onSuccess: (result) => {
      setActionMessage(result.message);
      void queryClient.invalidateQueries({ queryKey: ["evaluation", id] });
    },
  });

  if (isLoading) return <LoadingState />;
  if (isError || !data || !ledger)
    return <ErrorState onRetry={() => void refetch()} />;

  const question = findQuestion(data.questions, questionId);

  return (
    <div data-testid="evaluation-workspace-page" className="-m-2 sm:-m-3">
      <div className="px-2 sm:px-3 pt-2">
        <PageHeader
          title="Evaluation workspace"
          description={`${data.assessment.title} · ${data.student?.display_name ?? "Unresolved student"}`}
          breadcrumbs={[
            { label: "Submissions", href: "/submissions" },
            { label: id },
            { label: "Evaluation" },
          ]}
        />
      </div>

      <div
        data-testid="evaluation-3col"
        className="grid min-h-[70vh] gap-3 xl:grid-cols-[minmax(280px,1.1fr)_minmax(280px,1fr)_minmax(300px,1fr)]"
      >
        {/* LEFT: paper */}
        <div className="min-h-[480px] px-2 sm:px-3">
          <PaperViewerShell
            pages={data.pages}
            regions={
              relatedRegions.length > 0 ? relatedRegions : data.regions
            }
            activePageId={activePageId}
            selectedRegionId={selectedRegionId}
            onPageSelect={setActivePageId}
            onRegionSelect={setSelectedRegionId}
          />
        </div>

        {/* CENTER: question / key / rubric / curriculum */}
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

          {actionMessage && (
            <p
              data-testid="teacher-action-result"
              className="rounded-md bg-teal-50 px-3 py-2 text-sm text-teal-900 ring-1 ring-teal-200"
            >
              {actionMessage}
            </p>
          )}
        </div>

        {/* RIGHT: AI evaluation + teacher actions */}
        <div className="min-h-[480px] rounded-md border border-slate-200 bg-white p-4">
          <EvaluationDecisionPanel
            ledger={ledger}
            onAction={(action, payload) =>
              actionMutation.mutate({ action, payload })
            }
          />
        </div>
      </div>
    </div>
  );
}
