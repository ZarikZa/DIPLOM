import os
import zipfile
import json
from datetime import datetime
from django.db import connection
from django.conf import settings
from django.core import serializers
from pathlib import Path
import shutil
import tempfile
from django.apps import apps
import django
from io import BytesIO
import time

class DjangoBackupManager:
    def __init__(self):
        self.backup_dir = Path(settings.MEDIA_ROOT) / 'backups'
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        
        # Замените 'yourapp' на имя вашего приложения!
        self.models_to_backup = [
            'auth.User',
            'auth.Group', 
            'auth.Permission',
            'yourapp.Role',
            'yourapp.Company',
            'yourapp.Applicant',
            'yourapp.Employee',
            'yourapp.WorkConditions',
            'yourapp.StatusVacancies',
            'yourapp.StatusResponse',
            'yourapp.Vacancy',
            'yourapp.Complaint',
            'yourapp.Response',
            'yourapp.Favorites',
            'yourapp.AdminLog',
            'yourapp.Backup',
        ]
        
        # Для отслеживания прогресса
        self.progress_callback = None

    def set_progress_callback(self, callback):
        """Установка callback для отслеживания прогресса"""
        self.progress_callback = callback

    def _update_progress(self, message, percent=None):
        """Обновление прогресса"""
        if self.progress_callback:
            self.progress_callback(message, percent)

    def create_backup(self, backup_type='database', custom_name=None, user=None):
        """Создание бэкапа через Django"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        base_name = custom_name or f"backup_{backup_type}_{timestamp}"
        
        self._update_progress(f"Начинаем создание бэкапа типа: {backup_type}")
        
        try:
            if backup_type == 'full':
                return self._create_full_backup(base_name, user)
            elif backup_type == 'media':
                return self._create_media_backup(base_name, user)
            else:  # database
                return self._create_database_backup(base_name, user)
                
        except Exception as e:
            self._update_progress(f"Ошибка создания бэкапа: {str(e)}")
            return {'success': False, 'error': str(e)}

    def _create_database_backup(self, base_name, user):
        """Создание бэкапа базы данных через Django serializers"""
        filename = f"{base_name}.json"
        filepath = self.backup_dir / filename
        
        self._update_progress("Начинаем бэкап базы данных...", 10)
        
        try:
            backup_data = {}
            total_models = len(self.models_to_backup)
            
            # Собираем данные из всех моделей
            for i, model_path in enumerate(self.models_to_backup):
                try:
                    app_label, model_name = model_path.split('.')
                    model = apps.get_model(app_label, model_name)
                    
                    self._update_progress(f"Бэкап модели: {model_path}...", 10 + (i * 70 // total_models))
                    
                    # Сериализуем данные модели
                    data = serializers.serialize('json', model.objects.all())
                    backup_data[model_path] = json.loads(data)
                    
                    self._update_progress(f"Модель {model_path} завершена ({len(json.loads(data))} объектов)")
                    
                except Exception as e:
                    print(f"Warning: Could not backup {model_path}: {e}")
                    self._update_progress(f"Предупреждение: не удалось создать бэкап {model_path}: {e}")
                    continue
            
            self._update_progress("Сохраняем данные в файл...", 80)
            
            # Сохраняем в файл
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump({
                    'metadata': {
                        'created_at': datetime.now().isoformat(),
                        'backup_type': 'database',
                        'django_version': django.get_version(),
                        'models_backed_up': list(backup_data.keys())
                    },
                    'data': backup_data
                }, f, ensure_ascii=False, indent=2)
            
            file_size = filepath.stat().st_size
            
            self._update_progress(f"Бэкап базы данных завершен! Размер: {self._format_file_size(file_size)}", 100)
            
            return {
                'success': True,
                'filepath': str(filepath),
                'filename': filename,
                'file_size': file_size,
                'backup_type': 'database',
                'method': 'django_serializer',
                'created_at': datetime.now()
            }
            
        except Exception as e:
            if filepath.exists():
                filepath.unlink()
            self._update_progress(f"Ошибка бэкапа базы данных: {str(e)}")
            raise Exception(f"Database backup failed: {str(e)}")

    def _create_media_backup(self, base_name, user):
        """Создание бэкапа медиа файлов"""
        filename = f"{base_name}_media.zip"
        filepath = self.backup_dir / filename
        
        self._update_progress("Начинаем бэкап медиа файлов...", 10)
        
        try:
            media_dir = Path(settings.MEDIA_ROOT)
            media_files = []
            
            if media_dir.exists():
                self._update_progress("Сканируем медиа файлы...", 20)
                
                # Собираем список всех медиа файлов
                media_files = list(media_dir.rglob('*'))
                media_files = [f for f in media_files if f.is_file()]
                
                self._update_progress(f"Найдено {len(media_files)} файлов для бэкапа", 30)
            
            with zipfile.ZipFile(filepath, 'w', zipfile.ZIP_DEFLATED) as zipf:
                total_files = len(media_files)
                
                for i, media_file in enumerate(media_files):
                    try:
                        # Обновляем прогресс
                        progress = 30 + (i * 60 // total_files) if total_files > 0 else 90
                        self._update_progress(f"Добавляем файл: {media_file.name}...", progress)
                        
                        # Сохраняем относительный путь
                        arcname = media_file.relative_to(media_dir)
                        zipf.write(media_file, f"media/{arcname}")
                        
                        if i % 100 == 0:  # Логируем каждые 100 файлов
                            self._update_progress(f"Обработано {i}/{total_files} файлов...")
                            
                    except Exception as e:
                        print(f"Warning: Could not add {media_file}: {e}")
                        self._update_progress(f"Предупреждение: не удалось добавить {media_file}: {e}")
                        continue
            
            file_size = filepath.stat().st_size
            
            self._update_progress(f"Бэкап медиа файлов завершен! Размер: {self._format_file_size(file_size)}", 100)
            
            return {
                'success': True,
                'filepath': str(filepath),
                'filename': filename,
                'file_size': file_size,
                'backup_type': 'media',
                'method': 'zip',
                'created_at': datetime.now()
            }
            
        except Exception as e:
            if filepath.exists():
                filepath.unlink()
            self._update_progress(f"Ошибка бэкапа медиа файлов: {str(e)}")
            raise Exception(f"Media backup failed: {str(e)}")

    def _create_full_backup(self, base_name, user):
        """Создание полного бэкапа (база + медиа)"""
        filename = f"{base_name}_full.zip"
        filepath = self.backup_dir / filename
        
        self._update_progress("Начинаем создание полного бэкапа...", 5)
        
        try:
            # Сначала создаем бэкап базы данных
            self._update_progress("Создаем бэкап базы данных...", 10)
            db_backup = self._create_database_backup(f"{base_name}_db", user)
            
            self._update_progress("База данных завершена, начинаем упаковку в ZIP...", 50)
            
            with zipfile.ZipFile(filepath, 'w', zipfile.ZIP_DEFLATED) as zipf:
                # Добавляем бэкап базы данных
                self._update_progress("Добавляем бэкап базы данных в архив...", 60)
                zipf.write(db_backup['filepath'], 'database.json')
                
                # Добавляем медиа файлы
                self._update_progress("Добавляем медиа файлы в архив...", 70)
                media_dir = Path(settings.MEDIA_ROOT)
                if media_dir.exists():
                    media_files = list(media_dir.rglob('*'))
                    media_files = [f for f in media_files if f.is_file()]
                    total_files = len(media_files)
                    
                    for i, media_file in enumerate(media_files):
                        try:
                            progress = 70 + (i * 25 // total_files) if total_files > 0 else 95
                            self._update_progress(f"Добавляем медиа файл: {media_file.name}...", progress)
                            
                            arcname = media_file.relative_to(media_dir)
                            zipf.write(media_file, f"media/{arcname}")
                            
                            if i % 100 == 0:
                                self._update_progress(f"Медиа файлов обработано: {i}/{total_files}")
                                
                        except Exception as e:
                            print(f"Warning: Could not add {media_file}: {e}")
                            self._update_progress(f"Предупреждение: не удалось добавить {media_file}: {e}")
                            continue
            
            # Удаляем временный файл бэкапа БД
            if Path(db_backup['filepath']).exists():
                Path(db_backup['filepath']).unlink()
            
            file_size = filepath.stat().st_size
            
            self._update_progress(f"Полный бэкап завершен! Размер: {self._format_file_size(file_size)}", 100)
            
            return {
                'success': True,
                'filepath': str(filepath),
                'filename': filename,
                'file_size': file_size,
                'backup_type': 'full',
                'method': 'composite',
                'created_at': datetime.now()
            }
            
        except Exception as e:
            # Удаляем частично созданные файлы
            if filepath.exists():
                filepath.unlink()
            self._update_progress(f"Ошибка создания полного бэкапа: {str(e)}")
            raise Exception(f"Full backup failed: {str(e)}")

    def restore_backup(self, backup_file, user):
        """Восстановление из бэкапа без использования временных файлов"""
        self._update_progress("Начинаем восстановление из бэкапа...")
        
        try:
            # Читаем все содержимое файла в память
            file_content = backup_file.read()
            file_name = backup_file.name
            
            self._update_progress(f"Файл прочитан: {file_name}, размер: {self._format_file_size(len(file_content))}")
            
            # Определяем тип бэкапа и восстанавливаем
            if file_name.endswith('.zip'):
                result = self._restore_full_backup_from_memory(file_content, file_name, user)
            elif file_name.endswith('.json'):
                result = self._restore_database_backup_from_memory(file_content, file_name, user)
            else:
                raise Exception("Unsupported backup format. Use .zip or .json")
            
            self._update_progress("Восстановление завершено успешно!")
            return result
                
        except Exception as e:
            self._update_progress(f"Ошибка восстановления: {str(e)}")
            raise Exception(f"Restore failed: {str(e)}")

    def _restore_database_backup_from_memory(self, file_content, file_name, user):
        """Восстановление базы данных из JSON в памяти"""
        self._update_progress("Восстанавливаем базу данных из JSON...")
        
        try:
            # Декодируем JSON из памяти
            backup_data = json.loads(file_content.decode('utf-8'))
            
            if 'data' not in backup_data:
                raise Exception("Invalid backup format: missing 'data' section")
            
            restored_models = 0
            total_objects = 0
            total_models = len(backup_data['data'])
            
            # Восстанавливаем данные для каждой модели
            for i, (model_path, objects_data) in enumerate(backup_data['data'].items()):
                try:
                    progress = 10 + (i * 80 // total_models)
                    self._update_progress(f"Восстанавливаем модель: {model_path} ({len(objects_data)} объектов)...", progress)
                    
                    app_label, model_name = model_path.split('.')
                    model = apps.get_model(app_label, model_name)
                    
                    # Восстанавливаем объекты
                    for obj_data in objects_data:
                        try:
                            # Используем Django deserializer
                            obj = serializers.deserialize('json', json.dumps([obj_data]))
                            for deserialized_obj in obj:
                                deserialized_obj.save()
                            total_objects += 1
                        except Exception as e:
                            print(f"Warning: Could not restore object in {model_path}: {e}")
                            continue
                    
                    restored_models += 1
                    self._update_progress(f"Модель {model_path} восстановлена ({len(objects_data)} объектов)")
                    
                except Exception as e:
                    print(f"Warning: Could not restore model {model_path}: {e}")
                    self._update_progress(f"Предупреждение: не удалось восстановить модель {model_path}: {e}")
                    continue
            
            success_message = f'База данных успешно восстановлена: {restored_models} моделей, {total_objects} объектов'
            self._update_progress(success_message, 100)
            
            return {
                'success': True, 
                'message': success_message
            }
            
        except Exception as e:
            self._update_progress(f"Ошибка восстановления базы данных: {str(e)}")
            raise Exception(f"Database restore failed: {str(e)}")

    def _restore_full_backup_from_memory(self, file_content, file_name, user):
        """Восстановление полного бэкапа из памяти"""
        self._update_progress("Восстанавливаем полный бэкап...")
        
        try:
            # Используем BytesIO для работы с ZIP в памяти
            zip_buffer = BytesIO(file_content)
            
            with zipfile.ZipFile(zip_buffer, 'r') as zipf:
                self._update_progress("ZIP архив открыт, ищем файлы...")
                
                # Ищем файл базы данных
                db_file_info = None
                media_files_count = 0
                
                for file_info in zipf.filelist:
                    if file_info.filename == 'database.json':
                        db_file_info = file_info
                    elif file_info.filename.startswith('media/') and not file_info.is_dir():
                        media_files_count += 1
                
                self._update_progress(f"Найдено: database.json и {media_files_count} медиа файлов")
                
                if not db_file_info:
                    return {'success': False, 'error': 'Database backup not found in full backup'}
                
                # Читаем базу данных из ZIP
                with zipf.open('database.json') as db_file:
                    db_content = db_file.read()
                
                # Восстанавливаем базу данных
                self._update_progress("Восстанавливаем базу данных...", 30)
                db_result = self._restore_database_backup_from_memory(db_content, 'database.json', user)
                if not db_result['success']:
                    return db_result
                
                # Восстанавливаем медиа файлы
                self._update_progress("Восстанавливаем медиа файлы...", 70)
                media_files_restored = self._restore_media_from_zip(zipf)
                
                self._update_progress(f"Восстановлено {media_files_restored} медиа файлов", 100)
            
            return {
                'success': True, 
                'message': f'Полный бэкап успешно восстановлен. {media_files_restored} медиа файлов восстановлено.'
            }
            
        except Exception as e:
            self._update_progress(f"Ошибка восстановления полного бэкапа: {str(e)}")
            raise Exception(f"Full backup restore failed: {str(e)}")

    def _restore_media_from_zip(self, zipf):
        """Восстановление медиа файлов из ZIP архива"""
        media_files_restored = 0
        media_dest = Path(settings.MEDIA_ROOT)
        
        # Создаем backup старых медиа файлов
        backup_timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        media_backup = media_dest.parent / f"media_backup_{backup_timestamp}"
        
        try:
            # Создаем резервную копию существующих медиа файлов
            if media_dest.exists():
                print(f"Creating media backup: {media_backup}")
                shutil.move(str(media_dest), str(media_backup))
            
            # Создаем новую медиа директорию
            media_dest.mkdir(parents=True, exist_ok=True)
            
            # Восстанавливаем медиа файлы из ZIP
            for file_info in zipf.filelist:
                if file_info.filename.startswith('media/') and not file_info.is_dir():
                    try:
                        # Получаем относительный путь
                        relative_path = file_info.filename[6:]  # Убираем 'media/'
                        if not relative_path:
                            continue
                            
                        # Создаем полный путь назначения
                        dest_path = media_dest / relative_path
                        dest_path.parent.mkdir(parents=True, exist_ok=True)
                        
                        # Извлекаем файл
                        with zipf.open(file_info.filename) as source_file:
                            with open(dest_path, 'wb') as dest_file:
                                dest_file.write(source_file.read())
                        
                        media_files_restored += 1
                        
                    except Exception as e:
                        print(f"Warning: Could not restore media file {file_info.filename}: {e}")
                        continue
            
            return media_files_restored
            
        except Exception as e:
            # В случае ошибки пытаемся восстановить из backup
            print(f"Error restoring media, attempting rollback: {e}")
            if media_backup.exists() and not media_dest.exists():
                try:
                    shutil.move(str(media_backup), str(media_dest))
                    print("Media rollback successful")
                except Exception as rollback_error:
                    print(f"Media rollback failed: {rollback_error}")
            raise

    def get_system_info(self):
        """Получение информации о системе"""
        try:
            backup_files = list(self.backup_dir.glob('*'))
            total_size = sum(f.stat().st_size for f in backup_files if f.is_file())
            
            # Получаем размер базы данных
            db_size = self._get_database_size()
            
            return {
                'total_backups': len(backup_files),
                'total_size': total_size,
                'free_space': self._get_free_space(),
                'database_size': db_size,
                'backup_directory': str(self.backup_dir),
                'error': None
            }
        except Exception as e:
            return {
                'total_backups': 0,
                'total_size': 0,
                'free_space': 0,
                'database_size': 'Unknown',
                'error': str(e)
            }

    def _get_free_space(self):
        """Получение свободного места на диске"""
        try:
            total, used, free = shutil.disk_usage(self.backup_dir)
            return free
        except:
            return 0

    def _get_database_size(self):
        """Получение размера базы данных"""
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_database_size(%s)", [settings.DATABASES['default']['NAME']])
                result = cursor.fetchone()
                return self._format_file_size(result[0]) if result else 'Unknown'
        except:
            return 'Unknown'

    def _format_file_size(self, size_bytes):
        """Форматирование размера файла в читаемый вид"""
        if size_bytes == 0:
            return "0 B"
        
        size_names = ["B", "KB", "MB", "GB"]
        i = 0
        size = size_bytes
        
        while size >= 1024 and i < len(size_names) - 1:
            size /= 1024.0
            i += 1
        
        return f"{size:.2f} {size_names[i]}"

    def validate_backup(self, backup_file):
        """Проверка целостности бэкапа"""
        try:
            file_content = backup_file.read()
            
            if backup_file.name.endswith('.json'):
                # Проверяем JSON файл
                data = json.loads(file_content.decode('utf-8'))
                return 'metadata' in data and 'data' in data
            elif backup_file.name.endswith('.zip'):
                # Проверяем ZIP архив в памяти
                zip_buffer = BytesIO(file_content)
                with zipfile.ZipFile(zip_buffer, 'r') as zipf:
                    return zipf.testzip() is None
            else:
                return False
        except:
            return False
        finally:
            # Возвращаем указатель файла в начало
            backup_file.seek(0)

    def test_connection(self):
        """Тестирование подключения к базе данных"""
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                return {'success': True, 'message': 'Database connection OK'}
        except Exception as e:
            return {'success': False, 'message': f'Database connection failed: {str(e)}'}

    def _create_media_backup(self, base_name, user):
        """Создание бэкапа медиа файлов с детальной отладкой"""
        filename = f"{base_name}_media.zip"
        filepath = self.backup_dir / filename
        
        print(f"DEBUG: Starting media backup. Base name: {base_name}, Filepath: {filepath}")
        self._update_progress("Начинаем бэкап медиа файлов...", 10)
        
        try:
            media_dir = Path(settings.MEDIA_ROOT)
            print(f"DEBUG: Media directory: {media_dir}, exists: {media_dir.exists()}")
            
            media_files = []
            
            if media_dir.exists():
                self._update_progress("Сканируем медиа файлы...", 20)
                print("DEBUG: Starting to scan media files...")
                
                # Собираем список всех медиа файлов с детальным логированием
                start_time = time.time()
                try:
                    media_files = list(media_dir.rglob('*'))
                    print(f"DEBUG: Found {len(media_files)} total items in media directory")
                    
                    # Фильтруем только файлы
                    media_files = [f for f in media_files if f.is_file()]
                    print(f"DEBUG: Filtered to {len(media_files)} actual files")
                    
                    scan_time = time.time() - start_time
                    print(f"DEBUG: File scanning took {scan_time:.2f} seconds")
                    
                except Exception as scan_error:
                    print(f"DEBUG: Error during file scanning: {scan_error}")
                    raise scan_error
                
                self._update_progress(f"Найдено {len(media_files)} файлов для бэкапа", 30)
                
                # Если файлов слишком много, логируем первые 10
                if media_files:
                    print(f"DEBUG: First 10 files: {[str(f) for f in media_files[:10]]}")
            else:
                print("DEBUG: Media directory does not exist!")
                self._update_progress("Медиа директория не найдена", 30)
            
            # Проверяем доступность записи
            print(f"DEBUG: Checking write access to {filepath.parent}")
            try:
                filepath.parent.mkdir(parents=True, exist_ok=True)
                test_file = filepath.parent / "test_write.tmp"
                with open(test_file, 'w') as f:
                    f.write("test")
                test_file.unlink()
                print("DEBUG: Write access confirmed")
            except Exception as e:
                print(f"DEBUG: Write access error: {e}")
                raise Exception(f"No write access to backup directory: {e}")
            
            print(f"DEBUG: Creating ZIP file at {filepath}")
            self._update_progress("Создаем ZIP архив...", 40)
            
            with zipfile.ZipFile(filepath, 'w', zipfile.ZIP_DEFLATED) as zipf:
                total_files = len(media_files)
                print(f"DEBUG: Starting to add {total_files} files to ZIP")
                
                processed_files = 0
                success_files = 0
                error_files = 0
                
                for i, media_file in enumerate(media_files):
                    try:
                        processed_files += 1
                        
                        # Обновляем прогресс каждые 10 файлов или для первых 10 файлов
                        if i < 10 or i % 100 == 0:
                            progress = 40 + (i * 50 // total_files) if total_files > 0 else 90
                            self._update_progress(f"Добавляем файл {i+1}/{total_files}: {media_file.name}...", progress)
                            print(f"DEBUG: Processing file {i+1}/{total_files}: {media_file}")
                        
                        # Проверяем существование файла и его размер
                        if not media_file.exists():
                            print(f"DEBUG: File does not exist: {media_file}")
                            error_files += 1
                            continue
                        
                        file_size = media_file.stat().st_size
                        if file_size == 0:
                            print(f"DEBUG: Empty file: {media_file}")
                        
                        # Сохраняем относительный путь
                        try:
                            arcname = media_file.relative_to(media_dir)
                            zipf.write(media_file, f"media/{arcname}")
                            success_files += 1
                            
                            if i < 5:  # Детально логируем первые 5 файлов
                                print(f"DEBUG: Successfully added: {media_file} -> media/{arcname}")
                                
                        except Exception as write_error:
                            print(f"DEBUG: Error writing {media_file} to ZIP: {write_error}")
                            error_files += 1
                            continue
                            
                    except Exception as e:
                        print(f"DEBUG: Unexpected error processing {media_file}: {e}")
                        error_files += 1
                        continue
                
                print(f"DEBUG: ZIP creation completed. Success: {success_files}, Errors: {error_files}, Total: {processed_files}")
                self._update_progress(f"ZIP создан. Успешно: {success_files}, Ошибок: {error_files}", 90)
            
            # Проверяем созданный файл
            if filepath.exists():
                file_size = filepath.stat().st_size
                print(f"DEBUG: Backup file created successfully. Size: {file_size} bytes")
                
                # Проверяем целостность ZIP
                try:
                    with zipfile.ZipFile(filepath, 'r') as test_zip:
                        test_result = test_zip.testzip()
                        if test_result is None:
                            print("DEBUG: ZIP file integrity check passed")
                        else:
                            print(f"DEBUG: ZIP file integrity check failed: {test_result}")
                except Exception as integrity_error:
                    print(f"DEBUG: ZIP integrity check error: {integrity_error}")
            else:
                print("DEBUG: Backup file was not created!")
                raise Exception("Backup file was not created")
            
            file_size = filepath.stat().st_size
            
            final_message = f"Бэкап медиа файлов завершен! Размер: {self._format_file_size(file_size)}"
            print(f"DEBUG: {final_message}")
            self._update_progress(final_message, 100)
            
            return {
                'success': True,
                'filepath': str(filepath),
                'filename': filename,
                'file_size': file_size,
                'backup_type': 'media',
                'method': 'zip',
                'created_at': datetime.now()
            }
            
        except Exception as e:
            print(f"DEBUG: Media backup failed with error: {e}")
            if filepath.exists():
                try:
                    filepath.unlink()
                    print("DEBUG: Removed incomplete backup file")
                except:
                    print("DEBUG: Could not remove incomplete backup file")
            self._update_progress(f"Ошибка бэкапа медиа файлов: {str(e)}")
            raise Exception(f"Media backup failed: {str(e)}")

    def _create_full_backup(self, base_name, user):
        """Создание полного бэкапа (база + медиа)"""
        filename = f"{base_name}_full.zip"
        filepath = self.backup_dir / filename
        
        try:
            # Сначала создаем бэкап базы данных
            db_backup = self._create_database_backup(f"{base_name}_db", user)
            
            with zipfile.ZipFile(filepath, 'w', zipfile.ZIP_DEFLATED) as zipf:
                # Добавляем бэкап базы данных
                zipf.write(db_backup['filepath'], 'database.json')
                
                # Добавляем медиа файлы
                media_dir = Path(settings.MEDIA_ROOT)
                if media_dir.exists():
                    for media_file in media_dir.rglob('*'):
                        if media_file.is_file():
                            try:
                                arcname = media_file.relative_to(media_dir)
                                zipf.write(media_file, f"media/{arcname}")
                            except Exception as e:
                                print(f"Warning: Could not add {media_file}: {e}")
                                continue
            
            # Удаляем временный файл бэкапа БД
            if Path(db_backup['filepath']).exists():
                Path(db_backup['filepath']).unlink()
            
            file_size = filepath.stat().st_size
            
            return {
                'success': True,
                'filepath': str(filepath),
                'filename': filename,
                'file_size': file_size,
                'backup_type': 'full',
                'method': 'composite',
                'created_at': datetime.now()
            }
            
        except Exception as e:
            # Удаляем частично созданные файлы
            if filepath.exists():
                filepath.unlink()
            raise Exception(f"Full backup failed: {str(e)}")