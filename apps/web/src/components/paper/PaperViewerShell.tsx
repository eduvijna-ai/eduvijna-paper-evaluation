"use client";

import { useMemo, useState } from "react";
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
}: {
  pages: PaperPage[];
  regions: EvidenceRegion[];
  activePageId: string;
  selectedRegionId?: string | null;
  onPageSelect: (pageId: string) => void;
  onRegionSelect?: (regionId: string) => void;
  title?: string;
  showMarks?: boolean;
}) {
  const [zoom, setZoom] = useState(1);
  const pageIndex = useMemo(
    () => pages.findIndex((p) => p.id === activePageId),
    [pages, activePageId],
  );
  const pageRegions = regions.filter((r) => r.page_id === activePageId);
  const selected = regions.find((r) => r.id === selectedRegionId);
  const activePage = pages[pageIndex] ?? pages[0];

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
          <span className="text-xs text-slate-500">Synthetic · no PDFs</span>
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
          <div className="relative aspect-[8/11] w-full overflow-hidden rounded border border-slate-300 bg-[#f7f6f2] shadow-sm">
            <div className="absolute inset-0 opacity-40">
              <div className="h-full w-full bg-[repeating-linear-gradient(0deg,transparent,transparent_23px,#e2e8f0_24px)]" />
            </div>
            <div className="absolute left-6 right-6 top-8 space-y-3 text-[10px] leading-relaxed text-slate-400">
              <div className="h-3 w-1/3 rounded bg-slate-300/60" />
              <div className="h-2 w-full rounded bg-slate-200/70" />
              <div className="h-2 w-5/6 rounded bg-slate-200/70" />
              <div className="h-2 w-4/5 rounded bg-slate-200/70" />
              <div className="mt-8 h-2 w-full rounded bg-slate-200/70" />
              <div className="h-2 w-11/12 rounded bg-slate-200/70" />
              <div className="h-2 w-3/4 rounded bg-slate-200/70" />
            </div>
            <EvidenceRegionOverlay
              regions={pageRegions}
              selectedRegionId={selectedRegionId}
              onSelect={onRegionSelect}
              showMarks={showMarks}
            />
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
