"use client";

import { use, useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { api, isApiError } from "@/lib/api";
import { getApiCapabilities } from "@/lib/api/capabilities";
import { getSession, hasPermission } from "@/lib/auth/session";
import { PageHeader } from "@/components/layout/PageHeader";
import {
  StudentIdentityCard,
  StudentMatchCandidate,
} from "@/components/identity/StudentIdentityCard";
import { PaperViewerShell } from "@/components/paper/PaperViewerShell";
import { ErrorState, LoadingState } from "@/components/ui/FeedbackStates";
import { Button } from "@/components/ui/primitives";

const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

function isLiveIdentityContext(id: string): boolean {
  const caps = getApiCapabilities();
  if (caps.identityReview === "live" || caps.submissions === "live") return true;
  return UUID_RE.test(id) && !id.toLowerCase().includes("demo");
}

export default function IdentityReviewPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const router = useRouter();
  const queryClient = useQueryClient();
  const live = isLiveIdentityContext(id);
  const session = getSession();
  const canReview = hasPermission(session, "submission:review");
  const canReadOnly =
    !canReview && hasPermission(session, "submission:read");
  // Demo mock sessions treat teacher/admin as fully permitted via hasPermission.
  const actionsEnabled = live ? canReview : true;

  const [selectedStudentId, setSelectedStudentId] = useState<string | null>(
    null,
  );
  const [activePageId, setActivePageId] = useState("");
  const [choosingDifferent, setChoosingDifferent] = useState(false);
  const [pageImageUrl, setPageImageUrl] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["identity", id],
    queryFn: () => api.getIdentityReview(id),
  });

  useEffect(() => {
    if (!data?.pages?.length) return;
    setActivePageId((current) => {
      if (current && data.pages.some((p) => p.id === current)) return current;
      return data.pages[0]!.id;
    });
  }, [data]);

  useEffect(() => {
    if (!live || !activePageId || !api.getSubmissionPageImageBlob) {
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
  }, [live, activePageId]);

  const confirmMutation = useMutation({
    mutationFn: (studentId: string) => api.confirmIdentity(id, studentId),
    onSuccess: async () => {
      setActionError(null);
      await queryClient.invalidateQueries({ queryKey: ["submissions"] });
      await queryClient.invalidateQueries({ queryKey: ["submission", id] });
      await queryClient.invalidateQueries({ queryKey: ["identity", id] });
      if (live) {
        router.push(`/submissions/${id}`);
      } else {
        // B0 mock smoke / flow continues into mapping review.
        router.push(`/submissions/${id}/mapping`);
      }
    },
    onError: (err) => {
      setActionError(
        isApiError(err)
          ? err.message || err.userMessage()
          : err instanceof Error
            ? err.message
            : "Confirm failed",
      );
    },
  });

  const unmatchedMutation = useMutation({
    mutationFn: () => api.markIdentityUnmatched(id),
    onSuccess: async () => {
      setActionError(null);
      await queryClient.invalidateQueries({ queryKey: ["identity", id] });
      await queryClient.invalidateQueries({ queryKey: ["submissions"] });
      setSelectedStudentId(null);
      setChoosingDifferent(false);
      await refetch();
    },
    onError: (err) => {
      setActionError(
        isApiError(err)
          ? err.message || err.userMessage()
          : err instanceof Error
            ? err.message
            : "Mark unmatched failed",
      );
    },
  });

  if (isLoading) return <LoadingState />;
  if (isError || !data) return <ErrorState onRetry={() => void refetch()} />;

  const lowConfidence = data.submission.identity_confidence < 0.65;
  const notFinalized =
    data.submission.student_match_state !== "CONFIRMED" || lowConfidence;

  return (
    <div data-testid="identity-review-page">
      <PageHeader
        title="Identity review"
        description={
          live
            ? "Select the roster student manually. Confidence 0.0 means automated matching is inactive in B3."
            : "Confirm roll/name against the demo roster before mapping. Low confidence never looks finalized."
        }
        breadcrumbs={[
          { label: "Submissions", href: "/submissions" },
          { label: id, href: `/submissions/${id}` },
          { label: "Identity" },
        ]}
      />
      {notFinalized && (
        <div
          data-testid="identity-not-finalized-banner"
          className="mb-4 rounded-md bg-amber-50 px-4 py-3 text-sm text-amber-950 ring-1 ring-amber-200"
        >
          Identity is unresolved — do not treat this paper as matched until a
          teacher confirms a roster student.
        </div>
      )}
      {live && !data.automated_matching_active && (
        <p
          data-testid="identity-live-notice"
          className="mb-4 rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-600"
        >
          Automated extraction is not active. Choose a student from the roster,
          then confirm. Mapping is not available after confirm in live mode.
        </p>
      )}
      {live && canReadOnly && !canReview && (
        <p
          data-testid="identity-readonly-notice"
          className="mb-4 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-950"
        >
          You have read-only access (submission:read). Confirm and unmatch
          require submission:review.
        </p>
      )}
      <div className="grid gap-4 xl:grid-cols-2">
        <PaperViewerShell
          pages={data.pages}
          regions={[]}
          activePageId={activePageId || data.pages[0]?.id || ""}
          onPageSelect={setActivePageId}
          title="Header evidence"
          mode={live ? "live" : "synthetic"}
          pageImageUrl={live ? pageImageUrl : null}
        />
        <div className="space-y-4">
          <StudentIdentityCard
            rollDetected={
              data.detected?.roll ?? data.submission.roll_number_detected
            }
            nameDetected={
              data.detected?.name ?? data.submission.name_detected
            }
            matchState={data.submission.student_match_state}
            confidence={
              data.detected?.identity_confidence ??
              data.submission.identity_confidence
            }
          />
          {data.automated_matching_active && (
            <p
              data-testid="identity-automated-notice"
              className="rounded-md border border-violet-200 bg-violet-50 px-3 py-2 text-xs text-violet-950"
            >
              Automated identity matching is active — AI suggestions require human
              confirmation. Detected roll/name and confidence reflect OCR extraction.
            </p>
          )}
          <div>
            <h2 className="mb-2 text-sm font-semibold text-slate-800">
              Roster candidates
            </h2>
            <div className="space-y-2">
              {data.candidates.map((c) => (
                <StudentMatchCandidate
                  key={c.student_id}
                  candidate={c}
                  selected={selectedStudentId === c.student_id}
                  showSourceType={data.automated_matching_active}
                  onSelect={() => {
                    if (!actionsEnabled) return;
                    setSelectedStudentId(c.student_id);
                    setChoosingDifferent(true);
                  }}
                />
              ))}
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button
              data-testid="confirm-identity"
              disabled={
                !actionsEnabled ||
                !selectedStudentId ||
                confirmMutation.isPending
              }
              onClick={() => {
                if (selectedStudentId) confirmMutation.mutate(selectedStudentId);
              }}
            >
              Confirm
            </Button>
            <Button
              variant="secondary"
              data-testid="choose-different-student"
              disabled={!actionsEnabled}
              onClick={() => {
                setChoosingDifferent(true);
                setSelectedStudentId(null);
              }}
            >
              Choose Different Student
            </Button>
            <Button
              variant="danger"
              data-testid="mark-unmatched"
              disabled={!actionsEnabled || unmatchedMutation.isPending}
              onClick={() => unmatchedMutation.mutate()}
            >
              Mark Unmatched
            </Button>
          </div>
          {choosingDifferent && !selectedStudentId && (
            <p
              data-testid="choose-different-hint"
              className="text-xs text-slate-600"
            >
              Select a different roster candidate above, then Confirm.
            </p>
          )}
          {unmatchedMutation.isSuccess && (
            <p
              data-testid="unmatched-result"
              className="text-xs text-amber-900"
            >
              Marked unmatched — remains in identity review.
            </p>
          )}
          {actionError && (
            <p data-testid="identity-action-error" className="text-xs text-rose-700">
              {actionError}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
