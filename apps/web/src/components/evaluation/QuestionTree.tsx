"use client";

import { cn } from "@/lib/utils/cn";
import type { Question } from "@/lib/types/domain";
import type { EvaluationWorkflowState } from "@/lib/types/enums";
import { StatusBadge } from "@/components/layout/PageHeader";

export function QuestionStatus({
  state,
}: {
  state:
    | EvaluationWorkflowState
    | "PROPOSED"
    | "REVIEW_REQUIRED"
    | "CONFIRMED"
    | "CROSSED_OUT"
    | "MAPPED"
    | "AMBIGUOUS"
    | "UNMAPPED";
}) {
  if (
    state === "PROPOSED" ||
    state === "REVIEW_REQUIRED" ||
    state === "CONFIRMED" ||
    state === "CROSSED_OUT" ||
    state === "MAPPED" ||
    state === "AMBIGUOUS" ||
    state === "UNMAPPED"
  ) {
    const tone =
      state === "CONFIRMED" || state === "MAPPED"
        ? "bg-teal-50 text-teal-800 ring-teal-200"
        : state === "PROPOSED"
          ? "bg-sky-50 text-sky-800 ring-sky-200"
          : state === "REVIEW_REQUIRED" || state === "AMBIGUOUS"
            ? "bg-amber-50 text-amber-900 ring-amber-200"
            : state === "CROSSED_OUT"
              ? "bg-slate-100 text-slate-600 ring-slate-200"
              : "bg-rose-50 text-rose-800 ring-rose-200";
    return (
      <span
        data-testid={`question-status-${state}`}
        className={cn(
          "inline-flex rounded-md px-2 py-0.5 text-xs font-medium ring-1 ring-inset",
          tone,
        )}
      >
        {state.replaceAll("_", " ")}
      </span>
    );
  }
  return <StatusBadge kind="evaluation" state={state} />;
}

export function QuestionTree({
  questions,
  selectedId,
  onSelect,
  statusByQuestionId,
}: {
  questions: Question[];
  selectedId?: string;
  onSelect?: (id: string) => void;
  statusByQuestionId?: Record<string, EvaluationWorkflowState | string>;
}) {
  return (
    <ul data-testid="question-tree" className="space-y-1">
      {questions.map((q) => (
        <QuestionTreeNode
          key={q.id}
          question={q}
          depth={0}
          selectedId={selectedId}
          onSelect={onSelect}
          statusByQuestionId={statusByQuestionId}
        />
      ))}
    </ul>
  );
}

function QuestionTreeNode({
  question,
  depth,
  selectedId,
  onSelect,
  statusByQuestionId,
}: {
  question: Question;
  depth: number;
  selectedId?: string;
  onSelect?: (id: string) => void;
  statusByQuestionId?: Record<string, EvaluationWorkflowState | string>;
}) {
  const selected = selectedId === question.id;
  const status = statusByQuestionId?.[question.id];

  return (
    <li>
      <button
        type="button"
        data-testid={`question-tree-item-${question.code}`}
        onClick={() => onSelect?.(question.id)}
        className={cn(
          "flex w-full items-start justify-between gap-2 rounded-md px-2 py-1.5 text-left text-sm transition-colors",
          selected
            ? "bg-teal-50 text-teal-950 ring-1 ring-teal-200"
            : "hover:bg-slate-50 text-slate-800",
        )}
        style={{ paddingLeft: 8 + depth * 12 }}
      >
        <span>
          <span className="font-medium">{question.code}</span>
          <span className="ml-1.5 text-slate-500 line-clamp-1">
            {question.prompt}
          </span>
        </span>
        <span className="shrink-0 text-xs tabular-nums text-slate-500">
          {question.max_mark}m
        </span>
      </button>
      {status && (
        <div className="px-2 pb-1" style={{ paddingLeft: 8 + depth * 12 }}>
          <QuestionStatus
            state={
              status as
                | EvaluationWorkflowState
                | "PROPOSED"
                | "REVIEW_REQUIRED"
                | "CONFIRMED"
                | "CROSSED_OUT"
                | "MAPPED"
                | "AMBIGUOUS"
                | "UNMAPPED"
            }
          />
        </div>
      )}
      {question.children && question.children.length > 0 && (
        <ul className="space-y-1">
          {question.children.map((child) => (
            <QuestionTreeNode
              key={child.id}
              question={child}
              depth={depth + 1}
              selectedId={selectedId}
              onSelect={onSelect}
              statusByQuestionId={statusByQuestionId}
            />
          ))}
        </ul>
      )}
    </li>
  );
}
