"use client";

import { use } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { PageHeader } from "@/components/layout/PageHeader";
import { ErrorState, LoadingState } from "@/components/ui/FeedbackStates";
import type { CurriculumNode } from "@/lib/types/domain";

function NodeList({ nodes, depth = 0 }: { nodes: CurriculumNode[]; depth?: number }) {
  return (
    <ul className="space-y-1">
      {nodes.map((node) => (
        <li key={node.id}>
          <div
            className="flex items-center gap-2 rounded-md px-2 py-1.5 text-sm"
            style={{ paddingLeft: 8 + depth * 14 }}
          >
            <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-slate-600">
              {node.node_type}
            </span>
            <span className="font-medium text-slate-900">{node.title}</span>
            <span className="text-xs text-slate-400">{node.code}</span>
          </div>
          {node.children && node.children.length > 0 && (
            <NodeList nodes={node.children} depth={depth + 1} />
          )}
        </li>
      ))}
    </ul>
  );
}

export default function CurriculumDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["curriculum", id],
    queryFn: () => api.getCurriculum(id),
  });

  if (isLoading) return <LoadingState />;
  if (isError || !data) return <ErrorState onRetry={() => void refetch()} />;

  return (
    <div data-testid="curriculum-detail-page">
      <PageHeader
        title={data.curriculum.title}
        description={`Framework ${data.curriculum.board} · Version ${data.curriculum.grade_label}`}
        breadcrumbs={[
          { label: "Curriculum", href: "/curriculum" },
          { label: data.curriculum.code },
        ]}
      />
      <div className="rounded-md border border-slate-200 bg-white p-4">
        {data.tree.length > 0 ? (
          <NodeList nodes={data.tree} />
        ) : (
          <p data-testid="curriculum-tree-empty" className="text-sm text-slate-500">
            No curriculum nodes yet.
          </p>
        )}
      </div>
    </div>
  );
}
