"use client";

import { useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { api, isApiError } from "@/lib/api";
import { PageHeader } from "@/components/layout/PageHeader";
import { DataTable } from "@/components/ui/DataTable";
import { ErrorState, LoadingState } from "@/components/ui/FeedbackStates";
import { Button, Input } from "@/components/ui/primitives";
import { getSession, hasPermission } from "@/lib/auth/session";

const createSchema = z.object({
  code: z.string().min(1, "Code is required"),
  name: z.string().min(1, "Name is required"),
  description: z.string().optional(),
  academicFramework: z.string().optional(),
  versionLabel: z.string().min(1, "Version label is required"),
});

type CreateForm = z.infer<typeof createSchema>;

export default function CurriculumListPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const session = getSession();
  const canManage = hasPermission(session, "curriculum:manage");

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["curricula"],
    queryFn: () => api.listCurricula(),
  });

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<CreateForm>({
    resolver: zodResolver(createSchema),
    defaultValues: {
      code: "",
      name: "",
      description: "",
      academicFramework: "",
      versionLabel: "",
    },
  });

  const createMutation = useMutation({
    mutationFn: (values: CreateForm) => {
      if (!api.createCurriculum) {
        throw new Error("Curriculum create is not available in this API mode.");
      }
      return api.createCurriculum({
        code: values.code,
        name: values.name,
        description: values.description,
        academicFramework: values.academicFramework,
        versionLabel: values.versionLabel,
      });
    },
    onSuccess: async (created) => {
      await queryClient.invalidateQueries({ queryKey: ["curricula"] });
      reset();
      router.push(`/curriculum/${created.id}`);
    },
  });

  if (isLoading) return <LoadingState />;
  if (isError || !data) {
    if (isApiError(error) && error.kind === "forbidden") {
      return (
        <ErrorState
          title="Permission denied"
          message="You do not have curriculum:read permission."
        />
      );
    }
    return <ErrorState onRetry={() => void refetch()} />;
  }

  return (
    <div data-testid="curriculum-list-page">
      <PageHeader
        title="Curriculum"
        description="Live curriculum structures used for assessment authoring and curriculum mapping."
        breadcrumbs={[{ label: "Curriculum" }]}
        actions={
          canManage
            ? undefined
            : undefined
        }
      />
      {canManage && (
        <form
          data-testid="curriculum-create-form"
          className="mb-4 grid max-w-3xl gap-3 rounded-md border border-slate-200 bg-white p-4 sm:grid-cols-2"
          onSubmit={handleSubmit((values) => createMutation.mutate(values))}
        >
          <h2 className="sm:col-span-2 text-sm font-semibold text-slate-900">
            + Create curriculum
          </h2>
          <label className="text-sm">
            Code
            <Input data-testid="curriculum-create-code" className="mt-1" {...register("code")} />
            {errors.code && (
              <span className="mt-1 block text-xs text-rose-700">{errors.code.message}</span>
            )}
          </label>
          <label className="text-sm">
            Name / title
            <Input data-testid="curriculum-create-name" className="mt-1" {...register("name")} />
            {errors.name && (
              <span className="mt-1 block text-xs text-rose-700">{errors.name.message}</span>
            )}
          </label>
          <label className="text-sm">
            Academic framework
            <Input
              data-testid="curriculum-create-framework"
              className="mt-1"
              {...register("academicFramework")}
            />
          </label>
          <label className="text-sm">
            Version label
            <Input
              data-testid="curriculum-create-version"
              className="mt-1"
              {...register("versionLabel")}
            />
            {errors.versionLabel && (
              <span className="mt-1 block text-xs text-rose-700">
                {errors.versionLabel.message}
              </span>
            )}
          </label>
          <label className="sm:col-span-2 text-sm">
            Description
            <Input
              data-testid="curriculum-create-description"
              className="mt-1"
              {...register("description")}
            />
          </label>
          {createMutation.isError && (
            <p className="sm:col-span-2 text-sm text-rose-700" data-testid="curriculum-create-error">
              {isApiError(createMutation.error)
                ? createMutation.error.userMessage()
                : "Create failed"}
            </p>
          )}
          <div className="sm:col-span-2">
            <Button type="submit" data-testid="curriculum-create-submit" disabled={createMutation.isPending}>
              {createMutation.isPending ? "Creating…" : "Create curriculum"}
            </Button>
          </div>
        </form>
      )}
      <DataTable
        rows={data}
        onRowClick={(row) => router.push(`/curriculum/${row.id}`)}
        columns={[
          { key: "title", header: "Title", cell: (r) => r.title },
          { key: "code", header: "Code", cell: (r) => r.code },
          { key: "framework", header: "Framework", cell: (r) => r.board },
          { key: "version", header: "Version", cell: (r) => r.grade_label },
          { key: "nodes", header: "Nodes", cell: (r) => r.node_count },
        ]}
      />
    </div>
  );
}
