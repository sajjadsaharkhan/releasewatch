"""AttachmentService — the one creator of ``IssueAttachment`` rows (slice 17, prd-mcp.md A.4).

Four paths attach files: filing an item (``IssueService.create``), a merge or
recurrence (``MergeService.merge_into``), and the two upload-confirm endpoints
in ``api/v1/attachments.py``. All of them come through ``add``, which stamps
the agent context's token (agent content, BR-M05) and enqueues the existing
``validate_attachment`` job once the transaction commits. The MCP tools
``rw_file_*`` and ``rw_attach`` use it too. ``delete`` is the one remover.
"""

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.core.agent_context import current_agent_token_id
from app.db.models.issue_attachment import AttachmentType, IssueAttachment

_PENDING = "attachment_validation_pending"


class AttachmentService:

    async def add(
        self,
        db: AsyncSession,
        issue_id: int,
        uploaded_by_id: int | None,
        *,
        file_name: str,
        s3_key: str,
        mime_type: str,
        file_size_bytes: int | None,
        attachment_type: AttachmentType | str = AttachmentType.other,
    ) -> IssueAttachment:
        """Add one attachment to ``issue_id`` (flushed, not committed)."""
        attachment = IssueAttachment(
            issue_id=issue_id,
            uploaded_by_id=uploaded_by_id,
            file_name=file_name,
            s3_key=s3_key,
            mime_type=mime_type,
            file_size_bytes=file_size_bytes,
            attachment_type=attachment_type,
            via_mcp_token_id=current_agent_token_id(),
        )
        db.add(attachment)
        await db.flush()
        db.sync_session.info.setdefault(_PENDING, []).append((attachment.id, s3_key))
        return attachment

    async def add_pending(
        self, db: AsyncSession, issue_id: int, uploaded_by_id: int | None, pending,
    ) -> IssueAttachment:
        """``add`` for a ``PendingAttachment`` (a file uploaded before the item existed)."""
        return await self.add(
            db, issue_id, uploaded_by_id,
            file_name=pending.filename,
            s3_key=pending.s3_key,
            mime_type=pending.mime_type,
            file_size_bytes=pending.file_size_bytes,
            attachment_type=pending.attachment_type,
        )

    async def delete(self, db: AsyncSession, attachment: IssueAttachment, current_user) -> None:
        """Delete an attachment from S3 and the database (flushed, not committed).
        Only the uploader or an admin may. ``DELETE /issues/{id}/attachments/{aid}``
        and ``rw_delete_own`` come through here."""
        from fastapi import HTTPException, status

        from app.core.s3 import s3_service
        from app.db.models.user import UserRole

        is_uploader = attachment.uploaded_by_id == current_user.id
        is_admin = current_user.role == UserRole.admin
        if not (is_uploader or is_admin):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")

        s3_service.delete_file(attachment.s3_key)
        await db.delete(attachment)
        await db.flush()


@event.listens_for(Session, "after_commit")
def _validate_after_commit(session: Session) -> None:
    """The validation job reads the row, so it is sent only once the row exists."""
    from app.tasks.attachments import validate_attachment

    for attachment_id, s3_key in session.info.pop(_PENDING, None) or ():
        validate_attachment.apply_async(
            kwargs={"attachment_id": str(attachment_id), "s3_key": s3_key},
            queue="attachments",
        )


@event.listens_for(Session, "after_soft_rollback")
def _forget_after_rollback(session: Session, previous_transaction) -> None:
    if previous_transaction.parent is None:
        session.info.pop(_PENDING, None)


attachment_service = AttachmentService()
