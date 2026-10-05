import shutil
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, sessionmaker

from wmrm.application.assets import AssetService
from wmrm.persistence.database import (
    AnalysisRecord,
    ArtifactRecord,
    AssetRecord,
    PlanRecord,
    TaskRecord,
)


@dataclass(frozen=True, slots=True)
class CleanupSummary:
    artifacts: int = 0
    assets: int = 0
    temporary_files: int = 0


class RetentionService:
    def __init__(
        self,
        assets: AssetService,
        session_factory: sessionmaker[Session],
        artifact_retention_days: int,
        unreferenced_asset_retention_days: int,
        failed_work_retention_hours: int,
    ) -> None:
        self.assets = assets
        self.session_factory = session_factory
        self.artifact_retention_days = artifact_retention_days
        self.unreferenced_asset_retention_days = unreferenced_asset_retention_days
        self.failed_work_retention_hours = failed_work_retention_hours

    def cleanup(self, now: datetime | None = None) -> CleanupSummary:
        current = now or datetime.now(UTC)
        artifact_cutoff = current - timedelta(days=self.artifact_retention_days)
        asset_cutoff = current - timedelta(days=self.unreferenced_asset_retention_days)
        work_cutoff = current - timedelta(hours=self.failed_work_retention_hours)
        removed_artifacts = 0
        removed_assets = 0
        with self.session_factory() as session:
            old_tasks = session.scalars(
                select(TaskRecord).where(
                    TaskRecord.status.in_(["succeeded", "failed", "cancelled"]),
                    TaskRecord.updated_at < artifact_cutoff,
                )
            ).all()
            for task in old_tasks:
                artifacts = session.scalars(
                    select(ArtifactRecord).where(ArtifactRecord.task_id == task.id)
                ).all()
                for artifact in artifacts:
                    path = (self.assets.data_dir / artifact.relative_path).resolve()
                    if self.assets.data_dir in path.parents:
                        path.unlink(missing_ok=True)
                    session.delete(artifact)
                    removed_artifacts += 1
                shutil.rmtree(self.assets.data_dir / "artifacts" / task.id, ignore_errors=True)
                if task.status == "succeeded" and artifacts:
                    task.stage = "任务已完成；产物已按保留策略清理"

            old_assets = session.scalars(
                select(AssetRecord).where(AssetRecord.created_at < asset_cutoff)
            ).all()
            for asset in old_assets:
                plan_count = session.scalar(
                    select(func.count()).select_from(PlanRecord).where(
                        PlanRecord.asset_id == asset.id
                    )
                )
                if plan_count:
                    continue
                path = self.assets.path_for(asset)
                path.unlink(missing_ok=True)
                shutil.rmtree(path.parent, ignore_errors=True)
                session.execute(
                    delete(AnalysisRecord).where(AnalysisRecord.asset_id == asset.id)
                )
                session.delete(asset)
                removed_assets += 1
            session.commit()

        removed_temporary = 0
        for path in self.assets.tmp_root.glob("*"):
            try:
                modified = datetime.fromtimestamp(path.stat().st_mtime, UTC)
                if modified < work_cutoff:
                    if path.is_dir():
                        shutil.rmtree(path, ignore_errors=True)
                    else:
                        path.unlink(missing_ok=True)
                    removed_temporary += 1
            except FileNotFoundError:
                continue
        return CleanupSummary(removed_artifacts, removed_assets, removed_temporary)
