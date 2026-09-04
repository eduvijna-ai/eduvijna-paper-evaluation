"use client";

import { use, useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { PageHeader } from "@/components/layout/PageHeader";
import { PaperViewerShell } from "@/components/paper/PaperViewerShell";
import { QuestionTree, QuestionStatus } from "@/components/evaluation/QuestionTree";
import { ConfidenceIndicator, ErrorState, LoadingState } from "@/components/ui/FeedbackStates";
import type { MappingAction } from "@/lib/types/enums";
import { Button } from "@/components/ui/primitives";

const ACTIONS: Array<{ action: MappingAction; label: string }> = [
  { action: "ACCEPT", label: "Accept Mapping" },
  { action: "MOVE", label: "Move Answer" },
  { action: "MERGE", label: "Merge Continuation" },
  { action: "SPLIT", label: "Split Region" },
  { action: "IGNORE", label: "Ignore" },
  { action: "MARK_CROSSED_OUT", label: "Crossed Out" },
  { action: "MARK_CONTINUATION", label: "Mark Continuation" },
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
          { label: id, href: `/submissions/${id}` },
          { label: "Mapping" },
        ]}
      />
      <div
        data-testid="mapping-3col"
        className="grid min-h-[70vh] gap-3 xl:grid-cols-[minmax(280px,1.1fr)_minmax(240px,0.9fr)_minmax(260px,1fr)]"
      >
        {/* LEFT: paper */}
        <PaperViewerShell
          pages={data.pages}
          regions={data.regions}
          activePageId={activePageId}
          selectedRegionId={selectedRegionId}
          onPageSelect={setActivePageId}
          onRegionSelect={setSelectedRegionId}
          title="Evidence viewer"
        />

        {/* CENTER: question hierarchy */}
        <div className="flex min-h-[420px] flex-col gap-3 overflow-y-auto rounded-md border border-slate-200 bg-white p-4">
          <h2 className="text-sm font-semibold text-slate-800">
            Question hierarchy
          </h2>
          <QuestionTree
            questions={data.questions}
            selectedId={selectedQuestionId}
            onSelect={setSelectedQuestionId}
            statusByQuestionId={statusByQuestionId}
          />
        </div>

        {/* RIGHT: status + actions */}
        <div className="flex min-h-[420px] flex-col gap-4 rounded-md border border-slate-200 bg-white p-4">
          {selectedMapping ? (
            <div
              data-testid="mapping-selected-detail"
              className="rounded-md border border-slate-200 bg-slate-50 p-3"
            >
              <div className="flex items-center justify-between gap-2">
                <span className="text-sm font-medium text-slate-900">
                  {selectedMapping.question_code}
                </span>
                <QuestionStatus state={selectedMapping.status} />
              </div>
              <p className="mt-1 text-xs text-slate-500">
                Mapping state: PROPOSED | REVIEW_REQUIRED | CONFIRMED
              </p>
              <div className="mt-2">
                <ConfidenceIndicator
                  value={selectedMapping.confidence}
                  label="Mapping confidence"
                />
              </div>
            </div>
          ) : (
            <p className="text-sm text-slate-500">Select a region or question.</p>
          )}

          <div>
            <h3 className="mb-2 text-sm font-semibold text-slate-800">
              Mapping actions
            </h3>
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
              {ACTIONS.map(({ action, label }) => (
                <Button
                  key={action}
                  variant="secondary"
                  size="sm"
                  data-testid={`mapping-action-${action}`}
                  disabled={!selectedRegionId || actionMutation.isPending}
                  onClick={() => actionMutation.mutate(action)}
                >
                  {label}
                </Button>
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
