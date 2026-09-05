"use client";

import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { PageHeader } from "@/components/layout/PageHeader";
import { useState } from "react";

const schema = z.object({
  fileName: z.string().min(1, "Choose a file name for the demo import"),
  notes: z.string().optional(),
});

type FormValues = z.infer<typeof schema>;

export default function StudentsImportPage() {
  const [done, setDone] = useState(false);
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { fileName: "demo-roster.csv", notes: "" },
  });

  return (
    <div data-testid="students-import-page">
      <PageHeader
        title="Import students"
        description="Mock CSV import for CVB. No files are uploaded to a server."
        breadcrumbs={[
          { label: "Students", href: "/students" },
          { label: "Import" },
        ]}
      />
      <form
        className="max-w-lg space-y-4 rounded-md border border-slate-200 bg-white p-4"
        onSubmit={handleSubmit(() => setDone(true))}
      >
        <label className="block text-sm">
          <span className="font-medium text-slate-800">Roster file name</span>
          <input
            data-testid="import-filename"
            className="mt-1 w-full rounded-md border border-slate-200 px-3 py-2"
            {...register("fileName")}
          />
          {errors.fileName && (
            <span className="mt-1 block text-xs text-rose-700">
              {errors.fileName.message}
            </span>
          )}
        </label>
        <label className="block text-sm">
          <span className="font-medium text-slate-800">Notes</span>
          <textarea
            className="mt-1 w-full rounded-md border border-slate-200 px-3 py-2"
            rows={3}
            {...register("notes")}
          />
        </label>
        <button
          type="submit"
          data-testid="import-submit"
          className="rounded-md bg-teal-800 px-3 py-2 text-sm font-medium text-white hover:bg-teal-900"
        >
          Run demo import
        </button>
        {done && (
          <p
            data-testid="import-success"
            className="rounded-md bg-teal-50 px-3 py-2 text-sm text-teal-900 ring-1 ring-teal-200"
          >
            Demo import accepted. 3 synthetic students already available in the
            roster.
          </p>
        )}
      </form>
    </div>
  );
}
