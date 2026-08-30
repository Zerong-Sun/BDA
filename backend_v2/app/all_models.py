"""Import all ORM models so Alembic receives complete metadata."""
# ruff: noqa: F401

from .artifacts.models import Artifact, ArtifactLineageEdge, ArtifactUpload
from .audit.models import AuditLog
from .campaigns.models import Campaign, CampaignDecision, CampaignEvaluation, CampaignRound
from .candidates.models import Candidate, CandidateMetric
from .compute.models import ComputeDraft, IdempotencyRecord, Job, JobAttempt, JobEvent, JobSubmission, OutboxEvent
from .copilot.models import (
    CopilotAgentRun,
    CopilotAgentTask,
    CopilotAgentTurn,
    CopilotConfig,
    CopilotConversation,
    CopilotMessage,
)
from .delivery.models import DeliveryPackage
from .experiments.models import ExperimentResult
from .identity.models import OIDCLoginState, Organization, OrganizationMember, RefreshSession, User
from .intelligence.models import (
    DesignRoute,
    IntelligenceEvidence,
    IntelligenceHotspot,
    IntelligenceReport,
    IntelligenceRun,
)
from .knowledge.models import KnowledgeEntry
from .ligands.models import LigandImport
from .literature.models import (
    LiteratureChunk,
    LiteratureClaim,
    LiteratureDocument,
    LiteratureEvidence,
    LiteratureRelation,
    LiteratureRetrievalTrace,
    LiteratureSearchRun,
    LiteratureSubscription,
)
from .platform.models import MigrationRun, Operation
from .projects.models import Project, ProjectMember
from .registry.models import (
    ComputeNode,
    LLMProvider,
    MethodPlugin,
    ModelPlugin,
    ParameterCatalog,
    RegistryServer,
    ScriptAsset,
)
from .research.models import (
    ResearchBrief,
    ResearchFinding,
    ResearchGeneration,
    ResearchGoal,
    ResearchGoalLink,
)
from .targets.models import Target, TargetStructureRevision
from .timeline.models import ProjectTimelineEntry
from .wetlab.models import Protein
from .workflows.models import WorkflowNode, WorkflowRun

# Deliberately no `__all__`: this module exists for its import side effect —
# importing each model registers it on the shared SQLAlchemy metadata that
# Alembic reads. Nothing imports `*` from here - every consumer imports the
# module for the side effect alone - and the file-wide suppression at the top
# already covers the unused-import warnings.
#
# A list here would be a maintenance trap rather than a contract: the previous
# one had drifted to 24 of 61 models, so an `import *` would have silently
# yielded a subset. Register a new model by adding its import above.
