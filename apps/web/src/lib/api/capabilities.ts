import { getApiMode } from "./client";

/**
 * Semantic domain capability — ordinary feature components should use this
 * instead of inspecting transport mode ("mock" vs "hybrid").
 */
export type DomainCapability = "live" | "mock";

export interface ApiCapabilities {
  students: DomainCapability;
  guardians: DomainCapability;
  academicStructure: DomainCapability;
  institution: DomainCapability;
  curriculum: DomainCapability;
  assessments: DomainCapability;
  submissions: DomainCapability;
  reports: DomainCapability;
  analytics: DomainCapability;
  learning: DomainCapability;
  /** Developer-facing transport badge only */
  showTransportBadge: boolean;
}

export function getApiCapabilities(): ApiCapabilities {
  const hybrid = getApiMode() === "hybrid";
  if (hybrid) {
    return {
      students: "live",
      guardians: "live",
      academicStructure: "live",
      institution: "live",
      curriculum: "live",
      assessments: "live",
      submissions: "mock",
      reports: "mock",
      analytics: "mock",
      learning: "mock",
      showTransportBadge: true,
    };
  }
  return {
    students: "mock",
    guardians: "mock",
    academicStructure: "mock",
    institution: "mock",
    curriculum: "mock",
    assessments: "mock",
    submissions: "mock",
    reports: "mock",
    analytics: "mock",
    learning: "mock",
    showTransportBadge: true,
  };
}
