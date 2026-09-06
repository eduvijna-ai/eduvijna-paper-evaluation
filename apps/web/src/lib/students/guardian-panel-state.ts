export type GuardianPanelState =
  | "restricted"
  | "loading"
  | "error"
  | "empty"
  | "ready";

export function shouldLoadStudentGuardians(canRead: boolean): boolean {
  return canRead;
}

export function getGuardianPanelState(input: {
  canRead: boolean;
  isLoading: boolean;
  isError: boolean;
  guardianCount: number;
}): GuardianPanelState {
  if (!input.canRead) return "restricted";
  if (input.isLoading) return "loading";
  if (input.isError) return "error";
  if (input.guardianCount === 0) return "empty";
  return "ready";
}
