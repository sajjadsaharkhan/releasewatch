"""ORM model package — import all models here so Alembic sees them."""

from app.db.models.user import User
from app.db.models.user_identity import UserIdentity
from app.db.models.label import Label
from app.db.models.project import Project
from app.db.models.release import Release, register_stream_hooks
from app.db.models.issue_cycle import IssueCycle
from app.db.models.issue import Issue
from app.db.models.issue_timeline import IssueTimeline
from app.db.models.comment_reaction import CommentReaction
from app.db.models.issue_attachment import IssueAttachment
from app.db.models.inbox_item import InboxItem
from app.db.models.system_setting import SystemSetting
from app.db.models.telegram_integration import TelegramIntegration
from app.db.models.issue_embedding import IssueEmbedding
from app.db.models.support_template import SupportTemplate, SupportTemplateField
from app.db.models.issue_subscriber import IssueSubscriber
from app.db.models.issue_recurrence import IssueRecurrence
from app.db.models.backlog_category import BacklogCategory, register_default_category_hook

# Every project gets its fixed Default backlog category on insert, and every
# issue inserted without a category gets that Default — whatever creates them.
register_default_category_hook(Project, Issue)
# Every project gets its Stream on insert (BR-51); a Release starts in Planning.
register_stream_hooks(Project)

__all__ = [
    "User",
    "UserIdentity",
    "Label",
    "Project",
    "Release",
    "IssueCycle",
    "Issue",
    "IssueTimeline",
    "CommentReaction",
    "IssueAttachment",
    "InboxItem",
    "SystemSetting",
    "TelegramIntegration",
    "IssueEmbedding",
    "SupportTemplate",
    "SupportTemplateField",
    "IssueSubscriber",
    "IssueRecurrence",
    "BacklogCategory",
]
