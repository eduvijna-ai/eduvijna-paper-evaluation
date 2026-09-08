"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, isApiError } from "@/lib/api";
import { PageHeader } from "@/components/layout/PageHeader";
import { ErrorState, LoadingState } from "@/components/ui/FeedbackStates";
import {
  CURRICULUM_RESOURCE_KINDS,
  CURRICULUM_RESOURCE_STATUSES,
} from "@/lib/types/enums";
import type { CurriculumResource } from "@/lib/types/domain";

function actionErrorMessage(error: unknown): string {
  if (isApiError(error)) return error.message;
  if (error && typeof error === "object" && "message" in error) {
    return String((error as { message: unknown }).message);
  }
  return "Request failed";
}

export default function ResourceCatalogPage() {
  const queryClient = useQueryClient();
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [form, setForm] = useState({
    curriculum_id: "",
    code: "",
    title: "",
    resource_kind: "PRACTICE_SET",
    content_ref: "",
    curriculum_node_ids: "",
    description: "",
  });
  const [formError, setFormError] = useState<string | null>(null);

  const curriculaQuery = useQuery({
    queryKey: ["curricula"],
    queryFn: () => api.listCurricula(),
  });

  const resourcesQuery = useQuery({
    queryKey: ["b13-curriculum-resources", statusFilter || "all"],
    queryFn: () =>
      api.listCurriculumResources!({
        status: statusFilter || undefined,
      }),
  });

  const createMutation = useMutation({
    mutationFn: (payload: typeof form) => {
      const nodeIds = payload.curriculum_node_ids
        .split(/[\s,]+/)
        .map((s) => s.trim())
        .filter(Boolean);
      if (
        !payload.curriculum_id ||
        !payload.code ||
        !payload.title ||
        !payload.content_ref
      ) {
        throw new Error("Curriculum, code, title, and content_ref are required");
      }
      if (nodeIds.length === 0) {
        throw new Error("At least one curriculum node id is required");
      }
      if (
        /^https?:\/\//i.test(payload.content_ref) ||
        payload.content_ref.startsWith("//")
      ) {
        throw new Error("content_ref must not be an open-web URL");
      }
      return api.createCurriculumResource!({
        curriculum_id: payload.curriculum_id,
        code: payload.code,
        title: payload.title,
        description: payload.description || null,
        resource_kind: payload.resource_kind,
        content_ref: payload.content_ref,
        curriculum_node_ids: nodeIds,
      });
    },
    onSuccess: () => {
      setFormError(null);
      setForm((prev) => ({
        ...prev,
        code: "",
        title: "",
        content_ref: "",
        curriculum_node_ids: "",
        description: "",
      }));
      void queryClient.invalidateQueries({
        queryKey: ["b13-curriculum-resources"],
      });
    },
    onError: (err) => setFormError(actionErrorMessage(err)),
  });

  const lifecycleMutation = useMutation({
    mutationFn: async ({
      id,
      action,
    }: {
      id: string;
      action: "approve" | "activate" | "deactivate";
    }) => {
      if (action === "approve") return api.approveCurriculumResource!(id);
      if (action === "activate") return api.activateCurriculumResource!(id);
      return api.deactivateCurriculumResource!(id);
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: ["b13-curriculum-resources"],
      });
    },
  });

  const defaultCurriculumId = useMemo(() => {
    if (form.curriculum_id) return form.curriculum_id;
    return curriculaQuery.data?.[0]?.id ?? "";
  }, [form.curriculum_id, curriculaQuery.data]);

  if (resourcesQuery.isLoading || curriculaQuery.isLoading) {
    return <LoadingState />;
  }
  if (resourcesQuery.isError || !resourcesQuery.data) {
    if (isApiError(resourcesQuery.error) && resourcesQuery.error.kind === "forbidden") {
      return (
        <ErrorState
          title="Permission denied"
          message="You do not have learning:read permission for the resource catalog."
        />
      );
    }
    return (
      <ErrorState onRetry={() => void resourcesQuery.refetch()} />
    );
  }

  const items = resourcesQuery.data.items;

  return (
    <div data-testid="b13-resource-catalog">
      <PageHeader
        title="Curriculum resource catalog"
        description="Institution-approved practice materials (B13). No open-web discovery."
        breadcrumbs={[
          { label: "Learning" },
          { label: "Resources" },
        ]}
        actions={
          <Link
            href="/learning/student-demo-001"
            className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-800 hover:bg-slate-50"
            data-testid="b13-catalog-to-learning"
          >
            Adaptive learning
          </Link>
        }
      />

      <label className="mb-4 block max-w-xs text-sm text-slate-700">
        Filter by status
        <select
          data-testid="b13-resource-status-filter"
          className="mt-1 block w-full rounded-md border border-slate-300 px-2 py-1.5"
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
        >
          <option value="">All</option>
          {CURRICULUM_RESOURCE_STATUSES.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
      </label>

      <section
        data-testid="b13-resource-create"
        className="mb-6 rounded-md border border-slate-200 bg-white p-4"
      >
        <h2 className="text-sm font-semibold text-slate-800">
          Create DRAFT resource
        </h2>
        <p className="mt-1 text-xs text-slate-600">
          content_ref must be an opaque internal catalog key (not http/https).
        </p>
        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          <label className="block text-xs text-slate-700">
            Curriculum
            <select
              data-testid="b13-create-curriculum"
              className="mt-1 block w-full rounded-md border border-slate-300 px-2 py-1.5 text-sm"
              value={form.curriculum_id || defaultCurriculumId}
              onChange={(e) =>
                setForm((f) => ({ ...f, curriculum_id: e.target.value }))
              }
            >
              <option value="">Select…</option>
              {(curriculaQuery.data ?? []).map((c) => (
                <option key={c.id} value={c.id}>
                  {c.code} · {c.title}
                </option>
              ))}
            </select>
          </label>
          <label className="block text-xs text-slate-700">
            Kind
            <select
              data-testid="b13-create-kind"
              className="mt-1 block w-full rounded-md border border-slate-300 px-2 py-1.5 text-sm"
              value={form.resource_kind}
              onChange={(e) =>
                setForm((f) => ({ ...f, resource_kind: e.target.value }))
              }
            >
              {CURRICULUM_RESOURCE_KINDS.map((k) => (
                <option key={k} value={k}>
                  {k}
                </option>
              ))}
            </select>
          </label>
          <label className="block text-xs text-slate-700">
            Code
            <input
              data-testid="b13-create-code"
              className="mt-1 block w-full rounded-md border border-slate-300 px-2 py-1.5 text-sm"
              value={form.code}
              onChange={(e) => setForm((f) => ({ ...f, code: e.target.value }))}
            />
          </label>
          <label className="block text-xs text-slate-700">
            Title
            <input
              data-testid="b13-create-title"
              className="mt-1 block w-full rounded-md border border-slate-300 px-2 py-1.5 text-sm"
              value={form.title}
              onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))}
            />
          </label>
          <label className="block text-xs text-slate-700 sm:col-span-2">
            Content ref (internal)
            <input
              data-testid="b13-create-content-ref"
              className="mt-1 block w-full rounded-md border border-slate-300 px-2 py-1.5 text-sm"
              value={form.content_ref}
              onChange={(e) =>
                setForm((f) => ({ ...f, content_ref: e.target.value }))
              }
              placeholder="internal://catalog/…"
            />
          </label>
          <label className="block text-xs text-slate-700 sm:col-span-2">
            Curriculum node ids (comma-separated)
            <input
              data-testid="b13-create-node-ids"
              className="mt-1 block w-full rounded-md border border-slate-300 px-2 py-1.5 text-sm"
              value={form.curriculum_node_ids}
              onChange={(e) =>
                setForm((f) => ({
                  ...f,
                  curriculum_node_ids: e.target.value,
                }))
              }
              placeholder="node-concept-disc"
            />
          </label>
          <label className="block text-xs text-slate-700 sm:col-span-2">
            Description (optional)
            <textarea
              data-testid="b13-create-description"
              rows={2}
              className="mt-1 block w-full rounded-md border border-slate-300 px-2 py-1.5 text-sm"
              value={form.description}
              onChange={(e) =>
                setForm((f) => ({ ...f, description: e.target.value }))
              }
            />
          </label>
        </div>
        {(formError || createMutation.isError) && (
          <p className="mt-2 text-sm text-rose-700" data-testid="b13-create-error">
            {formError ?? actionErrorMessage(createMutation.error)}
          </p>
        )}
        <button
          type="button"
          data-testid="b13-create-submit"
          disabled={createMutation.isPending}
          onClick={() => {
            createMutation.mutate({
              ...form,
              curriculum_id: form.curriculum_id || defaultCurriculumId,
            });
          }}
          className="mt-3 rounded-md bg-teal-800 px-3 py-2 text-sm font-medium text-white hover:bg-teal-900 disabled:opacity-50"
        >
          {createMutation.isPending ? "Creating…" : "Create DRAFT"}
        </button>
      </section>

      {items.length === 0 ? (
        <p
          data-testid="b13-resource-list-empty"
          className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700"
        >
          No resources match this filter.
        </p>
      ) : (
        <ul className="space-y-2" data-testid="b13-resource-list">
          {items.map((resource) => (
            <ResourceRow
              key={resource.id}
              resource={resource}
              busy={lifecycleMutation.isPending}
              onApprove={() =>
                lifecycleMutation.mutate({ id: resource.id, action: "approve" })
              }
              onActivate={() =>
                lifecycleMutation.mutate({ id: resource.id, action: "activate" })
              }
              onDeactivate={() =>
                lifecycleMutation.mutate({
                  id: resource.id,
                  action: "deactivate",
                })
              }
            />
          ))}
        </ul>
      )}
    </div>
  );
}

function ResourceRow({
  resource,
  busy,
  onApprove,
  onActivate,
  onDeactivate,
}: {
  resource: CurriculumResource;
  busy: boolean;
  onApprove: () => void;
  onActivate: () => void;
  onDeactivate: () => void;
}) {
  return (
    <li
      data-testid="b13-resource-row"
      className="rounded-md border border-slate-200 bg-white px-3 py-3"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="text-sm font-semibold text-slate-900">
            {resource.title}
          </div>
          <div className="text-xs text-slate-600">
            {resource.code} · {resource.resource_kind} ·{" "}
            <span data-testid="b13-resource-status">{resource.status}</span>
          </div>
          <div className="mt-1 text-xs text-slate-500">{resource.content_ref}</div>
        </div>
        <div className="flex flex-wrap gap-2">
          {resource.status === "DRAFT" && (
            <button
              type="button"
              data-testid="b13-resource-approve"
              disabled={busy}
              onClick={onApprove}
              className="rounded-md bg-teal-800 px-2.5 py-1.5 text-xs font-medium text-white hover:bg-teal-900 disabled:opacity-50"
            >
              Approve
            </button>
          )}
          {(resource.status === "APPROVED" ||
            resource.status === "DEACTIVATED") && (
            <button
              type="button"
              data-testid="b13-resource-activate"
              disabled={busy}
              onClick={onActivate}
              className="rounded-md bg-teal-800 px-2.5 py-1.5 text-xs font-medium text-white hover:bg-teal-900 disabled:opacity-50"
            >
              Activate
            </button>
          )}
          {resource.status === "ACTIVE" && (
            <button
              type="button"
              data-testid="b13-resource-deactivate"
              disabled={busy}
              onClick={onDeactivate}
              className="rounded-md border border-slate-300 bg-white px-2.5 py-1.5 text-xs font-medium text-slate-800 hover:bg-slate-50 disabled:opacity-50"
            >
              Deactivate
            </button>
          )}
        </div>
      </div>
    </li>
  );
}
