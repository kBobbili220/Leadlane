import type { NativeConnection } from "./services.mjs";
export interface OwnerIdentity {
  user: { id: string; full_name: string; email: string };
  business: { id: string; name: string; slug: string; currency: string; timezone: string };
  role: "owner";
  expires_at: string;
}
export interface OwnerSession extends OwnerIdentity { access_token: string; token_type?: "bearer" }
export interface LoginInput { email: string; password: string }
export interface RegisterInput extends LoginInput { full_name: string; business_name: string }
export class AuthApiError extends Error { status?: number; constructor(message: string, status?: number) }
export function registerOwner(input: RegisterInput, connection?: NativeConnection): Promise<OwnerSession>;
export function loginOwner(input: LoginInput, connection?: NativeConnection): Promise<OwnerSession>;
export function getIdentity(token: string, connection?: NativeConnection): Promise<OwnerIdentity>;
export function logoutOwner(token: string, connection?: NativeConnection): Promise<null>;
