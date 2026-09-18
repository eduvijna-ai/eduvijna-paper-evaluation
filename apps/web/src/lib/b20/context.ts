/** Bounded B20 subject/language presentation helpers. */

export const B20_SUBJECT_PROFILES = [
  "MATHEMATICS",
  "PHYSICS",
  "CHEMISTRY",
  "STATISTICS",
  "ACCOUNTING",
  "STRUCTURED_DESCRIPTIVE",
  "UNSPECIFIED",
  "UNSUPPORTED",
] as const;

export type B20SubjectProfile = (typeof B20_SUBJECT_PROFILES)[number];

export const B20_LANGUAGE_OPTIONS = [
  { language: "en", script: "Latn", label: "English (Latin)" },
  { language: "hi", script: "Deva", label: "Hindi (Devanagari)" },
] as const;

export const B20_UNSUPPORTED_LANGUAGE_OPTION = {
  language: "ja",
  script: "Jpan",
  label: "Japanese (unsupported fixture)",
} as const;

export const B20_ERROR_CODES = {
  SUBJECT_PROFILE_UNSUPPORTED: "SUBJECT_PROFILE_UNSUPPORTED",
  LANGUAGE_UNSUPPORTED: "LANGUAGE_UNSUPPORTED",
  LANGUAGE_REVIEW_REQUIRED: "LANGUAGE_REVIEW_REQUIRED",
  SCRIPT_UNSUPPORTED: "SCRIPT_UNSUPPORTED",
  LANGUAGE_CONTEXT_REQUIRED: "LANGUAGE_CONTEXT_REQUIRED",
  LANGUAGE_CONTEXT_LOCKED: "LANGUAGE_CONTEXT_LOCKED",
} as const;

export function isKnownSubjectProfile(value: string | null | undefined): boolean {
  if (!value) return false;
  return (B20_SUBJECT_PROFILES as readonly string[]).includes(value);
}

export function subjectProfileLabel(value: string | null | undefined): string {
  if (!value) return "Unspecified";
  if (value === "STRUCTURED_DESCRIPTIVE") return "Structured descriptive";
  if (value === "UNSPECIFIED") return "Unspecified (legacy)";
  if (value === "UNSUPPORTED") return "Unsupported";
  return value.charAt(0) + value.slice(1).toLowerCase();
}

export function languageStateLabel(value: string | null | undefined): string {
  switch ((value ?? "UNKNOWN").toUpperCase()) {
    case "CONFIRMED":
      return "Confirmed";
    case "REVIEW_REQUIRED":
      return "Review required";
    case "UNSUPPORTED":
      return "Unsupported";
    default:
      return "Unknown";
  }
}

export function isMathVerificationEligible(profile: string | null | undefined): boolean {
  return profile === "MATHEMATICS" || profile === "UNSPECIFIED" || !profile;
}

export function isAutomationBlocked(code: string | null | undefined): boolean {
  if (!code) return false;
  return Object.values(B20_ERROR_CODES).includes(
    code as (typeof B20_ERROR_CODES)[keyof typeof B20_ERROR_CODES],
  );
}

export function canMutateSubmissionLanguage(session: {
  authMode?: string;
  role?: string;
  permissions?: string[];
} | null): boolean {
  if (!session) return false;
  if (session.authMode === "demo") {
    return (
      session.role === "PLATFORM_ADMIN" ||
      session.role === "TEACHER" ||
      (session.permissions ?? []).includes("submission:review") ||
      (session.permissions ?? []).includes("submission:upload")
    );
  }
  const permissions = session.permissions ?? [];
  return (
    permissions.includes("submission:review") ||
    permissions.includes("submission:upload")
  );
}

export function needsLanguageConfirmation(
  languageState?: string | null,
  automationBlockCode?: string | null,
): boolean {
  if ((languageState ?? "").toUpperCase() === "REVIEW_REQUIRED") return true;
  return automationBlockCode === B20_ERROR_CODES.LANGUAGE_REVIEW_REQUIRED;
}

export function buildLanguageConfirmRequest(
  languageCode: string,
  scriptCode: string,
): {
  language_code: string;
  script_code: string;
  source: "PROVIDED";
  confirm: true;
} {
  return {
    language_code: languageCode,
    script_code: scriptCode,
    source: "PROVIDED",
    confirm: true,
  };
}
