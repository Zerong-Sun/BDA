import './generatedTransport'
import { assessExtensionConfigurationApiV2RegistryExtensionsExtensionIdAssessmentsPost, getExtensionCatalogApiV2RegistryExtensionsGet } from './generated/sdk.gen'
import type { ExtensionAssessmentCreate } from './generated/types.gen'

export type { ExtensionAssessment, ExtensionCatalog, ExtensionEntry } from './generated/types.gen'

export async function getExtensionCatalog() {
  const { data } = await getExtensionCatalogApiV2RegistryExtensionsGet<true>({ throwOnError: true })
  return data
}

export async function assessExtension(extensionId: string, body: ExtensionAssessmentCreate) {
  const { data } = await assessExtensionConfigurationApiV2RegistryExtensionsExtensionIdAssessmentsPost<true>({ path: { extension_id: extensionId }, body, throwOnError: true })
  return data
}
