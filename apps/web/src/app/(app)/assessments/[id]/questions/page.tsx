"use client";

import { use, useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { getApiCapabilities } from "@/lib/api/capabilities";
import { isApiError } from "@/lib/api/http/errors";
import { PageHeader } from "@/components/layout/PageHeader";
import { QuestionTree } from "@/components/evaluation/QuestionTree";
import { ErrorState, LoadingState } from "@/components/ui/FeedbackStates";
import type {
  AssessmentArtifact,
  ProposedQuestionNode,
} from "@/lib/types/domain";

function isActiveRunStatus(status: string | undefined): boolean {
  return status === "QUEUED" || status === "RUNNING";
}

function formatBytes(size: number): string {
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}

function updateNodeAtPath(
  roots: ProposedQuestionNode[],
  path: number[],
  patch: Partial<ProposedQuestionNode>,
): ProposedQuestionNode[] {
  if (path.length === 0) return roots;
  const [index, ...rest] = path;
  return roots.map((node, i) => {
    if (i !== index) return node;
    if (rest.length === 0) return { ...node, ...patch };
    return {
      ...node,
      children: updateNodeAtPath(node.children ?? [], rest, patch),
    };
  });
}

function ProposedTreeEditor({
  roots,
  onChange,
  pathPrefix = [],
}: {
  roots: ProposedQuestionNode[];
  onChange: (next: ProposedQuestionNode[]) => void;
  pathPrefix?: number[];
}) {
  return (
    <ul className="space-y-3">
      {roots.map((node, index) => {
        const path = [...pathPrefix, index];
        const pathKey = path.join("-");
        return (
          <li
            key={`${node.stable_code}-${pathKey}`}
            className="rounded-md border border-slate-200 bg-slate-50 p-3"
          >
            <div className="grid gap-2 sm:grid-cols-2">
              <label className="text-xs text-slate-600">
                Code
                <input
                  data-testid={`proposal-code-${pathKey}`}
                  className="mt-1 w-full rounded border border-slate-300 bg-white px-2 py-1 text-sm"
                  value={node.stable_code}
                  onChange={(e) =>
                    onChange(
                      updateNodeAtPath(roots, [index], {
                        stable_code: e.target.value,
                      }),
                    )
                  }
                />
              </label>
              <label className="text-xs text-slate-600">
                Label
                <input
                  data-testid={`proposal-label-${pathKey}`}
                  className="mt-1 w-full rounded border border-slate-300 bg-white px-2 py-1 text-sm"
                  value={node.display_label}
                  onChange={(e) =>
                    onChange(
                      updateNodeAtPath(roots, [index], {
                        display_label: e.target.value,
                      }),
                    )
                  }
                />
              </label>
            </div>
            <label className="mt-2 block text-xs text-slate-600">
              Prompt
              <textarea
                data-testid={`proposal-prompt-${pathKey}`}
                className="mt-1 w-full rounded border border-slate-300 bg-white px-2 py-1 text-sm"
                rows={2}
                value={node.prompt_text}
                onChange={(e) =>
                  onChange(
                    updateNodeAtPath(roots, [index], {
                      prompt_text: e.target.value,
                    }),
                  )
                }
              />
            </label>
            <div className="mt-2 flex flex-wrap gap-3 text-xs text-slate-600">
              <span>Marks: {String(node.max_marks)}</span>
              <span>Mode: {node.scoring_mode}</span>
              <span>Type: {node.question_type}</span>
            </div>
            {(node.children?.length ?? 0) > 0 && (
              <div className="mt-3 border-l-2 border-slate-200 pl-3">
                <ProposedTreeEditor
                  roots={node.children ?? []}
                  pathPrefix={path}
                  onChange={(children) =>
                    onChange(
                      updateNodeAtPath(roots, [index], { children }),
                    )
                  }
                />
              </div>
            )}
          </li>
        );
      })}
    </ul>
  );
}

function LiveQuestionsPage({ id }: { id: string }) {
  const queryClient = useQueryClient();
  const [artifact, setArtifact] = useState<AssessmentArtifact | null>(null);
  const [activeRunId, setActiveRunId] = useState<string | null>(null);
  const [draftRoots, setDraftRoots] = useState<ProposedQuestionNode[] | null>(
    null,
  );
  const [actionError, setActionError] = useState<string | null>(null);

  const assessmentQuery = useQuery({
    queryKey: ["assessment", id],
    queryFn: () => api.getAssessment(id),
  });
  const versionQuery = useQuery({
    queryKey: ["assessment-version", id],
    queryFn: () => api.getLatestAssessmentVersion!(id),
  });
  const questionsQuery = useQuery({
    queryKey: ["assessment-questions", id],
    queryFn: () => api.getAssessmentQuestions(id),
  });

  const runQuery = useQuery({
    queryKey: ["authoring-ai-run", activeRunId],
    queryFn: () => api.getAuthoringAiRun!(activeRunId!),
    enabled: Boolean(activeRunId),
    refetchInterval: (q) =>
      isActiveRunStatus(q.state.data?.status) ? 2000 : false,
  });

  useEffect(() => {
    const run = runQuery.data;
    if (!run) return;
    if (run.status === "REVIEW_REQUIRED" && run.proposal_payload?.roots) {
      setDraftRoots(run.proposal_payload.roots);
    }
  }, [runQuery.data]);

  const uploadMutation = useMutation({
    mutationFn: (file: File) =>
      api.uploadQuestionPaper!(versionQuery.data!.id, file),
    onSuccess: (uploaded) => {
      setArtifact(uploaded);
      setActionError(null);
      void queryClient.invalidateQueries({ queryKey: ["assessment-version", id] });
    },
    onError: (err) => {
      setActionError(isApiError(err) ? err.message : "Upload failed");
    },
  });

  const parseMutation = useMutation({
    mutationFn: () =>
      api.prepareQuestionPaperParse!(versionQuery.data!.id),
    onSuccess: (run) => {
      setActiveRunId(run.id);
      setActionError(null);
      if (run.status === "REVIEW_REQUIRED" && run.proposal_payload?.roots) {
        setDraftRoots(run.proposal_payload.roots);
      }
    },
    onError: (err) => {
      setActionError(isApiError(err) ? err.message : "Parse failed");
    },
  });

  const saveProposalMutation = useMutation({
    mutationFn: () =>
      api.updateQuestionTreeProposal!(activeRunId!, {
        roots: draftRoots!,
        notes: "teacher edit",
      }),
    onSuccess: (run) => {
      setDraftRoots(run.proposal_payload?.roots ?? draftRoots);
      setActionError(null);
    },
    onError: (err) => {
      setActionError(isApiError(err) ? err.message : "Save failed");
    },
  });

  const applyMutation = useMutation({
    mutationFn: async () => {
      if (draftRoots && activeRunId) {
        await api.updateQuestionTreeProposal!(activeRunId, {
          roots: draftRoots,
          notes: "teacher apply",
        });
      }
      return api.applyQuestionTreeProposal!(activeRunId!);
    },
    onSuccess: async () => {
      setActionError(null);
      setDraftRoots(null);
      setActiveRunId(null);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["assessment-questions", id] }),
        queryClient.invalidateQueries({ queryKey: ["assessment", id] }),
      ]);
    },
    onError: (err) => {
      setActionError(isApiError(err) ? err.message : "Apply failed");
    },
  });

  if (
    assessmentQuery.isLoading ||
    questionsQuery.isLoading ||
    versionQuery.isLoading
  ) {
    return <LoadingState />;
  }
  if (
    assessmentQuery.isError ||
    questionsQuery.isError ||
    versionQuery.isError ||
    !assessmentQuery.data ||
    !questionsQuery.data ||
    !versionQuery.data
  ) {
    return <ErrorState onRetry={() => void questionsQuery.refetch()} />;
  }

  const assessment = assessmentQuery.data;
  const isDraft = assessment.workflow_state === "DRAFT";
  const run = runQuery.data;
  const parseStatus = run?.status ?? (questionsQuery.data.length > 0 ? "APPLIED" : "NOT_STARTED");
  const reviewing = run?.status === "REVIEW_REQUIRED" && draftRoots;
  const parsing = isActiveRunStatus(run?.status) || parseMutation.isPending;

  return (
    <div data-testid="assessment-questions-page" data-authoring-mode="live">
      <PageHeader
        title="Questions"
        description={assessment.title}
        breadcrumbs={[
          { label: "Assessments", href: "/assessments" },
          { label: assessment.code, href: `/assessments/${id}` },
          { label: "Questions" },
        ]}
      />

      {isDraft && (
        <section
          data-testid="question-paper-authoring"
          className="mb-4 space-y-3 rounded-md border border-slate-200 bg-white p-4"
        >
          <p
            data-testid="ai-proposal-truth-notice"
            className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900"
          >
            AI proposal requires teacher apply. Parsed structure is not the live
            question tree until you apply it.
          </p>

          <div className="flex flex-wrap items-center gap-3">
            <label className="inline-flex cursor-pointer items-center gap-2 rounded-md bg-teal-800 px-3 py-2 text-sm font-medium text-white hover:bg-teal-900">
              Upload question paper
              <input
                data-testid="question-paper-upload"
                type="file"
                accept="application/pdf,.pdf"
                className="sr-only"
                disabled={uploadMutation.isPending || questionsQuery.data.length > 0}
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) uploadMutation.mutate(file);
                  e.target.value = "";
                }}
              />
            </label>
            <button
              type="button"
              data-testid="parse-question-paper"
              className="rounded-md border border-slate-300 px-3 py-2 text-sm hover:bg-slate-50 disabled:opacity-50"
              disabled={
                parsing ||
                questionsQuery.data.length > 0 ||
                (!artifact && !versionQuery.data.question_paper_artifact_id)
              }
              onClick={() => parseMutation.mutate()}
            >
              {parsing ? "Parsing…" : "Parse question paper"}
            </button>
          </div>

          {(artifact || versionQuery.data.question_paper_artifact_id) && (
            <dl
              data-testid="question-paper-artifact"
              className="grid gap-2 rounded-md border border-slate-100 bg-slate-50 p-3 text-sm sm:grid-cols-2"
            >
              <div>
                <dt className="text-xs uppercase tracking-wide text-slate-500">
                  Filename
                </dt>
                <dd data-testid="artifact-filename">
                  {artifact?.original_filename ?? "Uploaded question paper"}
                </dd>
              </div>
              <div>
                <dt className="text-xs uppercase tracking-wide text-slate-500">
                  Type
                </dt>
                <dd data-testid="artifact-type">
                  {artifact?.mime_type ?? artifact?.artifact_type ?? "QUESTION_PAPER"}
                </dd>
              </div>
              <div>
                <dt className="text-xs uppercase tracking-wide text-slate-500">
                  Size
                </dt>
                <dd data-testid="artifact-size">
                  {artifact ? formatBytes(artifact.byte_size) : "—"}
                </dd>
              </div>
              <div>
                <dt className="text-xs uppercase tracking-wide text-slate-500">
                  Scan status
                </dt>
                <dd data-testid="artifact-scan-status">
                  {artifact?.security_scan_status ?? "—"}
                </dd>
              </div>
              <div>
                <dt className="text-xs uppercase tracking-wide text-slate-500">
                  Parse status
                </dt>
                <dd data-testid="artifact-parse-status">{parseStatus}</dd>
              </div>
            </dl>
          )}

          {actionError && (
            <p
              data-testid="question-paper-error"
              className="text-sm text-red-700"
            >
              {actionError}
            </p>
          )}

          {reviewing && (
            <div
              data-testid="question-tree-proposal"
              className="space-y-3 rounded-md border border-slate-200 p-3"
            >
              <h2 className="text-sm font-semibold text-slate-900">
                Proposed question structure
              </h2>
              <ProposedTreeEditor
                roots={draftRoots}
                onChange={(next) => {
                  // ProposedTreeEditor can emit nested child arrays; normalize to full roots
                  setDraftRoots(next);
                }}
              />
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  data-testid="save-question-tree-proposal"
                  className="rounded-md border border-slate-300 px-3 py-2 text-sm hover:bg-slate-50"
                  disabled={saveProposalMutation.isPending}
                  onClick={() => saveProposalMutation.mutate()}
                >
                  Save edits
                </button>
                <button
                  type="button"
                  data-testid="apply-question-tree"
                  className="rounded-md bg-teal-800 px-3 py-2 text-sm font-medium text-white hover:bg-teal-900"
                  disabled={applyMutation.isPending}
                  onClick={() => applyMutation.mutate()}
                >
                  Apply question structure
                </button>
              </div>
            </div>
          )}
        </section>
      )}

      <div className="rounded-md border border-slate-200 bg-white p-4">
        <QuestionTree questions={questionsQuery.data} />
        {questionsQuery.data.length === 0 && !reviewing && (
          <p className="mt-2 text-sm text-slate-500">
            No applied questions yet.
          </p>
        )}
      </div>
    </div>
  );
}

function MockQuestionsPage({ id }: { id: string }) {
  const assessmentQuery = useQuery({
    queryKey: ["assessment", id],
    queryFn: () => api.getAssessment(id),
  });
  const questionsQuery = useQuery({
    queryKey: ["assessment-questions", id],
    queryFn: () => api.getAssessmentQuestions(id),
  });

  if (assessmentQuery.isLoading || questionsQuery.isLoading)
    return <LoadingState />;
  if (
    assessmentQuery.isError ||
    questionsQuery.isError ||
    !assessmentQuery.data ||
    !questionsQuery.data
  ) {
    return <ErrorState onRetry={() => void questionsQuery.refetch()} />;
  }

  return (
    <div data-testid="assessment-questions-page" data-authoring-mode="mock">
      <PageHeader
        title="Questions"
        description={assessmentQuery.data.title}
        breadcrumbs={[
          { label: "Assessments", href: "/assessments" },
          { label: assessmentQuery.data.code, href: `/assessments/${id}` },
          { label: "Questions" },
        ]}
      />
      <div className="rounded-md border border-slate-200 bg-white p-4">
        <QuestionTree questions={questionsQuery.data} />
      </div>
    </div>
  );
}

export default function AssessmentQuestionsPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const live = getApiCapabilities().assessments === "live";
  return live ? <LiveQuestionsPage id={id} /> : <MockQuestionsPage id={id} />;
}
