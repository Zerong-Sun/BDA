export interface FAQItemRef {
  id: string
}

export interface FAQSectionRef {
  id: string
  items: FAQItemRef[]
}

export interface FAQAccordionItemData {
  id: string
  question: string
  answer: string
}

export interface FAQAccordionSectionData {
  id: string
  label: string
  title: string
  items: FAQAccordionItemData[]
}

export interface FAQSectionBundle {
  label: string
  title: string
  items: Record<string, { question: string; answer: string }>
}

export function resolveFaqSections(
  sections: Record<string, FAQSectionBundle> | undefined,
): FAQAccordionSectionData[] {
  if (!sections) return []

  return faqSectionRefs
    .map((sectionRef) => {
      const sectionBundle = sections[sectionRef.id]
      if (!sectionBundle) return null

      const items = sectionRef.items
        .map((itemRef) => {
          const itemBundle = sectionBundle.items[itemRef.id]
          if (!itemBundle?.question || !itemBundle?.answer) return null
          return {
            id: itemRef.id,
            question: itemBundle.question,
            answer: itemBundle.answer,
          }
        })
        .filter((item): item is NonNullable<typeof item> => item !== null)

      if (!sectionBundle.label || !sectionBundle.title || !items.length) return null

      return {
        id: sectionRef.id,
        label: sectionBundle.label,
        title: sectionBundle.title,
        items,
      }
    })
    .filter((section): section is FAQAccordionSectionData => section !== null)
}

/** Structural FAQ config — copy lives in i18n (`t.faq.sections`). */
export const faqSectionRefs: FAQSectionRef[] = [
  {
    id: 'gettingStarted',
    items: [
      { id: 'whatIsPlatform' },
      { id: 'whoIsItFor' },
      { id: 'prerequisites' },
      { id: 'firstWorkflow' },
    ],
  },
  {
    id: 'research',
    items: [
      { id: 'whyResearchRequired' },
      { id: 'missingCitations' },
      { id: 'paperTypes' },
      { id: 'completeSummary' },
      { id: 'incompleteResearch' },
    ],
  },
  {
    id: 'targetProtein',
    items: [
      { id: 'whyChooseTarget' },
      { id: 'fiveOptions' },
      { id: 'pdbVsAlphafold' },
      { id: 'noPdbStructure' },
      { id: 'structureStorage' },
    ],
  },
  {
    id: 'structurePrep',
    items: [
      { id: 'pdbDownloadFailures' },
      { id: 'missingResidues' },
      { id: 'wrongChain' },
      { id: 'metadataDisplay' },
    ],
  },
  {
    id: 'aiDesign',
    items: [
      { id: 'designModes' },
      { id: 'clarifyingQuestions' },
      { id: 'changeGoal' },
      { id: 'intermediateSteps' },
    ],
  },
  {
    id: 'results',
    items: [
      { id: 'interpretResults' },
      { id: 'modelDifferences' },
      { id: 'visualizationFails' },
      { id: 'partialResults' },
    ],
  },
  {
    id: 'projectsApi',
    items: [
      { id: 'projectCrud' },
      { id: 'buttonFailures' },
      { id: 'apiTimeout' },
      { id: 'schemaMismatch' },
      { id: 'incompleteState' },
    ],
  },
  {
    id: 'troubleshooting',
    items: [
      { id: 'loadingNeverEnds' },
      { id: 'emptyResearch' },
      { id: 'citationLinksMissing' },
      { id: 'pdbDownloadFailed' },
      { id: 'shallowAgent' },
      { id: 'lockedStep' },
      { id: 'deleteConfirmation' },
      { id: 'backendNotRunning' },
      { id: 'missingEnvVars' },
    ],
  },
]
