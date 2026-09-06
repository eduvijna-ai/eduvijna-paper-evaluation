import { describe, expect, it } from "vitest";
import {
  answerKeyApiToView,
  assessmentApiToView,
  assessmentFormToApi,
  countCurriculumNodes,
  curriculumApiToView,
  curriculumMappingsToView,
  curriculumNodeTitleMap,
  questionTreeApiToView,
  rubricCriterionApiToView,
} from "@/lib/api/mappers/authoring";
import type { A2CurriculumNode, A2QuestionVersion } from "@/lib/api/a2-types";

describe("B2 A2 authoring mappers", () => {
  const tree: A2CurriculumNode[] = [
    {
      id: "n1",
      tenant_id: "t1",
      curriculum_id: "c1",
      parent_id: null,
      node_type: "SUBJECT",
      code: "MATH",
      name: "Mathematics",
      sequence: 1,
      status: "active",
      children: [
        {
          id: "n2",
          tenant_id: "t1",
          curriculum_id: "c1",
          parent_id: "n1",
          node_type: "TOPIC",
          code: "ALG",
          name: "Algebra",
          sequence: 2,
          status: "active",
          children: [],
        },
      ],
    },
  ];

  it("maps curriculum metadata and recursively counts nodes", () => {
    expect(countCurriculumNodes(tree)).toBe(2);
    const view = curriculumApiToView(
      {
        id: "c1",
        tenant_id: "t1",
        code: "CUR",
        name: "Math curriculum",
        academic_framework: "CBSE",
        version_label: "2026",
        status: "active",
      },
      2,
    );
    expect(view).toMatchObject({
      title: "Math curriculum",
      board: "CBSE",
      grade_label: "2026",
      node_count: 2,
    });
  });

  it("maps live assessment and form without fabricating downstream counts", () => {
    const view = assessmentApiToView(
      {
        id: "a1",
        tenant_id: "t1",
        curriculum_id: "c1",
        code: "ASM",
        title: "Exam",
        assessment_type: "EXAM",
        max_marks: "40.00",
        status: "DRAFT",
      },
      {
        id: "c1",
        tenant_id: "t1",
        code: "CUR",
        name: "Mathematics",
        version_label: "2026",
        status: "active",
      },
      3,
    );
    expect(view.max_marks).toBe(40);
    expect(view.question_count).toBe(3);
    expect(view.submission_count).toBe(0);
    expect(view.subject).toBe("Mathematics");

    expect(
      assessmentFormToApi({
        curriculumId: "c1",
        code: " ASM-2 ",
        title: " Draft exam ",
        assessmentType: "EXAM",
        maxMarks: 10,
      }),
    ).toMatchObject({
      curriculum_id: "c1",
      code: "ASM-2",
      title: "Draft exam",
      max_marks: "10.00",
      academic_year_id: null,
      class_section_id: null,
    });
  });

  it("maps version-centric questions, answer keys, rubrics and mappings", () => {
    const questions: A2QuestionVersion[] = [
      {
        id: "qv1",
        tenant_id: "t1",
        assessment_version_id: "av1",
        question_id: "q1",
        parent_question_version_id: null,
        display_label: "1",
        sequence: 1,
        prompt_text: "2+2?",
        max_marks: "10.00",
        question_type: "SHORT",
        scoring_mode: "LEAF_SCORABLE",
        children: [],
      },
    ];
    expect(questionTreeApiToView(questions, "a1")[0]).toMatchObject({
      id: "qv1",
      assessment_id: "a1",
      code: "1",
      prompt: "2+2?",
      max_mark: 10,
    });

    expect(
      answerKeyApiToView(
        {
          id: "akv1",
          tenant_id: "t1",
          answer_key_id: "ak1",
          assessment_version_id: "av1",
          question_version_id: "qv1",
          version_number: 1,
          answer_text: "4",
          source_type: "TEACHER",
          status: "DRAFT",
        },
        new Map([["qv1", 10]]),
      ),
    ).toMatchObject({ question_id: "qv1", content: "4", marks: 10 });

    expect(
      rubricCriterionApiToView(
        {
          id: "rc1",
          tenant_id: "t1",
          rubric_version_id: "rv1",
          criterion_code: "C1",
          description: "Correct",
          max_marks: "10.00",
          sequence: 1,
          scoring_mode: "ADDITIVE",
          partial_credit_allowed: true,
          ecf_policy: "NONE",
        },
        "qv1",
      ),
    ).toMatchObject({ label: "C1", question_id: "qv1", max_marks: 10 });

    const titles = curriculumNodeTitleMap(tree);
    expect(
      curriculumMappingsToView(
        questions[0]!,
        [
          {
            id: "m1",
            tenant_id: "t1",
            question_version_id: "qv1",
            curriculum_node_id: "n2",
            mapping_type: "PRIMARY",
          },
        ],
        titles,
      ),
    ).toMatchObject({
      question_code: "1",
      curriculum_node_ids: ["n2"],
      node_titles: ["Algebra"],
    });
  });
});
