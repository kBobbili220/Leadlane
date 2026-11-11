import type { ServicePayload, ServiceRecord } from "../../public/service-client.mjs";
export interface NativeConnection {
  apiUrl?: string;
  hostUri?: string | null;
  fetchImpl?: typeof fetch;
}
export function resolveApiUrl(connection?: NativeConnection): string;
export function createNativeService(payload: ServicePayload, connection?: NativeConnection): Promise<ServiceRecord>;
export function listNativeServices(options: { offset?: number; limit?: number }, connection?: NativeConnection): Promise<ServiceRecord[]>;
