"use client";

import { useEffect, useMemo, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api, isApiError } from "@/lib/api";
import { getSession } from "@/lib/auth/session";
import { Button, Select } from "@/components/ui/primitives";
import type { TranscriptionWorkspacePayload } from "@/lib/types/domain";
import {
  B20_ERROR_CODES,
  B20_LANGUAGE_OPTIONS,
  buildLanguageConfirmRequest,
  canMutateSubmissionLanguage,
  languageStateLabel,
  needsLanguageConfirmation,
} from "@/lib/b20/context";

export function LanguageReviewPanel({
  submissionId,
  languageCode,
  scriptCode,
  languageSource,
  languageState,
  automationBlockCode,
}: {
  submissionId: string;
  languageCode?: string | null;
  scriptCode?: string | null;
  languageSource?: string | null;
  languageState?: string | null;
  automationBlockCode?: string | null;
}) {
  const queryClient = useQueryClient();
  const [language, setLanguage] = useState(languageCode ?? "");
  const [script, setScript] = useState(scriptCode ?? "");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLanguage(languageCode ?? "");
    setScript(scriptCode ?? "");
  }, [languageCode, scriptCode]);

  const options = useMemo(() => {
    const rows: Array<{ language: string; script: string; label: string }> =
      B20_LANGUAGE_OPTIONS.map((option) => ({
        language: option.language,
        script: option.script,
        label: option.label,
      }));
    if (
      languageCode &&
      !rows.some(
        (row) => row.language === languageCode && row.script === (scriptCode ?? ""),
      )
    ) {
      rows.push({
        language: languageCode,
        script: scriptCode ?? "",
        label: `${languageCode} (${scriptCode ?? "unknown"})`,
      });
    }
    return rows;
  }, [languageCode, scriptCode]);

  const scriptsForLanguage = options.filter((row) => row.language === language);

  const mutation = useMutation({
    mutationFn: () => {
      if (!api.putSubmissionLanguage) {
        throw new Error("Language confirmation is not available");
      }
      return api.putSubmissionLanguage(
        submissionId,
        buildLanguageConfirmRequest(language, script),
      );
    },
    onSuccess: async (updated) => {
      setError(null);
      queryClient.setQueryData(["submission", submissionId], { ...updated });
      queryClient.setQueryData(
        ["transcription", submissionId],
        (current: TranscriptionWorkspacePayload | undefined) => {
          if (!current) return current;
          return {
            ...current,
            language_context: {
              language_code: updated.language_code ?? null,
              script_code: updated.script_code ?? null,
              language_source: updated.language_source ?? null,
              language_confidence: updated.language_confidence ?? null,
              language_state: updated.language_state ?? "UNKNOWN",
            },
            automation_block_code: updated.automation_block_code ?? null,
          };
        },
      );
      await queryClient.invalidateQueries({ queryKey: ["submission", submissionId] });
      await queryClient.invalidateQueries({ queryKey: ["transcription", submissionId] });
    },
    onError: (err: unknown) => {
      if (isApiError(err) && err.code === B20_ERROR_CODES.LANGUAGE_CONTEXT_LOCKED) {
        setError(B20_ERROR_CODES.LANGUAGE_CONTEXT_LOCKED);
        return;
      }
      setError(
        isApiError(err)
          ? [err.code, err.message].filter(Boolean).join(" — ")
          : err instanceof Error
            ? err.message
            : "Language confirmation failed",
      );
    },
  });

  const effective = mutation.data;
  const state = effective?.language_state ?? languageState;
  const source = effective?.language_source ?? languageSource;
  const block =
    effective?.automation_block_code !== undefined
      ? effective.automation_block_code
      : automationBlockCode;
  if (!needsLanguageConfirmation(state, block)) {
    return null;
  }

  const canConfirm = canMutateSubmissionLanguage(getSession());

  return (
    <div
      data-testid="language-review-panel"
      className="mb-6 rounded-md border border-amber-200 bg-amber-50 p-4 text-sm text-amber-950"
    >
      <p className="font-semibold">Language review required</p>
      <p className="mt-1 text-xs">
        Confirm the detected language and script, or correct them before transcription
        proceeds.
      </p>
      <dl className="mt-3 grid gap-2 sm:grid-cols-2">
        <div>
          <dt className="text-xs text-amber-800">Provenance</dt>
          <dd data-testid="language-review-source" className="font-semibold">
            {source ?? "UNKNOWN"}
          </dd>
        </div>
        <div>
          <dt className="text-xs text-amber-800">State</dt>
          <dd data-testid="language-review-state" className="font-semibold">
            {languageStateLabel(state)}
          </dd>
        </div>
      </dl>
      {canConfirm ? (
        <>
          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            <label className="block">
              <span className="text-xs font-medium">Language</span>
              <Select
                data-testid="language-review-language"
                className="mt-1"
                value={language}
                onChange={(event) => {
                  const next = event.target.value;
                  setLanguage(next);
                  const match = options.find((row) => row.language === next);
                  if (match) setScript(match.script);
                }}
              >
                {Array.from(new Map(options.map((row) => [row.language, row])).values()).map(
                  (row) => (
                    <option key={row.language} value={row.language}>
                      {row.label}
                    </option>
                  ),
                )}
              </Select>
            </label>
            <label className="block">
              <span className="text-xs font-medium">Script</span>
              <Select
                data-testid="language-review-script"
                className="mt-1"
                value={script}
                onChange={(event) => setScript(event.target.value)}
              >
                {scriptsForLanguage.map((row) => (
                  <option key={`${row.language}-${row.script}`} value={row.script}>
                    {row.script}
                  </option>
                ))}
              </Select>
            </label>
          </div>
          {error && (
            <p
              data-testid="language-review-error"
              className="mt-3 rounded-md border border-rose-200 bg-rose-50 px-2 py-1 text-xs font-medium text-rose-900"
            >
              {error}
            </p>
          )}
          <Button
            className="mt-3"
            data-testid="confirm-language"
            disabled={!language || !script || mutation.isPending}
            onClick={() => mutation.mutate()}
          >
            Confirm language
          </Button>
        </>
      ) : (
        <p data-testid="language-review-readonly" className="mt-3 text-xs">
          Language confirmation requires submission:review or submission:upload.
        </p>
      )}
    </div>
  );
}
