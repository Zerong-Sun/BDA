import {
  getResearchPackagesApiV2ResearchPackagesGet,
  listOrganizationsApiV2OrganizationsGet,
  postResearchPackageImportApiV2ResearchPackageImportsPost,
} from './generated/sdk.gen'

export async function getBundledProteinResearchPackage() {
  const packages = await getResearchPackagesApiV2ResearchPackagesGet<true>({ throwOnError: true })
    .then((response) => response.data)
  const descriptor = packages[0]
  if (!descriptor) throw new Error('No research package is installed on the server')
  return descriptor
}

export async function syncBundledProteinResearchPackage() {
  const [descriptor, organizations] = await Promise.all([
    getBundledProteinResearchPackage(),
    listOrganizationsApiV2OrganizationsGet<true>({ throwOnError: true }).then((response) => response.data),
  ])
  if (!organizations[0]) throw new Error('No organization membership is available')
  return postResearchPackageImportApiV2ResearchPackageImportsPost<true>({
    body: {
      organization_id: organizations[0].id,
      package_id: descriptor.package_id,
      version: descriptor.version,
      checksum: descriptor.checksum,
    },
    throwOnError: true,
  }).then((response) => response.data)
}
