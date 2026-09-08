/** Demo-only B14 IDs and blueprint items for mock UI (never live UUIDs). */

export const REASSESSMENT_ID = "reassessment-demo-001";
export const REASSESSMENT_ID_CREATED = "reassessment-demo-created";
export const IMP_BLUEPRINT_ID = "imp-demo-001";
export const IMP_ITEM_ID_1 = "imp-item-demo-001";
export const IMP_ITEM_ID_2 = "imp-item-demo-002";

export function getDemoApprovedBlueprintItems() {
  return [
    {
      id: IMP_ITEM_ID_1,
      learning_recommendation_id: null,
      curriculum_node_id: "node-concept-disc",
      node_code: "DISC",
      node_title: "Discriminant",
      item_code: "I1",
      template_kind: "CONCEPT_CHECK",
      question_template_ref: "tmpl://concept-check",
      focus: "Second Derivatives (2q)",
      difficulty: "MEDIUM",
      suggested_marks: 4,
      sort_order: 1,
    },
    {
      id: IMP_ITEM_ID_2,
      learning_recommendation_id: null,
      curriculum_node_id: "node-topic-sim",
      node_code: "SIM",
      node_title: "Simultaneous Equations",
      item_code: "I2",
      template_kind: "APPLICATION",
      question_template_ref: "tmpl://application",
      focus: "Second Derivatives — application",
      difficulty: "MEDIUM",
      suggested_marks: 4,
      sort_order: 2,
    },
  ];
}
