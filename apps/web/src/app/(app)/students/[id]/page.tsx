"use client";

import Link from "next/link";
import { use, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { api, getApiCapabilities, isApiError } from "@/lib/api";
import { A1_PERMISSIONS } from "@/lib/api/a1-types";
import { getSession, hasPermission } from "@/lib/auth/session";
import { PageHeader } from "@/components/layout/PageHeader";
import { ErrorState, LoadingState } from "@/components/ui/FeedbackStates";
import { ConceptMasteryBar } from "@/components/learning/LearningComponents";

const editSchema = z.object({
  studentCode: z.string().min(1),
  fullName: z.string().min(1),
  rollNumber: z.string().optional(),
  admissionNumber: z.string().optional(),
});

const guardianSchema = z.object({
  displayName: z.string().min(1),
  email: z.string().email().optional().or(z.literal("")),
  phone: z.string().optional(),
  relationshipType: z.string().min(1),
});

type EditValues = z.infer<typeof editSchema>;
type GuardianForm = z.infer<typeof guardianSchema>;

export default function StudentDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const queryClient = useQueryClient();
  const session = useMemo(() => getSession(), []);
  const canWrite = hasPermission(session, A1_PERMISSIONS.studentWrite);
  const canGuardianWrite = hasPermission(session, A1_PERMISSIONS.guardianWrite);
  const caps = useMemo(() => getApiCapabilities(), []);
  const [editing, setEditing] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const studentQuery = useQuery({
    queryKey: ["student", id],
    queryFn: () => api.getStudent(id),
  });
  const analyticsQuery = useQuery({
    queryKey: ["student-analytics", id],
    queryFn: () => api.getStudentAnalytics(id),
    enabled: caps.analytics === "mock" && caps.students === "mock",
  });
  const linkedGuardiansQuery = useQuery({
    queryKey: ["student-guardians", id],
    queryFn: () => api.listStudentGuardians(id),
  });

  const editForm = useForm<EditValues>({
    resolver: zodResolver(editSchema),
  });
  const guardianForm = useForm<GuardianForm>({
    resolver: zodResolver(guardianSchema),
    defaultValues: {
      displayName: "",
      email: "",
      phone: "",
      relationshipType: "PARENT",
    },
  });

  const updateMutation = useMutation({
    mutationFn: (values: EditValues) =>
      api.updateStudent(id, {
        studentCode: values.studentCode,
        fullName: values.fullName,
        rollNumber: values.rollNumber,
        admissionNumber: values.admissionNumber,
        academicYearId: studentQuery.data?.academic_year_id,
        classSectionId: studentQuery.data?.class_section_id || null,
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["student", id] });
      await queryClient.invalidateQueries({ queryKey: ["students"] });
      setEditing(false);
      setMessage("Student updated.");
    },
    onError: (err) => {
      setMessage(isApiError(err) ? err.userMessage() : "Update failed");
    },
  });

  const createGuardianMutation = useMutation({
    mutationFn: async (values: GuardianForm) => {
      const guardian = await api.createGuardian({
        displayName: values.displayName,
        email: values.email || undefined,
        phone: values.phone,
      });
      await api.linkStudentGuardian(id, guardian.id, values.relationshipType);
      return guardian;
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["guardians"] });
      await queryClient.invalidateQueries({
        queryKey: ["student-guardians", id],
      });
      guardianForm.reset({
        displayName: "",
        email: "",
        phone: "",
        relationshipType: "PARENT",
      });
      setMessage("Guardian created and linked.");
    },
    onError: (err) => {
      setMessage(isApiError(err) ? err.userMessage() : "Guardian action failed");
    },
  });

  const unlinkMutation = useMutation({
    mutationFn: (guardianId: string) =>
      api.unlinkStudentGuardian(id, guardianId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: ["student-guardians", id],
      });
      setMessage("Guardian unlinked.");
    },
    onError: (err) => {
      setMessage(isApiError(err) ? err.userMessage() : "Unlink failed");
    },
  });

  if (studentQuery.isLoading) return <LoadingState />;
  if (studentQuery.isError || !studentQuery.data) {
    if (isApiError(studentQuery.error) && studentQuery.error.kind === "not_found") {
      return (
        <ErrorState
          title="Student not found"
          message="This student does not exist or is outside your tenant."
        />
      );
    }
    return <ErrorState onRetry={() => void studentQuery.refetch()} />;
  }

  const student = studentQuery.data;
  const analytics = analyticsQuery.data;
  const linkedGuardians = linkedGuardiansQuery.data ?? [];

  return (
    <div data-testid="student-detail-page">
      <PageHeader
        title={student.display_name}
        description={`Code ${student.student_code ?? student.external_ref} · ${student.grade}-${student.section}`}
        breadcrumbs={[
          { label: "Students", href: "/students" },
          { label: student.student_code ?? student.external_ref },
        ]}
        actions={
          <div className="flex gap-2">
            {canWrite && (
              <button
                type="button"
                data-testid="student-edit-toggle"
                onClick={() => {
                  setEditing((v) => !v);
                  editForm.reset({
                    studentCode:
                      student.student_code ?? student.external_ref,
                    fullName: student.display_name,
                    rollNumber: student.roll_number ?? "",
                    admissionNumber: student.admission_number ?? "",
                  });
                }}
                className="rounded-md border border-slate-200 px-3 py-2 text-sm hover:bg-slate-50"
              >
                Edit
              </button>
            )}
            {caps.reports === "mock" && caps.students === "mock" && (
              <>
                <Link
                  href={`/reports/student/${student.id}/assessment/assess-demo-001`}
                  className="rounded-md border border-slate-200 px-3 py-2 text-sm hover:bg-slate-50"
                >
                  Student report
                </Link>
                <Link
                  href={`/learning/${student.id}`}
                  className="rounded-md bg-teal-800 px-3 py-2 text-sm font-medium text-white hover:bg-teal-900"
                >
                  Adaptive learning
                </Link>
              </>
            )}
          </div>
        }
      />

      {message && (
        <p className="mb-4 rounded-md bg-teal-50 px-3 py-2 text-sm text-teal-900">
          {message}
        </p>
      )}

      {editing && (
        <form
          data-testid="student-edit-form"
          className="mb-4 grid max-w-xl gap-3 rounded-md border border-slate-200 bg-white p-4 sm:grid-cols-2"
          onSubmit={editForm.handleSubmit((values) =>
            updateMutation.mutate(values),
          )}
        >
          <label className="text-sm">
            Code
            <input
              className="mt-1 w-full rounded-md border px-3 py-2"
              {...editForm.register("studentCode")}
            />
          </label>
          <label className="text-sm">
            Full name
            <input
              className="mt-1 w-full rounded-md border px-3 py-2"
              {...editForm.register("fullName")}
            />
          </label>
          <label className="text-sm">
            Roll
            <input
              className="mt-1 w-full rounded-md border px-3 py-2"
              {...editForm.register("rollNumber")}
            />
          </label>
          <label className="text-sm">
            Admission
            <input
              className="mt-1 w-full rounded-md border px-3 py-2"
              {...editForm.register("admissionNumber")}
            />
          </label>
          <button
            type="submit"
            data-testid="student-edit-submit"
            disabled={updateMutation.isPending}
            className="rounded-md bg-teal-800 px-3 py-2 text-sm text-white disabled:opacity-60 sm:col-span-2"
          >
            Save changes
          </button>
        </form>
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="rounded-md border border-slate-200 bg-white p-4">
          <h2 className="text-sm font-semibold text-slate-800">Profile</h2>
          <dl className="mt-3 space-y-2 text-sm">
            <div className="flex justify-between">
              <dt className="text-slate-500">Status</dt>
              <dd>{student.status}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-slate-500">Roll</dt>
              <dd>{student.roll_number ?? student.external_ref}</dd>
            </div>
          </dl>
        </div>

        <div
          className="rounded-md border border-slate-200 bg-white p-4 space-y-3"
          data-testid="student-guardians"
        >
          <h2 className="text-sm font-semibold text-slate-800">Guardians</h2>
          <p className="text-xs text-slate-500">
            Linked guardians persist after reload.
          </p>
          {linkedGuardiansQuery.isLoading ? (
            <LoadingState label="Loading guardians…" />
          ) : linkedGuardians.length === 0 ? (
            <p className="text-sm text-slate-500" data-testid="guardians-empty">
              No guardians linked.
            </p>
          ) : (
            <ul className="space-y-1 text-sm" data-testid="guardians-linked-list">
              {linkedGuardians.map((g) => (
                <li
                  key={g.guardianId}
                  className="flex justify-between gap-2"
                  data-testid={`guardian-link-${g.guardianId}`}
                >
                  <span>
                    {g.displayName}
                    <span className="text-slate-500">
                      {" "}
                      · {g.relationshipType}
                    </span>
                  </span>
                  {canGuardianWrite && (
                    <button
                      type="button"
                      data-testid={`guardian-unlink-${g.guardianId}`}
                      className="text-xs text-rose-700"
                      disabled={unlinkMutation.isPending}
                      onClick={() => unlinkMutation.mutate(g.guardianId)}
                    >
                      Unlink
                    </button>
                  )}
                </li>
              ))}
            </ul>
          )}
          {canGuardianWrite && (
            <form
              data-testid="guardian-create-form"
              className="space-y-2 border-t border-slate-100 pt-3"
              onSubmit={guardianForm.handleSubmit((values) =>
                createGuardianMutation.mutate(values),
              )}
            >
              <input
                placeholder="Display name"
                className="w-full rounded-md border px-3 py-2 text-sm"
                {...guardianForm.register("displayName")}
              />
              <input
                placeholder="Email"
                className="w-full rounded-md border px-3 py-2 text-sm"
                {...guardianForm.register("email")}
              />
              <input
                placeholder="Relationship (e.g. PARENT)"
                className="w-full rounded-md border px-3 py-2 text-sm"
                {...guardianForm.register("relationshipType")}
              />
              <button
                type="submit"
                data-testid="guardian-create-submit"
                disabled={createGuardianMutation.isPending}
                className="rounded-md bg-teal-800 px-3 py-2 text-sm text-white disabled:opacity-60"
              >
                Create & link guardian
              </button>
            </form>
          )}
        </div>

        {caps.analytics === "mock" && caps.students === "mock" && (
          <div className="rounded-md border border-slate-200 bg-white p-4 space-y-3 lg:col-span-2">
            <h2 className="text-sm font-semibold text-slate-800">
              Concept mastery (mock domain)
            </h2>
            {analytics?.concept_mastery.map((c) => (
              <ConceptMasteryBar
                key={c.concept}
                concept={c.concept}
                mastery={c.mastery}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
