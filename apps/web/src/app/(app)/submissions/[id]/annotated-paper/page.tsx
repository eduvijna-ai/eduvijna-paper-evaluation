"use client";

import { use, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { PageHeader } from "@/components/layout/PageHeader";
import { PaperViewerShell } from "@/components/paper/PaperViewerShell";
import {
  ErrorCategoryBadge,
  RubricCriterionRow,
} from "@/components/evaluation/ScoreComponents";
import { ErrorState, LoadingState } from "@/components/ui/FeedbackStates";
import type { Question } from "@/lib/types/domain";
import { formatScorePair } from "@/lib/helpers/score";

function findQuestionById(
  nodes: Question[],
  id: string,
): Question | undefined {
  for (const node of nodes) {
    if (node.id === id) return node;
    if (node.children) {
      const found = findQuestionById(node.children, id);
      if (found) return found;
    }
  }
  return undefined;
}

export default function AnnotatedPaperPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const [activePageId, setActivePageId] = useState("page-1");
  const [selectedRegionId, setSelectedRegionId] = useState<string | null>(
    "reg-2",
  );

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["evaluation-annotated", id],
    queryFn: () => api.getEvaluationWorkspace(id),
  });

  const selectedRegion = useMemo(
    () => data?.regions.find((r) => r.id === selectedRegionId),
    [data, selectedRegionId],
  );

  const relatedLedger = useMemo(() => {
    if (!data || !selectedRegion?.question_id) return data?.ledgers[0];
    return (
      data.ledgers.find(
        (l) =>
          l.question_id === selectedRegion.question_id ||
          selectedRegion.question_id?.startsWith(l.question_id) ||
          l.answer_region_ids.includes(selectedRegion.id),
      ) ?? data.ledgers[0]
    );
  }, [data, selectedRegion]);

  if (isLoading) return <LoadingState />;
  if (isError || !data) return <ErrorState onRetry={() => void refetch()} />;

  const q = relatedLedger
    ? findQuestionById(data.questions, relatedLedger.question_id)
    : undefined;
  const displayCode = q?.code ?? relatedLedger?.question_id ?? "Q";

  return (
    <div data-testid="annotated-paper-page">
      <PageHeader
        title="Annotated paper"
        description="Synthetic ✓ +marks, ✕ deductions, △ partial — click a region for criterion detail."
        breadcrumbs={[
          { label: "Submissions", href: "/submissions" },
          { label: id, href: `/submissions/${id}` },
          { label: "Annotated paper" },
        ]}
      />
      <div className="grid gap-4 xl:grid-cols-[1.2fr_0.8fr]">
        <PaperViewerShell
          pages={data.pages}
          regions={data.regions}
          activePageId={activePageId}
          selectedRegionId={selectedRegionId}
          onPageSelect={setActivePageId}
          onRegionSelect={setSelectedRegionId}
          title="Annotated evidence"
          showMarks
        />
        <div className="space-y-3 rounded-md border border-slate-200 bg-white p-4">
          <h2 className="text-sm font-semibold text-slate-800">
            Annotation detail
          </h2>
          <div
            data-testid="annotation-score-chip"
            className="rounded-md bg-slate-900 px-3 py-2 text-sm font-semibold text-white"
          >
            {displayCode}{" "}
            {relatedLedger
              ? formatScorePair(
                  relatedLedger.proposed_ai_score,
                  relatedLedger.max_mark,
                )
              : "—"}
          </div>

          {selectedRegion && (
            <div
              data-testid="annotation-region-detail"
              className="rounded-md border border-teal-200 bg-teal-50/40 p-3"
            >
              <div className="text-sm font-medium text-slate-900">
                {selectedRegion.label}
              </div>
              <p className="mt-1 text-xs text-slate-600">
                Mark:{" "}
                {selectedRegion.annotation_kind === "FULL"
                  ? "✓ Full credit"
                  : selectedRegion.annotation_kind === "PARTIAL"
                    ? "△ Partial"
                    : selectedRegion.annotation_kind === "DEDUCTION"
                      ? "✕ Deduction"
                      : "Neutral"}
              </p>
            </div>
          )}

          {relatedLedger && (
            <div data-testid="annotation-criterion-panel" className="space-y-2">
              <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                Criterion / reason
              </h3>
              {relatedLedger.criterion_decisions.length === 0 ? (
                <p className="text-sm text-slate-500">
                  {relatedLedger.feedback_draft || "No criteria recorded."}
                </p>
              ) : (
                relatedLedger.criterion_decisions.map((c) => (
                  <RubricCriterionRow
                    key={c.rubric_criterion_id}
                    criterion={c}
                  />
                ))
              )}
              <p className="text-sm text-slate-700">
                <span className="font-medium">Explanation: </span>
                {relatedLedger.feedback_draft}
              </p>
              <div className="flex flex-wrap gap-1">
                {relatedLedger.error_codes.map((code) => (
                  <ErrorCategoryBadge key={code} code={code} />
                ))}
              </div>
            </div>
          )}

          <div>
            <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
              All questions
            </h3>
            {data.ledgers.map((ledger) => {
              const qq = findQuestionById(data.questions, ledger.question_id);
              return (
                <div
                  key={ledger.id}
                  className="mb-2 rounded-md border border-slate-100 px-3 py-2"
                >
                  <div className="text-sm font-medium text-slate-900">
                    {qq?.code ?? ledger.question_id}{" "}
                    {formatScorePair(ledger.proposed_ai_score, ledger.max_mark)}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
