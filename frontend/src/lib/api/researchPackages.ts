import { BundledResearchPackageSchema } from '../schemas/researchPackage'
import { listOrganizationsApiV2OrganizationsGet, postResearchPackageImportApiV2ResearchPackageImportsPost } from './generated/sdk.gen'

const PACKAGE_URL = '/research-packages/pd1-demo-v1.json'

export async function getBundledProteinResearchPackage() {
  const response = await fetch(PACKAGE_URL)
  if (!response.ok) throw new Error(`Research package could not be loaded (${response.status})`)
  return BundledResearchPackageSchema.parse(await response.json())
}

export async function syncBundledProteinResearchPackage() {
  const [bundle, organizations] = await Promise.all([
    getBundledProteinResearchPackage(),
    listOrganizationsApiV2OrganizationsGet<true>({ throwOnError: true }).then((response) => response.data),
  ])
  if (!organizations[0]) throw new Error('No organization membership is available')
  return postResearchPackageImportApiV2ResearchPackageImportsPost<true>({
    body: { organization_id: organizations[0].id, package: bundle },
    throwOnError: true,
  }).then((response) => response.data)
}
