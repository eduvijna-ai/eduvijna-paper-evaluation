"use client";

import { use, useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { getApiCapabilities } from "@/lib/api/capabilities";
import { isApiError } from "@/lib/api/http/errors";
import { PageHeader } from "@/components/layout/PageHeader";
import { ErrorState, LoadingState } from "@/components/ui/FeedbackStates";
import type { CurriculumNode, Question } from "@/lib/types/domain";

function isActiveRunStatus(status: string | undefined): boolean {
  return status === "QUEUED" || status === "RUNNING";
}

function leafQuestions(nodes: Question[]): Question[] {
  return nodes.flatMap((node) => {
    if (node.is_leaf_scorable || !node.children?.length) {
      return [node];
    }
    return leafQuestions(node.children);
  });
}

function flattenNodeTitles(nodes: CurriculumNode[]): Map<string, string> {
  const titles = new Map<string, string>();
  const visit = (items: CurriculumNode[]) => {
    for (const node of items) {
      titles.set(node.id, node.title || node.code);
      if (node.children?.length) visit(node.children);
    }
  };
  visit(nodes);
  return titles;
}

function CanonicalMapTable({
  rows,
}: {
  rows: Array<{
    question_id: string;
    question_code: string;
    node_titles: string[];
  }>;
}) {
  return (
    <div className="overflow-x-auto rounded-md border border-slate-200 bg-white">
      <table className="min-w-full text-left text-sm" data-testid="curriculum-map-table">
        <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
          <tr>
            <th className="px-3 py-2.5 font-medium">Question</th>
            <th className="px-3 py-2.5 font-medium">Curriculum nodes</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {rows.map((row) => (
            <tr key={row.question_id} data-testid={`curriculum-map-row-${row.question_code}`}>
              <td className="px-3 py-2.5 font-medium text-slate-900">
                {row.question_code}
              </td>
              <td className="px-3 py-2.5 text-slate-700">
                {row.node_titles.length > 0 ? row.node_titles.join(" · ") : "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function LiveCurriculumMapPage({ id }: { id: string }) {
  const queryClient = useQueryClient();
  const [selectedQuestionId, setSelectedQuestionId] = useState<string>("");
  const [activeRunId, setActiveRunId] = useState<string | null>(null);
  const [selectedIndices, setSelectedIndices] = useState<Set<number>>(new Set());
  const [actionError, setActionError] = useState<string | null>(null);

  const assessmentQuery = useQuery({
    queryKey: ["assessment", id],
    queryFn: () => api.getAssessment(id),
  });
  const mapQuery = useQuery({
    queryKey: ["assessment-curriculum-map", id],
    queryFn: () => api.getAssessmentCurriculumMap(id),
  });
  const questionsQuery = useQuery({
    queryKey: ["assessment-questions", id],
    queryFn: () => api.getAssessmentQuestions(id),
  });
  const curriculumQuery = useQuery({
    queryKey: ["curriculum", assessmentQuery.data?.curriculum_id],
    queryFn: () => api.getCurriculum(assessmentQuery.data!.curriculum_id),
    enabled: Boolean(assessmentQuery.data?.curriculum_id),
  });

  const runQuery = useQuery({
    queryKey: ["authoring-ai-run", activeRunId],
    queryFn: () => api.getAuthoringAiRun!(activeRunId!),
    enabled: Boolean(activeRunId),
    refetchInterval: (q) =>
      isActiveRunStatus(q.state.data?.status) ? 2000 : false,
  });

  const leaves = useMemo(
    () => leafQuestions(questionsQuery.data ?? []),
    [questionsQuery.data],
  );

  const nodeTitles = useMemo(
    () => flattenNodeTitles(curriculumQuery.data?.tree ?? []),
    [curriculumQuery.data?.tree],
  );

  const proposedMappings = useMemo(() => {
    const run = runQuery.data;
    if (run?.status !== "REVIEW_REQUIRED") return [];
    const raw = run.proposal_payload?.mappings;
    return Array.isArray(raw) ? raw : [];
  }, [runQuery.data]);

  useEffect(() => {
    if (!selectedQuestionId && leaves.length > 0) {
      setSelectedQuestionId(leaves[0].id);
    }
  }, [leaves, selectedQuestionId]);

  useEffect(() => {
    if (proposedMappings.length > 0) {
      setSelectedIndices(new Set(proposedMappings.map((_, index) => index)));
    } else {
      setSelectedIndices(new Set());
    }
  }, [proposedMappings]);

  useEffect(() => {
    const status = runQuery.data?.status;
    if (status === "FAILED" || status === "UNAVAILABLE") {
      setActionError(
        runQuery.data?.failure_detail ||
          runQuery.data?.failure_code ||
          "Curriculum mapping suggestion failed",
      );
      setActiveRunId(null);
    }
  }, [runQuery.data?.status, runQuery.data?.failure_code, runQuery.data?.failure_detail]);

  const proposeMutation = useMutation({
    mutationFn: () =>
      api.prepareAiCurriculumMappingProposal!({
        questionVersionId: selectedQuestionId,
        curriculumId: assessmentQuery.data?.curriculum_id,
      }),
    onSuccess: (run) => {
      setActionError(null);
      queryClient.setQueryData(["authoring-ai-run", run.id], run);
      setActiveRunId(run.id);
    },
    onError: (err) => {
      setActionError(
        isApiError(err) ? err.message : "AI curriculum suggestion failed",
      );
    },
  });

  const applyMutation = useMutation({
    mutationFn: () =>
      api.applyCurriculumMappings!(
        activeRunId!,
        [...selectedIndices].sort((a, b) => a - b),
      ),
    onSuccess: async (run) => {
      setActionError(null);
      queryClient.setQueryData(["authoring-ai-run", run.id], run);
      if (run.status === "SUCCEEDED") {
        setActiveRunId(null);
        setSelectedIndices(new Set());
        await queryClient.invalidateQueries({
          queryKey: ["assessment-curriculum-map", id],
        });
      }
    },
    onError: (err) => {
      setActionError(
        isApiError(err) ? err.message : "Apply curriculum mappings failed",
      );
    },
  });

  if (
    assessmentQuery.isLoading ||
    mapQuery.isLoading ||
    questionsQuery.isLoading
  ) {
    return <LoadingState />;
  }
  if (
    assessmentQuery.isError ||
    mapQuery.isError ||
    questionsQuery.isError ||
    !assessmentQuery.data ||
    !mapQuery.data ||
    !questionsQuery.data
  ) {
    return <ErrorState onRetry={() => void mapQuery.refetch()} />;
  }

  const editable =
    assessmentQuery.data.workflow_state === "DRAFT" ||
    assessmentQuery.data.workflow_state === "RUBRIC_REVIEW";
  const generating = isActiveRunStatus(runQuery.data?.status);
  const reviewing =
    runQuery.data?.status === "REVIEW_REQUIRED" && proposedMappings.length > 0;

  return (
    <div data-testid="assessment-curriculum-map-page" data-authoring-mode="live">
      <PageHeader
        title="Curriculum map"
        description={`Question → curriculum node links for ${assessmentQuery.data.title}`}
        breadcrumbs={[
          { label: "Assessments", href: "/assessments" },
          {
            label: assessmentQuery.data.code,
            href: `/assessments/${id}`,
          },
          { label: "Curriculum map" },
        ]}
      />

      <CanonicalMapTable rows={mapQuery.data} />

      {editable && (
        <section
          data-testid="curriculum-mapping-authoring"
          className="mt-4 space-y-3 rounded-md border border-slate-200 bg-white p-4"
        >
          <p
            data-testid="curriculum-mapping-truth-notice"
            className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900"
          >
            AI suggestions require teacher apply. Suggested nodes are not
            canonical curriculum mappings until you apply them.
          </p>

          {actionError && (
            <p
              data-testid="curriculum-mapping-error"
              className="text-sm text-red-700"
            >
              {actionError}
            </p>
          )}

          <div className="flex flex-wrap items-end gap-3">
            <label className="flex min-w-[12rem] flex-1 flex-col gap-1 text-sm text-slate-700">
              Scorable question
              <select
                data-testid="curriculum-mapping-question-select"
                className="rounded border border-slate-300 px-2 py-1.5 text-sm"
                value={selectedQuestionId}
                onChange={(e) => {
                  setSelectedQuestionId(e.target.value);
                  setActiveRunId(null);
                  setActionError(null);
                }}
              >
                {leaves.map((question) => (
                  <option key={question.id} value={question.id}>
                    {question.code} — {question.prompt.slice(0, 60)}
                  </option>
                ))}
              </select>
            </label>
            <button
              type="button"
              data-testid="generate-ai-curriculum-mapping"
              className="rounded-md bg-teal-800 px-3 py-1.5 text-sm font-medium text-white hover:bg-teal-900 disabled:opacity-50"
              disabled={
                !selectedQuestionId ||
                proposeMutation.isPending ||
                generating ||
                applyMutation.isPending
              }
              onClick={() => proposeMutation.mutate()}
            >
              Generate AI suggestion
            </button>
          </div>

          {generating && (
            <p
              data-testid="curriculum-mapping-run-status"
              className="text-sm text-slate-600"
            >
              AI run status: {runQuery.data?.status}
            </p>
          )}

          {reviewing && (
            <div
              data-testid="curriculum-mapping-proposal"
              className="space-y-2 rounded-md border border-dashed border-slate-300 bg-slate-50 p-3"
            >
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                AI suggestion (not applied)
              </p>
              <ul className="space-y-2">
                {proposedMappings.map((mapping, index) => {
                  const nodeId = String(mapping.curriculum_node_id ?? "");
                  const title = nodeTitles.get(nodeId) ?? nodeId;
                  const checked = selectedIndices.has(index);
                  return (
                    <li
                      key={`${nodeId}-${index}`}
                      data-testid={`curriculum-mapping-proposal-row-${index}`}
                      className="flex items-start gap-2 text-sm text-slate-800"
                    >
                      <input
                        type="checkbox"
                        data-testid={`curriculum-mapping-select-${index}`}
                        className="mt-1"
                        checked={checked}
                        onChange={(e) => {
                          setSelectedIndices((prev) => {
                            const next = new Set(prev);
                            if (e.target.checked) next.add(index);
                            else next.delete(index);
                            return next;
                          });
                        }}
                      />
                      <div>
                        <div className="font-medium">{title}</div>
                        <div className="text-xs text-slate-500">
                          {mapping.mapping_type ?? "PRIMARY"}
                          {mapping.rationale ? ` · ${mapping.rationale}` : ""}
                        </div>
                      </div>
                    </li>
                  );
                })}
              </ul>
              <button
                type="button"
                data-testid="apply-curriculum-mappings"
                className="rounded-md bg-teal-800 px-3 py-1.5 text-sm font-medium text-white hover:bg-teal-900 disabled:opacity-50"
                disabled={
                  selectedIndices.size === 0 || applyMutation.isPending
                }
                onClick={() => applyMutation.mutate()}
              >
                Apply selected mappings
              </button>
            </div>
          )}
        </section>
      )}
    </div>
  );
}

function MockCurriculumMapPage({ id }: { id: string }) {
  const assessmentQuery = useQuery({
    queryKey: ["assessment", id],
    queryFn: () => api.getAssessment(id),
  });
  const mapQuery = useQuery({
    queryKey: ["assessment-curriculum-map", id],
    queryFn: () => api.getAssessmentCurriculumMap(id),
  });

  if (assessmentQuery.isLoading || mapQuery.isLoading) return <LoadingState />;
  if (
    assessmentQuery.isError ||
    mapQuery.isError ||
    !assessmentQuery.data ||
    !mapQuery.data
  ) {
    return <ErrorState onRetry={() => void mapQuery.refetch()} />;
  }

  return (
    <div data-testid="assessment-curriculum-map-page" data-authoring-mode="mock">
      <PageHeader
        title="Curriculum map"
        description={`Question → curriculum node links for ${assessmentQuery.data.title}`}
        breadcrumbs={[
          { label: "Assessments", href: "/assessments" },
          { label: assessmentQuery.data.code, href: `/assessments/${id}` },
          { label: "Curriculum map" },
        ]}
      />
      <CanonicalMapTable rows={mapQuery.data} />
    </div>
  );
}

export default function AssessmentCurriculumMapPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const live = getApiCapabilities().assessments === "live";
  return live ? (
    <LiveCurriculumMapPage id={id} />
  ) : (
    <MockCurriculumMapPage id={id} />
  );
}
