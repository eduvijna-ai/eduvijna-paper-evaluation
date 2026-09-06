"use client";

import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { PageHeader } from "@/components/layout/PageHeader";
import { api, getApiMode, isApiError } from "@/lib/api";
import { A1_PERMISSIONS } from "@/lib/api/a1-types";
import { getSession, hasPermission } from "@/lib/auth/session";
import { LoadingState } from "@/components/ui/FeedbackStates";

const yearSchema = z.object({
  name: z.string().min(1),
  startsOn: z.string().min(1),
  endsOn: z.string().min(1),
  isCurrent: z.boolean().optional(),
});

const sectionSchema = z.object({
  name: z.string().min(1),
  gradeLabel: z.string().min(1),
  academicYearId: z.string().min(1),
});

type YearForm = z.infer<typeof yearSchema>;
type SectionForm = z.infer<typeof sectionSchema>;

export default function AdminPage() {
  const mode = getApiMode();
  const queryClient = useQueryClient();
  const session = useMemo(() => getSession(), []);
  const canYearWrite = hasPermission(session, A1_PERMISSIONS.academicYearWrite);
  const canSectionWrite = hasPermission(
    session,
    A1_PERMISSIONS.classSectionWrite,
  );
  const [notice, setNotice] = useState<string | null>(null);

  const institutionQuery = useQuery({
    queryKey: ["institution"],
    queryFn: () => api.getInstitution(),
  });
  const yearsQuery = useQuery({
    queryKey: ["academic-years"],
    queryFn: () => api.listAcademicYears(),
  });
  const sectionsQuery = useQuery({
    queryKey: ["class-sections"],
    queryFn: () => api.listClassSections(),
  });

  const yearForm = useForm<YearForm>({
    resolver: zodResolver(yearSchema),
    defaultValues: {
      name: "",
      startsOn: "",
      endsOn: "",
      isCurrent: false,
    },
  });
  const sectionForm = useForm<SectionForm>({
    resolver: zodResolver(sectionSchema),
    defaultValues: { name: "", gradeLabel: "", academicYearId: "" },
  });

  const createYear = useMutation({
    mutationFn: (v: YearForm) => api.createAcademicYear(v),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["academic-years"] });
      yearForm.reset();
      setNotice("Academic year created.");
    },
    onError: (e) =>
      setNotice(isApiError(e) ? e.userMessage() : "Year create failed"),
  });

  const createSection = useMutation({
    mutationFn: (v: SectionForm) => api.createClassSection(v),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["class-sections"] });
      sectionForm.reset({ name: "", gradeLabel: "", academicYearId: "" });
      setNotice("Class section created.");
    },
    onError: (e) =>
      setNotice(isApiError(e) ? e.userMessage() : "Section create failed"),
  });

  return (
    <div data-testid="admin-page">
      <PageHeader
        title="Admin"
        description="Institution, academic years, and class sections."
        breadcrumbs={[{ label: "Admin" }]}
      />
      {notice && (
        <p className="mb-4 rounded-md bg-teal-50 px-3 py-2 text-sm text-teal-900">
          {notice}
        </p>
      )}
      <div className="grid gap-4 lg:grid-cols-2">
        <section className="rounded-md border border-slate-200 bg-white p-4">
          <h2 className="text-sm font-semibold text-slate-800">Institution</h2>
          {institutionQuery.isLoading ? (
            <LoadingState />
          ) : (
            <dl className="mt-3 space-y-2 text-sm">
              <div className="flex justify-between gap-3">
                <dt className="text-slate-500">Name</dt>
                <dd data-testid="admin-institution-name">
                  {institutionQuery.data?.name ?? "—"}
                </dd>
              </div>
              <div className="flex justify-between gap-3">
                <dt className="text-slate-500">Code</dt>
                <dd>{institutionQuery.data?.code ?? "—"}</dd>
              </div>
              <div className="flex justify-between gap-3">
                <dt className="text-slate-500">API mode</dt>
                <dd data-testid="api-mode">{mode}</dd>
              </div>
            </dl>
          )}
        </section>

        <section className="rounded-md border border-slate-200 bg-white p-4">
          <h2 className="text-sm font-semibold text-slate-800">
            Domain routing
          </h2>
          <ul className="mt-3 space-y-2 text-sm text-slate-700">
            <li>Auth / Institution / Years / Sections / Students / Guardians · live when hybrid</li>
            <li>Curriculum / Assessment / Submissions / Evaluation · mock until later phase</li>
          </ul>
        </section>

        <section
          className="rounded-md border border-slate-200 bg-white p-4"
          data-testid="academic-years-panel"
        >
          <h2 className="text-sm font-semibold text-slate-800">
            Academic years
          </h2>
          <ul className="mt-3 space-y-1 text-sm">
            {(yearsQuery.data ?? []).map((y) => (
              <li key={y.id}>
                {y.name}
                {y.isCurrent ? " · current" : ""}
              </li>
            ))}
            {(yearsQuery.data ?? []).length === 0 && (
              <li className="text-slate-500">No academic years.</li>
            )}
          </ul>
          {canYearWrite && (
            <form
              className="mt-4 space-y-2 border-t pt-3"
              onSubmit={yearForm.handleSubmit((v) => createYear.mutate(v))}
            >
              <input
                placeholder="Name (e.g. 2026-27)"
                className="w-full rounded-md border px-3 py-2 text-sm"
                data-testid="year-name"
                {...yearForm.register("name")}
              />
              <input
                type="date"
                className="w-full rounded-md border px-3 py-2 text-sm"
                {...yearForm.register("startsOn")}
              />
              <input
                type="date"
                className="w-full rounded-md border px-3 py-2 text-sm"
                {...yearForm.register("endsOn")}
              />
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" {...yearForm.register("isCurrent")} />
                Current year
              </label>
              <button
                type="submit"
                data-testid="year-create-submit"
                disabled={createYear.isPending}
                className="rounded-md bg-teal-800 px-3 py-2 text-sm text-white disabled:opacity-60"
              >
                Add year
              </button>
            </form>
          )}
        </section>

        <section
          className="rounded-md border border-slate-200 bg-white p-4"
          data-testid="class-sections-panel"
        >
          <h2 className="text-sm font-semibold text-slate-800">
            Class sections
          </h2>
          <ul className="mt-3 space-y-1 text-sm">
            {(sectionsQuery.data ?? []).map((s) => (
              <li key={s.id}>
                {s.gradeLabel} / {s.name}
                {s.academicYearName ? ` · ${s.academicYearName}` : ""}
              </li>
            ))}
            {(sectionsQuery.data ?? []).length === 0 && (
              <li className="text-slate-500">No class sections.</li>
            )}
          </ul>
          {canSectionWrite && (
            <form
              className="mt-4 space-y-2 border-t pt-3"
              onSubmit={sectionForm.handleSubmit((v) =>
                createSection.mutate(v),
              )}
            >
              <select
                className="w-full rounded-md border px-3 py-2 text-sm"
                data-testid="section-year"
                {...sectionForm.register("academicYearId")}
              >
                <option value="">Academic year</option>
                {(yearsQuery.data ?? []).map((y) => (
                  <option key={y.id} value={y.id}>
                    {y.name}
                  </option>
                ))}
              </select>
              <input
                placeholder="Grade label"
                className="w-full rounded-md border px-3 py-2 text-sm"
                {...sectionForm.register("gradeLabel")}
              />
              <input
                placeholder="Section name"
                className="w-full rounded-md border px-3 py-2 text-sm"
                data-testid="section-name"
                {...sectionForm.register("name")}
              />
              <button
                type="submit"
                data-testid="section-create-submit"
                disabled={createSection.isPending}
                className="rounded-md bg-teal-800 px-3 py-2 text-sm text-white disabled:opacity-60"
              >
                Add section
              </button>
            </form>
          )}
        </section>
      </div>
    </div>
  );
}
