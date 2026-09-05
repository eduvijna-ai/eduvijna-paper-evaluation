import type { Guardian, GuardianInput } from "@/lib/api/a1-types";

/** UI view-model for guardians (camelCase at the boundary). */
export interface GuardianView {
  id: string;
  tenantId: string;
  displayName: string;
  email: string | null;
  phone: string | null;
}

export interface GuardianFormValues {
  displayName: string;
  email?: string;
  phone?: string;
}

export function guardianApiToViewModel(api: Guardian): GuardianView {
  return {
    id: api.id,
    tenantId: api.tenant_id,
    displayName: api.display_name,
    email: api.email ?? null,
    phone: api.phone ?? null,
  };
}

export function guardianFormToApi(form: GuardianFormValues): GuardianInput {
  return {
    display_name: form.displayName.trim(),
    email: form.email?.trim() || null,
    phone: form.phone?.trim() || null,
  };
}
