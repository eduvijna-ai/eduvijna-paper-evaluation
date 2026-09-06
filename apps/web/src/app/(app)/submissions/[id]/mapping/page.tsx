"use client";

import { use, useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { api, isApiError } from "@/lib/api";
import { getApiCapabilities } from "@/lib/api/capabilities";
import { getSession, hasPermission } from "@/lib/auth/session";
import { PageHeader } from "@/components/layout/PageHeader";
import { PaperViewerShell } from "@/components/paper/PaperViewerShell";
import { QuestionTree, QuestionStatus } from "@/components/evaluation/QuestionTree";
import { ConfidenceIndicator, ErrorState, LoadingState } from "@/components/ui/FeedbackStates";
import type { MappingAction } from "@/lib/types/enums";
import type { Question } from "@/lib/types/domain";
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

const DEFAULT_TEST_BBOX = { x: 0.1, y: 0.1, width: 0.3, height: 0.2 };

function firstLeafQuestionId(questions: Question[]): string | null {
  for (const q of questions) {
    if (q.is_leaf_scorable || !q.children?.length) {
      return q.id;
    }
    const nested = firstLeafQuestionId(q.children);
    if (nested) return nested;
  }
  return null;
}

function MockMappingReview({ id }: { id: string }) {
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
        <PaperViewerShell
          pages={data.pages}
          regions={data.regions}
          activePageId={activePageId}
          selectedRegionId={selectedRegionId}
          onPageSelect={setActivePageId}
          onRegionSelect={setSelectedRegionId}
          title="Evidence viewer"
        />

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

function LiveMappingReview({ id }: { id: string }) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const session = getSession();
  const canReview = hasPermission(session, "mapping:review");
  const canRead =
    canReview || hasPermission(session, "mapping:read");
  const actionsEnabled = canReview;

  const [activePageId, setActivePageId] = useState("");
  const [selectedRegionId, setSelectedRegionId] = useState<string | null>(null);
  const [selectedQuestionId, setSelectedQuestionId] = useState<string>("");
  const [drawEnabled, setDrawEnabled] = useState(false);
  const [pageImageUrl, setPageImageUrl] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["mapping", id],
    queryFn: () => api.getMappingReview(id),
  });

  useEffect(() => {
    if (!data?.pages?.length) return;
    setActivePageId((current) => {
      if (current && data.pages.some((p) => p.id === current)) return current;
      return data.pages[0]!.id;
    });
  }, [data]);

  useEffect(() => {
    if (!data?.questions?.length) return;
    setSelectedQuestionId((current) => {
      if (current) return current;
      return firstLeafQuestionId(data.questions) ?? data.questions[0]!.id;
    });
  }, [data]);

  useEffect(() => {
    if (!activePageId || !api.getSubmissionPageImageBlob) {
      setPageImageUrl(null);
      return;
    }
    let revoked = false;
    let objectUrl: string | null = null;
    void api
      .getSubmissionPageImageBlob(activePageId)
      .then((blob) => {
        if (revoked) return;
        objectUrl = URL.createObjectURL(blob);
        setPageImageUrl(objectUrl);
      })
      .catch(() => {
        if (!revoked) setPageImageUrl(null);
      });
    return () => {
      revoked = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [activePageId]);

  const invalidate = async () => {
    await queryClient.invalidateQueries({ queryKey: ["mapping", id] });
    await queryClient.invalidateQueries({ queryKey: ["submission", id] });
  };

  const onMutationError = (err: unknown) => {
    setActionError(
      isApiError(err)
        ? err.message || err.userMessage()
        : err instanceof Error
          ? err.message
          : "Action failed",
    );
  };

  const createRegionMutation = useMutation({
    mutationFn: (input: {
      pageId: string;
      bbox: { x: number; y: number; width: number; height: number };
      label?: string;
    }) =>
      api.createAnswerRegion!(input.pageId, {
        label: input.label ?? "Answer region",
        region_type: "ANSWER",
        bbox: input.bbox,
      }),
    onSuccess: async (region) => {
      setActionError(null);
      setDrawEnabled(false);
      setSelectedRegionId(region.id);
      setStatusMessage("Answer region created");
      await invalidate();
    },
    onError: onMutationError,
  });

  const assignMutation = useMutation({
    mutationFn: () =>
      api.upsertQuestionMapping!(id, selectedQuestionId, {
        disposition: "ANSWERED",
        region_ids: selectedRegionId ? [selectedRegionId] : [],
      }),
    onSuccess: async () => {
      setActionError(null);
      setStatusMessage("Region assigned to question");
      await invalidate();
    },
    onError: onMutationError,
  });

  const blankMutation = useMutation({
    mutationFn: () =>
      api.upsertQuestionMapping!(id, selectedQuestionId, {
        disposition: "BLANK",
        region_ids: [],
      }),
    onSuccess: async () => {
      setActionError(null);
      setStatusMessage("Question marked blank");
      await invalidate();
    },
    onError: onMutationError,
  });

  const confirmMutation = useMutation({
    mutationFn: () => api.confirmQuestionMapping!(id, selectedQuestionId),
    onSuccess: async () => {
      setActionError(null);
      setStatusMessage("Question mapping confirmed");
      await invalidate();
    },
    onError: onMutationError,
  });

  const finalizeMutation = useMutation({
    mutationFn: () => api.finalizeMappingReview!(id),
    onSuccess: async () => {
      setActionError(null);
      await invalidate();
      router.push(`/submissions/${id}`);
    },
    onError: onMutationError,
  });

  const continuationMutation = useMutation({
    mutationFn: (isContinuation: boolean) =>
      api.updateSubmissionPage!(activePageId, {
        is_continuation: isContinuation,
      }),
    onSuccess: async () => {
      setActionError(null);
      setStatusMessage("Page continuation updated");
      await invalidate();
    },
    onError: onMutationError,
  });

  const statusByQuestionId = useMemo(() => {
    const map: Record<string, string> = {};
    data?.mappings?.forEach((m) => {
      map[m.question_version_id] = m.mapping_state;
    });
    data?.mapping.forEach((m) => {
      if (!map[m.question_id]) map[m.question_id] = m.status;
    });
    return map;
  }, [data]);

  if (!canRead && session) {
    return (
      <ErrorState
        title="No mapping access"
        message="You need mapping:read or mapping:review to open this workspace."
      />
    );
  }

  if (isLoading) return <LoadingState />;
  if (isError || !data) return <ErrorState onRetry={() => void refetch()} />;

  const selectedLiveMapping =
    data.mappings?.find((m) => m.question_version_id === selectedQuestionId) ??
    null;
  const selectedLegacy = data.mapping.find(
    (m) => m.question_id === selectedQuestionId,
  );
  const activePage = data.pages.find((p) => p.id === activePageId);
  const selectedRegion = selectedRegionId
    ? data.regions.find((r) => r.id === selectedRegionId)
    : null;
  const completion = data.completion;
  const busy =
    createRegionMutation.isPending ||
    assignMutation.isPending ||
    blankMutation.isPending ||
    confirmMutation.isPending ||
    finalizeMutation.isPending ||
    continuationMutation.isPending;

  return (
    <div data-testid="mapping-review-page" data-mapping-mode="live">
      <PageHeader
        title="Question mapping"
        description="Manually assign answer regions to scorable questions."
        breadcrumbs={[
          { label: "Submissions", href: "/submissions" },
          { label: id, href: `/submissions/${id}` },
          { label: "Mapping" },
        ]}
      />

      <p
        data-testid="mapping-manual-notice"
        className="mb-3 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-950"
      >
        {data.automated_region_detection_active || data.automated_mapping_active
          ? "Automated mapping assistance is active — review AI proposals before confirming."
          : "Manual mapping — automated mapping not active."}
      </p>

      {completion && (
        <p
          data-testid="mapping-completion"
          className="mb-3 text-sm text-slate-700"
        >
          {completion.confirmed_count} of {completion.leaf_total} scorable
          questions confirmed
        </p>
      )}

      {actionError && (
        <p
          data-testid="mapping-action-error"
          className="mb-3 rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-900"
        >
          {actionError}
        </p>
      )}
      {statusMessage && (
        <p
          data-testid="mapping-status-message"
          className="mb-3 text-xs text-teal-800"
        >
          {statusMessage}
        </p>
      )}

      <div
        data-testid="mapping-3col"
        className="grid min-h-[70vh] gap-3 xl:grid-cols-[minmax(280px,1.1fr)_minmax(240px,0.9fr)_minmax(260px,1fr)]"
      >
        <PaperViewerShell
          pages={data.pages}
          regions={data.regions}
          activePageId={activePageId || data.pages[0]?.id || ""}
          selectedRegionId={selectedRegionId}
          onPageSelect={setActivePageId}
          onRegionSelect={setSelectedRegionId}
          title="Evidence viewer"
          mode="live"
          pageImageUrl={pageImageUrl}
          drawEnabled={drawEnabled && actionsEnabled}
          onRegionDrawn={(bbox) => {
            if (!activePageId) return;
            createRegionMutation.mutate({ pageId: activePageId, bbox });
          }}
        />

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

        <div className="flex min-h-[420px] flex-col gap-4 rounded-md border border-slate-200 bg-white p-4">
          {selectedRegion && (
            <div
              data-testid="mapping-selected-region"
              className="rounded-md border border-slate-200 bg-slate-50 p-3"
            >
              <div className="flex items-center justify-between gap-2">
                <span className="text-sm font-medium text-slate-900">
                  {selectedRegion.label}
                </span>
                {selectedRegion.source_type === "AI" && (
                  <span
                    data-testid="region-ai-proposal-badge"
                    className="inline-flex rounded-md bg-violet-50 px-2 py-0.5 text-xs font-medium text-violet-800 ring-1 ring-violet-200"
                  >
                    AI proposal
                  </span>
                )}
              </div>
              {selectedRegion.source_type === "AI" && (
                <div className="mt-2">
                  <ConfidenceIndicator
                    value={selectedRegion.confidence}
                    label="Detection confidence"
                  />
                </div>
              )}
            </div>
          )}
          {(selectedLiveMapping || selectedLegacy) && (
            <div
              data-testid="mapping-selected-detail"
              className="rounded-md border border-slate-200 bg-slate-50 p-3"
            >
              <div className="flex items-center justify-between gap-2">
                <span className="text-sm font-medium text-slate-900">
                  {selectedLiveMapping?.question_code ??
                    selectedLegacy?.question_code}
                </span>
                <QuestionStatus
                  state={
                    selectedLiveMapping?.mapping_state ??
                    selectedLegacy?.status ??
                    "UNMAPPED"
                  }
                />
              </div>
              {selectedLiveMapping && (
                <p className="mt-1 text-xs text-slate-500">
                  Disposition: {selectedLiveMapping.disposition}
                  {selectedLiveMapping.mapped_by === "AI" ? (
                    <span
                      data-testid="mapping-ai-badge"
                      className="ml-2 inline-flex rounded-md bg-violet-50 px-2 py-0.5 font-medium text-violet-800 ring-1 ring-violet-200"
                    >
                      mapped_by=AI
                    </span>
                  ) : (
                    <span
                      data-testid="mapping-human-badge"
                      className="ml-2 inline-flex rounded-md bg-slate-50 px-2 py-0.5 font-medium text-slate-700 ring-1 ring-slate-200"
                    >
                      mapped_by=HUMAN
                    </span>
                  )}
                </p>
              )}
              <div className="mt-2">
                <ConfidenceIndicator
                  value={
                    selectedLiveMapping?.mapped_by === "AI"
                      ? selectedLiveMapping.mapping_confidence
                      : selectedLiveMapping?.mapped_by === "HUMAN"
                        ? selectedLiveMapping.mapping_confidence
                        : selectedLegacy?.confidence ?? 0
                  }
                  label={
                    selectedLiveMapping?.mapped_by === "AI"
                      ? "AI mapping confidence"
                      : "Mapping confidence"
                  }
                />
              </div>
            </div>
          )}

          {actionsEnabled ? (
            <div className="flex flex-col gap-2">
              <h3 className="text-sm font-semibold text-slate-800">
                Mapping controls
              </h3>
              <Button
                variant="secondary"
                size="sm"
                data-testid="add-answer-region"
                disabled={!activePageId || busy}
                onClick={() => {
                  if (!activePageId) return;
                  createRegionMutation.mutate({
                    pageId: activePageId,
                    bbox: DEFAULT_TEST_BBOX,
                    label: "Answer region",
                  });
                }}
              >
                Add answer region
              </Button>
              <Button
                variant="secondary"
                size="sm"
                data-testid="toggle-draw-region"
                disabled={!activePageId || busy}
                onClick={() => setDrawEnabled((v) => !v)}
              >
                {drawEnabled ? "Cancel draw" : "Draw answer region"}
              </Button>
              <Button
                variant="secondary"
                size="sm"
                data-testid="assign-region"
                disabled={!selectedRegionId || !selectedQuestionId || busy}
                onClick={() => assignMutation.mutate()}
              >
                Assign selected region
              </Button>
              <Button
                variant="secondary"
                size="sm"
                data-testid="mark-blank"
                disabled={!selectedQuestionId || busy}
                onClick={() => blankMutation.mutate()}
              >
                Mark blank
              </Button>
              <Button
                variant="secondary"
                size="sm"
                data-testid="confirm-mapping"
                disabled={!selectedQuestionId || busy}
                onClick={() => confirmMutation.mutate()}
              >
                Confirm question
              </Button>
              <label className="mt-1 flex items-center gap-2 text-xs text-slate-700">
                <input
                  type="checkbox"
                  data-testid="page-continuation-toggle"
                  checked={Boolean(activePage?.is_continuation)}
                  disabled={!activePageId || busy}
                  onChange={(e) =>
                    continuationMutation.mutate(e.target.checked)
                  }
                />
                Page is continuation
              </label>
              <Button
                size="sm"
                data-testid="finalize-mapping"
                disabled={busy}
                onClick={() => finalizeMutation.mutate()}
              >
                Finalize mapping
              </Button>
            </div>
          ) : (
            <p className="text-sm text-slate-500">
              Read-only — mapping:review is required to edit.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

export default function MappingReviewPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const live = getApiCapabilities().mapping === "live";
  return live ? <LiveMappingReview id={id} /> : <MockMappingReview id={id} />;
}
