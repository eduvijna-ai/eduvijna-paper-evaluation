import { describe, expect, it } from "vitest";
import {
  curriculumFormToApi,
  curriculumNodeFormToApi,
} from "@/lib/api/mappers/authoring";

describe("curriculum authoring mappers", () => {
  it("maps curriculum create form to API contract", () => {
    expect(
      curriculumFormToApi({
        code: "CBSE-MATH",
        name: "Mathematics",
        academicFramework: "CBSE",
        versionLabel: "2026-27",
      }),
    ).toEqual({
      code: "CBSE-MATH",
      name: "Mathematics",
      description: null,
      academic_framework: "CBSE",
      version_label: "2026-27",
      status: "active",
    });
  });

  it("maps curriculum node form to API contract", () => {
    expect(
      curriculumNodeFormToApi({
        parentId: "parent-1",
        nodeType: "UNIT",
        code: "U1",
        name: "Algebra",
        sequence: 2,
      }),
    ).toEqual({
      parent_id: "parent-1",
      node_type: "UNIT",
      code: "U1",
      name: "Algebra",
      description: null,
      sequence: 2,
      metadata: {},
      status: "active",
    });
  });
});
