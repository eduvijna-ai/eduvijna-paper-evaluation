/** Whether all required evidence regions have a confirmed transcription outcome. */
export function isTranscriptionReviewComplete(
  reviewed: number,
  required: number,
): boolean {
  return reviewed === required;
}

/** Finalize control eligibility (permission + busy handled separately). */
export function canFinalizeTranscriptionWorkspace(
  reviewed: number,
  required: number,
  busy: boolean,
): boolean {
  return !busy && isTranscriptionReviewComplete(reviewed, required);
}
