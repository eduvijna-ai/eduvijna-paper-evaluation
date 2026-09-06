import { afterEach, describe, expect, it, vi } from "vitest";
import {
  identityReviewApiToView,
  paperPageApiToView,
  submissionApiToView,
  type B3IdentityReviewDto,
  type B3SubmissionDto,
} from "@/lib/api/http/submissions";
import { getApiCapabilities } from "@/lib/api/capabilities";

describe("B3 submission mappers", () => {
  const dto: B3SubmissionDto = {
    id: "11111111-1111-4111-8111-111111111111",
    tenant_id: "22222222-2222-4222-8222-222222222222",
    assessment_id: "33333333-3333-4333-8333-333333333333",
    assessment_version_id: "44444444-4444-4444-8444-444444444444",
    assessment_title: "Mid-Term Math",
    student_id: null,
    student_display_name: null,
    workflow_state: "IDENTITY_REVIEW",
    student_match_state: "REVIEW_REQUIRED",
    roll_number_detected: null,
    name_detected: null,
    identity_confidence: "0.0000",
    mapping_confidence: 0,
    source_content_sha256: "abc123",
    original_filename: "sheet.pdf",
    mime_type: "application/pdf",
    byte_size: 1024,
    storage_status: "AVAILABLE",
    page_count: 2,
    bundle_name: "batch-1",
    uploaded_at: "2026-09-06T10:00:00Z",
    updated_at: "2026-09-06T10:05:00Z",
  };

  it("maps submission dump to domain without inventing identity confidence", () => {
    const view = submissionApiToView(dto);
    expect(view).toMatchObject({
      id: dto.id,
      assessment_title: "Mid-Term Math",
      workflow_state: "IDENTITY_REVIEW",
      student_match_state: "REVIEW_REQUIRED",
      identity_confidence: 0,
      mapping_confidence: 0,
      page_count: 2,
      original_filename: "sheet.pdf",
      source_content_sha256: "abc123",
    });
  });

  it("maps pages with defaults when dimensions are missing", () => {
    expect(
      paperPageApiToView({
        id: "p1",
        page_index: 0,
      }),
    ).toMatchObject({
      id: "p1",
      page_number: 1,
      label: "Page 1",
      width: 800,
      height: 1100,
    });
  });

  it("maps identity review payload including zero-confidence candidates", () => {
    const payload: B3IdentityReviewDto = {
      submission: dto,
      pages: [{ id: "p1", page_number: 1, label: "Page 1", width: 100, height: 200 }],
      candidates: [
        {
          student_id: "s1",
          display_name: "Ada",
          external_ref: "STU-1",
          confidence: 0,
          match_reasons: ["Manual roster selection"],
        },
      ],
      automated_matching_active: false,
    };
    const view = identityReviewApiToView(payload);
    expect(view.pages).toHaveLength(1);
    expect(view.candidates[0]).toMatchObject({
      student_id: "s1",
      confidence: 0,
      match_reasons: ["Manual roster selection"],
    });
  });
});

describe("B3 API capabilities", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("marks submissions, identityReview, and mapping live in hybrid", () => {
    vi.stubEnv("NEXT_PUBLIC_API_MODE", "hybrid");
    const caps = getApiCapabilities();
    expect(caps.submissions).toBe("live");
    expect(caps.identityReview).toBe("live");
    expect(caps.mapping).toBe("live");
    expect(caps.transcription).toBe("live");
    expect(caps.evaluation).toBe("live");
    expect(caps.reports).toBe("mock");
    expect(caps.analytics).toBe("mock");
    expect(caps.learning).toBe("mock");
  });

  it("keeps all domains mock in default mock mode", () => {
    vi.stubEnv("NEXT_PUBLIC_API_MODE", "mock");
    const caps = getApiCapabilities();
    expect(caps.submissions).toBe("mock");
    expect(caps.identityReview).toBe("mock");
    expect(caps.mapping).toBe("mock");
    expect(caps.evaluation).toBe("mock");
  });
});
