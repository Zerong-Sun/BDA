import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import {
  adjacentTourStep,
  firstTourStep,
  TOUR_SECTIONS,
  type TourSectionId,
} from '../../features/tour/tourData'

export type Language = 'en' | 'zh'
export type AppMode = 'application' | 'demo'
export type UiDensity = 'guided' | 'advanced'
export type ThemePreference = 'light' | 'dark' | 'system'
export interface CopilotChatMessage {
  role: 'user' | 'assistant' | 'system'
  content: string
  meta?: {
    reviewTrack?: string
    reviewIntent?: boolean
    citations?: Array<Record<string, unknown>>
    toolCalls?: Array<Record<string, unknown>>
  }
}

export interface CopilotProjectSession {
  conversationId: string | null
  messages: CopilotChatMessage[]
}

export interface WorkflowSeed {
  projectId: string
  goal: string
  source: 'research_review'
}

export type TourStatus = 'idle' | 'active' | 'paused' | 'completed'
export interface TourState {
  status: TourStatus
  sectionId: TourSectionId
  stepId: string
  completedSections: TourSectionId[]
  updatedAt: string | null
}

export const initialTourState: TourState = {
  status: 'idle',
  sectionId: 'projects',
  stepId: 'projects-welcome',
  completedSections: [],
  updatedAt: null,
}

export const legacyCopilotIntro =
  'I am BDA Copilot for this project. Ask me to plan a route, inspect uploaded files, explain workflow state, draft an LSF job, or summarize biomaterials evidence. I will keep the same conversation as you move between pages.'

export const defaultCopilotMessages: CopilotChatMessage[] = []

interface AppState {
  language: Language
  appMode: AppMode
  uiDensity: UiDensity
  themePreference: ThemePreference
  activeProjectId: string
  copilotMessages: CopilotChatMessage[]
  copilotSessions: Record<string, CopilotProjectSession>
  copilotDraft: string
  copilotSelectedEntityIds: string[]
  copilotOpen: boolean
  settingsOpen: boolean
  activityOpen: boolean
  copilotWidth: number
  targetIntakeOpen: boolean
  deletingProjectId: string | null
  workflowSeed: WorkflowSeed | null
  tourState: TourState
  tourMenuOpen: boolean
  setLanguage: (language: Language) => void
  setAppMode: (mode: AppMode) => void
  setUiDensity: (density: UiDensity) => void
  setThemePreference: (preference: ThemePreference) => void
  setActiveProjectId: (projectId: string) => void
  clearProjectState: (projectId: string) => void
  setCopilotMessages: (
    messages:
      | CopilotChatMessage[]
      | ((messages: CopilotChatMessage[]) => CopilotChatMessage[]),
  ) => void
  setCopilotSessionMessages: (
    projectId: string,
    messages: CopilotChatMessage[] | ((messages: CopilotChatMessage[]) => CopilotChatMessage[]),
  ) => void
  setCopilotConversationId: (projectId: string, conversationId: string | null) => void
  resetCopilotSession: (projectId: string) => void
  setCopilotDraft: (draft: string) => void
  setCopilotSelectedEntityIds: (entityIds: string[]) => void
  resetCopilotMessages: () => void
  setCopilotOpen: (open: boolean) => void
  setSettingsOpen: (open: boolean) => void
  setActivityOpen: (open: boolean) => void
  setCopilotWidth: (width: number) => void
  setTargetIntakeOpen: (open: boolean) => void
  setDeletingProjectId: (projectId: string | null) => void
  setWorkflowSeed: (seed: WorkflowSeed | null) => void
  startTour: (sectionId?: TourSectionId) => void
  resumeTour: () => void
  advanceTour: () => void
  backTour: () => void
  skipTour: () => void
  restartTour: () => void
  completeTour: () => void
  setTourMenuOpen: (open: boolean) => void
}

export const useAppStore = create<AppState>()(
  persist(
    (set) => ({
      language: 'en',
      appMode: 'application',
      uiDensity: 'guided',
      themePreference: 'system',
      activeProjectId: '',
      copilotMessages: defaultCopilotMessages,
      copilotSessions: {},
      copilotDraft: '',
      copilotSelectedEntityIds: [],
      copilotOpen: true,
      settingsOpen: false,
      activityOpen: false,
      copilotWidth: 380,
      targetIntakeOpen: false,
      deletingProjectId: null,
      workflowSeed: null,
      tourState: initialTourState,
      tourMenuOpen: false,
      setLanguage: (language) => set({ language }),
      setAppMode: (appMode) => set({ appMode }),
      setUiDensity: (uiDensity) => set({ uiDensity }),
      setThemePreference: (themePreference) => set({ themePreference }),
      setActiveProjectId: (activeProjectId) => set({ activeProjectId }),
      clearProjectState: (projectId) =>
        set((state) => ({
          activeProjectId: state.activeProjectId === projectId ? '' : state.activeProjectId,
        })),
      setCopilotMessages: (messages) =>
        set((state) => ({
          copilotMessages:
            typeof messages === 'function'
              ? messages(state.copilotMessages)
              : messages,
        })),
      setCopilotSessionMessages: (projectId, messages) => set((state) => {
        const current = state.copilotSessions[projectId] ?? { conversationId: null, messages: [] }
        return {
          copilotSessions: {
            ...state.copilotSessions,
            [projectId]: {
              ...current,
              messages: typeof messages === 'function' ? messages(current.messages) : messages,
            },
          },
        }
      }),
      setCopilotConversationId: (projectId, conversationId) => set((state) => {
        const current = state.copilotSessions[projectId] ?? { conversationId: null, messages: [] }
        return { copilotSessions: { ...state.copilotSessions, [projectId]: { ...current, conversationId } } }
      }),
      resetCopilotSession: (projectId) => set((state) => ({
        copilotSessions: {
          ...state.copilotSessions,
          [projectId]: { conversationId: null, messages: [] },
        },
      })),
      setCopilotDraft: (copilotDraft) => set({ copilotDraft }),
      setCopilotSelectedEntityIds: (copilotSelectedEntityIds) => set({ copilotSelectedEntityIds }),
      resetCopilotMessages: () => set({ copilotMessages: defaultCopilotMessages }),
      setCopilotOpen: (copilotOpen) => set({ copilotOpen }),
      setSettingsOpen: (settingsOpen) => set({ settingsOpen }),
      setActivityOpen: (activityOpen) => set({ activityOpen }),
      setCopilotWidth: (copilotWidth) => set({ copilotWidth }),
      setTargetIntakeOpen: (targetIntakeOpen) => set({ targetIntakeOpen }),
      setDeletingProjectId: (deletingProjectId) => set({ deletingProjectId }),
      setWorkflowSeed: (workflowSeed) => set({ workflowSeed }),
      startTour: (sectionId = 'projects') => {
        const first = firstTourStep(sectionId)
        set((state) => ({
          tourState: {
            ...state.tourState,
            status: 'active',
            sectionId,
            stepId: first.id,
            updatedAt: new Date().toISOString(),
          },
          tourMenuOpen: false,
        }))
      },
      resumeTour: () => set((state) => ({
        tourState: { ...state.tourState, status: 'active', updatedAt: new Date().toISOString() },
        tourMenuOpen: false,
      })),
      advanceTour: () => set((state) => {
        const next = adjacentTourStep(state.tourState.sectionId, state.tourState.stepId, 1)
        if (next) {
          return { tourState: { ...state.tourState, stepId: next.id, updatedAt: new Date().toISOString() } }
        }
        const completedSections = state.tourState.completedSections.includes(state.tourState.sectionId)
          ? state.tourState.completedSections
          : [...state.tourState.completedSections, state.tourState.sectionId]
        const allCompleted = completedSections.length === TOUR_SECTIONS.length
        return {
          tourState: {
            ...state.tourState,
            status: allCompleted ? 'completed' : 'paused',
            completedSections,
            updatedAt: new Date().toISOString(),
          },
          tourMenuOpen: !allCompleted,
        }
      }),
      backTour: () => set((state) => {
        const previous = adjacentTourStep(state.tourState.sectionId, state.tourState.stepId, -1)
        return previous
          ? { tourState: { ...state.tourState, stepId: previous.id, updatedAt: new Date().toISOString() } }
          : state
      }),
      skipTour: () => set((state) => ({
        tourState: { ...state.tourState, status: 'paused', updatedAt: new Date().toISOString() },
        tourMenuOpen: true,
      })),
      restartTour: () => set({
        tourState: { ...initialTourState, status: 'active', updatedAt: new Date().toISOString() },
        tourMenuOpen: false,
      }),
      completeTour: () => set((state) => ({
        tourState: {
          ...state.tourState,
          status: 'completed',
          completedSections: state.tourState.completedSections,
          updatedAt: new Date().toISOString(),
        },
        tourMenuOpen: false,
      })),
      setTourMenuOpen: (tourMenuOpen) => set({ tourMenuOpen }),
    }),
    {
      name: 'bda-app-store',
      partialize: (state) => ({
        language: state.language,
        appMode: state.appMode,
        uiDensity: state.uiDensity,
        themePreference: state.themePreference,
        activeProjectId: state.activeProjectId,
        copilotMessages: state.copilotMessages,
        copilotSessions: state.copilotSessions,
        copilotOpen: state.copilotOpen,
        settingsOpen: state.settingsOpen,
        copilotWidth: state.copilotWidth,
        targetIntakeOpen: state.targetIntakeOpen,
        tourState: state.tourState,
      }),
    },
  ),
)
