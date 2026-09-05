"use client";

import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { PageHeader } from "@/components/layout/PageHeader";

const schema = z.object({
  title: z.string().min(3),
  code: z.string().min(2),
  subject: z.string().min(2),
  grade: z.string().min(1),
  max_marks: z.number().positive(),
});

type FormValues = z.infer<typeof schema>;

export default function NewAssessmentPage() {
  const router = useRouter();
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      title: "Demo Assessment Draft",
      code: "MATH-DEMO-NEW",
      subject: "Mathematics",
      grade: "10",
      max_marks: 40,
    },
  });

  return (
    <div data-testid="assessment-new-page">
      <PageHeader
        title="New assessment"
        description="Creates a local draft record in the mock service layer."
        breadcrumbs={[
          { label: "Assessments", href: "/assessments" },
          { label: "New" },
        ]}
      />
      <form
        className="max-w-xl space-y-4 rounded-md border border-slate-200 bg-white p-4"
        onSubmit={handleSubmit(() => router.push("/assessments/assess-demo-002"))}
      >
        {(
          [
            ["title", "Title"],
            ["code", "Code"],
            ["subject", "Subject"],
            ["grade", "Grade"],
            ["max_marks", "Max marks"],
          ] as const
        ).map(([name, label]) => (
          <label key={name} className="block text-sm">
            <span className="font-medium text-slate-800">{label}</span>
            <input
              data-testid={`assessment-field-${name}`}
              type={name === "max_marks" ? "number" : "text"}
              className="mt-1 w-full rounded-md border border-slate-200 px-3 py-2"
              {...register(name, {
                valueAsNumber: name === "max_marks",
              })}
            />
            {errors[name] && (
              <span className="mt-1 block text-xs text-rose-700">
                {errors[name]?.message as string}
              </span>
            )}
          </label>
        ))}
        <button
          type="submit"
          data-testid="assessment-create-submit"
          className="rounded-md bg-teal-800 px-3 py-2 text-sm font-medium text-white hover:bg-teal-900"
        >
          Create draft
        </button>
      </form>
    </div>
  );
}
