import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactElement } from "react";
import { LanguageReviewPanel } from "@/lib/b20/LanguageReviewPanel";
import { ApiError } from "@/lib/api/http/errors";
import type { Submission } from "@/lib/types/domain";

const putSubmissionLanguage = vi.fn();

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    api: {
      putSubmissionLanguage: (...args: unknown[]) => putSubmissionLanguage(...args),
    },
  };
});

function wrap(ui: ReactElement) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

function confirmedSubmission(overrides: Partial<Submission> = {}): Submission {
  return {
    id: "sub-review",
    tenant_id: "t1",
    assessment_id: "a1",
    assessment_title: "Mathematics",
    student_id: "s1",
    student_display_name: "Demo",
    roll_number_detected: "R1",
    name_detected: "Demo",
    workflow_state: "IDENTITY_REVIEW",
    student_match_state: "REVIEW_REQUIRED",
    identity_confidence: 0.4,
    mapping_confidence: 0,
    page_count: 1,
    uploaded_at: "2026-09-18T10:00:00Z",
    updated_at: "2026-09-18T10:00:00Z",
    language_code: "hi",
    script_code: "Deva",
    language_source: "PROVIDED",
    language_confidence: null,
    language_state: "CONFIRMED",
    automation_block_code: null,
    ...overrides,
  };
}

describe("LanguageReviewPanel", () => {
  afterEach(() => {
    putSubmissionLanguage.mockReset();
  });

  it("renders review-required detected language as needing confirmation", () => {
    wrap(
      <LanguageReviewPanel
        submissionId="sub-review"
        languageCode="hi"
        scriptCode="Deva"
        languageSource="DETECTED"
        languageState="REVIEW_REQUIRED"
        automationBlockCode="LANGUAGE_REVIEW_REQUIRED"
      />,
    );
    expect(screen.getByTestId("language-review-panel")).toBeInTheDocument();
    expect(screen.getByTestId("language-review-source")).toHaveTextContent("DETECTED");
    expect(screen.getByTestId("language-review-state")).toHaveTextContent(/Review required/i);
    expect(screen.getByTestId("confirm-language")).toBeInTheDocument();
  });

  it("sends provided confirmation for the same language/script pair", async () => {
    const user = userEvent.setup();
    putSubmissionLanguage.mockResolvedValue(confirmedSubmission());
    wrap(
      <LanguageReviewPanel
        submissionId="sub-review"
        languageCode="hi"
        scriptCode="Deva"
        languageSource="DETECTED"
        languageState="REVIEW_REQUIRED"
        automationBlockCode="LANGUAGE_REVIEW_REQUIRED"
      />,
    );
    await user.click(screen.getByTestId("confirm-language"));
    await waitFor(() => {
      expect(putSubmissionLanguage).toHaveBeenCalledWith("sub-review", {
        language_code: "hi",
        script_code: "Deva",
        source: "PROVIDED",
        confirm: true,
      });
    });
    await waitFor(() => {
      expect(screen.queryByTestId("language-review-panel")).not.toBeInTheDocument();
    });
  });

  it("surfaces LANGUAGE_CONTEXT_LOCKED for a prohibited correction", async () => {
    const user = userEvent.setup();
    putSubmissionLanguage.mockRejectedValue(
      new ApiError({
        message: "Language/script cannot change after transcription evidence exists",
        status: 409,
        kind: "conflict",
        code: "LANGUAGE_CONTEXT_LOCKED",
      }),
    );
    wrap(
      <LanguageReviewPanel
        submissionId="sub-review"
        languageCode="hi"
        scriptCode="Deva"
        languageSource="DETECTED"
        languageState="REVIEW_REQUIRED"
        automationBlockCode="LANGUAGE_REVIEW_REQUIRED"
      />,
    );
    await user.selectOptions(screen.getByTestId("language-review-language"), "en");
    await user.click(screen.getByTestId("confirm-language"));
    await waitFor(() => {
      expect(screen.getByTestId("language-review-error")).toHaveTextContent(
        "LANGUAGE_CONTEXT_LOCKED",
      );
    });
    expect(screen.getByTestId("language-review-panel")).toBeInTheDocument();
  });

  it("does not offer confirmation for unsupported language", () => {
    wrap(
      <LanguageReviewPanel
        submissionId="sub-unsupported"
        languageCode="ja"
        scriptCode="Jpan"
        languageSource="PROVIDED"
        languageState="UNSUPPORTED"
        automationBlockCode="LANGUAGE_UNSUPPORTED"
      />,
    );
    expect(screen.queryByTestId("language-review-panel")).not.toBeInTheDocument();
    expect(screen.queryByTestId("confirm-language")).not.toBeInTheDocument();
  });
});
