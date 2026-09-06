"use client";

import { useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { api, isApiError } from "@/lib/api";
import { getApiCapabilities } from "@/lib/api/capabilities";
import { PageHeader } from "@/components/layout/PageHeader";
import { Button, Input, Select } from "@/components/ui/primitives";
import { LoadingState } from "@/components/ui/FeedbackStates";

const mockSchema = z.object({
  assessmentId: z.string().min(1),
  bundleName: z.string().min(1),
});

const liveSchema = z.object({
  assessmentId: z.string().min(1, "Select an active assessment"),
  bundleName: z.string().optional(),
});

type MockFormValues = z.infer<typeof mockSchema>;
type LiveFormValues = z.infer<typeof liveSchema>;

function RawUnmarkedBanner() {
  return (
    <div
      data-testid="raw-unmarked-banner"
      className="mb-4 rounded-md border-2 border-amber-400 bg-amber-50 px-4 py-4"
      role="note"
    >
      <p className="text-xs font-semibold uppercase tracking-wide text-amber-900">
        Upload requirement
      </p>
      <p className="mt-1 text-base font-bold tracking-tight text-amber-950 sm:text-lg">
        RAW, UNMARKED HANDWRITTEN ANSWER SHEETS
      </p>
      <p className="mt-1 text-sm text-amber-900/90">
        Do not upload marked, annotated, or typed scripts. Only unmarked
        handwritten student answer sheets are accepted for identity, mapping,
        and evaluation.
      </p>
    </div>
  );
}

function MockUploadForm() {
  const router = useRouter();
  const [message, setMessage] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<MockFormValues>({
    resolver: zodResolver(mockSchema),
    defaultValues: {
      assessmentId: "assess-demo-001",
      bundleName: "demo-papers-batch-01",
    },
  });

  return (
    <form
      className="max-w-lg space-y-4 rounded-md border border-slate-200 bg-white p-4"
      onSubmit={handleSubmit(() => {
        setMessage("Demo bundle accepted. Opening identity review queue…");
        setTimeout(() => router.push("/submissions/sub-demo-002/identity"), 400);
      })}
    >
      <label className="block text-sm">
        <span className="font-medium text-slate-800">Assessment</span>
        <Select
          data-testid="upload-assessment"
          className="mt-1"
          {...register("assessmentId")}
        >
          <option value="assess-demo-001">
            Mid-Term Mathematics — Demo Set A
          </option>
          <option value="assess-demo-002">
            Unit Test — Quadratic Equations
          </option>
        </Select>
      </label>
      <label className="block text-sm">
        <span className="font-medium text-slate-800">Bundle name</span>
        <Input
          data-testid="upload-bundle-name"
          className="mt-1"
          {...register("bundleName")}
        />
        {errors.bundleName && (
          <span className="mt-1 block text-xs text-rose-700">
            {errors.bundleName.message}
          </span>
        )}
      </label>
      <div className="rounded-md border border-dashed border-slate-300 bg-slate-50 px-4 py-8 text-center text-sm text-slate-500">
        Drop zone placeholder — CVB uses synthetic fixtures, not PDF uploads.
      </div>
      <Button type="submit" data-testid="upload-submit">
        Start demo upload
      </Button>
      {message && (
        <p data-testid="upload-success" className="text-sm text-teal-800">
          {message}
        </p>
      )}
    </form>
  );
}

function LiveUploadForm() {
  const router = useRouter();
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  const assessmentsQuery = useQuery({
    queryKey: ["assessments", "upload"],
    queryFn: () => api.listAssessments(),
  });

  const activeAssessments = useMemo(
    () =>
      (assessmentsQuery.data ?? []).filter(
        (a) => a.workflow_state === "ACTIVE",
      ),
    [assessmentsQuery.data],
  );

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LiveFormValues>({
    resolver: zodResolver(liveSchema),
    defaultValues: {
      assessmentId: "",
      bundleName: "",
    },
  });

  if (assessmentsQuery.isLoading) return <LoadingState />;

  if (activeAssessments.length === 0) {
    return (
      <div
        data-testid="upload-empty-active"
        className="max-w-lg rounded-md border border-slate-200 bg-white p-4 text-sm text-slate-700"
      >
        No ACTIVE assessments are available for upload. Activate an assessment
        before ingesting answer sheets.
      </div>
    );
  }

  return (
    <form
      className="max-w-lg space-y-4 rounded-md border border-slate-200 bg-white p-4"
      onSubmit={handleSubmit(async (values) => {
        if (!file) {
          setError("Choose a PDF or image file to upload.");
          return;
        }
        if (!api.uploadSubmission) {
          setError("Upload is not available in this API mode.");
          return;
        }
        setPending(true);
        setError(null);
        try {
          const created = await api.uploadSubmission({
            assessmentId: values.assessmentId,
            bundleName: values.bundleName,
            file,
          });
          router.push(`/submissions/${created.id}`);
        } catch (err) {
          setError(
            isApiError(err)
              ? err.message || err.userMessage()
              : err instanceof Error
                ? err.message
                : "Upload failed",
          );
        } finally {
          setPending(false);
        }
      })}
    >
      <label className="block text-sm">
        <span className="font-medium text-slate-800">Assessment</span>
        <Select
          data-testid="upload-assessment"
          className="mt-1"
          disabled={pending}
          {...register("assessmentId")}
        >
          <option value="">Select an ACTIVE assessment…</option>
          {activeAssessments.map((a) => (
            <option key={a.id} value={a.id}>
              {a.title} ({a.code})
            </option>
          ))}
        </Select>
        {errors.assessmentId && (
          <span className="mt-1 block text-xs text-rose-700">
            {errors.assessmentId.message}
          </span>
        )}
      </label>
      <label className="block text-sm">
        <span className="font-medium text-slate-800">
          Bundle name <span className="font-normal text-slate-500">(optional)</span>
        </span>
        <Input
          data-testid="upload-bundle-name"
          className="mt-1"
          disabled={pending}
          {...register("bundleName")}
        />
      </label>
      <label className="block text-sm">
        <span className="font-medium text-slate-800">Answer sheet file</span>
        <Input
          data-testid="upload-file"
          className="mt-1"
          type="file"
          accept=".pdf,.png,.jpg,.jpeg,application/pdf,image/png,image/jpeg"
          disabled={pending}
          onChange={(e) => {
            const next = e.target.files?.[0] ?? null;
            setFile(next);
            setError(null);
          }}
        />
        {file && (
          <span
            data-testid="upload-filename"
            className="mt-1 block text-xs text-slate-600"
          >
            {file.name}
          </span>
        )}
      </label>
      <Button type="submit" data-testid="upload-submit" disabled={pending}>
        {pending ? "Uploading…" : "Upload submission"}
      </Button>
      {error && (
        <p data-testid="upload-error" className="text-sm text-rose-700">
          {error}
        </p>
      )}
    </form>
  );
}

export default function SubmissionsUploadPage() {
  const capabilities = getApiCapabilities();
  const live = capabilities.submissions === "live";

  return (
    <div data-testid="submissions-upload-page">
      <PageHeader
        title="Upload submissions"
        description={
          live
            ? "Upload raw unmarked answer sheets for live identity review."
            : "Mock upload only — stores no real scanned papers."
        }
        breadcrumbs={[
          { label: "Submissions", href: "/submissions" },
          { label: "Upload" },
        ]}
      />
      <RawUnmarkedBanner />
      {live ? <LiveUploadForm /> : <MockUploadForm />}
    </div>
  );
}
