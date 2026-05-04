from __future__ import annotations

import json
import re
import shutil
import zipfile
from contextlib import contextmanager, suppress
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from django.apps import apps
from django.conf import settings
from django.core.files import File
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.management import call_command
from django.core.management.color import no_style
from django.db import connection
from django.utils import timezone


class DjangoBackupManager:
    """Storage-agnostic backup manager for database and media archives."""

    ARCHIVE_METADATA_NAME = "metadata.json"
    ARCHIVE_DATABASE_NAME = "database.json"
    ARCHIVE_MEDIA_PREFIX = "media/"
    FORMAT_NAME = "workmpt-backup"
    FORMAT_VERSION = 2
    STORAGE_SKIP_ROOTS = ("backups", "_tmp_uploads", "_tmp_backup")
    DUMPDATA_EXCLUDES = (
        "admin.logentry",
        "sessions.session",
        "apihh_main.backup",
        "home.role",
    )

    def __init__(self):
        base_tmp_dir = Path(
            getattr(settings, "FILE_UPLOAD_TEMP_DIR", Path(settings.BASE_DIR) / "_tmp_uploads")
        )
        self.temp_root = base_tmp_dir / "_tmp_backup"
        self.temp_root.mkdir(parents=True, exist_ok=True)
        self.progress_callback = None

    def set_progress_callback(self, callback):
        self.progress_callback = callback

    def _update_progress(self, message, percent=None):
        if self.progress_callback:
            self.progress_callback(message, percent)

    def create_backup(self, backup_type="database", custom_name=None, user=None):
        backup_type = (backup_type or "database").strip().lower()
        base_name = self._build_base_name(backup_type, custom_name)

        creators = {
            "database": self._create_database_backup,
            "media": self._create_media_backup,
            "full": self._create_full_backup,
        }
        creator = creators.get(backup_type)
        if creator is None:
            return {"success": False, "error": "Unsupported backup type."}

        try:
            return creator(base_name, user)
        except Exception as exc:
            self._update_progress(f"Ошибка создания бэкапа: {exc}")
            return {"success": False, "error": str(exc)}

    def inspect_backup(self, backup_file):
        file_name = Path(getattr(backup_file, "name", "")).name
        suffix = Path(file_name).suffix.lower()

        try:
            if hasattr(backup_file, "seek"):
                backup_file.seek(0)

            if suffix == ".zip":
                with zipfile.ZipFile(backup_file, "r") as archive:
                    members = archive.namelist()
                    metadata = self._read_archive_metadata(archive)
                    contains_database = self.ARCHIVE_DATABASE_NAME in members
                    contains_media = any(
                        name.startswith(self.ARCHIVE_MEDIA_PREFIX) and not name.endswith("/")
                        for name in members
                    )
                    if not contains_database and not contains_media:
                        return {"valid": False, "error": "Archive has no database or media payload."}

                    backup_type = metadata.get("backup_type")
                    if backup_type not in {"database", "media", "full"}:
                        if contains_database and contains_media:
                            backup_type = "full"
                        elif contains_media:
                            backup_type = "media"
                        else:
                            backup_type = "database"

                    return {
                        "valid": True,
                        "backup_type": backup_type,
                        "format": metadata.get("format") or "legacy-zip",
                        "contains_database": contains_database,
                        "contains_media": contains_media,
                    }

            if suffix == ".json":
                payload = json.load(backup_file)
                if isinstance(payload, list):
                    return {
                        "valid": True,
                        "backup_type": "database",
                        "format": "fixture-json",
                        "contains_database": True,
                        "contains_media": False,
                    }
                if isinstance(payload, dict) and isinstance(payload.get("data"), dict):
                    return {
                        "valid": True,
                        "backup_type": "database",
                        "format": "legacy-django-json",
                        "contains_database": True,
                        "contains_media": False,
                    }
                return {"valid": False, "error": "Unsupported JSON backup structure."}

            return {"valid": False, "error": "Unsupported backup format."}
        except Exception as exc:
            return {"valid": False, "error": str(exc)}
        finally:
            if hasattr(backup_file, "seek"):
                with suppress(Exception):
                    backup_file.seek(0)

    def validate_backup(self, backup_file):
        return bool(self.inspect_backup(backup_file).get("valid"))

    def restore_backup(self, backup_file, user):
        self._update_progress("Подготавливаем файл бэкапа...", 5)
        temp_path = self._copy_backup_to_temp_file(backup_file)

        try:
            suffix = temp_path.suffix.lower()
            if suffix == ".zip":
                return self._restore_archive(temp_path, user)
            if suffix == ".json":
                return self._restore_database_payload(temp_path, user)
            raise Exception("Unsupported backup format. Use .zip or .json")
        finally:
            with suppress(FileNotFoundError):
                temp_path.unlink()

    def get_system_info(self):
        backup_model = self._backup_model()
        totals = {"total_backups": 0, "total_size": 0, "free_space": 0, "database_size": "Unknown"}

        try:
            totals["total_backups"] = backup_model.objects.count()
            totals["total_size"] = sum(
                (backup.file_size or 0) for backup in backup_model.objects.only("file_size")
            )
            totals["free_space"] = self._get_free_space()
            totals["database_size"] = self._get_database_size()

            db_status = self._check_database_connection()
            storage_status = self._check_storage_connection()
            error = None
            if not db_status["success"]:
                error = db_status["message"]
            elif not storage_status["success"]:
                error = storage_status["message"]

            totals.update(
                {
                    "backup_directory": self._describe_backup_location(),
                    "storage_backend": default_storage.__class__.__name__,
                    "storage_status": storage_status,
                    "database_status": db_status,
                    "error": error,
                }
            )
            return totals
        except Exception as exc:
            totals["error"] = str(exc)
            totals["backup_directory"] = self._describe_backup_location()
            totals["storage_backend"] = default_storage.__class__.__name__
            return totals

    def get_media_stats(self):
        stats = {
            "exists": True,
            "total_files": 0,
            "total_size": 0,
            "file_types": {},
            "largest_files": [],
        }

        media_files = self._collect_media_storage_files()
        largest = []
        for storage_path in media_files:
            with suppress(Exception):
                file_size = default_storage.size(storage_path)
                suffix = Path(storage_path).suffix.lower() or "<none>"
                stats["total_files"] += 1
                stats["total_size"] += file_size
                stats["file_types"][suffix] = stats["file_types"].get(suffix, 0) + 1
                largest.append((storage_path, file_size))

        largest.sort(key=lambda item: item[1], reverse=True)
        stats["largest_files"] = largest[:10]
        return stats

    def test_connection(self):
        db_status = self._check_database_connection()
        storage_status = self._check_storage_connection()
        if db_status["success"] and storage_status["success"]:
            return {"success": True, "message": "Database and storage connections are OK."}
        if not db_status["success"]:
            return db_status
        return storage_status

    def _create_database_backup(self, base_name, user):
        display_name = f"{base_name}.zip"
        archive_path = self._make_temp_file(".zip")

        self._update_progress("Создаем дамп базы данных...", 10)
        try:
            with self._temporary_work_dir() as work_dir:
                database_dump_path = work_dir / self.ARCHIVE_DATABASE_NAME
                self._dump_database(database_dump_path)
                metadata = self._build_metadata("database", user=user)
                self._update_progress("Упаковываем дамп базы данных...", 75)
                self._write_archive(
                    archive_path,
                    metadata=metadata,
                    database_dump_path=database_dump_path,
                )
            file_size = archive_path.stat().st_size
            self._update_progress("Бэкап базы данных готов.", 100)
            return self._result_payload(archive_path, display_name, "database", file_size)
        except Exception:
            with suppress(FileNotFoundError):
                archive_path.unlink()
            raise

    def _create_media_backup(self, base_name, user):
        display_name = f"{base_name}.zip"
        archive_path = self._make_temp_file(".zip")
        media_files = self._collect_media_storage_files()

        self._update_progress("Собираем медиафайлы для бэкапа...", 10)
        try:
            metadata = self._build_metadata("media", user=user, media_files_count=len(media_files))
            self._write_archive(
                archive_path,
                metadata=metadata,
                media_files=media_files,
            )
            file_size = archive_path.stat().st_size
            self._update_progress("Медиабэкап готов.", 100)
            return self._result_payload(archive_path, display_name, "media", file_size)
        except Exception:
            with suppress(FileNotFoundError):
                archive_path.unlink()
            raise

    def _create_full_backup(self, base_name, user):
        display_name = f"{base_name}.zip"
        archive_path = self._make_temp_file(".zip")
        media_files = self._collect_media_storage_files()

        self._update_progress("Создаем полный бэкап: база данных и медиа...", 5)
        try:
            with self._temporary_work_dir() as work_dir:
                database_dump_path = work_dir / self.ARCHIVE_DATABASE_NAME
                self._dump_database(database_dump_path)
                metadata = self._build_metadata("full", user=user, media_files_count=len(media_files))
                self._write_archive(
                    archive_path,
                    metadata=metadata,
                    database_dump_path=database_dump_path,
                    media_files=media_files,
                )
            file_size = archive_path.stat().st_size
            self._update_progress("Полный бэкап готов.", 100)
            return self._result_payload(archive_path, display_name, "full", file_size)
        except Exception:
            with suppress(FileNotFoundError):
                archive_path.unlink()
            raise

    def _write_archive(self, archive_path, *, metadata, database_dump_path=None, media_files=None):
        media_files = media_files or []
        total_media = len(media_files)

        with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(
                self.ARCHIVE_METADATA_NAME,
                json.dumps(metadata, ensure_ascii=False, indent=2),
            )

            if database_dump_path is not None:
                archive.write(database_dump_path, self.ARCHIVE_DATABASE_NAME)

            if media_files:
                for index, storage_path in enumerate(media_files, start=1):
                    progress = 55 + int(index * 40 / max(total_media, 1))
                    if index == 1 or index == total_media or index % 25 == 0:
                        self._update_progress(
                            f"Добавляем медиафайл {index}/{total_media}: {Path(storage_path).name}",
                            progress,
                        )
                    with default_storage.open(storage_path, "rb") as source, archive.open(
                        f"{self.ARCHIVE_MEDIA_PREFIX}{storage_path}", "w"
                    ) as destination:
                        shutil.copyfileobj(source, destination, length=1024 * 1024)

    def _dump_database(self, output_path):
        exclude = list(self.DUMPDATA_EXCLUDES)
        with open(output_path, "w", encoding="utf-8") as output:
            call_command(
                "dumpdata",
                database="default",
                exclude=exclude,
                indent=2,
                verbosity=0,
                stdout=output,
            )

    def _restore_archive(self, archive_path, user):
        self._update_progress("Открываем архив бэкапа...", 10)
        with open(archive_path, "rb") as archive_file:
            backup_info = self.inspect_backup(archive_file)
        if not backup_info.get("valid"):
            raise Exception(backup_info.get("error") or "Invalid archive backup.")

        with zipfile.ZipFile(archive_path, "r") as archive:
            contains_database = backup_info.get("contains_database")
            contains_media = backup_info.get("contains_media")
            database_result = None

            if contains_database:
                self._update_progress("Восстанавливаем базу данных из архива...", 25)
                with self._temporary_work_dir() as work_dir:
                    database_payload_path = work_dir / self.ARCHIVE_DATABASE_NAME
                    with archive.open(self.ARCHIVE_DATABASE_NAME, "r") as source, open(
                        database_payload_path, "wb"
                    ) as destination:
                        shutil.copyfileobj(source, destination)
                    database_result = self._restore_database_payload(database_payload_path, user)
                    if not database_result["success"]:
                        return database_result

            if contains_media:
                self._update_progress("Восстанавливаем медиахранилище...", 80)
                restored_media = self._restore_media_from_archive(archive)
                message = f"Восстановление завершено. Медиафайлов восстановлено: {restored_media}."
            else:
                message = database_result["message"] if database_result else "Восстановление завершено."

            self._update_progress(message, 100)
            return {"success": True, "message": message}

    def _restore_database_payload(self, payload_path, user):
        fixture_path = self._normalize_database_payload(payload_path)
        preserved_backups = self._capture_backup_records()
        actor_user_id = getattr(user, "id", None)

        try:
            self._update_progress("Очищаем текущую базу данных...", 35)
            call_command("flush", database="default", verbosity=0, interactive=False)
            self._update_progress("Загружаем данные из бэкапа...", 65)
            call_command("loaddata", str(fixture_path), database="default", verbosity=0)
            self._update_progress("Возвращаем служебные записи бэкапов...", 85)
            self._restore_backup_records(preserved_backups, actor_user_id=actor_user_id)
            self._update_progress("Синхронизируем счетчики идентификаторов...", 92)
            self.reset_primary_key_sequences()
        finally:
            if fixture_path != payload_path:
                with suppress(FileNotFoundError):
                    fixture_path.unlink()

        return {"success": True, "message": "База данных успешно восстановлена."}

    def _normalize_database_payload(self, payload_path):
        if payload_path.suffix.lower() != ".json":
            raise Exception("Database payload must be a JSON file.")

        with open(payload_path, "r", encoding="utf-8") as source:
            payload = json.load(source)

        if isinstance(payload, list):
            return payload_path

        if isinstance(payload, dict) and isinstance(payload.get("data"), dict):
            fixture_items = []
            for objects_data in payload["data"].values():
                if isinstance(objects_data, list):
                    fixture_items.extend(objects_data)
            temp_fixture = self._make_temp_file(".json")
            with open(temp_fixture, "w", encoding="utf-8") as destination:
                json.dump(fixture_items, destination, ensure_ascii=False, indent=2)
            return temp_fixture

        raise Exception("Unsupported JSON backup structure.")

    def _restore_media_from_archive(self, archive):
        current_media_files = self._collect_media_storage_files()
        for storage_path in current_media_files:
            with suppress(Exception):
                default_storage.delete(storage_path)

        restored_count = 0
        media_members = [
            name
            for name in archive.namelist()
            if name.startswith(self.ARCHIVE_MEDIA_PREFIX) and not name.endswith("/")
        ]

        for index, archive_name in enumerate(media_members, start=1):
            relative_path = archive_name[len(self.ARCHIVE_MEDIA_PREFIX) :].strip("/")
            if not relative_path or self._should_skip_storage_path(relative_path):
                continue
            progress = 82 + int(index * 16 / max(len(media_members), 1))
            if index == 1 or index == len(media_members) or index % 25 == 0:
                self._update_progress(
                    f"Восстанавливаем медиафайл {index}/{len(media_members)}: {Path(relative_path).name}",
                    progress,
                )
            with archive.open(archive_name, "r") as source:
                default_storage.save(relative_path, File(source, name=Path(relative_path).name))
            restored_count += 1

        return restored_count

    def _capture_backup_records(self):
        backup_model = self._backup_model()
        return [
            {
                "id": backup.id,
                "name": backup.name,
                "backup_file": backup.backup_file.name,
                "backup_type": backup.backup_type,
                "file_size": backup.file_size,
                "created_by_id": backup.created_by_id,
            }
            for backup in backup_model.objects.all()
        ]

    def _restore_backup_records(self, preserved_records, *, actor_user_id=None):
        if not preserved_records:
            return

        backup_model = self._backup_model()
        user_model = self._user_model()
        actor_user = None
        if actor_user_id is not None:
            actor_user = user_model.objects.filter(pk=actor_user_id).first()
        fallback_user = actor_user or user_model.objects.filter(is_superuser=True).order_by("id").first()
        fallback_user = fallback_user or user_model.objects.order_by("id").first()

        for record in preserved_records:
            if not record["backup_file"] or not default_storage.exists(record["backup_file"]):
                continue

            created_by = user_model.objects.filter(pk=record["created_by_id"]).first() or fallback_user
            if created_by is None:
                continue

            backup = backup_model(
                id=record["id"],
                name=record["name"],
                backup_file=record["backup_file"],
                backup_type=record["backup_type"],
                file_size=record["file_size"],
                created_by=created_by,
            )
            backup.save(force_insert=True)

    def reset_primary_key_sequences(self, models=None):
        model_list = list(
            models
            or [
                model
                for model in apps.get_models()
                if model._meta.managed and not model._meta.proxy and not model._meta.swapped
            ]
        )
        if not model_list:
            return

        sql_statements = connection.ops.sequence_reset_sql(no_style(), model_list)
        if not sql_statements:
            return

        with connection.cursor() as cursor:
            for sql in sql_statements:
                cursor.execute(sql)

    def _check_database_connection(self):
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            return {"success": True, "message": "Database connection OK"}
        except Exception as exc:
            return {"success": False, "message": f"Database connection failed: {exc}"}

    def _check_storage_connection(self):
        probe_name = f"backups/_healthchecks/{timezone.now().strftime('%Y%m%d_%H%M%S_%f')}.txt"
        try:
            saved_name = default_storage.save(
                probe_name,
                ContentFile(b"backup-healthcheck", name="healthcheck.txt"),
            )
            default_storage.delete(saved_name)
            return {"success": True, "message": "Storage connection OK"}
        except Exception as exc:
            return {"success": False, "message": f"Storage connection failed: {exc}"}

    def _collect_media_storage_files(self):
        collected = []
        for storage_path in self._walk_storage(""):
            if not self._should_skip_storage_path(storage_path):
                collected.append(storage_path)
        return collected

    def _walk_storage(self, prefix):
        try:
            directories, files = default_storage.listdir(prefix)
        except Exception:
            return

        for file_name in files:
            storage_path = f"{prefix}/{file_name}" if prefix else file_name
            yield storage_path.replace("\\", "/").lstrip("/")

        for directory in directories:
            next_prefix = f"{prefix}/{directory}" if prefix else directory
            normalized_prefix = next_prefix.replace("\\", "/").strip("/")
            if self._should_skip_storage_path(normalized_prefix):
                continue
            yield from self._walk_storage(normalized_prefix)

    def _should_skip_storage_path(self, relative_path):
        normalized = str(relative_path).replace("\\", "/").strip("/")
        if not normalized:
            return False
        for root in self.STORAGE_SKIP_ROOTS:
            if normalized == root or normalized.startswith(f"{root}/"):
                return True
        return False

    def _get_free_space(self):
        try:
            return shutil.disk_usage(self.temp_root).free
        except Exception:
            return 0

    def _get_database_size(self):
        engine = settings.DATABASES["default"]["ENGINE"]
        try:
            with connection.cursor() as cursor:
                if "postgresql" in engine:
                    cursor.execute("SELECT pg_database_size(%s)", [settings.DATABASES["default"]["NAME"]])
                    result = cursor.fetchone()
                    return self._format_file_size(result[0]) if result else "Unknown"
                if "sqlite3" in engine:
                    db_path = Path(settings.DATABASES["default"]["NAME"])
                    return self._format_file_size(db_path.stat().st_size) if db_path.exists() else "Unknown"
        except Exception:
            return "Unknown"
        return "Unknown"

    def _format_file_size(self, size_bytes):
        if not size_bytes:
            return "0 B"

        size_names = ["B", "KB", "MB", "GB", "TB"]
        size = float(size_bytes)
        index = 0
        while size >= 1024 and index < len(size_names) - 1:
            size /= 1024.0
            index += 1
        return f"{size:.2f} {size_names[index]}"

    def _build_metadata(self, backup_type, *, user=None, media_files_count=0):
        user_email = ""
        if user is not None:
            user_email = getattr(user, "email", "") or getattr(user, "username", "")
        return {
            "format": self.FORMAT_NAME,
            "version": self.FORMAT_VERSION,
            "backup_type": backup_type,
            "created_at": timezone.now().isoformat(),
            "created_by": user_email,
            "database_engine": settings.DATABASES["default"]["ENGINE"],
            "storage_backend": default_storage.__class__.__name__,
            "use_s3_media": bool(getattr(settings, "USE_S3_MEDIA", False)),
            "media_files_count": media_files_count,
        }

    def _read_archive_metadata(self, archive):
        if self.ARCHIVE_METADATA_NAME not in archive.namelist():
            return {}
        with archive.open(self.ARCHIVE_METADATA_NAME, "r") as metadata_file:
            return json.loads(metadata_file.read().decode("utf-8"))

    def _build_base_name(self, backup_type, custom_name):
        timestamp = timezone.now().strftime("%Y%m%d_%H%M%S")
        if custom_name:
            cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", custom_name.strip()).strip("._-")
            if cleaned:
                return f"{cleaned}_{timestamp}"
        return f"backup_{backup_type}_{timestamp}"

    def _result_payload(self, archive_path, display_name, backup_type, file_size):
        return {
            "success": True,
            "filepath": str(archive_path),
            "filename": display_name,
            "file_size": file_size,
            "backup_type": backup_type,
            "created_at": timezone.now(),
        }

    def _make_temp_file(self, suffix):
        self.temp_root.mkdir(parents=True, exist_ok=True)
        temp_path = self.temp_root / f"backup_{uuid4().hex}{suffix}"
        with open(temp_path, "xb"):
            pass
        return temp_path

    @contextmanager
    def _temporary_work_dir(self):
        self.temp_root.mkdir(parents=True, exist_ok=True)
        work_dir = self.temp_root / f"work_{uuid4().hex}"
        work_dir.mkdir(parents=True, exist_ok=False)
        try:
            yield work_dir
        finally:
            shutil.rmtree(work_dir, ignore_errors=True)

    def _copy_backup_to_temp_file(self, backup_file):
        suffix = Path(getattr(backup_file, "name", "")).suffix or ".bin"
        temp_path = self._make_temp_file(suffix)
        with open(temp_path, "wb") as destination:
            if hasattr(backup_file, "chunks"):
                for chunk in backup_file.chunks():
                    destination.write(chunk)
            else:
                shutil.copyfileobj(backup_file, destination)
        if hasattr(backup_file, "seek"):
            with suppress(Exception):
                backup_file.seek(0)
        return temp_path

    def _describe_backup_location(self):
        if getattr(settings, "USE_S3_MEDIA", False):
            bucket = getattr(settings, "AWS_STORAGE_BUCKET_NAME", "").strip()
            location = getattr(settings, "AWS_LOCATION", "").strip("/")
            prefix = "backups/"
            if location:
                prefix = f"{location}/{prefix}"
            return f"S3: {bucket}/{prefix}".rstrip("/")
        return str(Path(settings.MEDIA_ROOT) / "backups")

    def _backup_model(self):
        return apps.get_model("apihh_main", "Backup")

    def _user_model(self):
        return apps.get_model("apihh_main", "User")
