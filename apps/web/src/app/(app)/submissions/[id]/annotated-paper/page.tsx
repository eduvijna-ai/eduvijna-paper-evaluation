"use client";

import { use, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { PageHeader } from "@/components/layout/PageHeader";
import { PaperViewerShell } from "@/components/paper/PaperViewerShell";
import { ErrorCategoryBadge } from "@/components/evaluation/ScoreComponents";
import { ErrorState, LoadingState } from "@/components/ui/FeedbackStates";
import type { Question } from "@/lib/types/domain";

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

  if (isLoading) return <LoadingState />;
  if (isError || !data) return <ErrorState onRetry={() => void refetch()} />;

  return (
    <div data-testid="annotated-paper-page">
      <PageHeader
        title="Annotated paper"
        description="Placeholder viewer with evidence overlays — no real student PDFs."
        breadcrumbs={[
          { label: "Submissions", href: "/submissions" },
          { label: id },
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
        />
        <div className="space-y-3 rounded-md border border-slate-200 bg-white p-4">
          <h2 className="text-sm font-semibold text-slate-800">
            Annotation legend
          </h2>
          {data.ledgers.map((ledger) => {
            const q = findQuestionById(data.questions, ledger.question_id);
            return (
              <div
                key={ledger.id}
                className="rounded-md border border-slate-100 px-3 py-2"
              >
                <div className="text-sm font-medium text-slate-900">
                  {q?.code ?? ledger.question_id}
                </div>
                <div className="mt-1 text-xs text-slate-500">
                  Score {ledger.proposed_ai_score}/{ledger.max_mark}
                </div>
                <div className="mt-2 flex flex-wrap gap-1">
                  {ledger.error_codes.map((code) => (
                    <ErrorCategoryBadge key={code} code={code} />
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
