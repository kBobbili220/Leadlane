export interface ServiceFormValues {
  name: string;
  description: string;
  pricingMode: "fixed" | "custom";
  price: string;
  duration: string;
  unit: string;
  isActive: boolean;
}
export type FormErrors = Partial<Record<"name" | "price" | "duration" | "unit", string>>;
export interface ServicePayload {
  name: string;
  description: string | null;
  base_price_minor: number | null;
  estimated_duration_minutes: number | null;
  unit_label: string;
  is_active: boolean;
  sort_order: number;
}
export interface ServiceRecord extends ServicePayload {
  id: string;
  business_id: string;
  created_at: string;
  updated_at: string;
}
export class ServiceRequestError extends Error {
  uncertain: boolean;
  fields: FormErrors;
  status?: number;
  constructor(message: string, options?: { uncertain?: boolean; fields?: FormErrors; status?: number });
}
export function buildServicePayload(values: ServiceFormValues): { payload: ServicePayload | null; errors: FormErrors };
export function formatPrice(minor: number | null): string;
export function createService(payload: ServicePayload, options?: { accessToken?: string; fetchImpl?: typeof fetch; timeoutMs?: number }): Promise<ServiceRecord>;
export function listServices(options?: { accessToken?: string; offset?: number; limit?: number; fetchImpl?: typeof fetch; timeoutMs?: number }): Promise<ServiceRecord[]>;
