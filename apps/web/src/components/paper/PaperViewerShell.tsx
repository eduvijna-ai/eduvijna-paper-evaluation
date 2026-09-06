"use client";

import { useMemo, useRef, useState } from "react";
import { cn } from "@/lib/utils/cn";
import type {
  EvidenceRegion,
  NormalizedRect,
  PaperDocument,
  PaperPage,
} from "@/lib/types/domain";
import { ConfidenceIndicator } from "@/components/ui/FeedbackStates";

export type { NormalizedRect, PaperDocument };

/** Convert normalized 0–1 rect to CSS percentage styles. */
export function normalizedRectToPercentStyle(rect: Pick<
  NormalizedRect,
  "x" | "y" | "width" | "height"
>): React.CSSProperties {
  return {
    left: `${rect.x * 100}%`,
    top: `${rect.y * 100}%`,
    width: `${rect.width * 100}%`,
    height: `${rect.height * 100}%`,
  };
}

/**
 * Convert a client-space drag (pointer events) into a normalized 0–1 bbox
 * relative to the unscaled page box. Prefer `getBoundingClientRect` of the
 * page element so CSS zoom transforms are accounted for correctly.
 */
export function clientRectToNormalizedBBox(
  pageEl: HTMLElement,
  start: { x: number; y: number },
  end: { x: number; y: number },
): { x: number; y: number; width: number; height: number } {
  const rect = pageEl.getBoundingClientRect();
  const width = rect.width || 1;
  const height = rect.height || 1;
  const clamp01 = (v: number) => Math.min(1, Math.max(0, v));
  const round6 = (v: number) => Math.round(v * 1e6) / 1e6;
  const x1 = clamp01((Math.min(start.x, end.x) - rect.left) / width);
  const y1 = clamp01((Math.min(start.y, end.y) - rect.top) / height);
  const x2 = clamp01((Math.max(start.x, end.x) - rect.left) / width);
  const y2 = clamp01((Math.max(start.y, end.y) - rect.top) / height);
  return {
    x: round6(x1),
    y: round6(y1),
    width: round6(Math.max(0, x2 - x1)),
    height: round6(Math.max(0, y2 - y1)),
  };
}

export const SYNTHETIC_DEMO_DOCUMENT: PaperDocument = {
  id: "doc-demo-001",
  title: "Synthetic demo answer sheet",
  page_count: 2,
  pages: [
    { id: "page-1", page_number: 1, label: "Page 1", width: 800, height: 1100 },
    { id: "page-2", page_number: 2, label: "Page 2", width: 800, height: 1100 },
  ],
};

const MARK_GLYPH: Record<
  NonNullable<EvidenceRegion["annotation_kind"]>,
  string
> = {
  FULL: "✓",
  PARTIAL: "△",
  DEDUCTION: "✕",
  NEUTRAL: "·",
};

export function PageThumbnailStrip({
  pages,
  activePageId,
  onSelect,
}: {
  pages: PaperPage[];
  activePageId: string;
  onSelect: (pageId: string) => void;
}) {
  return (
    <div
      data-testid="page-thumbnail-strip"
      className="flex gap-2 overflow-x-auto border-b border-slate-200 bg-slate-50 p-2"
    >
      {pages.map((page) => (
        <button
          key={page.id}
          type="button"
          data-testid={`page-thumb-${page.page_number}`}
          onClick={() => onSelect(page.id)}
          className={cn(
            "flex h-20 w-14 shrink-0 flex-col items-center justify-end rounded border bg-white p-1 text-[10px]",
            activePageId === page.id
              ? "border-teal-600 ring-1 ring-teal-600"
              : "border-slate-200 hover:border-slate-300",
          )}
        >
          <div className="mb-1 h-full w-full rounded-sm bg-gradient-to-b from-slate-100 to-slate-200" />
          {page.label}
        </button>
      ))}
    </div>
  );
}

export function AnnotationMarker({
  label,
  active,
  kind,
  rect,
}: {
  label: string;
  active?: boolean;
  kind?: EvidenceRegion["annotation_kind"];
  /** When provided, positions marker using normalized page coords */
  rect?: Pick<NormalizedRect, "x" | "y">;
}) {
  const glyph = kind ? MARK_GLYPH[kind] : null;
  return (
    <span
      data-testid="annotation-marker"
      data-kind={kind ?? "none"}
      className={cn(
        "inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide",
        active ? "bg-teal-700 text-white" : "bg-slate-800/80 text-white",
        rect && "absolute",
      )}
      style={
        rect
          ? { left: `${rect.x * 100}%`, top: `${rect.y * 100}%` }
          : undefined
      }
    >
      {glyph && <span aria-hidden>{glyph}</span>}
      {label}
    </span>
  );
}

export function EvidenceRegionOverlay({
  regions,
  selectedRegionId,
  onSelect,
  showMarks = false,
}: {
  regions: EvidenceRegion[];
  selectedRegionId?: string | null;
  onSelect?: (regionId: string) => void;
  showMarks?: boolean;
}) {
  return (
    <div data-testid="evidence-region-overlay" className="absolute inset-0">
      {regions.map((region) => {
        const selected = selectedRegionId === region.id;
        const mark = region.annotation_kind;
        return (
          <button
            key={region.id}
            type="button"
            data-testid={`evidence-region-${region.id}`}
            onClick={() => onSelect?.(region.id)}
            className={cn(
              "absolute rounded-sm border-2 text-left transition-colors",
              region.crossed_out
                ? "border-slate-400 border-dashed bg-slate-400/10"
                : selected
                  ? "border-teal-600 bg-teal-500/15"
                  : "border-sky-500/70 bg-sky-400/10 hover:bg-sky-400/20",
            )}
            style={normalizedRectToPercentStyle(region)}
            title={region.label}
            aria-label={`${region.label}${mark ? `, ${mark}` : ""}`}
          >
            <div className="absolute -top-5 left-0">
              <AnnotationMarker
                label={
                  showMarks && mark && mark !== "NEUTRAL"
                    ? `${MARK_GLYPH[mark]} ${region.label}`
                    : region.label
                }
                active={selected}
                kind={showMarks ? mark : undefined}
              />
            </div>
          </button>
        );
      })}
    </div>
  );
}

const ZOOM_STEPS = [0.75, 1, 1.25, 1.5, 2] as const;

export function PaperViewerShell({
  pages,
  regions,
  activePageId,
  selectedRegionId,
  onPageSelect,
  onRegionSelect,
  title = "Answer paper",
  showMarks = false,
  mode = "synthetic",
  pageImageUrl = null,
  drawEnabled = false,
  onRegionDrawn,
}: {
  pages: PaperPage[];
  regions: EvidenceRegion[];
  activePageId: string;
  selectedRegionId?: string | null;
  onPageSelect: (pageId: string) => void;
  onRegionSelect?: (regionId: string) => void;
  title?: string;
  showMarks?: boolean;
  /** Live B3 pages render a real PNG; synthetic keeps the fixture sketch. */
  mode?: "synthetic" | "live";
  pageImageUrl?: string | null;
  /** When true, pointer drag draws a new normalized region on the page surface. */
  drawEnabled?: boolean;
  onRegionDrawn?: (bbox: {
    x: number;
    y: number;
    width: number;
    height: number;
  }) => void;
}) {
  const [zoom, setZoom] = useState(1);
  const pageSurfaceRef = useRef<HTMLDivElement>(null);
  const dragStartRef = useRef<{ x: number; y: number } | null>(null);
  const [draftBBox, setDraftBBox] = useState<{
    x: number;
    y: number;
    width: number;
    height: number;
  } | null>(null);

  const pageIndex = useMemo(
    () => pages.findIndex((p) => p.id === activePageId),
    [pages, activePageId],
  );
  const pageRegions = regions.filter((r) => r.page_id === activePageId);
  const selected = regions.find((r) => r.id === selectedRegionId);
  const activePage = pages[pageIndex] ?? pages[0];
  const liveImage = mode === "live" && Boolean(pageImageUrl);

  const goPage = (delta: number) => {
    const next = pages[pageIndex + delta];
    if (next) onPageSelect(next.id);
  };

  const zoomIn = () => {
    const idx = ZOOM_STEPS.findIndex((z) => z >= zoom);
    const next = ZOOM_STEPS[Math.min(ZOOM_STEPS.length - 1, Math.max(0, idx) + (ZOOM_STEPS[idx] === zoom ? 1 : 0))];
    if (next) setZoom(next);
  };
  const zoomOut = () => {
    const idx = [...ZOOM_STEPS].reverse().findIndex((z) => z <= zoom);
    const fromEnd = idx === -1 ? 0 : ZOOM_STEPS.length - 1 - idx;
    const next = ZOOM_STEPS[Math.max(0, fromEnd - (ZOOM_STEPS[fromEnd] === zoom ? 1 : 0))];
    if (next) setZoom(next);
  };

  const finishDraw = (clientX: number, clientY: number) => {
    const start = dragStartRef.current;
    const pageEl = pageSurfaceRef.current;
    dragStartRef.current = null;
    setDraftBBox(null);
    if (!start || !pageEl || !onRegionDrawn) return;
    const bbox = clientRectToNormalizedBBox(
      pageEl,
      start,
      { x: clientX, y: clientY },
    );
    if (bbox.width < 0.01 || bbox.height < 0.01) return;
    onRegionDrawn(bbox);
  };

  return (
    <div
      data-testid="paper-viewer-shell"
      className="flex h-full min-h-[420px] flex-col overflow-hidden rounded-md border border-slate-200 bg-white"
    >
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200 px-3 py-2">
        <h2 className="text-sm font-semibold text-slate-800">{title}</h2>
        <div className="flex items-center gap-2">
          <div
            data-testid="paper-page-nav"
            className="flex items-center gap-1 rounded-md border border-slate-200 bg-slate-50 px-1 py-0.5"
          >
            <button
              type="button"
              data-testid="paper-page-prev"
              disabled={pageIndex <= 0}
              onClick={() => goPage(-1)}
              className="rounded px-2 py-1 text-xs text-slate-700 hover:bg-white disabled:opacity-40"
            >
              Prev
            </button>
            <span className="px-1 text-xs tabular-nums text-slate-600">
              {activePage?.page_number ?? 1}/{pages.length}
            </span>
            <button
              type="button"
              data-testid="paper-page-next"
              disabled={pageIndex >= pages.length - 1}
              onClick={() => goPage(1)}
              className="rounded px-2 py-1 text-xs text-slate-700 hover:bg-white disabled:opacity-40"
            >
              Next
            </button>
          </div>
          <div
            data-testid="paper-zoom-controls"
            className="flex items-center gap-1 rounded-md border border-slate-200 bg-slate-50 px-1 py-0.5"
          >
            <button
              type="button"
              data-testid="paper-zoom-out"
              onClick={zoomOut}
              className="rounded px-2 py-1 text-xs text-slate-700 hover:bg-white"
            >
              −
            </button>
            <span className="min-w-[3rem] text-center text-xs tabular-nums text-slate-600">
              {Math.round(zoom * 100)}%
            </span>
            <button
              type="button"
              data-testid="paper-zoom-in"
              onClick={zoomIn}
              className="rounded px-2 py-1 text-xs text-slate-700 hover:bg-white"
            >
              +
            </button>
          </div>
          <span className="text-xs text-slate-500">
            {drawEnabled
              ? "Draw mode"
              : liveImage
                ? "Live page image"
                : "Synthetic · no PDFs"}
          </span>
        </div>
      </div>
      <PageThumbnailStrip
        pages={pages}
        activePageId={activePageId}
        onSelect={onPageSelect}
      />
      <div className="relative flex-1 overflow-auto bg-slate-100 p-4">
        <div
          className="relative mx-auto origin-top transition-transform"
          style={{
            transform: `scale(${zoom})`,
            width: "100%",
            maxWidth: 448,
          }}
        >
          <div
            ref={pageSurfaceRef}
            data-testid="paper-page-surface"
            className={cn(
              "relative aspect-[8/11] w-full overflow-hidden rounded border border-slate-300 bg-[#f7f6f2] shadow-sm",
              drawEnabled && "cursor-crosshair",
            )}
            onPointerDown={(e) => {
              if (!drawEnabled) return;
              e.currentTarget.setPointerCapture(e.pointerId);
              dragStartRef.current = { x: e.clientX, y: e.clientY };
              setDraftBBox({ x: 0, y: 0, width: 0, height: 0 });
            }}
            onPointerMove={(e) => {
              if (!drawEnabled || !dragStartRef.current || !pageSurfaceRef.current) {
                return;
              }
              setDraftBBox(
                clientRectToNormalizedBBox(
                  pageSurfaceRef.current,
                  dragStartRef.current,
                  { x: e.clientX, y: e.clientY },
                ),
              );
            }}
            onPointerUp={(e) => {
              if (!drawEnabled) return;
              finishDraw(e.clientX, e.clientY);
            }}
            onPointerCancel={() => {
              dragStartRef.current = null;
              setDraftBBox(null);
            }}
          >
            {liveImage ? (
              // eslint-disable-next-line @next/next/no-img-element -- blob URLs from authenticated fetch
              <img
                data-testid="live-page-image"
                src={pageImageUrl!}
                alt={activePage?.label ?? "Submission page"}
                className="pointer-events-none absolute inset-0 h-full w-full object-contain bg-white"
                draggable={false}
              />
            ) : (
              <>
                <div className="pointer-events-none absolute inset-0 opacity-40">
                  <div className="h-full w-full bg-[repeating-linear-gradient(0deg,transparent,transparent_23px,#e2e8f0_24px)]" />
                </div>
                <div className="pointer-events-none absolute left-6 right-6 top-8 space-y-3 text-[10px] leading-relaxed text-slate-400">
                  <div className="h-3 w-1/3 rounded bg-slate-300/60" />
                  <div className="h-2 w-full rounded bg-slate-200/70" />
                  <div className="h-2 w-5/6 rounded bg-slate-200/70" />
                  <div className="h-2 w-4/5 rounded bg-slate-200/70" />
                  <div className="mt-8 h-2 w-full rounded bg-slate-200/70" />
                  <div className="h-2 w-11/12 rounded bg-slate-200/70" />
                  <div className="h-2 w-3/4 rounded bg-slate-200/70" />
                </div>
              </>
            )}
            <EvidenceRegionOverlay
              regions={pageRegions}
              selectedRegionId={selectedRegionId}
              onSelect={drawEnabled ? undefined : onRegionSelect}
              showMarks={showMarks}
            />
            {draftBBox && draftBBox.width > 0 && draftBBox.height > 0 && (
              <div
                data-testid="draw-draft-region"
                className="pointer-events-none absolute border-2 border-dashed border-teal-600 bg-teal-500/20"
                style={normalizedRectToPercentStyle(draftBBox)}
              />
            )}
          </div>
        </div>
      </div>
      {selected && (
        <div className="border-t border-slate-200 px-3 py-2">
          <ConfidenceIndicator
            value={selected.confidence}
            label={`Region: ${selected.label}`}
          />
        </div>
      )}
    </div>
  );
}
