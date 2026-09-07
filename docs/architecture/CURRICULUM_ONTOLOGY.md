# Curriculum Ontology

**Product:** EduVijna Paper Evaluation (CVB v0.1)  
**Last updated:** 2026-09-04  
**Related:** [DOMAIN_MODEL.md](./DOMAIN_MODEL.md), [DATABASE_SCHEMA.md](./DATABASE_SCHEMA.md)

---

## 1. Purpose

EduVijna maps every assessment question and evaluation outcome to an **institution-approved curriculum**. Learning recommendations, mastery tracking, and improvement assessments are **constrained to this curriculum** — no open-web content links in CVB.

---

## 2. Hierarchy

Canonical levels (top → bottom):

```
Curriculum
 └── Grade / Semester
      └── Subject
           └── Unit
                └── Chapter
                     └── Topic
                          └── Subtopic
                               └── Concept
                                    └── Skill
                                         └── Learning Outcome
```

**CVB note:** Mathematics pilot typically uses Grade → Subject (Mathematics) → Unit → Chapter → Topic → Concept → Skill → Learning Outcome. `Semester` and `Subtopic` are optional intermediate levels for higher-ed boards.

---

## 3. Generic CurriculumNode Model

All hierarchy levels are stored as **`CurriculumNode`** rows distinguished by `node_type`.

### 3.1 Node types

| `node_type` | Typical parent | Description |
|-------------|----------------|-------------|
| `GRADE` | — (root under Curriculum) | e.g. Grade 10 |
| `SEMESTER` | Grade or Curriculum | Higher-ed term |
| `SUBJECT` | Grade/Semester | e.g. Mathematics |
| `UNIT` | Subject | Major syllabus unit |
| `CHAPTER` | Unit | Textbook chapter |
| `TOPIC` | Chapter | Teachable topic |
| `SUBTOPIC` | Topic | Optional finer split |
| `CONCEPT` | Topic/Subtopic | Atomic knowledge unit |
| `SKILL` | Concept | Procedural capability |
| `LEARNING_OUTCOME` | Skill/Concept | Measurable outcome statement |

### 3.2 Fields (see DOMAIN_MODEL)

- Tree via `parent_id` self-FK
- Stable `code` unique within curriculum (e.g. `G10-MATH-U3-C2-T1-CPT-quadratic-formula`)
- `sort_order` for sibling ordering
- `metadata` JSONB: Bloom level, board standard refs, difficulty band

### 3.3 Tree rules

1. Single root path from Curriculum to any node.
2. `node_type` depth should follow hierarchy order; skips allowed (e.g. Topic → Concept without Subtopic).
3. A question maps to **one or more** nodes, typically at `CONCEPT`, `SKILL`, or `LEARNING_OUTCOME` granularity.

---

## 4. Prerequisites

### 4.1 Model

`CurriculumPrerequisite` is a **directed edge**:

```
from_node_id  ──prerequisite──▶  to_node_id
```

- **`from_node`**: prerequisite concept/skill/LO
- **`to_node`**: dependent concept/skill/LO that assumes mastery of `from_node`
- **`strength`**: `REQUIRED` (must master first) or `RECOMMENDED` (helpful)

### 4.2 Graph properties

- Edges are scoped to one `curriculum_id`.
- Cycles forbidden — validated on write.
- Transitive closure computed at recommendation time (not stored).

### 4.3 Example

```
[Linear Equations] ──REQUIRED──▶ [Quadratic Equations]
[Factorisation]    ──REQUIRED──▶ [Quadratic Formula Application]
```

---

## 5. Question & Evaluation Mapping

| Artifact | Mapping |
|----------|---------|
| `QuestionVersion.curriculum_node_ids` | Primary curriculum tags |
| `RubricCriterion.curriculum_node_ids` | Criterion-level granularity |
| `QuestionEvaluation.curriculum_concept_ids` | Evaluated concepts from ledger |
| `MasteryEvidence.curriculum_node_id` | Evidence per node |

**Rule:** Evaluation error taxonomy codes ([ERROR_TAXONOMY.md](./ERROR_TAXONOMY.md)) combined with concept mapping drive weakness identification.

---

## 6. Learning Recommendations (Constraints)

`LearningRecommendation` MUST satisfy:

1. `curriculum_id` matches student's active curriculum for the subject.
2. `target_node_id` ∈ nodes of that curriculum.
3. `prerequisite_node_ids` ordered by topological sort of prerequisite graph.
4. No external URL resources in CVB — only node references and generated text.

**Repair-before-advance:** If weakness detected at node X, recommend prerequisites of X (strength = `REQUIRED`) before X itself.

---

## 7. Mastery Semantics

| Signal | Source |
|--------|--------|
| **Concept mastery** | Correct reasoning despite arithmetic slips → `MasteryEvidence.evidence_type = CONCEPT` |
| **Execution accuracy** | Procedural/arithmetic performance → `EXECUTION` |
| **Procedure** | Method selection → `PROCEDURE` |

`MasteryEvidence` is **B8 live**. `MasteryState` longitudinal aggregates remain
**AFTER_CLIENT_APPROVAL** — B8 exposes a current evidence profile via API projection only,
without persisting `mastery_states` rows ([DOMAIN_MODEL.md](./DOMAIN_MODEL.md)).

---

## 8. Import & Authoring (CVB)

- Curriculum authored via admin UI or CSV import (future).
- CVB ships **synthetic demo curriculum** for Mathematics Grade 10.
- Versioning: bump `Curriculum.version` on structural change; historical evaluations retain node IDs (nodes soft-archived, not deleted).

---

## 9. API Surface (Preview)

| Endpoint | Purpose |
|----------|---------|
| `GET /api/v1/curricula/{id}/tree` | Nested node tree |
| `GET /api/v1/curricula/{id}/prerequisites` | Edge list |
| `GET /api/v1/curriculum-nodes/{id}/ancestors` | Breadcrumb path |

Full conventions: [API_CONVENTIONS.md](./API_CONVENTIONS.md).

---

## 10. Document Control

| Version | Date | Change |
|---------|------|--------|
| 0.1 | 2026-09-04 | Initial curriculum ontology |
