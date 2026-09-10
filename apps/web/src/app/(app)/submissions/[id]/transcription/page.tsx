"use client";

import { use, useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { api, isApiError } from "@/lib/api";
import { getApiCapabilities } from "@/lib/api/capabilities";
import { getSession, hasPermission } from "@/lib/auth/session";
import { PageHeader } from "@/components/layout/PageHeader";
import { PaperViewerShell } from "@/components/paper/PaperViewerShell";
import {
  ConfidenceIndicator,
  ErrorState,
  LoadingState,
} from "@/components/ui/FeedbackStates";
import { Button } from "@/components/ui/primitives";
import type {
  EvidenceRegion,
  PaperPage,
  TranscriptionQuestionItem,
  TranscriptionRegionView,
} from "@/lib/types/domain";
import { cn } from "@/lib/utils/cn";

function regionsToEvidence(
  items: TranscriptionQuestionItem[],
): EvidenceRegion[] {
  const regions: EvidenceRegion[] = [];
  for (const item of items) {
    for (const region of item.regions) {
      regions.push({
        id: region.id,
        page_id: `page-${(region.page_index ?? 0) + 1}`,
        page_number: (region.page_index ?? 0) + 1,
        x: region.bbox.x,
        y: region.bbox.y,
        width: region.bbox.width,
        height: region.bbox.height,
        label: region.label,
        confidence: region.detection_confidence,
        question_id: item.question_version_id,
        crossed_out: false,
        region_type: region.region_type,
        source_type: region.source_type,
      });
    }
  }
  return regions;
}

function syntheticPages(items: TranscriptionQuestionItem[]): PaperPage[] {
  const pageIndexes = new Set<number>();
  for (const item of items) {
    for (const region of item.regions) {
      pageIndexes.add(region.page_index ?? 0);
    }
  }
  if (pageIndexes.size === 0) {
    return [{ id: "page-1", page_number: 1, label: "Page 1", width: 800, height: 1100 }];
  }
  return [...pageIndexes]
    .sort((a, b) => a - b)
    .map((index) => ({
      id: `page-${index + 1}`,
      page_number: index + 1,
      label: `Page ${index + 1}`,
      width: 800,
      height: 1100,
    }));
}

function TranscriptionCopy({
  region,
}: {
  region: TranscriptionRegionView;
}) {
  const active = region.active_transcription;
  const ai = region.latest_ai_proposal;
  const isHuman =
    active?.source_type === "HUMAN" ||
    (active && ai && active.id !== ai.id);

  if (active?.unreadable) {
    return (
      <p className="text-sm text-amber-900" data-testid="transcription-unreadable">
        Marked unreadable — no text transcription.
      </p>
    );
  }
  if (active?.visual_only) {
    return (
      <p className="text-sm text-slate-700" data-testid="transcription-visual-only">
        Visual-only evidence — diagram or sketch without text transcription.
      </p>
    );
  }

  if (isHuman && active) {
    return (
      <div data-testid="transcription-human-copy">
        <p className="text-xs font-medium text-teal-800">
          Human-corrected transcription
        </p>
        <p className="mt-1 whitespace-pre-wrap text-sm text-slate-900">
          {active.text ?? active.latex ?? "—"}
        </p>
      </div>
    );
  }

  if (ai) {
    return (
      <div data-testid="transcription-ai-copy">
        <p className="text-xs font-medium text-violet-800">
          AI transcription proposal — review before evaluation
        </p>
        <p className="mt-1 whitespace-pre-wrap text-sm text-slate-900">
          {ai.text ?? ai.latex ?? "—"}
        </p>
        {ai.transcription_confidence !== null && (
          <div className="mt-2">
            <ConfidenceIndicator
              value={ai.transcription_confidence}
              label="Transcription confidence"
            />
          </div>
        )}
      </div>
    );
  }

  return (
    <p className="text-sm text-slate-500" data-testid="transcription-empty">
      No transcription yet — enter text or mark unreadable.
    </p>
  );
}

function RegionReviewPanel({
  region,
  cropUrl,
  actionsEnabled,
  busy,
  onSaveText,
  onConfirm,
  onMarkUnreadable,
  onMarkVisualOnly,
}: {
  region: TranscriptionRegionView;
  cropUrl: string | null;
  actionsEnabled: boolean;
  busy: boolean;
  onSaveText: (text: string) => void;
  onConfirm: () => void;
  onMarkUnreadable: () => void;
  onMarkVisualOnly: () => void;
}) {
  const active = region.active_transcription;
  const ai = region.latest_ai_proposal;
  const confirmable = active ?? ai;
  const draftSeed =
    active?.source_type === "HUMAN"
      ? active.text ?? ""
      : ai?.text ?? active?.text ?? "";
  const [draft, setDraft] = useState(draftSeed);

  useEffect(() => {
    setDraft(draftSeed);
  }, [draftSeed, region.id]);

  const confirmed = active?.status === "CONFIRMED";

  return (
    <div
      data-testid={`transcription-region-${region.id}`}
      className="rounded-md border border-slate-200 bg-white p-3"
    >
      <div className="flex items-start justify-between gap-2">
        <div>
          <h3 className="text-sm font-semibold text-slate-900">{region.label}</h3>
          {region.source_type === "AI" && (
            <span
              data-testid="region-ai-badge"
              className="mt-1 inline-flex rounded-md bg-violet-50 px-2 py-0.5 text-xs font-medium text-violet-800 ring-1 ring-violet-200"
            >
              AI proposal
            </span>
          )}
        </div>
        {region.detection_confidence > 0 && region.source_type === "AI" && (
          <ConfidenceIndicator
            value={region.detection_confidence}
            label="Detection confidence"
          />
        )}
      </div>

      {cropUrl && (
        <img
          src={cropUrl}
          alt={`Crop for ${region.label}`}
          data-testid="region-crop-thumb"
          className="mt-3 max-h-32 rounded border border-slate-200 object-contain"
        />
      )}

      <div className="mt-3">
        <TranscriptionCopy region={region} />
      </div>

      {actionsEnabled && (
        <div className="mt-4 space-y-2">
          <label className="block text-xs font-medium text-slate-700">
            Correct transcription
          </label>
          <textarea
            data-testid="transcription-text-input"
            className="w-full rounded-md border border-slate-200 px-3 py-2 text-sm"
            rows={3}
            value={draft}
            disabled={busy || confirmed}
            onChange={(e) => setDraft(e.target.value)}
          />
          <div className="flex flex-wrap gap-2">
            <Button
              size="sm"
              variant="secondary"
              data-testid="save-transcription"
              disabled={busy || confirmed || !draft.trim()}
              onClick={() => onSaveText(draft.trim())}
            >
              Save correction
            </Button>
            <Button
              size="sm"
              data-testid="confirm-transcription"
              disabled={busy || confirmed || !confirmable}
              onClick={onConfirm}
            >
              {confirmed ? "Confirmed" : "Accept / confirm"}
            </Button>
            <Button
              size="sm"
              variant="secondary"
              data-testid="mark-unreadable"
              disabled={busy || confirmed}
              onClick={onMarkUnreadable}
            >
              Mark unreadable
            </Button>
            <Button
              size="sm"
              variant="secondary"
              data-testid="mark-visual-only"
              disabled={busy || confirmed}
              onClick={onMarkVisualOnly}
            >
              Visual only
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}

function TranscriptionReview({ id }: { id: string }) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const live = getApiCapabilities().transcription === "live";
  const session = getSession();
  const canReview = hasPermission(session, "transcription:review");
  const canRead = canReview || hasPermission(session, "transcription:read");
  const actionsEnabled = live ? canReview : true;

  const [selectedRegionId, setSelectedRegionId] = useState<string | null>(null);
  const [activePageId, setActivePageId] = useState("");
  const [pageImageUrl, setPageImageUrl] = useState<string | null>(null);
  const [cropUrls, setCropUrls] = useState<Record<string, string>>({});
  const [actionError, setActionError] = useState<string | null>(null);
  const [forbidden, setForbidden] = useState(false);

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["transcription", id],
    queryFn: () => api.getTranscriptionWorkspace!(id),
    retry: (count, err) => {
      if (isApiError(err) && err.status === 403) return false;
      return count < 2;
    },
  });

  useEffect(() => {
    if (isApiError(error) && error.status === 403) {
      setForbidden(true);
    }
  }, [error]);

  const pages = useMemo(
    () => (data ? syntheticPages(data.items) : []),
    [data],
  );
  const evidenceRegions = useMemo(
    () => (data ? regionsToEvidence(data.items) : []),
    [data],
  );

  useEffect(() => {
    if (!pages.length) return;
    setActivePageId((current) => {
      if (current && pages.some((p) => p.id === current)) return current;
      return pages[0]!.id;
    });
  }, [pages]);

  useEffect(() => {
    if (!data?.items.length) return;
    const firstRegion = data.items
      .flatMap((item) => item.regions)
      .find((r) => r.requires_transcription);
    if (firstRegion && !selectedRegionId) {
      setSelectedRegionId(firstRegion.id);
    }
  }, [data, selectedRegionId]);

  useEffect(() => {
    if (!live || !activePageId || !api.getSubmissionPageImageBlob) {
      setPageImageUrl(null);
      return;
    }
    const page = pages.find((p) => p.id === activePageId);
    if (!page) return;
    let revoked = false;
    let objectUrl: string | null = null;
    void api
      .getSubmissionPageImageBlob(page.id)
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
  }, [live, activePageId, pages]);

  useEffect(() => {
    if (!live || !api.getRegionCropBlob || !data) return;
    const regionIds = data.items.flatMap((item) =>
      item.regions.filter((r) => r.requires_transcription).map((r) => r.id),
    );
    const urls: Record<string, string> = {};
    let cancelled = false;
    void Promise.all(
      regionIds.map(async (regionId) => {
        try {
          const blob = await api.getRegionCropBlob!(regionId);
          if (cancelled) return;
          urls[regionId] = URL.createObjectURL(blob);
        } catch {
          /* crop may be unavailable */
        }
      }),
    ).then(() => {
      if (!cancelled) setCropUrls(urls);
    });
    return () => {
      cancelled = true;
      Object.values(urls).forEach((url) => URL.revokeObjectURL(url));
    };
  }, [live, data]);

  const invalidate = async () => {
    await queryClient.invalidateQueries({ queryKey: ["transcription", id] });
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

  const saveMutation = useMutation({
    mutationFn: (input: { regionId: string; text: string }) =>
      api.putRegionTranscription!(input.regionId, { text: input.text }),
    onSuccess: async () => {
      setActionError(null);
      await invalidate();
    },
    onError: onMutationError,
  });

  const unreadableMutation = useMutation({
    mutationFn: (regionId: string) =>
      api.putRegionTranscription!(regionId, { unreadable: true, outcome: "UNREADABLE" }),
    onSuccess: async () => {
      setActionError(null);
      await invalidate();
    },
    onError: onMutationError,
  });

  const visualMutation = useMutation({
    mutationFn: (regionId: string) =>
      api.putRegionTranscription!(regionId, { visual_only: true, outcome: "VISUAL_ONLY" }),
    onSuccess: async () => {
      setActionError(null);
      await invalidate();
    },
    onError: onMutationError,
  });

  const confirmMutation = useMutation({
    mutationFn: (transcriptionId: string) =>
      api.confirmTranscription!(transcriptionId),
    onSuccess: async () => {
      setActionError(null);
      await invalidate();
    },
    onError: onMutationError,
  });

  const finalizeMutation = useMutation({
    mutationFn: () => api.finalizeTranscription!(id),
    onSuccess: () => {
      setActionError(null);
      // Navigate immediately so slow query invalidation under CI load cannot stall
      // the post-finalize UI transition (APP-013.1 reliability).
      router.push(`/submissions/${id}`);
      void invalidate();
    },
    onError: onMutationError,
  });

  const busy =
    saveMutation.isPending ||
    unreadableMutation.isPending ||
    visualMutation.isPending ||
    confirmMutation.isPending ||
    finalizeMutation.isPending;

  if (!canRead && session && live) {
    return (
      <ErrorState
        title="No transcription access"
        message="You need transcription:read or transcription:review to open this workspace."
      />
    );
  }

  if (forbidden || (isApiError(error) && error.status === 403)) {
    return (
      <ErrorState
        title="Transcription access denied"
        message="You do not have permission to view this transcription workspace (transcription:read required)."
      />
    );
  }

  if (isLoading) return <LoadingState />;
  if (isError || !data) return <ErrorState onRetry={() => void refetch()} />;

  return (
    <div data-testid="transcription-review-page" data-transcription-mode={live ? "live" : "mock"}>
      <PageHeader
        title="Transcription review"
        description="Confirm AI proposals or enter human corrections before evaluation."
        breadcrumbs={[
          { label: "Submissions", href: "/submissions" },
          { label: id, href: `/submissions/${id}` },
          { label: "Transcription" },
        ]}
      />

      <p
        data-testid="transcription-progress"
        className="mb-3 text-sm font-medium text-slate-800"
      >
        {data.progress.label}
      </p>

      {data.automated_transcription_active && (
        <p
          data-testid="transcription-automated-notice"
          className="mb-3 rounded-md border border-violet-200 bg-violet-50 px-3 py-2 text-xs text-violet-950"
        >
          Automated transcription is active — review each AI proposal before confirming.
        </p>
      )}

      {live && canRead && !canReview && (
        <p
          data-testid="transcription-readonly-notice"
          className="mb-3 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-950"
        >
          Read-only access — transcription:review is required to edit or confirm.
        </p>
      )}

      {actionError && (
        <p
          data-testid="transcription-action-error"
          className="mb-3 rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-900"
        >
          {actionError}
        </p>
      )}

      <div
        data-testid="transcription-layout"
        className="grid min-h-[70vh] gap-3 xl:grid-cols-[minmax(280px,1.1fr)_minmax(320px,1fr)]"
      >
        <PaperViewerShell
          pages={pages}
          regions={evidenceRegions}
          activePageId={activePageId || pages[0]?.id || ""}
          selectedRegionId={selectedRegionId}
          onPageSelect={setActivePageId}
          onRegionSelect={setSelectedRegionId}
          title="Evidence viewer"
          mode={live ? "live" : "synthetic"}
          pageImageUrl={live ? pageImageUrl : null}
        />

        <div className="flex min-h-[420px] flex-col gap-4 overflow-y-auto">
          {data.items.map((item) => (
            <section
              key={item.question_version_id}
              data-testid={`transcription-question-${item.question_version_id}`}
              className="rounded-md border border-slate-200 bg-slate-50 p-3"
            >
              <h2 className="text-sm font-semibold text-slate-900">
                {item.question_label}
                {item.disposition === "BLANK" && (
                  <span className="ml-2 text-xs font-normal text-slate-500">
                    (blank)
                  </span>
                )}
              </h2>
              <div className="mt-2 space-y-3">
                {item.regions.length === 0 ? (
                  <p className="text-xs text-slate-500">No evidence regions.</p>
                ) : (
                  item.regions.map((region) => (
                    <div
                      key={region.id}
                      className={cn(
                        "cursor-pointer",
                        selectedRegionId === region.id && "ring-2 ring-teal-600 rounded-md",
                      )}
                      onClick={() => setSelectedRegionId(region.id)}
                    >
                      <RegionReviewPanel
                        region={region}
                        cropUrl={cropUrls[region.id] ?? null}
                        actionsEnabled={actionsEnabled && region.requires_transcription}
                        busy={busy}
                        onSaveText={(text) =>
                          saveMutation.mutate({ regionId: region.id, text })
                        }
                        onConfirm={() => {
                          const txId =
                            region.active_transcription?.id ??
                            region.latest_ai_proposal?.id;
                          if (txId) confirmMutation.mutate(txId);
                        }}
                        onMarkUnreadable={() => unreadableMutation.mutate(region.id)}
                        onMarkVisualOnly={() => visualMutation.mutate(region.id)}
                      />
                    </div>
                  ))
                )}
              </div>
            </section>
          ))}

          {actionsEnabled && (
            <Button
              data-testid="finalize-transcription"
              disabled={busy}
              onClick={() => finalizeMutation.mutate()}
            >
              Finalize transcription
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}

export default function TranscriptionReviewPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  return <TranscriptionReview id={id} />;
}
