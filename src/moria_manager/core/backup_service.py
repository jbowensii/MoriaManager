"""Backup and restore operations for game saves (ZIP-based)

NOTE: This module is not currently used. The main_window.py uses BackupIndexManager
for individual .sav file backups instead of zip-based backups.
"""

# """Backup and restore operations for game saves"""
#
# import shutil
# import uuid
# import zipfile
# from datetime import datetime
# from pathlib import Path
# from typing import Optional
#
# from ..config.manager import ConfigurationManager
# from ..config.paths import GamePaths
# from ..config.schema import BackupRecord, Installation, InstallationType
# from ..logging_config import get_logger
#
# logger = get_logger("backup_service")
#
#
# class BackupError(Exception):
#     """Exception raised for backup operation errors"""
#     pass
#
#
# class RestoreError(Exception):
#     """Exception raised for restore operation errors"""
#     pass
#
#
# class BackupService:
#     """Handle backup and restore operations for game saves.
#
#     Manages creating zip backups, restoring from backups,
#     and enforcing backup limits per installation.
#     """
#
#     def __init__(self, config_manager: ConfigurationManager):
#         self.config_manager = config_manager
#
#     @property
#     def config(self):
#         return self.config_manager.config
#
#     def create_backup(
#         self,
#         installation: Installation,
#         description: str = "",
#     ) -> BackupRecord:
#         """Create a backup of the specified installation's saves.
#
#         Args:
#             installation: The installation to backup
#             description: Optional description for the backup
#
#         Returns:
#             BackupRecord for the created backup
#
#         Raises:
#             BackupError: If backup creation fails
#         """
#         if not installation.save_path:
#             raise BackupError(f"No save path configured for {installation.display_name}")
#
#         if not installation.save_path.exists():
#             raise BackupError(f"Save path does not exist: {installation.save_path}")
#
#         timestamp = datetime.now()
#         backup_id = str(uuid.uuid4())
#
#         # Create backup directory structure
#         backup_dir = self._get_backup_dir(installation.id)
#         backup_dir.mkdir(parents=True, exist_ok=True)
#
#         # Create zip file with timestamp
#         filename = f"backup_{timestamp.strftime('%Y%m%d_%H%M%S')}.zip"
#         backup_path = backup_dir / filename
#
#         try:
#             logger.info(f"Creating backup for {installation.display_name} at {backup_path}")
#             with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as zf:
#                 file_count = 0
#                 for file in installation.save_path.rglob('*'):
#                     if file.is_file():
#                         arcname = file.relative_to(installation.save_path)
#                         zf.write(file, arcname)
#                         file_count += 1
#
#                 if file_count == 0:
#                     raise BackupError("No save files found to backup")
#
#             logger.info(f"Backup created successfully: {file_count} files archived")
#         except PermissionError as e:
#             logger.error(f"Permission denied creating backup: {e}")
#             raise BackupError(f"Permission denied: {e}")
#         except OSError as e:
#             logger.error(f"Failed to create backup: {e}")
#             raise BackupError(f"Failed to create backup: {e}")
#
#         # Create and store record
#         record = BackupRecord(
#             id=backup_id,
#             installation=installation.id,
#             timestamp=timestamp,
#             description=description or f"Backup from {timestamp.strftime('%Y-%m-%d %H:%M')}",
#             file_path=backup_path,
#         )
#
#         self.config_manager.add_backup(record)
#
#         # Enforce max backups limit
#         self._enforce_backup_limit(installation.id)
#
#         return record
#
#     def restore_backup(
#         self,
#         backup: BackupRecord,
#         create_safety_backup: bool = True,
#     ) -> bool:
#         """Restore a backup to its installation.
#
#         Args:
#             backup: The backup record to restore
#             create_safety_backup: If True, create a backup of current state first
#
#         Returns:
#             True if restore was successful
#
#         Raises:
#             RestoreError: If restore operation fails
#         """
#         if not backup.exists():
#             raise RestoreError(f"Backup file not found: {backup.file_path}")
#
#         installation = self.config.get_installation(backup.installation)
#         if installation is None:
#             raise RestoreError(f"Installation not found: {backup.installation.value}")
#
#         if not installation.save_path:
#             raise RestoreError(f"No save path configured for {installation.display_name}")
#
#         # Safety: backup current state first
#         if create_safety_backup and installation.save_path.exists():
#             try:
#                 any_files = any(installation.save_path.rglob('*'))
#                 if any_files:
#                     logger.info("Creating safety backup before restore")
#                     self.create_backup(installation, "Auto-backup before restore")
#             except BackupError as e:
#                 # If we can't create safety backup, still proceed with restore
#                 logger.warning(f"Could not create safety backup, proceeding with restore: {e}")
#
#         try:
#             logger.info(f"Restoring backup {backup.file_path} to {installation.save_path}")
#             # Clear current saves
#             if installation.save_path.exists():
#                 shutil.rmtree(installation.save_path)
#
#             # Create save directory
#             installation.save_path.mkdir(parents=True, exist_ok=True)
#
#             # Extract backup
#             with zipfile.ZipFile(backup.file_path, 'r') as zf:
#                 zf.extractall(installation.save_path)
#
#             logger.info("Backup restored successfully")
#         except PermissionError as e:
#             logger.error(f"Permission denied during restore: {e}")
#             raise RestoreError(f"Permission denied: {e}")
#         except zipfile.BadZipFile:
#             logger.error(f"Backup file is corrupted: {backup.file_path}")
#             raise RestoreError("Backup file is corrupted")
#         except OSError as e:
#             logger.error(f"Failed to restore backup: {e}")
#             raise RestoreError(f"Failed to restore backup: {e}")
#
#         return True
#
#     def delete_backup(self, backup: BackupRecord) -> bool:
#         """Delete a backup file and its record.
#
#         Args:
#             backup: The backup record to delete
#
#         Returns:
#             True if deletion was successful
#         """
#         logger.info(f"Deleting backup {backup.id}: {backup.file_path}")
#         # Delete the file if it exists
#         if backup.exists():
#             try:
#                 backup.file_path.unlink()
#             except OSError as e:
#                 # File might already be deleted
#                 logger.debug(f"Could not delete backup file (may already be deleted): {e}")
#
#         # Remove from configuration
#         return self.config_manager.remove_backup(backup.id)
#
#     def get_backup_info(self, backup: BackupRecord) -> dict:
#         """Get detailed information about a backup.
#
#         Args:
#             backup: The backup record to inspect
#
#         Returns:
#             Dictionary with backup details
#         """
#         info = {
#             "id": backup.id,
#             "installation": backup.installation.value,
#             "timestamp": backup.timestamp.isoformat(),
#             "description": backup.description,
#             "file_path": str(backup.file_path),
#             "exists": backup.exists(),
#             "size_mb": backup.get_size_mb(),
#             "files": [],
#         }
#
#         if backup.exists():
#             try:
#                 with zipfile.ZipFile(backup.file_path, 'r') as zf:
#                     info["files"] = [f.filename for f in zf.filelist]
#             except zipfile.BadZipFile:
#                 info["files"] = []
#
#         return info
#
#     def _get_backup_dir(self, installation_type: InstallationType) -> Path:
#         """Get the backup directory for an installation type.
#
#         Args:
#             installation_type: The installation type
#
#         Returns:
#             Path to the backup directory
#         """
#         backup_location = self.config.settings.backup_location or GamePaths.BACKUP_DEFAULT
#         return backup_location / installation_type.value
#
#     def _enforce_backup_limit(self, installation_type: InstallationType) -> None:
#         """Remove oldest backups if over the limit.
#
#         Args:
#             installation_type: The installation type to check
#         """
#         max_backups = self.config.settings.max_backups_per_installation
#         backups = self.config.get_backups_for_installation(installation_type)
#
#         # Backups are already sorted newest first
#         while len(backups) > max_backups:
#             oldest = backups.pop()  # Remove from end (oldest)
#             self.delete_backup(oldest)
#             # Refresh the list since delete_backup modifies config
#             backups = self.config.get_backups_for_installation(installation_type)
