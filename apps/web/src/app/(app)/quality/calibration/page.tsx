"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { A1_PERMISSIONS } from "@/lib/api/a1-types";
import { api, isApiError } from "@/lib/api";
import { getSession, hasPermission } from "@/lib/auth/session";
import { PageHeader } from "@/components/layout/PageHeader";
import { ErrorState, LoadingState } from "@/components/ui/FeedbackStates";

function actionErrorMessage(error: unknown): string {
  if (isApiError(error)) return error.message;
  if (error && typeof error === "object" && "message" in error) {
    return String((error as { message: unknown }).message);
  }
  return "Request failed";
}

export default function CalibrationPage() {
  const queryClient = useQueryClient();
  const session = getSession();
  const canManage = hasPermission(session, A1_PERMISSIONS.qualityManage);
  const canParticipate = hasPermission(
    session,
    A1_PERMISSIONS.calibrationParticipate,
  );
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [title, setTitle] = useState("New calibration");
  const [versionId, setVersionId] = useState("assess-ver-demo-001");
  const [score, setScore] = useState("4");
  const [formError, setFormError] = useState<string | null>(null);

  const sessionsQuery = useQuery({
    queryKey: ["b17-calibration-sessions"],
    queryFn: () => api.listCalibrationSessions!(),
  });

  const mySessionsQuery = useQuery({
    queryKey: ["b17-my-calibration-sessions"],
    queryFn: () => api.listMyCalibrationSessions!(),
    enabled: canParticipate,
  });

  const sessions = sessionsQuery.data?.items ?? [];
  const activeId = selectedId ?? sessions[0]?.id ?? null;

  const detailQuery = useQuery({
    queryKey: ["b17-calibration-session", activeId],
    queryFn: () => api.getCalibrationSession!(activeId!),
    enabled: Boolean(activeId),
  });

  const progressQuery = useQuery({
    queryKey: ["b17-calibration-progress", activeId],
    queryFn: () => api.getCalibrationProgress!(activeId!),
    enabled: Boolean(activeId),
  });

  const createMutation = useMutation({
    mutationFn: () =>
      api.createCalibrationSession!({
        assessment_version_id: versionId,
        title,
        min_cases: 2,
      }),
    onSuccess: (session) => {
      setFormError(null);
      setSelectedId(session.id);
      void queryClient.invalidateQueries({
        queryKey: ["b17-calibration-sessions"],
      });
    },
    onError: (err) => setFormError(actionErrorMessage(err)),
  });

  const activateMutation = useMutation({
    mutationFn: () => api.activateCalibrationSession!(activeId!),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: ["b17-calibration-session", activeId],
      });
      void queryClient.invalidateQueries({
        queryKey: ["b17-calibration-sessions"],
      });
    },
    onError: (err) => setFormError(actionErrorMessage(err)),
  });

  const closeMutation = useMutation({
    mutationFn: () => api.closeCalibrationSession!(activeId!),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: ["b17-calibration-session", activeId],
      });
      void queryClient.invalidateQueries({
        queryKey: ["b17-calibration-sessions"],
      });
    },
    onError: (err) => setFormError(actionErrorMessage(err)),
  });

  const firstCaseId = detailQuery.data?.cases?.[0]?.id;
  const blindQuery = useQuery({
    queryKey: ["b17-calibration-blind", activeId, firstCaseId],
    queryFn: () => api.getBlindCalibrationCase!(activeId!, firstCaseId!),
    enabled: Boolean(activeId && firstCaseId && canParticipate),
  });

  const submitMutation = useMutation({
    mutationFn: () =>
      api.submitCalibrationResponse!(activeId!, firstCaseId!, {
        score: Number(score),
      }),
    onSuccess: () => {
      setFormError(null);
      void queryClient.invalidateQueries({
        queryKey: ["b17-calibration-progress", activeId],
      });
    },
    onError: (err) => setFormError(actionErrorMessage(err)),
  });

  if (sessionsQuery.isLoading) {
    return <LoadingState label="Loading calibration…" />;
  }
  if (sessionsQuery.isError) {
    return <ErrorState message={actionErrorMessage(sessionsQuery.error)} />;
  }

  return (
    <div className="space-y-6" data-testid="b17-calibration-workspace">
      <PageHeader
        title="Evaluator calibration"
        description="Blind scoring sessions with ICC consistency metrics (PEV-049)."
      />

      {canManage ? (
        <section className="flex flex-wrap items-end gap-3">
          <label className="flex flex-col gap-1 text-sm">
            Title
            <input
              data-testid="b17-calibration-title-input"
              className="rounded border px-2 py-1"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
            />
          </label>
          <label className="flex flex-col gap-1 text-sm">
            Assessment version ID
            <input
              data-testid="b17-calibration-version-input"
              className="rounded border px-2 py-1"
              value={versionId}
              onChange={(e) => setVersionId(e.target.value)}
            />
          </label>
          <button
            type="button"
            data-testid="b17-calibration-create"
            className="rounded bg-slate-900 px-3 py-2 text-sm text-white"
            onClick={() => createMutation.mutate()}
          >
            Create session
          </button>
        </section>
      ) : null}
      {formError ? (
        <p className="text-sm text-red-700" data-testid="b17-calibration-error">
          {formError}
        </p>
      ) : null}

      <section data-testid="b17-calibration-session-list" className="space-y-2">
        <h2 className="text-lg font-medium">Sessions</h2>
        <ul className="divide-y rounded border">
          {sessions.map((s) => (
            <li key={s.id}>
              <button
                type="button"
                data-testid="b17-calibration-session-row"
                className={`flex w-full justify-between px-3 py-2 text-left text-sm ${
                  activeId === s.id ? "bg-slate-100" : ""
                }`}
                onClick={() => setSelectedId(s.id)}
              >
                <span>{s.title}</span>
                <span data-testid="b17-calibration-session-status">
                  {s.status}
                </span>
              </button>
            </li>
          ))}
        </ul>
      </section>

      {canParticipate ? (
        <section data-testid="b17-my-calibration-sessions" className="space-y-2">
          <h2 className="text-lg font-medium">My sessions</h2>
          <ul className="text-sm">
            {(mySessionsQuery.data?.items ?? []).map((s) => (
              <li key={s.id} data-testid="b17-my-calibration-row">
                {s.title} — {s.status}
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {activeId && detailQuery.data ? (
        <section data-testid="b17-calibration-detail" className="space-y-3">
          <div className="flex gap-2">
            {canManage && detailQuery.data.status === "DRAFT" ? (
              <button
                type="button"
                data-testid="b17-calibration-activate"
                className="rounded border px-3 py-1 text-sm"
                onClick={() => activateMutation.mutate()}
              >
                Activate
              </button>
            ) : null}
            {canManage && detailQuery.data.status === "ACTIVE" ? (
              <button
                type="button"
                data-testid="b17-calibration-close"
                className="rounded border px-3 py-1 text-sm"
                onClick={() => closeMutation.mutate()}
              >
                Close
              </button>
            ) : null}
          </div>
          <p data-testid="b17-calibration-progress" className="text-sm">
            Progress: cases={progressQuery.data?.case_count ?? "—"}, participants=
            {progressQuery.data?.participant_count ?? "—"}, responses=
            {progressQuery.data?.response_count ?? "—"}
          </p>
          <div data-testid="b17-calibration-cases">
            {(detailQuery.data.cases ?? []).map((c) => (
              <div key={c.id} data-testid="b17-calibration-case-row">
                {c.case_code} (max {c.max_mark})
              </div>
            ))}
          </div>
          {blindQuery.data ? (
            <div data-testid="b17-calibration-blind" className="rounded border p-3">
              <p className="text-sm font-medium">Blind case {blindQuery.data.case_code}</p>
              <p className="text-xs text-slate-600">
                Reference score hidden. Max mark: {blindQuery.data.max_mark}
              </p>
              {canParticipate && detailQuery.data.status === "ACTIVE" ? (
                <div className="mt-2 flex gap-2">
                  <input
                    data-testid="b17-calibration-score-input"
                    className="w-24 rounded border px-2 py-1 text-sm"
                    value={score}
                    onChange={(e) => setScore(e.target.value)}
                  />
                  <button
                    type="button"
                    data-testid="b17-calibration-submit"
                    className="rounded bg-slate-900 px-3 py-1 text-sm text-white"
                    onClick={() => submitMutation.mutate()}
                  >
                    Submit score
                  </button>
                </div>
              ) : null}
            </div>
          ) : null}
        </section>
      ) : null}
    </div>
  );
}
