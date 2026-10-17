import './generatedTransport'
import {
  listLessonsApiV2ProjectsProjectIdDesignLessonsGet,
  postLessonApiV2ProjectsProjectIdDesignLessonsPost,
  importLessonApiV2ProjectsProjectIdDesignLessonsImportPost,
  getDesignLearningApiV2WorkflowRunsWorkflowIdDesignLearningGet,
  postReviewApiV2WorkflowRunsWorkflowIdDesignLearningReviewsPost,
  postFeedbackApiV2WorkflowRunsWorkflowIdDesignLearningFeedbackPost,
} from './generated/sdk.gen'
import type { LessonCreate, ReviewCreate, FeedbackCreate, ReviewItem } from './generated/types.gen'
export type { LessonCreate, ReviewCreate, FeedbackCreate, ReviewItem }

export interface Lesson {
  id: string; project_id: string; created_at: string; created_by: string; review_id: string | null; item_key: string | null; supersedes_id: string | null;
  payload: LessonCreate & { origin?: { project_id: string; lesson_id: string } }
}
export interface Review { id: string; created_at: string; workflow_run_id: string; payload: ReviewCreate & { lesson_snapshots: Lesson[] } }
export interface DesignLearning {
  required: boolean; state: 'missing' | 'stale' | 'ready' | 'frozen'; workflow_version: number; fingerprint: string; memory_digest: string;
  checklist: { key: string; title: string; title_en: string; prompt: string; prompt_en: string }[];
  lessons: Lesson[]; review: Review | null; history: Review[]; pending_feedback: string[]; feedback: Lesson[];
}
export async function listDesignLessons(projectId: string): Promise<Lesson[]> {
  const { data } = await listLessonsApiV2ProjectsProjectIdDesignLessonsGet<true>({ path: { project_id: projectId }, throwOnError: true })
  return (data as { items: Lesson[] }).items
}
export async function createDesignLesson(projectId: string, body: LessonCreate) {
  return postLessonApiV2ProjectsProjectIdDesignLessonsPost<true>({ path: { project_id: projectId }, body, throwOnError: true })
}
export async function importDesignLesson(projectId: string, sourceId: string) {
  return importLessonApiV2ProjectsProjectIdDesignLessonsImportPost<true>({ path: { project_id: projectId }, body: { source_id: sourceId }, throwOnError: true })
}
export async function getDesignLearning(workflowId: string): Promise<DesignLearning> {
  const { data } = await getDesignLearningApiV2WorkflowRunsWorkflowIdDesignLearningGet<true>({ path: { workflow_id: workflowId }, throwOnError: true })
  return data as DesignLearning
}
export async function saveDesignReview(workflowId: string, version: number, body: ReviewCreate) {
  return postReviewApiV2WorkflowRunsWorkflowIdDesignLearningReviewsPost<true>({ path: { workflow_id: workflowId }, headers: { 'If-Match': `W/"${version}"` }, body, throwOnError: true })
}
export async function saveDesignFeedback(workflowId: string, body: FeedbackCreate) {
  return postFeedbackApiV2WorkflowRunsWorkflowIdDesignLearningFeedbackPost<true>({ path: { workflow_id: workflowId }, body, throwOnError: true })
}
