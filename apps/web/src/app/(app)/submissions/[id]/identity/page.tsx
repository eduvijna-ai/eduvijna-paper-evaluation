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

  if (isLoading) return <LoadingState />;
  if (isError || !data) return <ErrorState onRetry={() => void refetch()} />;

  return (
    <div data-testid="identity-review-page">
      <PageHeader
        title="Identity review"
        description="Confirm roll/name against the demo roster before mapping."
        breadcrumbs={[
          { label: "Submissions", href: "/submissions" },
          { label: id },
          { label: "Identity" },
        ]}
      />
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
                  onSelect={() => setSelectedStudentId(c.student_id)}
                />
              ))}
            </div>
          </div>
          <button
            type="button"
            data-testid="confirm-identity"
            disabled={!selectedStudentId || confirmMutation.isPending}
            onClick={() => {
              if (selectedStudentId) confirmMutation.mutate(selectedStudentId);
            }}
            className="rounded-md bg-teal-800 px-3 py-2 text-sm font-medium text-white hover:bg-teal-900 disabled:opacity-50"
          >
            Confirm match
          </button>
        </div>
      </div>
    </div>
  );
}
