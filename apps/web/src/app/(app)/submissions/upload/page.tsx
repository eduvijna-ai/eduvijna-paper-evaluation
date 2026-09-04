"use client";

import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { useRouter } from "next/navigation";
import { PageHeader } from "@/components/layout/PageHeader";

const schema = z.object({
  assessmentId: z.string().min(1),
  bundleName: z.string().min(1),
});

type FormValues = z.infer<typeof schema>;

export default function SubmissionsUploadPage() {
  const router = useRouter();
  const [message, setMessage] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      assessmentId: "assess-demo-001",
      bundleName: "demo-papers-batch-01",
    },
  });

  return (
    <div data-testid="submissions-upload-page">
      <PageHeader
        title="Upload submissions"
        description="Mock upload only — stores no real scanned papers."
        breadcrumbs={[
          { label: "Submissions", href: "/submissions" },
          { label: "Upload" },
        ]}
      />
      <form
        className="max-w-lg space-y-4 rounded-md border border-slate-200 bg-white p-4"
        onSubmit={handleSubmit(() => {
          setMessage("Demo bundle accepted. Opening identity review queue…");
          setTimeout(() => router.push("/submissions/sub-demo-002/identity"), 400);
        })}
      >
        <label className="block text-sm">
          <span className="font-medium text-slate-800">Assessment</span>
          <select
            data-testid="upload-assessment"
            className="mt-1 w-full rounded-md border border-slate-200 px-3 py-2"
            {...register("assessmentId")}
          >
            <option value="assess-demo-001">
              Mid-Term Mathematics — Demo Set A
            </option>
            <option value="assess-demo-002">
              Unit Test — Quadratic Equations
            </option>
          </select>
        </label>
        <label className="block text-sm">
          <span className="font-medium text-slate-800">Bundle name</span>
          <input
            data-testid="upload-bundle-name"
            className="mt-1 w-full rounded-md border border-slate-200 px-3 py-2"
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
        <button
          type="submit"
          data-testid="upload-submit"
          className="rounded-md bg-teal-800 px-3 py-2 text-sm font-medium text-white hover:bg-teal-900"
        >
          Start demo upload
        </button>
        {message && (
          <p data-testid="upload-success" className="text-sm text-teal-800">
            {message}
          </p>
        )}
      </form>
    </div>
  );
}
