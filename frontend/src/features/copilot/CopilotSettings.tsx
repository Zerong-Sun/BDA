import { useCallback, useEffect, useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  CheckCircleIcon,
  KeyIcon,
  PlugsConnectedIcon,
  SpinnerGapIcon,
  WarningIcon,
  XCircleIcon,
} from '@phosphor-icons/react'
import { getCopilotConfig, testCopilotConfig, updateCopilotConfig } from '../../lib/api/copilot'
import { Button } from '../../components/ui/Button'
import { Input } from '../../components/ui/Input'
import { Label } from '../../components/ui/label'
import { Skeleton } from '../../components/ui/Skeleton'
import { Textarea } from '../../components/ui/textarea'
import { Alert, AlertDescription } from '../../components/reui/alert'
import { Frame, FrameDescription, FrameHeader, FramePanel, FrameTitle } from '../../components/reui/frame'
import { useI18n } from '../../lib/i18n'
import { useProjectContext } from '../../lib/hooks/useProjectContext'

export interface CopilotSettingsActions {
  save: () => void
  test: () => void
  savePending: boolean
  testPending: boolean
  canSave: boolean
  canTest: boolean
}

interface CopilotSettingsProps {
  hideActions?: boolean
  onActionsReady?: (actions: CopilotSettingsActions) => void
}

export function CopilotSettings({ hideActions = false, onActionsReady }: CopilotSettingsProps) {
  const { t, format } = useI18n()
  const queryClient = useQueryClient()
  const { projectId } = useProjectContext()
  const { data: config, isLoading, isError } = useQuery({
    queryKey: ['copilot-config', projectId],
    queryFn: () => getCopilotConfig(projectId),
    enabled: Boolean(projectId),
    retry: false,
  })
  const [baseUrlDraft, setBaseUrlDraft] = useState<string | null>(null)
  const [modelDraft, setModelDraft] = useState<string | null>(null)
  const [promptDraft, setPromptDraft] = useState<string | null>(null)
  const [apiKey, setApiKey] = useState('')
  const baseUrl = baseUrlDraft ?? config?.llm_api_base ?? 'https://api.deepseek.com'
  const model = modelDraft ?? config?.llm_model ?? 'deepseek-v4-pro'
  const systemPrompt = promptDraft ?? config?.system_prompt ?? ''

  const save = useMutation({
    mutationFn: () =>
      updateCopilotConfig(projectId, {
        llm_api_base: baseUrl.trim(),
        llm_model: model.trim(),
        system_prompt: systemPrompt.trim(),
        ...(apiKey.trim() ? { llm_api_key: apiKey.trim() } : {}),
      }),
    onSuccess: () => {
      setApiKey('')
      setBaseUrlDraft(null)
      setModelDraft(null)
      setPromptDraft(null)
      void queryClient.invalidateQueries({ queryKey: ['copilot-config'] })
    },
  })
  const test = useMutation({ mutationFn: () => testCopilotConfig(projectId) })
  const mutationPending = save.isPending || test.isPending
  const canSave = Boolean(baseUrl.trim() && model.trim())
  const canTest = Boolean(config?.api_key_configured)
  const saveConfiguration = save.mutate
  const testConfiguration = test.mutate
  const publishSave = useCallback(() => {
    if (!mutationPending && canSave) saveConfiguration()
  }, [canSave, mutationPending, saveConfiguration])
  const publishTest = useCallback(() => {
    if (!mutationPending && canTest) testConfiguration()
  }, [canTest, mutationPending, testConfiguration])
  const externalActions = useMemo<CopilotSettingsActions>(
    () => ({
      save: publishSave,
      test: publishTest,
      savePending: save.isPending,
      testPending: test.isPending,
      canSave: canSave && !mutationPending,
      canTest: canTest && !mutationPending,
    }),
    [
      canSave,
      canTest,
      mutationPending,
      publishSave,
      publishTest,
      save.isPending,
      test.isPending,
    ],
  )

  useEffect(() => {
    onActionsReady?.(externalActions)
  }, [externalActions, onActionsReady])

  return (
    <Frame variant="ghost" spacing="sm">
      <FrameHeader>
        <FrameTitle className="flex items-center gap-2">
          <KeyIcon className="size-4 text-primary" aria-hidden="true" />
          {t.copilot.settings.title}
        </FrameTitle>
        <FrameDescription>{t.copilot.settings.body}</FrameDescription>
      </FrameHeader>
      <FramePanel>
        {isLoading ? (
          <div className="grid gap-2" role="status" aria-label={t.copilot.settings.loadingAriaLabel}>
            <Skeleton className="h-8 w-full motion-reduce:animate-none" />
            <Skeleton className="h-20 w-full motion-reduce:animate-none" />
            <Skeleton className="h-8 w-full motion-reduce:animate-none" />
            <span className="sr-only">{t.copilot.settings.loadingSrOnly}</span>
          </div>
        ) : null}
        {isError ? (
          <Alert variant="destructive">
            <WarningIcon aria-hidden="true" />
            <AlertDescription>{t.copilot.settings.loadFailed}</AlertDescription>
          </Alert>
        ) : null}
        {!isLoading && !isError ? (
          <div className="grid gap-3">
            <div className="grid gap-1">
              <Label htmlFor="copilot-api-base">{t.copilot.settings.apiBaseLabel}</Label>
              <Input
                id="copilot-api-base"
                value={baseUrl}
                onChange={(event) => setBaseUrlDraft(event.target.value)}
              />
            </div>
            <div className="grid gap-1">
              <Label htmlFor="copilot-project-prompt">
                {t.copilot.settings.projectPromptLabel}
              </Label>
              <Textarea
                id="copilot-project-prompt"
                className="min-h-24"
                value={systemPrompt}
                onChange={(event) => setPromptDraft(event.target.value)}
              />
            </div>
            <div className="grid gap-1">
              <Label htmlFor="copilot-model">{t.copilot.settings.modelLabel}</Label>
              <Input
                id="copilot-model"
                value={model}
                onChange={(event) => setModelDraft(event.target.value)}
              />
            </div>
            <div className="grid gap-1">
              <Label htmlFor="copilot-api-key">
                {t.copilot.settings.apiKeyLabel}{' '}
                {config?.api_key_configured
                  ? `(${config.api_key_preview ?? t.copilot.settings.apiKeyConfigured})`
                  : ''}
              </Label>
              <Input
                id="copilot-api-key"
                type="password"
                autoComplete="off"
                placeholder={
                  config?.api_key_configured
                    ? t.copilot.settings.apiKeyPlaceholderKeep
                    : t.copilot.settings.apiKeyPlaceholderNew
                }
                value={apiKey}
                onChange={(event) => setApiKey(event.target.value)}
              />
            </div>
          </div>
        ) : null}

        {!hideActions ? (
          <div className="mt-3 flex flex-wrap gap-2">
            <Button
              type="button"
              size="sm"
              disabled={mutationPending || !canSave}
              onClick={() => save.mutate()}
            >
              {save.isPending ? (
                <SpinnerGapIcon
                  className="animate-spin motion-reduce:animate-none"
                  aria-hidden="true"
                />
              ) : (
                <KeyIcon aria-hidden="true" />
              )}
              {t.copilot.settings.saveConfiguration}
            </Button>
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={mutationPending || !canTest}
              onClick={() => test.mutate()}
            >
              {test.isPending ? (
                <SpinnerGapIcon
                  className="animate-spin motion-reduce:animate-none"
                  aria-hidden="true"
                />
              ) : (
                <PlugsConnectedIcon aria-hidden="true" />
              )}
              {t.copilot.settings.testApi}
            </Button>
          </div>
        ) : null}

        {save.isSuccess ? (
          <Alert className="mt-3" variant="success" role="status">
            <CheckCircleIcon aria-hidden="true" />
            <AlertDescription>{t.copilot.settings.savedSuccess}</AlertDescription>
          </Alert>
        ) : null}
        {save.isError ? (
          <Alert className="mt-3" variant="destructive">
            <XCircleIcon aria-hidden="true" />
            <AlertDescription>
              {save.error instanceof Error ? save.error.message : t.copilot.settings.saveFailed}
            </AlertDescription>
          </Alert>
        ) : null}
        {test.data ? (
          <Alert className="mt-3" variant={test.data.connected ? 'success' : 'destructive'} role="status">
            {test.data.connected ? (
              <CheckCircleIcon aria-hidden="true" />
            ) : (
              <XCircleIcon aria-hidden="true" />
            )}
            <AlertDescription>
              {test.data.connected
                ? format(t.copilot.settings.connected, {
                    model: test.data.model,
                    sample: test.data.sample ?? t.copilot.settings.connectionOk,
                  })
                : format(t.copilot.settings.connectionFailed, {
                    reason: test.data.reason ?? t.copilot.settings.unknownError,
                  })}
            </AlertDescription>
          </Alert>
        ) : null}
        {test.isError ? (
          <Alert className="mt-3" variant="destructive">
            <XCircleIcon aria-hidden="true" />
            <AlertDescription>
              {test.error instanceof Error
                ? test.error.message
                : t.copilot.settings.connectionFailedGeneric}
            </AlertDescription>
          </Alert>
        ) : null}
      </FramePanel>
    </Frame>
  )
}
