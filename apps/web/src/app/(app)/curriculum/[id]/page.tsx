"use client";

import { use, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { api } from "@/lib/api";
import { PageHeader } from "@/components/layout/PageHeader";
import { ErrorState, LoadingState } from "@/components/ui/FeedbackStates";
import { Button, Input, Select } from "@/components/ui/primitives";
import type { CurriculumNode } from "@/lib/types/domain";
import { getSession, hasPermission } from "@/lib/auth/session";

function flattenNodes(nodes: CurriculumNode[]): CurriculumNode[] {
  const out: CurriculumNode[] = [];
  const walk = (list: CurriculumNode[]) => {
    for (const node of list) {
      out.push(node);
      if (node.children?.length) walk(node.children);
    }
  };
  walk(nodes);
  return out;
}

function NodeList({ nodes, depth = 0 }: { nodes: CurriculumNode[]; depth?: number }) {
  return (
    <ul className="space-y-1">
      {nodes.map((node) => (
        <li key={node.id}>
          <div
            className="flex items-center gap-2 rounded-md px-2 py-1.5 text-sm"
            style={{ paddingLeft: 8 + depth * 14 }}
            data-testid={`curriculum-node-${node.id}`}
          >
            <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-slate-600">
              {node.node_type}
            </span>
            <span className="font-medium text-slate-900">{node.title}</span>
            <span className="text-xs text-slate-400">{node.code}</span>
          </div>
          {node.children && node.children.length > 0 && (
            <NodeList nodes={node.children} depth={depth + 1} />
          )}
        </li>
      ))}
    </ul>
  );
}

const nodeSchema = z.object({
  parentId: z.string().optional(),
  nodeType: z.string().min(1),
  code: z.string().min(1),
  name: z.string().min(1),
  description: z.string().optional(),
  sequence: z.coerce.number().int().min(0).optional(),
  status: z.string().optional(),
});

type NodeForm = z.infer<typeof nodeSchema>;

export default function CurriculumDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const queryClient = useQueryClient();
  const session = getSession();
  const canManage = hasPermission(session, "curriculum:manage");
  const [editingNodeId, setEditingNodeId] = useState<string | null>(null);

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["curriculum", id],
    queryFn: () => api.getCurriculum(id),
  });

  const flatNodes = useMemo(() => flattenNodes(data?.tree ?? []), [data?.tree]);

  const {
    register,
    handleSubmit,
    reset,
    setValue,
    formState: { errors },
  } = useForm<NodeForm>({
    resolver: zodResolver(nodeSchema),
    defaultValues: {
      parentId: "",
      nodeType: "UNIT",
      code: "",
      name: "",
      description: "",
      sequence: 0,
      status: "active",
    },
  });

  const createNode = useMutation({
    mutationFn: (values: NodeForm) => {
      if (!api.createCurriculumNode) {
        throw new Error("Curriculum node create is not available.");
      }
      return api.createCurriculumNode(id, {
        parentId: values.parentId || null,
        nodeType: values.nodeType,
        code: values.code,
        name: values.name,
        description: values.description,
        sequence: values.sequence,
        status: values.status,
      });
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["curriculum", id] });
      reset({ parentId: "", nodeType: "UNIT", code: "", name: "", description: "", sequence: 0 });
      setEditingNodeId(null);
    },
  });

  const updateNode = useMutation({
    mutationFn: (values: NodeForm) => {
      if (!api.updateCurriculumNode || !editingNodeId) {
        throw new Error("Curriculum node update is not available.");
      }
      return api.updateCurriculumNode(editingNodeId, {
        parentId: values.parentId || null,
        nodeType: values.nodeType,
        name: values.name,
        description: values.description,
        sequence: values.sequence,
        status: values.status,
      });
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["curriculum", id] });
      setEditingNodeId(null);
      reset();
    },
  });

  if (isLoading) return <LoadingState />;
  if (isError || !data) return <ErrorState onRetry={() => void refetch()} />;

  const startEdit = (node: CurriculumNode) => {
    setEditingNodeId(node.id);
    setValue("parentId", node.parent_id ?? "");
    setValue("nodeType", node.node_type);
    setValue("code", node.code);
    setValue("name", node.title);
    setValue("sequence", node.sort_order ?? 0);
    setValue("status", "active");
  };

  return (
    <div data-testid="curriculum-detail-page">
      <PageHeader
        title={data.curriculum.title}
        description={`Framework ${data.curriculum.board} · Version ${data.curriculum.grade_label}`}
        breadcrumbs={[
          { label: "Curriculum", href: "/curriculum" },
          { label: data.curriculum.code },
        ]}
      />
      {canManage && (
        <form
          data-testid="curriculum-node-form"
          className="mb-4 grid max-w-3xl gap-3 rounded-md border border-slate-200 bg-white p-4 sm:grid-cols-2"
          onSubmit={handleSubmit((values) =>
            editingNodeId ? updateNode.mutate(values) : createNode.mutate(values),
          )}
        >
          <h2 className="sm:col-span-2 text-sm font-semibold text-slate-900">
            {editingNodeId ? "Edit node" : "+ Add node"}
          </h2>
          <label className="text-sm">
            Parent
            <Select data-testid="curriculum-node-parent" className="mt-1" {...register("parentId")}>
              <option value="">(root)</option>
              {flatNodes.map((node) => (
                <option key={node.id} value={node.id}>
                  {node.code} — {node.title}
                </option>
              ))}
            </Select>
          </label>
          <label className="text-sm">
            Node type
            <Select data-testid="curriculum-node-type" className="mt-1" {...register("nodeType")}>
              <option value="GRADE">GRADE</option>
              <option value="SUBJECT">SUBJECT</option>
              <option value="UNIT">UNIT</option>
              <option value="CHAPTER">CHAPTER</option>
              <option value="TOPIC">TOPIC</option>
              <option value="CONCEPT">CONCEPT</option>
            </Select>
          </label>
          <label className="text-sm">
            Code
            <Input
              data-testid="curriculum-node-code"
              className="mt-1"
              disabled={Boolean(editingNodeId)}
              {...register("code")}
            />
            {errors.code && (
              <span className="mt-1 block text-xs text-rose-700">{errors.code.message}</span>
            )}
          </label>
          <label className="text-sm">
            Name
            <Input data-testid="curriculum-node-name" className="mt-1" {...register("name")} />
            {errors.name && (
              <span className="mt-1 block text-xs text-rose-700">{errors.name.message}</span>
            )}
          </label>
          <label className="text-sm">
            Sequence
            <Input
              data-testid="curriculum-node-sequence"
              type="number"
              className="mt-1"
              {...register("sequence")}
            />
          </label>
          <label className="text-sm">
            Status
            <Select data-testid="curriculum-node-status" className="mt-1" {...register("status")}>
              <option value="active">active</option>
              <option value="inactive">inactive</option>
            </Select>
          </label>
          <label className="sm:col-span-2 text-sm">
            Description
            <Input
              data-testid="curriculum-node-description"
              className="mt-1"
              {...register("description")}
            />
          </label>
          <div className="sm:col-span-2 flex flex-wrap gap-2">
            <Button
              type="submit"
              data-testid="curriculum-node-submit"
              disabled={createNode.isPending || updateNode.isPending}
            >
              {editingNodeId ? "Save node" : "Add node"}
            </Button>
            {editingNodeId && (
              <Button
                type="button"
                variant="secondary"
                onClick={() => {
                  setEditingNodeId(null);
                  reset();
                }}
              >
                Cancel edit
              </Button>
            )}
          </div>
        </form>
      )}
      <div className="rounded-md border border-slate-200 bg-white p-4">
        {data.tree.length > 0 ? (
          <>
            {canManage && (
              <ul className="mb-3 flex flex-wrap gap-2 text-xs">
                {flatNodes.map((node) => (
                  <li key={`edit-${node.id}`}>
                    <button
                      type="button"
                      className="rounded border border-slate-200 px-2 py-1 hover:bg-slate-50"
                      data-testid={`curriculum-node-edit-${node.id}`}
                      onClick={() => startEdit(node)}
                    >
                      Edit {node.code}
                    </button>
                  </li>
                ))}
              </ul>
            )}
            <NodeList nodes={data.tree} />
          </>
        ) : (
          <p data-testid="curriculum-tree-empty" className="text-sm text-slate-500">
            No curriculum nodes yet.
          </p>
        )}
      </div>
    </div>
  );
}
