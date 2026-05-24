"""ORM model package — import all models here so Alembic sees them."""

from app.db.models.user import User
from app.db.models.label import Label
from app.db.models.project import Project
from app.db.models.release import Release
from app.db.models.issue import Issue
from app.db.models.issue_timeline import IssueTimeline
from app.db.models.issue_attachment import IssueAttachment
from app.db.models.inbox_item import InboxItem
from app.db.models.regression_history import RegressionHistory
from app.db.models.system_setting import SystemSetting

__all__ = [
    "User",
    "Label",
    "Project",
    "Release",
    "Issue",
    "IssueTimeline",
    "IssueAttachment",
    "InboxItem",
    "RegressionHistory",
    "SystemSetting",
]
