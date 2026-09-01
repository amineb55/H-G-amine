"""Multi-tenancy: organisations, workspaces, roles and permissions.

Spec §5: an Organisation owns Workspaces ("espaces"), and a workspace is the
hermetic unit of data. Every read and write of tenant data names its
workspace at the data layer — never only in the interface (P8).

Until authentication lands, the application serves a single default
workspace, and human actions are journalled under a placeholder actor
(debt D3 in docs/DETTES.md).
"""

import logging
from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from app.services import inspection_store

logger = logging.getLogger(__name__)

ORGANISATIONS_COLLECTION = "organisations"
WORKSPACES_COLLECTION = "workspaces"

DEFAULT_ORGANISATION_ID = "org-default"
# The store owns this value so pre-tenancy records resolve to it without an
# import cycle; tenancy re-exports it as the semantic name.
DEFAULT_WORKSPACE_ID = inspection_store.DEFAULT_WORKSPACE_ID

# Actor recorded on journal entries until authentication provides a real one.
UNAUTHENTICATED_ACTOR = "unauthenticated"


class OrganisationType(str, Enum):
    ENTREPRISE = "entreprise"
    CONSULTANT = "consultant"
    GROUPE = "groupe"


class Organisation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    type: OrganisationType
    default_language: str = "fr"


class Workspace(BaseModel):
    """The hermetic unit of data: a consultant's client, or a company site."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    organisation_id: str = Field(min_length=1)
    name: str = Field(min_length=1)


class Role(str, Enum):
    """Who someone is within an organisation or a workspace (spec §5.2)."""

    OWNER = "owner"
    ADMIN = "admin"
    CONSULTANT = "consultant"
    AUDITOR = "auditor"
    ASSIGNEE = "assignee"
    READER = "reader"


class Action(str, Enum):
    """What can be done. The matrix below is the single source of truth."""

    VIEW = "view"
    CREATE_INSPECTION = "create_inspection"
    VALIDATE_FINDINGS = "validate_findings"
    EDIT_FINDINGS = "edit_findings"
    DISPATCH = "dispatch"
    TREAT_ASSIGNED = "treat_assigned"
    RUN_AUDITS = "run_audits"
    WRITE_DOCUMENTS = "write_documents"
    MANAGE_WORKSPACES = "manage_workspaces"
    MANAGE_USERS = "manage_users"
    BILLING = "billing"
    DELETE_ORGANISATION = "delete_organisation"


# Spec §5.2, one row per role. Every permission check goes through can().
PERMISSIONS: dict[Role, frozenset[Action]] = {
    Role.OWNER: frozenset(Action),
    Role.ADMIN: frozenset(
        {
            Action.VIEW,
            Action.MANAGE_WORKSPACES,
            Action.MANAGE_USERS,
        }
    ),
    Role.CONSULTANT: frozenset(
        {
            Action.VIEW,
            Action.CREATE_INSPECTION,
            Action.VALIDATE_FINDINGS,
            Action.EDIT_FINDINGS,
            Action.DISPATCH,
            Action.RUN_AUDITS,
            Action.WRITE_DOCUMENTS,
        }
    ),
    Role.AUDITOR: frozenset(
        {
            Action.VIEW,
            Action.CREATE_INSPECTION,
            Action.VALIDATE_FINDINGS,
            Action.EDIT_FINDINGS,
            Action.DISPATCH,
            Action.RUN_AUDITS,
        }
    ),
    Role.ASSIGNEE: frozenset({Action.VIEW, Action.TREAT_ASSIGNED}),
    Role.READER: frozenset({Action.VIEW}),
}


def can(role: Role, action: Action) -> bool:
    """Whether a role may perform an action. Deny by default."""
    return action in PERMISSIONS.get(role, frozenset())


async def ensure_default() -> None:
    """Create the default organisation and workspace if they do not exist.

    Idempotent; run at startup. Everything the application stored before
    multi-tenancy belongs to this workspace.
    """
    if await inspection_store.get_document(
        ORGANISATIONS_COLLECTION, DEFAULT_ORGANISATION_ID
    ) is None:
        organisation = Organisation(
            id=DEFAULT_ORGANISATION_ID,
            name="Default organisation",
            type=OrganisationType.ENTREPRISE,
        )
        await inspection_store.put_document(
            ORGANISATIONS_COLLECTION,
            DEFAULT_ORGANISATION_ID,
            {**organisation.model_dump(), "created_at": _now()},
        )
        logger.info("Created the default organisation.")

    if await inspection_store.get_document(
        WORKSPACES_COLLECTION, DEFAULT_WORKSPACE_ID
    ) is None:
        workspace = Workspace(
            id=DEFAULT_WORKSPACE_ID,
            organisation_id=DEFAULT_ORGANISATION_ID,
            name="Default workspace",
        )
        await inspection_store.put_document(
            WORKSPACES_COLLECTION,
            DEFAULT_WORKSPACE_ID,
            {**workspace.model_dump(), "created_at": _now()},
        )
        logger.info("Created the default workspace.")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
