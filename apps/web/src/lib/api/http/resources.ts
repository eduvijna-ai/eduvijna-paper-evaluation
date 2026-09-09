import type {
  CurriculumResource,
  CurriculumResourceCreate,
  CurriculumResourceList,
  CurriculumResourceUpdate,
  StudentResourceAssignment,
  StudentResourceAssignmentCreate,
  StudentResourceAssignmentList,
} from "@/lib/types/domain";
import { httpRequest } from "./client";

export interface B13CurriculumResourceDto {
  id: string;
  curriculum_id: string;
  code: string;
  title: string;
  description?: string | null;
  resource_kind: string;
  status: string;
  content_ref: string;
  curriculum_node_ids?: string[];
  created_by?: string | null;
  approved_by?: string | null;
  approved_at?: string | null;
  created_at?: string;
  updated_at?: string;
}

export interface B13CurriculumResourceListDto {
  curriculum_id?: string | null;
  status_filter?: string | null;
  items?: B13CurriculumResourceDto[];
}

export interface B13StudentResourceAssignmentDto {
  id: string;
  student_id: string;
  resource_id: string;
  resource: B13CurriculumResourceDto;
  learning_recommendation_id?: string | null;
  status: string;
  assigned_by?: string | null;
  assigned_at?: string;
  cancelled_at?: string | null;
  cancelled_by?: string | null;
}

export interface B13StudentResourceAssignmentListDto {
  student_id: string;
  curriculum_id?: string | null;
  items?: B13StudentResourceAssignmentDto[];
}

export function curriculumResourceApiToView(
  dto: B13CurriculumResourceDto,
): CurriculumResource {
  return {
    id: dto.id,
    curriculum_id: dto.curriculum_id,
    code: dto.code,
    title: dto.title,
    description: dto.description ?? null,
    resource_kind: dto.resource_kind,
    status: dto.status,
    content_ref: dto.content_ref,
    curriculum_node_ids: [...(dto.curriculum_node_ids ?? [])],
    created_by: dto.created_by ?? null,
    approved_by: dto.approved_by ?? null,
    approved_at: dto.approved_at ?? null,
    created_at: dto.created_at ?? new Date().toISOString(),
    updated_at: dto.updated_at ?? new Date().toISOString(),
  };
}

export function curriculumResourceListApiToView(
  dto: B13CurriculumResourceListDto,
): CurriculumResourceList {
  return {
    curriculum_id: dto.curriculum_id ?? null,
    status_filter: dto.status_filter ?? null,
    items: (dto.items ?? []).map(curriculumResourceApiToView),
  };
}

export function studentResourceAssignmentApiToView(
  dto: B13StudentResourceAssignmentDto,
): StudentResourceAssignment {
  return {
    id: dto.id,
    student_id: dto.student_id,
    resource_id: dto.resource_id,
    resource: curriculumResourceApiToView(dto.resource),
    learning_recommendation_id: dto.learning_recommendation_id ?? null,
    status: dto.status,
    assigned_by: dto.assigned_by ?? null,
    assigned_at: dto.assigned_at ?? new Date().toISOString(),
    cancelled_at: dto.cancelled_at ?? null,
    cancelled_by: dto.cancelled_by ?? null,
  };
}

export function studentResourceAssignmentListApiToView(
  dto: B13StudentResourceAssignmentListDto,
): StudentResourceAssignmentList {
  return {
    student_id: dto.student_id,
    curriculum_id: dto.curriculum_id ?? null,
    items: (dto.items ?? []).map(studentResourceAssignmentApiToView),
  };
}

/**
 * Live B13 curriculum resource catalog + student assignment HTTP adapter.
 */
export const ResourcesHttpApi = {
  async listCurriculumResources(filters?: {
    curriculumId?: string;
    status?: string;
  }): Promise<CurriculumResourceList> {
    const params = new URLSearchParams();
    if (filters?.curriculumId) params.set("curriculum_id", filters.curriculumId);
    if (filters?.status) params.set("status", filters.status);
    const qs = params.toString();
    const dto = await httpRequest<B13CurriculumResourceListDto>(
      `/api/v1/learning/resources${qs ? `?${qs}` : ""}`,
    );
    return curriculumResourceListApiToView(dto);
  },

  async getCurriculumResource(id: string): Promise<CurriculumResource> {
    const dto = await httpRequest<B13CurriculumResourceDto>(
      `/api/v1/learning/resources/${id}`,
    );
    return curriculumResourceApiToView(dto);
  },

  async createCurriculumResource(
    input: CurriculumResourceCreate,
  ): Promise<CurriculumResource> {
    const dto = await httpRequest<B13CurriculumResourceDto>(
      `/api/v1/learning/resources`,
      {
        method: "POST",
        body: {
          curriculum_id: input.curriculum_id,
          code: input.code,
          title: input.title,
          description: input.description ?? null,
          resource_kind: input.resource_kind,
          content_ref: input.content_ref,
          curriculum_node_ids: input.curriculum_node_ids,
        },
      },
    );
    return curriculumResourceApiToView(dto);
  },

  async updateCurriculumResource(
    id: string,
    input: CurriculumResourceUpdate,
  ): Promise<CurriculumResource> {
    const dto = await httpRequest<B13CurriculumResourceDto>(
      `/api/v1/learning/resources/${id}`,
      { method: "PATCH", body: input },
    );
    return curriculumResourceApiToView(dto);
  },

  async approveCurriculumResource(id: string): Promise<CurriculumResource> {
    const dto = await httpRequest<B13CurriculumResourceDto>(
      `/api/v1/learning/resources/${id}/approve`,
      { method: "POST" },
    );
    return curriculumResourceApiToView(dto);
  },

  async activateCurriculumResource(id: string): Promise<CurriculumResource> {
    const dto = await httpRequest<B13CurriculumResourceDto>(
      `/api/v1/learning/resources/${id}/activate`,
      { method: "POST" },
    );
    return curriculumResourceApiToView(dto);
  },

  async deactivateCurriculumResource(id: string): Promise<CurriculumResource> {
    const dto = await httpRequest<B13CurriculumResourceDto>(
      `/api/v1/learning/resources/${id}/deactivate`,
      { method: "POST" },
    );
    return curriculumResourceApiToView(dto);
  },

  async replaceCurriculumResourceNodes(
    id: string,
    nodeIds: string[],
  ): Promise<CurriculumResource> {
    const dto = await httpRequest<B13CurriculumResourceDto>(
      `/api/v1/learning/resources/${id}/nodes`,
      {
        method: "PUT",
        body: { curriculum_node_ids: nodeIds },
      },
    );
    return curriculumResourceApiToView(dto);
  },

  async listStudentResourceAssignments(
    studentId: string,
    filters?: { curriculumId?: string; status?: string },
  ): Promise<StudentResourceAssignmentList> {
    const params = new URLSearchParams();
    if (filters?.curriculumId) params.set("curriculum_id", filters.curriculumId);
    if (filters?.status) params.set("status", filters.status);
    const qs = params.toString();
    const dto = await httpRequest<B13StudentResourceAssignmentListDto>(
      `/api/v1/learning/students/${studentId}/resource-assignments${qs ? `?${qs}` : ""}`,
    );
    return studentResourceAssignmentListApiToView(dto);
  },

  async assignStudentResource(
    studentId: string,
    input: StudentResourceAssignmentCreate,
  ): Promise<StudentResourceAssignment> {
    const dto = await httpRequest<B13StudentResourceAssignmentDto>(
      `/api/v1/learning/students/${studentId}/resource-assignments`,
      {
        method: "POST",
        body: {
          resource_id: input.resource_id,
          learning_recommendation_id: input.learning_recommendation_id ?? null,
        },
      },
    );
    return studentResourceAssignmentApiToView(dto);
  },

  async cancelStudentResourceAssignment(
    assignmentId: string,
  ): Promise<StudentResourceAssignment> {
    const dto = await httpRequest<B13StudentResourceAssignmentDto>(
      `/api/v1/learning/resource-assignments/${assignmentId}/cancel`,
      { method: "POST" },
    );
    return studentResourceAssignmentApiToView(dto);
  },
};
