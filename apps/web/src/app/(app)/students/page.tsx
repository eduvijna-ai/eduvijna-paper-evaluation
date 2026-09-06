"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect, useMemo, useState } from "react";
import { api, isApiError } from "@/lib/api";
import { A1_PERMISSIONS } from "@/lib/api/a1-types";
import { getSession, hasPermission } from "@/lib/auth/session";
import { PageHeader } from "@/components/layout/PageHeader";
import { DataTable } from "@/components/ui/DataTable";
import { ErrorState, LoadingState } from "@/components/ui/FeedbackStates";

const createSchema = z.object({
  studentCode: z.string().min(1, "Required"),
  fullName: z.string().min(1, "Required"),
  rollNumber: z.string().optional(),
  admissionNumber: z.string().optional(),
  academicYearId: z.string().optional(),
  classSectionId: z.string().optional(),
});

type CreateValues = z.infer<typeof createSchema>;

export default function StudentsPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const session = useMemo(() => getSession(), []);
  // Re-read session after hydration so bearer permissions from /auth/me apply.
  const [sessionState, setSessionState] = useState(session);
  useEffect(() => {
    setSessionState(getSession());
  }, []);
  const canWrite = hasPermission(sessionState, A1_PERMISSIONS.studentWrite);
  const canImport = hasPermission(sessionState, A1_PERMISSIONS.studentImport);
  const [showCreate, setShowCreate] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [selectedYearId, setSelectedYearId] = useState("");

  const studentsQuery = useQuery({
    queryKey: ["students"],
    queryFn: () => api.listStudents(),
  });
  const yearsQuery = useQuery({
    queryKey: ["academic-years"],
    queryFn: () => api.listAcademicYears(),
  });
  const sectionsQuery = useQuery({
    queryKey: ["class-sections"],
    queryFn: () => api.listClassSections(),
  });

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<CreateValues>({
    resolver: zodResolver(createSchema),
    defaultValues: {
      studentCode: "",
      fullName: "",
      rollNumber: "",
      admissionNumber: "",
    },
  });

  const createMutation = useMutation({
    mutationFn: (values: CreateValues) =>
      api.createStudent({
        studentCode: values.studentCode,
        fullName: values.fullName,
        rollNumber: values.rollNumber,
        admissionNumber: values.admissionNumber,
        academicYearId: values.academicYearId || null,
        classSectionId: values.classSectionId || null,
      }),
    onSuccess: async (student) => {
      await queryClient.invalidateQueries({ queryKey: ["students"] });
      setShowCreate(false);
      reset();
      router.push(`/students/${student.id}`);
    },
    onError: (err) => {
      setCreateError(isApiError(err) ? err.userMessage() : "Create failed");
    },
  });

  if (studentsQuery.isLoading) return <LoadingState />;
  if (studentsQuery.isError) {
    const err = studentsQuery.error;
    if (isApiError(err) && err.kind === "forbidden") {
      return (
        <ErrorState
          title="Permission denied"
          message="You do not have student:read permission."
        />
      );
    }
    return <ErrorState onRetry={() => void studentsQuery.refetch()} />;
  }

  const data = studentsQuery.data ?? [];

  return (
    <div data-testid="students-page">
      <PageHeader
        title="Students"
        description="Institution roster. Pagination is not available in A1 yet."
        breadcrumbs={[{ label: "Students" }]}
        actions={
          <div className="flex gap-2">
            {canWrite && (
              <button
                type="button"
                data-testid="student-create-toggle"
                onClick={() => setShowCreate((v) => !v)}
                className="rounded-md border border-slate-200 bg-white px-3 py-2 text-sm hover:bg-slate-50"
              >
                New student
              </button>
            )}
            {canImport && (
              <Link
                href="/students/import"
                data-testid="students-import-link"
                className="rounded-md bg-teal-800 px-3 py-2 text-sm font-medium text-white hover:bg-teal-900"
              >
                Import roster
              </Link>
            )}
          </div>
        }
      />

      {showCreate && canWrite && (
        <form
          data-testid="student-create-form"
          className="mb-4 grid max-w-2xl gap-3 rounded-md border border-slate-200 bg-white p-4 sm:grid-cols-2"
          onSubmit={handleSubmit((values) => {
            setCreateError(null);
            createMutation.mutate(values);
          })}
        >
          <label className="text-sm">
            <span className="font-medium">Student code</span>
            <input
              className="mt-1 w-full rounded-md border border-slate-200 px-3 py-2"
              {...register("studentCode")}
            />
            {errors.studentCode && (
              <span className="text-xs text-rose-700">
                {errors.studentCode.message}
              </span>
            )}
          </label>
          <label className="text-sm">
            <span className="font-medium">Full name</span>
            <input
              className="mt-1 w-full rounded-md border border-slate-200 px-3 py-2"
              {...register("fullName")}
            />
            {errors.fullName && (
              <span className="text-xs text-rose-700">
                {errors.fullName.message}
              </span>
            )}
          </label>
          <label className="text-sm">
            <span className="font-medium">Roll number</span>
            <input
              className="mt-1 w-full rounded-md border border-slate-200 px-3 py-2"
              {...register("rollNumber")}
            />
          </label>
          <label className="text-sm">
            <span className="font-medium">Admission number</span>
            <input
              className="mt-1 w-full rounded-md border border-slate-200 px-3 py-2"
              {...register("admissionNumber")}
            />
          </label>
          <label className="text-sm">
            <span className="font-medium">Academic year</span>
            <select
              className="mt-1 w-full rounded-md border border-slate-200 px-3 py-2"
              {...register("academicYearId")}
              onChange={(e) => {
                setSelectedYearId(e.target.value);
                void register("academicYearId").onChange(e);
              }}
            >
              <option value="">—</option>
              {(yearsQuery.data ?? []).map((y) => (
                <option key={y.id} value={y.id}>
                  {y.name}
                </option>
              ))}
            </select>
          </label>
          <label className="text-sm">
            <span className="font-medium">Class section</span>
            <select
              className="mt-1 w-full rounded-md border border-slate-200 px-3 py-2"
              {...register("classSectionId")}
            >
              <option value="">—</option>
              {(sectionsQuery.data ?? [])
                .filter(
                  (s) =>
                    !selectedYearId || s.academicYearId === selectedYearId,
                )
                .map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.gradeLabel} / {s.name}
                  </option>
                ))}
            </select>
          </label>
          {createError && (
            <p className="sm:col-span-2 text-sm text-rose-700">{createError}</p>
          )}
          <div className="sm:col-span-2">
            <button
              type="submit"
              data-testid="student-create-submit"
              disabled={createMutation.isPending}
              className="rounded-md bg-teal-800 px-3 py-2 text-sm font-medium text-white disabled:opacity-60"
            >
              {createMutation.isPending ? "Saving…" : "Create student"}
            </button>
          </div>
        </form>
      )}

      {data.length === 0 ? (
        <p
          data-testid="students-empty"
          className="rounded-md border border-dashed border-slate-300 bg-white p-8 text-center text-sm text-slate-600"
        >
          No students yet. Create one or import a CSV roster.
        </p>
      ) : (
        <DataTable
          rows={data}
          onRowClick={(row) => router.push(`/students/${row.id}`)}
          columns={[
            {
              key: "code",
              header: "Code",
              cell: (r) => r.student_code ?? r.external_ref,
            },
            { key: "name", header: "Name", cell: (r) => r.display_name },
            {
              key: "class",
              header: "Class",
              cell: (r) => `${r.grade}-${r.section}`,
            },
            { key: "status", header: "Status", cell: (r) => r.status },
          ]}
        />
      )}
    </div>
  );
}
