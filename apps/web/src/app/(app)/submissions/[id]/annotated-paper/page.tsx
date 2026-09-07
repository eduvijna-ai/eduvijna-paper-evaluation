"use client";

import Link from "next/link";
import { use, useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, isApiError } from "@/lib/api";
import { getApiCapabilities } from "@/lib/api/capabilities";
import { PageHeader } from "@/components/layout/PageHeader";
import { PaperViewerShell } from "@/components/paper/PaperViewerShell";
import {
  ErrorCategoryBadge,
  RubricCriterionRow,
} from "@/components/evaluation/ScoreComponents";
import { ErrorState, LoadingState } from "@/components/ui/FeedbackStates";
import type { Question } from "@/lib/types/domain";
import { formatScorePair } from "@/lib/helpers/score";

const LIVE_UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

function isLiveUuid(id: string): boolean {
  return LIVE_UUID_RE.test(id) && !id.toLowerCase().includes("demo");
}

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

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export default function AnnotatedPaperPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const publicationLive = getApiCapabilities().publication === "live";
  const liveMode = publicationLive && isLiveUuid(id);

  const [activePageId, setActivePageId] = useState<string | null>(null);
  const [selectedRegionId, setSelectedRegionId] = useState<string | null>(null);
  const [pageImageUrl, setPageImageUrl] = useState<string | null>(null);
  const [downloadError, setDownloadError] = useState<string | null>(null);

  const mockQuery = useQuery({
    queryKey: ["evaluation-annotated", id],
    queryFn: () => api.getEvaluationWorkspace(id),
    enabled: !liveMode,
  });

  const liveQuery = useQuery({
    queryKey: ["annotated-paper", id],
    queryFn: () => api.getAnnotatedPaperWorkspace!(id),
    enabled: liveMode,
  });

  const liveData = liveQuery.data;
  const mockData = mockQuery.data;

  useEffect(() => {
    if (!liveMode || !liveData?.pages.length) return;
    if (!activePageId) {
      setActivePageId(liveData.pages[0]!.id);
      if (liveData.regions[0]) setSelectedRegionId(liveData.regions[0].id);
    }
  }, [liveMode, liveData, activePageId]);

  useEffect(() => {
    if (!liveMode || !activePageId || !api.getSubmissionPageImageBlob) {
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
  }, [liveMode, activePageId]);

  const selectedLiveAnnotation = useMemo(() => {
    if (!liveData || !selectedRegionId) return null;
    return (
      liveData.annotations.find((a) => a.id === selectedRegionId) ?? null
    );
  }, [liveData, selectedRegionId]);

  const selectedRegion = useMemo(() => {
    if (liveMode) {
      return liveData?.regions.find((r) => r.id === selectedRegionId);
    }
    return mockData?.regions.find((r) => r.id === selectedRegionId);
  }, [liveMode, liveData, mockData, selectedRegionId]);

  const relatedLedger = useMemo(() => {
    if (liveMode || !mockData) return undefined;
    if (!selectedRegion?.question_id) return mockData.ledgers[0];
    return (
      mockData.ledgers.find(
        (l) =>
          l.question_id === selectedRegion.question_id ||
          selectedRegion.question_id?.startsWith(l.question_id) ||
          l.answer_region_ids.includes(selectedRegion.id),
      ) ?? mockData.ledgers[0]
    );
  }, [liveMode, mockData, selectedRegion]);

  if (liveMode) {
    if (liveQuery.isLoading) return <LoadingState />;
    if (liveQuery.isError || !liveData) {
      return <ErrorState onRetry={() => void liveQuery.refetch()} />;
    }

    const latest = liveData.published_result;
    const ready =
      latest &&
      (latest.status === "GENERATED" || latest.status === "PUBLISHED");
    const pageId = activePageId ?? liveData.pages[0]?.id ?? "";
    const selectedQuestion = liveData.questions.find(
      (q) =>
        selectedLiveAnnotation?.question_evaluation_id === q.id ||
        q.id === selectedRegionId,
    );

    return (
      <div data-testid="annotated-paper-page">
        <PageHeader
          title="Annotated paper"
          description="Final human-approved marks only — never proposed AI scores."
          breadcrumbs={[
            { label: "Submissions", href: "/submissions" },
            { label: id, href: `/submissions/${id}` },
            { label: "Annotated paper" },
          ]}
          actions={
            ready ? (
              <button
                type="button"
                data-testid="download-evaluated-pdf"
                className="rounded-md bg-teal-800 px-3 py-2 text-sm font-medium text-white hover:bg-teal-900"
                onClick={async () => {
                  try {
                    setDownloadError(null);
                    const blob = await api.getPublicationArtifactBlob!(
                      latest.id,
                      "ANNOTATED_PDF",
                    );
                    downloadBlob(blob, "evaluated-paper.pdf");
                  } catch (err) {
                    setDownloadError(
                      isApiError(err) ? err.message : "Download failed.",
                    );
                  }
                }}
              >
                Download evaluated PDF
              </button>
            ) : (
              <Link
                href={`/submissions/${id}/publication`}
                data-testid="link-generate-publication"
                className="rounded-md border border-slate-300 px-3 py-2 text-sm font-medium text-slate-800 hover:bg-slate-50"
              >
                Open publication
              </Link>
            )
          }
        />

        {!ready && (
          <p
            data-testid="annotated-paper-not-ready"
            className="mb-4 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-950"
          >
            Annotated paper annotations appear after the publication package is
            generated.{" "}
            <Link
              href={`/submissions/${id}/publication`}
              className="font-medium underline"
            >
              Generate publication package
            </Link>
          </p>
        )}

        {downloadError && (
          <p className="mb-3 text-sm text-rose-700">{downloadError}</p>
        )}

        {latest && (
          <p
            data-testid="annotated-paper-total"
            className="mb-3 text-sm text-slate-700"
          >
            Total{" "}
            <span className="font-semibold tabular-nums">
              {formatScorePair(latest.total_score, latest.max_total_score ?? 0)}
            </span>
          </p>
        )}

        <div className="grid gap-4 xl:grid-cols-[1.2fr_0.8fr]">
          <PaperViewerShell
            pages={liveData.pages}
            regions={liveData.regions}
            activePageId={pageId}
            selectedRegionId={selectedRegionId}
            onPageSelect={setActivePageId}
            onRegionSelect={setSelectedRegionId}
            title="Annotated evidence"
            showMarks
            mode="live"
            pageImageUrl={pageImageUrl}
          />
          <div className="space-y-3 rounded-md border border-slate-200 bg-white p-4">
            <h2 className="text-sm font-semibold text-slate-800">
              Annotation detail
            </h2>
            <div
              data-testid="annotation-score-chip"
              className="rounded-md bg-slate-900 px-3 py-2 text-sm font-semibold text-white"
            >
              {selectedQuestion
                ? `${selectedQuestion.question_code} ${formatScorePair(selectedQuestion.final_score, selectedQuestion.max_mark)}`
                : selectedLiveAnnotation
                  ? formatScorePair(
                      typeof selectedLiveAnnotation.payload.final_marks ===
                        "number"
                        ? selectedLiveAnnotation.payload.final_marks
                        : typeof selectedLiveAnnotation.payload.final_marks ===
                            "string"
                          ? Number(selectedLiveAnnotation.payload.final_marks)
                          : null,
                      typeof selectedLiveAnnotation.payload.max_marks ===
                        "number"
                        ? selectedLiveAnnotation.payload.max_marks
                        : typeof selectedLiveAnnotation.payload.max_marks ===
                            "string"
                          ? Number(selectedLiveAnnotation.payload.max_marks)
                          : 0,
                    )
                  : "—"}
            </div>

            {selectedLiveAnnotation && (
              <div
                data-testid="annotation-region-detail"
                className="rounded-md border border-teal-200 bg-teal-50/40 p-3"
              >
                <div className="text-sm font-medium text-slate-900">
                  {selectedLiveAnnotation.annotation_type}
                </div>
                <p className="mt-1 text-xs text-slate-600">
                  {typeof selectedLiveAnnotation.payload.reason === "string"
                    ? selectedLiveAnnotation.payload.reason
                    : typeof selectedLiveAnnotation.payload.text === "string"
                      ? selectedLiveAnnotation.payload.text
                      : "Ledger annotation"}
                </p>
              </div>
            )}

            <div>
              <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
                All questions (final scores)
              </h3>
              {liveData.questions.length === 0 ? (
                <p className="text-sm text-slate-500">
                  No final scores available yet.
                </p>
              ) : (
                liveData.questions.map((q) => (
                  <div
                    key={q.id}
                    className="mb-2 rounded-md border border-slate-100 px-3 py-2"
                  >
                    <div
                      data-testid={`annotated-final-score-${q.id}`}
                      className="text-sm font-medium text-slate-900"
                    >
                      {q.question_code}{" "}
                      {formatScorePair(q.final_score, q.max_mark)}
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </div>
    );
  }

  // —— Mock mode (unchanged behaviour) ——
  if (mockQuery.isLoading) return <LoadingState />;
  if (mockQuery.isError || !mockData) {
    return <ErrorState onRetry={() => void mockQuery.refetch()} />;
  }

  const mockActivePageId = activePageId ?? "page-1";
  const mockSelectedRegionId = selectedRegionId ?? "reg-2";
  const q = relatedLedger
    ? findQuestionById(mockData.questions, relatedLedger.question_id)
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
          pages={mockData.pages}
          regions={mockData.regions}
          activePageId={mockActivePageId}
          selectedRegionId={mockSelectedRegionId}
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
            {mockData.ledgers.map((ledger) => {
              const qq = findQuestionById(mockData.questions, ledger.question_id);
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
