"use client";

import { cn } from "@/lib/utils/cn";
import type { EvidenceRegion, PaperPage } from "@/lib/types/domain";
import { ConfidenceIndicator } from "@/components/ui/FeedbackStates";

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
}: {
  label: string;
  active?: boolean;
}) {
  return (
    <span
      data-testid="annotation-marker"
      className={cn(
        "inline-flex rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide",
        active
          ? "bg-teal-700 text-white"
          : "bg-slate-800/80 text-white",
      )}
    >
      {label}
    </span>
  );
}

export function EvidenceRegionOverlay({
  regions,
  selectedRegionId,
  onSelect,
}: {
  regions: EvidenceRegion[];
  selectedRegionId?: string | null;
  onSelect?: (regionId: string) => void;
}) {
  return (
    <div data-testid="evidence-region-overlay" className="absolute inset-0">
      {regions.map((region) => {
        const selected = selectedRegionId === region.id;
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
            style={{
              left: `${region.x}%`,
              top: `${region.y}%`,
              width: `${region.width}%`,
              height: `${region.height}%`,
            }}
            title={region.label}
          >
            <div className="absolute -top-5 left-0">
              <AnnotationMarker label={region.label} active={selected} />
            </div>
          </button>
        );
      })}
    </div>
  );
}

export function PaperViewerShell({
  pages,
  regions,
  activePageId,
  selectedRegionId,
  onPageSelect,
  onRegionSelect,
  title = "Answer paper",
}: {
  pages: PaperPage[];
  regions: EvidenceRegion[];
  activePageId: string;
  selectedRegionId?: string | null;
  onPageSelect: (pageId: string) => void;
  onRegionSelect?: (regionId: string) => void;
  title?: string;
}) {
  const pageRegions = regions.filter((r) => r.page_id === activePageId);
  const selected = regions.find((r) => r.id === selectedRegionId);

  return (
    <div
      data-testid="paper-viewer-shell"
      className="flex h-full min-h-[420px] flex-col overflow-hidden rounded-md border border-slate-200 bg-white"
    >
      <div className="flex items-center justify-between border-b border-slate-200 px-3 py-2">
        <h2 className="text-sm font-semibold text-slate-800">{title}</h2>
        <span className="text-xs text-slate-500">Placeholder viewer · no PDFs</span>
      </div>
      <PageThumbnailStrip
        pages={pages}
        activePageId={activePageId}
        onSelect={onPageSelect}
      />
      <div className="relative flex-1 bg-slate-100 p-4">
        <div className="relative mx-auto aspect-[8/11] max-h-full w-full max-w-md overflow-hidden rounded border border-slate-300 bg-[#f7f6f2] shadow-sm">
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
          />
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
