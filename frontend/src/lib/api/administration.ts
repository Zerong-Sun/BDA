import './generatedTransport'
import {
  addOrganizationMemberApiV2OrganizationsOrganizationIdMembersPost,
  createOrganizationApiV2OrganizationsPost,
  getOperationsSummaryApiV2PlatformOperationsSummaryGet,
  listAuditLogsApiV2AuditLogsGet,
  listOrganizationMembersApiV2OrganizationsOrganizationIdMembersGet,
  listOrganizationsApiV2OrganizationsGet,
} from './generated/sdk.gen'
import type {
  AuditLogResponse,
  OperationsSummary,
  OrganizationMemberResponse,
  OrganizationResponse,
} from './generated/types.gen'

/**
 * The two administration reads the flow matrix has always claimed a UI for.
 *
 * `audit_logs`, `organizations` and `organization_members` are all declared with
 * `ui: ["administration"]`, and that screen did not exist: every one of these
 * operations was generated into the SDK and never called. The matrix checks that a
 * table is declared, not that the interface it names is real.
 */

export type AuditLogEntry = AuditLogResponse
export type Organization = OrganizationResponse
export type OrganizationMember = OrganizationMemberResponse

export interface AuditQuery {
  project_id?: string
  action?: string
  limit?: number
}

export async function listAuditLogs(query: AuditQuery = {}): Promise<AuditLogEntry[]> {
  const page = await listAuditLogsApiV2AuditLogsGet<true>({
    query: {
      limit: query.limit ?? 50,
      project_id: query.project_id || undefined,
      action: query.action || undefined,
    },
    throwOnError: true,
  })
  return page.data.items
}

export async function listOrganizations(): Promise<Organization[]> {
  const response = await listOrganizationsApiV2OrganizationsGet<true>({ throwOnError: true })
  return response.data
}

export async function listOrganizationMembers(
  organizationId: string,
): Promise<OrganizationMember[]> {
  const response = await listOrganizationMembersApiV2OrganizationsOrganizationIdMembersGet<true>({
    path: { organization_id: organizationId },
    throwOnError: true,
  })
  return response.data
}

export async function createOrganization(name: string): Promise<Organization> {
  const response = await createOrganizationApiV2OrganizationsPost<true>({
    body: { name },
    throwOnError: true,
  })
  return response.data
}

/** Upserts: adding someone who is already in changes their role rather than failing. */
export async function addOrganizationMember(
  organizationId: string,
  userId: string,
  role: string,
): Promise<Organization> {
  const response = await addOrganizationMemberApiV2OrganizationsOrganizationIdMembersPost<true>({
    path: { organization_id: organizationId },
    body: { user_id: userId, role: role as 'owner' | 'admin' | 'researcher' | 'viewer' },
    throwOnError: true,
  })
  return response.data
}

/**
 * The one question an operator has: is anything stuck?
 *
 * Every number here was already computed server-side and had no caller. Backlog and
 * missing artifacts are the two that mean something is wrong rather than merely busy -
 * outbox backlog is undelivered events, and an artifact in `failed`/`missing` is a
 * result the platform believes in but cannot produce.
 */
export function getOperationsSummary(): Promise<OperationsSummary> {
  return getOperationsSummaryApiV2PlatformOperationsSummaryGet<true>({ throwOnError: true })
    .then((response) => response.data)
}
