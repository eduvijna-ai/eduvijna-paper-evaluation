"use client";

import { use, useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { PageHeader } from "@/components/layout/PageHeader";
import { PaperViewerShell } from "@/components/paper/PaperViewerShell";
import { QuestionTree } from "@/components/evaluation/QuestionTree";
import { ConfidenceIndicator } from "@/components/ui/FeedbackStates";
import { ErrorState, LoadingState } from "@/components/ui/FeedbackStates";
import type { MappingAction } from "@/lib/types/enums";
import { QuestionStatus } from "@/components/evaluation/QuestionTree";

const ACTIONS: MappingAction[] = [
  "ACCEPT",
  "MOVE",
  "MERGE",
  "SPLIT",
  "IGNORE",
  "MARK_CROSSED_OUT",
];

export default function MappingReviewPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const [activePageId, setActivePageId] = useState("page-1");
  const [selectedRegionId, setSelectedRegionId] = useState<string | null>(
    "reg-3",
  );
  const [selectedQuestionId, setSelectedQuestionId] = useState<string>("q-2");
  const [lastAction, setLastAction] = useState<string | null>(null);

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["mapping", id],
    queryFn: () => api.getMappingReview(id),
  });

  const actionMutation = useMutation({
    mutationFn: (action: MappingAction) =>
      api.applyMappingAction(
        id,
        selectedRegionId ?? "",
        action,
        selectedQuestionId,
      ),
    onSuccess: (result) => setLastAction(result.action),
  });

  const statusByQuestionId = useMemo(() => {
    const map: Record<string, string> = {};
    data?.mapping.forEach((m) => {
      map[m.question_id] = m.status;
    });
    return map;
  }, [data]);

  if (isLoading) return <LoadingState />;
  if (isError || !data) return <ErrorState onRetry={() => void refetch()} />;

  const selectedMapping = data.mapping.find((m) =>
    selectedRegionId
      ? m.region_ids.includes(selectedRegionId)
      : m.question_id === selectedQuestionId,
  );

  return (
    <div data-testid="mapping-review-page">
      <PageHeader
        title="Question mapping"
        description="Align evidence regions to the question hierarchy. Low confidence stays unresolved."
        breadcrumbs={[
          { label: "Submissions", href: "/submissions" },
          { label: id },
          { label: "Mapping" },
        ]}
      />
      <div className="grid gap-4 xl:grid-cols-2">
        <PaperViewerShell
          pages={data.pages}
          regions={data.regions}
          activePageId={activePageId}
          selectedRegionId={selectedRegionId}
          onPageSelect={setActivePageId}
          onRegionSelect={setSelectedRegionId}
          title="Evidence viewer"
        />
        <div className="flex min-h-[420px] flex-col gap-4 rounded-md border border-slate-200 bg-white p-4">
          <div>
            <h2 className="text-sm font-semibold text-slate-800">
              Question hierarchy
            </h2>
            <div className="mt-2">
              <QuestionTree
                questions={data.questions}
                selectedId={selectedQuestionId}
                onSelect={setSelectedQuestionId}
                statusByQuestionId={statusByQuestionId}
              />
            </div>
          </div>

          {selectedMapping && (
            <div className="rounded-md border border-slate-200 bg-slate-50 p-3">
              <div className="flex items-center justify-between gap-2">
                <span className="text-sm font-medium text-slate-900">
                  {selectedMapping.question_code}
                </span>
                <QuestionStatus state={selectedMapping.status} />
              </div>
              <div className="mt-2">
                <ConfidenceIndicator
                  value={selectedMapping.confidence}
                  label="Mapping confidence"
                />
              </div>
            </div>
          )}

          <div>
            <h3 className="mb-2 text-sm font-semibold text-slate-800">
              Mapping actions
            </h3>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
              {ACTIONS.map((action) => (
                <button
                  key={action}
                  type="button"
                  data-testid={`mapping-action-${action}`}
                  disabled={!selectedRegionId || actionMutation.isPending}
                  onClick={() => actionMutation.mutate(action)}
                  className="rounded-md border border-slate-200 px-2 py-2 text-xs font-medium text-slate-800 hover:bg-slate-50 disabled:opacity-50"
                >
                  {action.replaceAll("_", " ")}
                </button>
              ))}
            </div>
            {lastAction && (
              <p
                data-testid="mapping-action-result"
                className="mt-2 text-xs text-teal-800"
              >
                Applied {lastAction.replaceAll("_", " ")} (mock).
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
