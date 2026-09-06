"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { api, isApiError } from "@/lib/api";
import { A2_PERMISSIONS } from "@/lib/api/a2-types";
import { getApiCapabilities } from "@/lib/api/capabilities";
import { getSession, hasPermission } from "@/lib/auth/session";
import { PageHeader } from "@/components/layout/PageHeader";
import { ErrorState, LoadingState } from "@/components/ui/FeedbackStates";

const schema = z.object({
  title: z.string().min(3, "Enter a title"),
  code: z.string().min(2, "Enter a code"),
  curriculumId: z.string().min(1, "Choose a curriculum"),
  assessmentType: z.string().min(1, "Enter an assessment type"),
  maxMarks: z.number().positive("Marks must be greater than zero"),
});

type FormValues = z.infer<typeof schema>;

export default function NewAssessmentPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const capabilities = getApiCapabilities();
  const initialSession = useMemo(() => getSession(), []);
  const [session, setSession] = useState(initialSession);
  const [submitError, setSubmitError] = useState<string | null>(null);
  useEffect(() => setSession(getSession()), []);
  const canManage = hasPermission(session, A2_PERMISSIONS.assessmentManage);
  const mockMode = capabilities.assessments === "mock";

  const curriculaQuery = useQuery({
    queryKey: ["curricula"],
    queryFn: () => api.listCurricula(),
  });

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      title: "Assessment Draft",
      code: "ASSESS-NEW",
      curriculumId: "",
      assessmentType: "EXAM",
      maxMarks: 40,
    },
  });

  const createMutation = useMutation({
    mutationFn: async (values: FormValues) => {
      if (!api.createAssessment) {
        throw new Error("Live assessment creation is unavailable in this API provider");
      }
      return api.createAssessment({
        curriculumId: values.curriculumId,
        code: values.code,
        title: values.title,
        assessmentType: values.assessmentType,
        maxMarks: values.maxMarks,
      });
    },
    onSuccess: async (assessment) => {
      await queryClient.invalidateQueries({ queryKey: ["assessments"] });
      router.push(`/assessments/${assessment.id}`);
    },
    onError: (error) => {
      setSubmitError(isApiError(error) ? error.userMessage() : "Assessment creation failed");
    },
  });

  if (!mockMode && !canManage) {
    return (
      <ErrorState
        title="Permission denied"
        message="You do not have assessment:manage permission."
      />
    );
  }
  if (curriculaQuery.isLoading) return <LoadingState />;
  if (curriculaQuery.isError || !curriculaQuery.data) {
    return <ErrorState onRetry={() => void curriculaQuery.refetch()} />;
  }

  return (
    <div data-testid="assessment-new-page">
      <PageHeader
        title="New assessment"
        description={
          mockMode
            ? "Demo draft creation in the mock workflow."
            : "Create a live A2 draft assessment and initial version."
        }
        breadcrumbs={[
          { label: "Assessments", href: "/assessments" },
          { label: "New" },
        ]}
      />
      <form
        className="max-w-xl space-y-4 rounded-md border border-slate-200 bg-white p-4"
        onSubmit={handleSubmit((values) => {
          setSubmitError(null);
          if (mockMode && !api.createAssessment) {
            router.push("/assessments/assess-demo-002");
            return;
          }
          createMutation.mutate(values);
        })}
      >
        <label className="block text-sm">
          <span className="font-medium text-slate-800">Title</span>
          <input
            data-testid="assessment-field-title"
            className="mt-1 w-full rounded-md border border-slate-200 px-3 py-2"
            {...register("title")}
          />
          {errors.title && (
            <span className="mt-1 block text-xs text-rose-700">{errors.title.message}</span>
          )}
        </label>
        <label className="block text-sm">
          <span className="font-medium text-slate-800">Code</span>
          <input
            data-testid="assessment-field-code"
            className="mt-1 w-full rounded-md border border-slate-200 px-3 py-2"
            {...register("code")}
          />
          {errors.code && (
            <span className="mt-1 block text-xs text-rose-700">{errors.code.message}</span>
          )}
        </label>
        <label className="block text-sm">
          <span className="font-medium text-slate-800">Curriculum</span>
          <select
            data-testid="assessment-field-curriculumId"
            className="mt-1 w-full rounded-md border border-slate-200 px-3 py-2"
            {...register("curriculumId")}
          >
            <option value="">Choose curriculum</option>
            {curriculaQuery.data.map((curriculum) => (
              <option key={curriculum.id} value={curriculum.id}>
                {curriculum.code} — {curriculum.title}
              </option>
            ))}
          </select>
          {errors.curriculumId && (
            <span className="mt-1 block text-xs text-rose-700">
              {errors.curriculumId.message}
            </span>
          )}
        </label>
        <label className="block text-sm">
          <span className="font-medium text-slate-800">Assessment type</span>
          <input
            data-testid="assessment-field-assessmentType"
            className="mt-1 w-full rounded-md border border-slate-200 px-3 py-2"
            {...register("assessmentType")}
          />
        </label>
        <label className="block text-sm">
          <span className="font-medium text-slate-800">Max marks</span>
          <input
            data-testid="assessment-field-maxMarks"
            type="number"
            step="0.01"
            className="mt-1 w-full rounded-md border border-slate-200 px-3 py-2"
            {...register("maxMarks", { valueAsNumber: true })}
          />
          {errors.maxMarks && (
            <span className="mt-1 block text-xs text-rose-700">{errors.maxMarks.message}</span>
          )}
        </label>

        {submitError && (
          <p data-testid="assessment-create-error" className="text-sm text-rose-700">
            {submitError}
          </p>
        )}
        <button
          type="submit"
          data-testid="assessment-create-submit"
          disabled={createMutation.isPending}
          className="rounded-md bg-teal-800 px-3 py-2 text-sm font-medium text-white hover:bg-teal-900 disabled:opacity-50"
        >
          {createMutation.isPending ? "Creating…" : "Create draft"}
        </button>
      </form>
    </div>
  );
}
