"use client";

import { use, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { PageHeader } from "@/components/layout/PageHeader";
import {
  StudentIdentityCard,
  StudentMatchCandidate,
} from "@/components/identity/StudentIdentityCard";
import { PaperViewerShell } from "@/components/paper/PaperViewerShell";
import { ErrorState, LoadingState } from "@/components/ui/FeedbackStates";
import { Button } from "@/components/ui/primitives";

export default function IdentityReviewPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const router = useRouter();
  const queryClient = useQueryClient();
  const [selectedStudentId, setSelectedStudentId] = useState<string | null>(
    null,
  );
  const [activePageId, setActivePageId] = useState("page-1");
  const [choosingDifferent, setChoosingDifferent] = useState(false);

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["identity", id],
    queryFn: () => api.getIdentityReview(id),
  });

  const confirmMutation = useMutation({
    mutationFn: (studentId: string) => api.confirmIdentity(id, studentId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["submissions"] });
      router.push(`/submissions/${id}/mapping`);
    },
  });

  const unmatchedMutation = useMutation({
    mutationFn: () => api.markIdentityUnmatched(id),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["identity", id] });
      await queryClient.invalidateQueries({ queryKey: ["submissions"] });
      setSelectedStudentId(null);
      setChoosingDifferent(false);
      await refetch();
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
        description="Confirm roll/name against the demo roster before mapping. Low confidence never looks finalized."
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
      <div className="grid gap-4 xl:grid-cols-2">
        <PaperViewerShell
          pages={data.pages}
          regions={[]}
          activePageId={activePageId}
          onPageSelect={setActivePageId}
          title="Header evidence"
        />
        <div className="space-y-4">
          <StudentIdentityCard
            rollDetected={data.submission.roll_number_detected}
            nameDetected={data.submission.name_detected}
            matchState={data.submission.student_match_state}
            confidence={data.submission.identity_confidence}
          />
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
                  onSelect={() => {
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
              disabled={!selectedStudentId || confirmMutation.isPending}
              onClick={() => {
                if (selectedStudentId) confirmMutation.mutate(selectedStudentId);
              }}
            >
              Confirm
            </Button>
            <Button
              variant="secondary"
              data-testid="choose-different-student"
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
              disabled={unmatchedMutation.isPending}
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
        </div>
      </div>
    </div>
  );
}
