from pathlib import Path
import subprocess
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import user_passes_test
from django.contrib import messages
from django.http import FileResponse, HttpResponse, JsonResponse
from django.core.files import File
from django.db import connection, IntegrityError
from django.db.utils import ProgrammingError
from datetime import timedelta
import os
from urllib.parse import urlencode, urljoin, urlparse

from django.urls import reverse
from matplotlib import pyplot as plt

from .procedure_manager import DjangoBackupManager
from .forms import AdminProfileEditForm, BackupUploadForm, SiteAdminCreateForm, SiteAdminEditForm
from home.models import *
from home.models import Company, Complaint, User, Vacancy, StatusVacancies
from home.models import Backup, AdminLog, ActionType
from home.api_client import api_base_url, api_get, api_patch, api_post
from .forms import CompanyModerationForm

def is_admin(user):
    """Проверка что пользователь администратор (суперпользователь или adminsite)"""
    return user.is_authenticated and (user.is_superuser or user.user_type == 'adminsite')

def is_superuser_only(user):
    """Проверка что пользователь ТОЛЬКО суперпользователь"""
    return user.is_authenticated and user.is_superuser

def get_admin_context(request):
    pending_count = Company.objects.filter(status=Company.STATUS_PENDING).count()
    pending_complaints_count = Complaint.objects.filter(status='pending').count()
    site_admins_count = User.objects.filter(user_type='adminsite', is_active=True).count()
    pending_category_suggestions_count = _fetch_suggestions_count(request, 'pending')
    
    return {
        'pending_companies_count': pending_count,
        'pending_complaints_count': pending_complaints_count,
        'pending_category_suggestions_count': pending_category_suggestions_count,
        'site_admins_count': site_admins_count,
        'is_superuser': request.user.is_superuser,
    }


def get_platform_users_queryset():
    return User.objects.exclude(user_type='adminsite').exclude(is_superuser=True)


def _save_backup_record_with_synced_sequence(backup_manager: DjangoBackupManager, backup: Backup) -> None:
    backup_manager.reset_primary_key_sequences([Backup])
    try:
        backup.save(force_insert=True)
    except IntegrityError as exc:
        error_text = str(exc).lower()
        if 'duplicate key' not in error_text and 'unique constraint' not in error_text:
            raise
        backup_manager.reset_primary_key_sequences([Backup])
        backup.save(force_insert=True)

def get_or_create_action_type(code, name=None):
    """
    Вспомогательная функция для получения или создания типа действия
    Используется при создании логов
    """
    if name is None:
        # Генерируем читаемое имя из кода
        name = ' '.join(word.capitalize() for word in code.split('_'))
    
    try:
        action_type = ActionType.objects.get(code=code)
    except ActionType.DoesNotExist:
        action_type = ActionType.objects.create(
            code=code,
            name=name,
            description=f'Автоматически созданный тип действия: {name}'
        )
    
    return action_type


def _api_safe_json(resp):
    try:
        return resp.json()
    except Exception:
        return None


def _api_results(payload):
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        return []

    for key in ('results', 'items'):
        value = payload.get(key)
        if isinstance(value, list):
            return value

    data = payload.get('data')
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ('results', 'items'):
            value = data.get(key)
            if isinstance(value, list):
                return value

    for value in payload.values():
        if isinstance(value, list):
            return value

    return []


def _api_first_error(payload, default_message: str) -> str:
    if isinstance(payload, str) and payload.strip():
        return payload.strip()

    if isinstance(payload, list):
        for item in payload:
            text = _api_first_error(item, '')
            if text:
                return text

    if isinstance(payload, dict):
        for key in ('detail', 'error', 'message'):
            if key in payload:
                text = _api_first_error(payload.get(key), '')
                if text:
                    return text
        for key, value in payload.items():
            text = _api_first_error(value, '')
            if text:
                if key in ('non_field_errors', '__all__'):
                    return text
                return f'{key}: {text}'

    return default_message


def _extract_company_document_path(raw_name: str) -> str:
    normalized = str(raw_name or '').strip().replace('\\', '/')
    if not normalized:
        return ''

    if normalized.startswith(('http://', 'https://')):
        return normalized

    lowered = normalized.lower()
    for marker in ('company_documents/', 'vacancy_videos/', 'media/'):
        idx = lowered.find(marker)
        if idx != -1:
            normalized = normalized[idx:]
            lowered = normalized.lower()
            break

    if lowered.startswith('vacancy_videos/'):
        normalized = normalized[len('vacancy_videos/'):]
        lowered = normalized.lower()

    if lowered.startswith('media/'):
        normalized = normalized[len('media/'):]

    return normalized.lstrip('/')


def _resolve_company_document(company) -> tuple[str, str]:
    document = getattr(company, 'verification_document', None)
    if not document:
        return '', ''

    raw_name = str(getattr(document, 'name', '') or '').strip()
    display_name = Path(raw_name.replace('\\', '/')).name or raw_name

    if raw_name.startswith(('http://', 'https://')):
        return raw_name, display_name

    local_url = ''
    local_exists = False
    try:
        local_url = document.url
    except Exception:
        local_url = ''

    try:
        local_exists = Path(document.path).exists()
    except Exception:
        local_exists = False

    if local_url and local_exists:
        return local_url, display_name

    relative_path = _extract_company_document_path(raw_name)
    if relative_path.startswith(('http://', 'https://')):
        parsed_remote = urlparse(relative_path)
        remote_name = Path(parsed_remote.path).name or display_name
        return relative_path, remote_name

    if not relative_path:
        relative_path = display_name

    api_url = api_base_url()
    parsed = urlparse(api_url)
    if parsed.scheme and parsed.netloc and relative_path:
        origin = f'{parsed.scheme}://{parsed.netloc}/'
        cleaned = relative_path.replace('\\', '/').lstrip('/')
        candidates = []
        if cleaned.lower().startswith(('vacancy_videos/', 'media/')):
            candidates.append(urljoin(origin, cleaned))
        candidates.append(urljoin(origin, f'vacancy_videos/{cleaned}'))
        candidates.append(urljoin(origin, f'media/{cleaned}'))
        candidates.append(urljoin(origin, cleaned))

        seen = set()
        for candidate in candidates:
            if candidate and candidate not in seen:
                seen.add(candidate)
                return candidate, Path(cleaned).name or display_name

    return local_url, display_name


def _fetch_suggestions_count(request, status_value: str | None = None) -> int:
    params = {'page': 1}
    if status_value:
        params['status'] = status_value
    try:
        resp = api_get(request, 'admin/vacancy-category-suggestions/', params=params)
        payload = _api_safe_json(resp) or {}
        if resp.status_code >= 400:
            return 0
        if isinstance(payload, dict) and 'count' in payload:
            return int(payload.get('count') or 0)
        return len(_api_results(payload))
    except Exception:
        return 0


def _fetch_skill_suggestions_count(request, status_value: str | None = None) -> int:
    params = {'page': 1}
    if status_value:
        params['status'] = status_value
    try:
        resp = api_get(request, 'admin/skill-suggestions/', params=params)
        payload = _api_safe_json(resp) or {}
        if resp.status_code >= 400:
            return 0
        if isinstance(payload, dict) and 'count' in payload:
            return int(payload.get('count') or 0)
        return len(_api_results(payload))
    except Exception:
        return 0


def _collect_api_rows(request, path: str, params: dict | None = None, max_pages: int = 20):
    rows: list[dict] = []
    query_params = dict(params or {})
    page = 1

    while page <= max_pages:
        query_params['page'] = page
        resp = api_get(request, path, params=query_params)
        payload = _api_safe_json(resp) or {}
        if resp.status_code >= 400:
            return None, payload

        chunk = _api_results(payload)
        rows.extend(item for item in chunk if isinstance(item, dict))

        next_url = payload.get('next') if isinstance(payload, dict) else None
        if not next_url:
            break
        page += 1

    return rows, None

@user_passes_test(is_admin, login_url='/admin/login/')
def admin_dashboard(request):
    """Главная страница админки"""
    context = get_admin_context(request)
    
    pending_companies = Company.objects.filter(status=Company.STATUS_PENDING)
    total_companies = Company.objects.count()
    approved_companies = Company.objects.filter(status=Company.STATUS_APPROVED).count()
    rejected_companies = Company.objects.filter(status=Company.STATUS_REJECTED).count()
    pending_complaints_count = Complaint.objects.filter(status='pending').count()
    
    # Последние логи
    recent_logs = AdminLog.objects.all().order_by('-created_at')[:10]
    
    # Статистика пользователей
    total_users = get_platform_users_queryset().count()
    company_users = User.objects.filter(user_type='company').count()
    applicant_users = User.objects.filter(user_type='applicant').count()
    
    context.update({
        'pending_count': pending_companies.count(),
        'total_companies': total_companies,
        'approved_companies': approved_companies,
        'rejected_companies': rejected_companies,
        'total_users': total_users,
        'company_users': company_users,
        'applicant_users': applicant_users,
        'recent_logs': recent_logs,
        'pending_complaints_count': pending_complaints_count,
    })
    return render(request, 'admin_panel/dashboard.html', context)


@user_passes_test(is_admin, login_url='/admin/login/')
def category_moderation(request):
    context = get_admin_context(request)

    if not request.session.get('api_access'):
        messages.warning(
            request,
            'Для модерации категорий нужна авторизация через форму входа приложения (JWT).'
        )
        context.update({
            'suggestions': [],
            'status_filter': 'all',
            'search_query': '',
            'total_suggestions_count': 0,
            'pending_suggestions_count': 0,
            'approved_suggestions_count': 0,
            'rejected_suggestions_count': 0,
            'pending_complaints_count': Complaint.objects.filter(status='pending').count(),
            'current_page': 1,
            'has_next_page': False,
            'has_previous_page': False,
            'next_page': 1,
            'previous_page': 1,
            'total_pages': 1,
        })
        return render(request, 'admin_panel/category_moderation.html', context)

    status_filter = (request.GET.get('status') or 'all').strip().lower()
    if status_filter not in {'all', 'pending', 'approved', 'rejected'}:
        status_filter = 'all'

    search_query = (request.GET.get('search') or '').strip()
    page = request.GET.get('page') or 1
    try:
        current_page = int(page)
    except Exception:
        current_page = 1

    if request.method == 'POST':
        form_action = (request.POST.get('form_action') or '').strip().lower() or 'moderate'

        if form_action == 'create_category':
            category_name = (request.POST.get('category_name') or '').strip()
            category_notes = (request.POST.get('category_notes') or '').strip()

            if not category_name:
                messages.error(
                    request,
                    'Укажите название категории.' if request.LANGUAGE_CODE != 'en' else 'Enter a category name.',
                )
            else:
                payload = {'name': category_name}
                if category_notes:
                    payload['admin_notes'] = category_notes
                try:
                    resp = api_post(request, 'admin/vacancy-category-suggestions/', json=payload)
                    data = _api_safe_json(resp)
                    if resp.status_code >= 400:
                        messages.error(
                            request,
                            _api_first_error(
                                data,
                                (
                                    'Не удалось добавить категорию.'
                                    if request.LANGUAGE_CODE != 'en'
                                    else 'Failed to add category.'
                                ),
                            ),
                        )
                    else:
                        created_name = str((data or {}).get('name') or category_name).strip()
                        action_type = get_or_create_action_type(
                            'vacancy_category_created_by_admin',
                            (
                                'Категория вакансии добавлена'
                                if request.LANGUAGE_CODE != 'en'
                                else 'Vacancy category created'
                            ),
                        )
                        AdminLog.objects.create(
                            admin=request.user,
                            action=action_type,
                            details=(
                                f'Добавлена категория вакансии: "{created_name}"'
                                if request.LANGUAGE_CODE != 'en'
                                else f'Vacancy category added: "{created_name}"'
                            ),
                        )
                        messages.success(
                            request,
                            (
                                f'Категория "{created_name}" добавлена.'
                                if request.LANGUAGE_CODE != 'en'
                                else f'Category "{created_name}" added.'
                            ),
                        )
                except Exception:
                    messages.error(
                        request,
                        (
                            'Ошибка сети при добавлении категории.'
                            if request.LANGUAGE_CODE != 'en'
                            else 'Network error while adding category.'
                        ),
                    )
        else:
            suggestion_id = (request.POST.get('suggestion_id') or '').strip()
            new_status = (request.POST.get('status') or '').strip().lower()
            admin_notes = (request.POST.get('admin_notes') or '').strip()

            if not suggestion_id:
                messages.error(
                    request,
                    (
                        'Не найдена заявка категории для обработки.'
                        if request.LANGUAGE_CODE != 'en'
                        else 'Category suggestion not found for processing.'
                    ),
                )
            elif new_status not in {'approved', 'rejected'}:
                messages.error(
                    request,
                    'Выбран некорректный статус.' if request.LANGUAGE_CODE != 'en' else 'Invalid status selected.',
                )
            else:
                payload = {'status': new_status}
                if admin_notes:
                    payload['admin_notes'] = admin_notes

                try:
                    resp = api_patch(
                        request,
                        f'admin/vacancy-category-suggestions/{suggestion_id}/',
                        json=payload,
                    )
                    data = _api_safe_json(resp)
                    if resp.status_code >= 400:
                        messages.error(
                            request,
                            _api_first_error(
                                data,
                                (
                                    'Не удалось обновить статус категории.'
                                    if request.LANGUAGE_CODE != 'en'
                                    else 'Failed to update category status.'
                                ),
                            ),
                        )
                    else:
                        action_type = get_or_create_action_type(
                            'vacancy_category_approved' if new_status == 'approved' else 'vacancy_category_rejected',
                            (
                                'Категория вакансии одобрена'
                                if (new_status == 'approved' and request.LANGUAGE_CODE != 'en')
                                else (
                                    'Категория вакансии отклонена'
                                    if request.LANGUAGE_CODE != 'en'
                                    else (
                                        'Vacancy category approved'
                                        if new_status == 'approved'
                                        else 'Vacancy category rejected'
                                    )
                                )
                            ),
                        )
                        category_name = ''
                        if isinstance(data, dict):
                            category_name = str(data.get('name') or '').strip()
                        details = (
                            f'Категория "{category_name}" '
                            f'{"одобрена" if new_status == "approved" else "отклонена"} администратором'
                            if request.LANGUAGE_CODE != 'en'
                            else f'Category "{category_name}" {"approved" if new_status == "approved" else "rejected"} by admin'
                        )
                        if admin_notes:
                            details += (
                                f'. Комментарий: {admin_notes}'
                                if request.LANGUAGE_CODE != 'en'
                                else f'. Note: {admin_notes}'
                            )
                        AdminLog.objects.create(
                            admin=request.user,
                            action=action_type,
                            details=details,
                        )
                        messages.success(
                            request,
                            (
                                'Категория одобрена.' if new_status == 'approved' else 'Категория отклонена.'
                            )
                            if request.LANGUAGE_CODE != 'en'
                            else ('Category approved.' if new_status == 'approved' else 'Category rejected.'),
                        )
                except Exception:
                    messages.error(
                        request,
                        (
                            'Ошибка сети при обновлении статуса категории.'
                            if request.LANGUAGE_CODE != 'en'
                            else 'Network error while updating category status.'
                        ),
                    )

        redirect_url = reverse('admin_category_moderation')
        params = {}
        if status_filter != 'all':
            params['status'] = status_filter
        if search_query:
            params['search'] = search_query
        if params:
            redirect_url = f"{redirect_url}?{urlencode(params)}"
        return redirect(redirect_url)

    suggestions = []
    total_count = 0
    next_url = None
    previous_url = None
    try:
        params = {'page': page}
        if status_filter != 'all':
            params['status'] = status_filter
        if search_query:
            params['search'] = search_query

        resp = api_get(request, 'admin/vacancy-category-suggestions/', params=params)
        data = _api_safe_json(resp) or {}
        if resp.status_code >= 400:
            messages.error(
                request,
                _api_first_error(data, 'Не удалось загрузить заявки категорий.')
            )
        else:
            suggestions = _api_results(data)
            if isinstance(data, dict):
                total_count = int(data.get('count') or len(suggestions))
                next_url = data.get('next')
                previous_url = data.get('previous')
            else:
                total_count = len(suggestions)
    except Exception:
        messages.error(request, 'Ошибка сети при загрузке заявок категорий.')

    pending_count = _fetch_suggestions_count(request, 'pending')
    approved_count = _fetch_suggestions_count(request, 'approved')
    rejected_count = _fetch_suggestions_count(request, 'rejected')
    pending_complaints_count = Complaint.objects.filter(status='pending').count()
    if total_count == 0:
        total_count = pending_count + approved_count + rejected_count
    page_size = max(len(suggestions), 1)

    context.update({
        'suggestions': suggestions,
        'status_filter': status_filter,
        'search_query': search_query,
        'total_suggestions_count': total_count,
        'pending_suggestions_count': pending_count,
        'approved_suggestions_count': approved_count,
        'rejected_suggestions_count': rejected_count,
        'pending_complaints_count': pending_complaints_count,
        'current_page': current_page,
        'has_next_page': bool(next_url),
        'has_previous_page': bool(previous_url),
        'next_page': current_page + 1 if next_url else current_page,
        'previous_page': current_page - 1 if previous_url and current_page > 1 else 1,
        'total_pages': (total_count + page_size - 1) // page_size,
    })
    return render(request, 'admin_panel/category_moderation.html', context)


@user_passes_test(is_admin, login_url='/admin/login/')
def taxonomy_management(request):
    context = get_admin_context(request)
    context['pending_complaints_count'] = Complaint.objects.filter(status='pending').count()

    if not request.session.get('api_access'):
        messages.warning(
            request,
            (
                'Для управления навыками войдите через форму приложения (JWT).'
                if request.LANGUAGE_CODE != 'en'
                else 'To manage skills, sign in through the application form (JWT).'
            ),
        )
        context.update(
            {
                'skills': [],
                'skills_count': 0,
                'vacancy_categories': [],
                'vacancy_categories_count': 0,
                'recent_admin_categories': [],
                'skill_suggestions': [],
                'pending_skill_suggestions_count': 0,
                'approved_skill_suggestions_count': 0,
                'rejected_skill_suggestions_count': 0,
                'total_skill_suggestions_count': 0,
            }
        )
        return render(request, 'admin_panel/taxonomy_management.html', context)

    if request.method == 'POST':
        action = (request.POST.get('form_action') or '').strip()

        if action == 'create_skill':
            skill_name = (request.POST.get('skill_name') or '').strip()
            if not skill_name:
                messages.error(
                    request,
                    'Укажите название навыка.' if request.LANGUAGE_CODE != 'en' else 'Enter a skill name.',
                )
            else:
                try:
                    resp = api_post(request, 'admin/skills/', json={'name': skill_name})
                    payload = _api_safe_json(resp)
                    if resp.status_code >= 400:
                        messages.error(
                            request,
                            _api_first_error(
                                payload,
                                (
                                    'Не удалось добавить навык.'
                                    if request.LANGUAGE_CODE != 'en'
                                    else 'Failed to add skill.'
                                ),
                            ),
                        )
                    else:
                        created_name = str((payload or {}).get('name') or skill_name).strip()
                        action_type = get_or_create_action_type(
                            'skill_created',
                            'Создан навык' if request.LANGUAGE_CODE != 'en' else 'Skill created',
                        )
                        AdminLog.objects.create(
                            admin=request.user,
                            action=action_type,
                            details=(
                                f'Добавлен навык: "{created_name}"'
                                if request.LANGUAGE_CODE != 'en'
                                else f'Skill added: "{created_name}"'
                            ),
                        )
                        messages.success(
                            request,
                            (
                                f'Навык "{created_name}" добавлен.'
                                if request.LANGUAGE_CODE != 'en'
                                else f'Skill "{created_name}" added.'
                            ),
                        )
                except Exception:
                    messages.error(
                        request,
                        (
                            'Ошибка сети при добавлении навыка.'
                            if request.LANGUAGE_CODE != 'en'
                            else 'Network error while adding skill.'
                        ),
                    )
        elif action == 'review_skill_suggestion':
            suggestion_id_raw = (request.POST.get('suggestion_id') or '').strip()
            suggestion_status = (request.POST.get('suggestion_status') or '').strip().lower()
            admin_notes = (request.POST.get('admin_notes') or '').strip()

            try:
                suggestion_id = int(suggestion_id_raw)
            except (TypeError, ValueError):
                suggestion_id = None

            if not suggestion_id:
                messages.error(
                    request,
                    (
                        'Некорректный идентификатор заявки навыка.'
                        if request.LANGUAGE_CODE != 'en'
                        else 'Invalid skill suggestion id.'
                    ),
                )
            elif suggestion_status not in {'approved', 'rejected'}:
                messages.error(
                    request,
                    (
                        'Выберите решение по заявке: одобрить или отклонить.'
                        if request.LANGUAGE_CODE != 'en'
                        else 'Choose approval or rejection for the suggestion.'
                    ),
                )
            else:
                payload = {'status': suggestion_status, 'admin_notes': admin_notes}
                try:
                    resp = api_patch(request, f'admin/skill-suggestions/{suggestion_id}/', json=payload)
                    response_payload = _api_safe_json(resp)
                    if resp.status_code >= 400:
                        messages.error(
                            request,
                            _api_first_error(
                                response_payload,
                                (
                                    'Не удалось обработать заявку навыка.'
                                    if request.LANGUAGE_CODE != 'en'
                                    else 'Failed to review skill suggestion.'
                                ),
                            ),
                        )
                    else:
                        suggestion_name = str((response_payload or {}).get('name') or '').strip() or f'ID {suggestion_id}'
                        if suggestion_status == 'approved':
                            action_type = get_or_create_action_type(
                                'skill_suggestion_approved',
                                'Заявка навыка одобрена' if request.LANGUAGE_CODE != 'en' else 'Skill suggestion approved',
                            )
                            details = (
                                f'Одобрена заявка на навык: "{suggestion_name}"'
                                if request.LANGUAGE_CODE != 'en'
                                else f'Approved skill suggestion: "{suggestion_name}"'
                            )
                            messages.success(
                                request,
                                (
                                    f'Заявка "{suggestion_name}" одобрена.'
                                    if request.LANGUAGE_CODE != 'en'
                                    else f'Suggestion "{suggestion_name}" approved.'
                                ),
                            )
                        else:
                            action_type = get_or_create_action_type(
                                'skill_suggestion_rejected',
                                'Заявка навыка отклонена' if request.LANGUAGE_CODE != 'en' else 'Skill suggestion rejected',
                            )
                            details = (
                                f'Отклонена заявка на навык: "{suggestion_name}"'
                                if request.LANGUAGE_CODE != 'en'
                                else f'Rejected skill suggestion: "{suggestion_name}"'
                            )
                            messages.success(
                                request,
                                (
                                    f'Заявка "{suggestion_name}" отклонена.'
                                    if request.LANGUAGE_CODE != 'en'
                                    else f'Suggestion "{suggestion_name}" rejected.'
                                ),
                            )

                        AdminLog.objects.create(
                            admin=request.user,
                            action=action_type,
                            details=details,
                        )
                except Exception:
                    messages.error(
                        request,
                        (
                            'Ошибка сети при проверке заявки навыка.'
                            if request.LANGUAGE_CODE != 'en'
                            else 'Network error while reviewing skill suggestion.'
                        ),
                    )
        else:
            messages.error(
                request,
                (
                    'Неизвестное действие формы.'
                    if request.LANGUAGE_CODE != 'en'
                    else 'Unknown form action.'
                ),
            )

        return redirect('admin_taxonomy_management')

    skills: list[dict] = []
    vacancy_categories: list[dict] = []
    recent_admin_categories: list[dict] = []
    skill_suggestions: list[dict] = []

    try:
        skill_rows, skill_error = _collect_api_rows(request, 'skills/', params={})
        if skill_error is not None:
            messages.error(
                request,
                _api_first_error(
                    skill_error,
                    (
                        'Не удалось загрузить список навыков.'
                        if request.LANGUAGE_CODE != 'en'
                        else 'Failed to load skills list.'
                    ),
                ),
            )
        else:
            skills = sorted(skill_rows or [], key=lambda item: str(item.get('name') or '').lower())
    except Exception:
        messages.error(
            request,
            (
                'Ошибка сети при загрузке навыков.'
                if request.LANGUAGE_CODE != 'en'
                else 'Network error while loading skills.'
            ),
        )

    try:
        skill_suggestions_rows, skill_suggestions_error = _collect_api_rows(
            request,
            'admin/skill-suggestions/',
            params={'status': 'pending'},
        )
        if skill_suggestions_error is not None:
            messages.error(
                request,
                _api_first_error(
                    skill_suggestions_error,
                    (
                        'Не удалось загрузить заявки навыков.'
                        if request.LANGUAGE_CODE != 'en'
                        else 'Failed to load skill suggestions.'
                    ),
                ),
            )
        else:
            skill_suggestions = skill_suggestions_rows or []
    except Exception:
        messages.error(
            request,
            (
                'Ошибка сети при загрузке заявок навыков.'
                if request.LANGUAGE_CODE != 'en'
                else 'Network error while loading skill suggestions.'
            ),
        )

    try:
        category_rows, category_error = _collect_api_rows(request, 'vacancy-categories/', params={})
        if category_error is not None:
            messages.error(
                request,
                _api_first_error(
                    category_error,
                    (
                        'Не удалось загрузить список категорий вакансий.'
                        if request.LANGUAGE_CODE != 'en'
                        else 'Failed to load vacancy categories list.'
                    ),
                ),
            )
        else:
            vacancy_categories = sorted(category_rows or [], key=lambda item: str(item.get('name') or '').lower())
    except Exception:
        messages.error(
            request,
            (
                'Ошибка сети при загрузке категорий вакансий.'
                if request.LANGUAGE_CODE != 'en'
                else 'Network error while loading vacancy categories.'
            ),
        )

    try:
        suggestions_resp = api_get(
            request,
            'admin/vacancy-category-suggestions/',
            params={'status': 'approved', 'page': 1},
        )
        suggestions_payload = _api_safe_json(suggestions_resp) or {}
        if suggestions_resp.status_code < 400:
            recent_admin_categories = _api_results(suggestions_payload)[:8]
    except Exception:
        recent_admin_categories = []

    pending_skill_suggestions_count = _fetch_skill_suggestions_count(request, 'pending')
    approved_skill_suggestions_count = _fetch_skill_suggestions_count(request, 'approved')
    rejected_skill_suggestions_count = _fetch_skill_suggestions_count(request, 'rejected')
    total_skill_suggestions_count = (
        pending_skill_suggestions_count
        + approved_skill_suggestions_count
        + rejected_skill_suggestions_count
    )

    context.update(
        {
            'skills': skills,
            'skills_count': len(skills),
            'vacancy_categories': vacancy_categories,
            'vacancy_categories_count': len(vacancy_categories),
            'recent_admin_categories': recent_admin_categories,
            'skill_suggestions': skill_suggestions,
            'pending_skill_suggestions_count': pending_skill_suggestions_count,
            'approved_skill_suggestions_count': approved_skill_suggestions_count,
            'rejected_skill_suggestions_count': rejected_skill_suggestions_count,
            'total_skill_suggestions_count': total_skill_suggestions_count,
        }
    )
    return render(request, 'admin_panel/taxonomy_management.html', context)

from django.core.mail import send_mail
from django.conf import settings

@user_passes_test(is_admin, login_url='/admin/login/')
def company_moderation(request):
    """Страница модерации компаний"""
    context = get_admin_context(request)

    companies = Company.objects.all().order_by('-created_at')
    pending_companies = companies.filter(status=Company.STATUS_PENDING)

    if request.method == 'POST':
        company_id = request.POST.get('company_id')
        status = request.POST.get('status')

        if company_id and status:
            try:
                company = Company.objects.get(id=company_id)
            except Company.DoesNotExist:
                messages.error(request, 'Компания для модерации не найдена.')
            else:
                old_status = company.status
                company.status = status
                company.save(update_fields=['status'])

                if old_status != company.status:
                    email_sent = send_company_status_email(company, old_status)

                    if company.status == Company.STATUS_APPROVED:
                        action_type = get_or_create_action_type('company_approved', 'Компания одобрена')
                        details = f'Компания {company.name} одобрена'
                    elif company.status == Company.STATUS_REJECTED:
                        action_type = get_or_create_action_type('company_rejected', 'Компания отклонена')
                        details = f'Компания {company.name} отклонена'
                    else:
                        action_type = get_or_create_action_type('company_updated', 'Компания обновлена')
                        details = f'Статус компании {company.name} изменен на {company.get_status_display()}'

                    details += ' (email отправлен)' if email_sent else ' (ошибка отправки email)'

                    AdminLog.objects.create(
                        admin=request.user,
                        action=action_type,
                        target_company=company,
                        details=details,
                    )

                    if email_sent:
                        messages.success(request, f'Письмо о смене статуса отправлено: {company.user.email}')
                    else:
                        messages.warning(request, 'Статус обновлен, но письмо отправить не удалось.')

    context.update({
        'pending_companies': pending_companies,
        'all_companies': companies,
        'status_choices': Company.STATUS_CHOICES,
    })
    return render(request, 'admin_panel/company_moderation.html', context)
@user_passes_test(is_admin, login_url='/admin/login/')
def company_detail(request, company_id):
    context = get_admin_context(request)

    company = get_object_or_404(Company, id=company_id)

    if request.method == 'POST':
        form = CompanyModerationForm(request.POST, instance=company)
        if form.is_valid():
            old_status = company.status
            company = form.save()

            if old_status != company.status:
                email_sent = send_company_status_email(company, old_status)

                if company.status == Company.STATUS_APPROVED:
                    action_type = get_or_create_action_type('company_approved', 'Компания одобрена')
                    details = f'Компания {company.name} одобрена через детальную страницу'
                elif company.status == Company.STATUS_REJECTED:
                    action_type = get_or_create_action_type('company_rejected', 'Компания отклонена')
                    details = f'Компания {company.name} отклонена через детальную страницу'
                else:
                    action_type = get_or_create_action_type('company_updated', 'Компания обновлена')
                    details = f'Статус компании {company.name} изменен на {company.get_status_display()}'

                details += ' (email отправлен)' if email_sent else ' (ошибка отправки email)'

                AdminLog.objects.create(
                    admin=request.user,
                    action=action_type,
                    target_company=company,
                    details=details,
                )

                if email_sent:
                    messages.success(request, f'Письмо о смене статуса отправлено: {company.user.email}')
                else:
                    messages.warning(request, 'Статус обновлен, но письмо отправить не удалось.')

            return redirect('admin_company_moderation')
    else:
        form = CompanyModerationForm(instance=company)

    company_document_url, company_document_name = _resolve_company_document(company)

    context.update({
        'company': company,
        'form': form,
        'company_document_url': company_document_url,
        'company_document_name': company_document_name,
    })
    return render(request, 'admin_panel/company_detail.html', context)
def send_company_status_email(company, old_status):
    recipient = (getattr(getattr(company, 'user', None), 'email', '') or '').strip()
    if not recipient:
        return False

    status_map = {
        Company.STATUS_APPROVED: (
            'Компания подтверждена',
            'Ваша компания прошла модерацию и теперь может полноценно работать на платформе.'
        ),
        Company.STATUS_REJECTED: (
            'Компания отклонена',
            'Компания не прошла модерацию. Проверьте документы и свяжитесь с поддержкой при необходимости.'
        ),
        Company.STATUS_PENDING: (
            'Компания отправлена на проверку',
            'Статус компании изменен на "На проверке". Ожидайте решения администратора.'
        ),
    }

    status_title, status_description = status_map.get(
        company.status,
        ('Статус компании обновлен', f'Новый статус компании: {company.get_status_display()}')
    )

    old_status_display = dict(Company.STATUS_CHOICES).get(old_status, old_status)
    new_status_display = company.get_status_display()
    updated_at = company.created_at.strftime('%d.%m.%Y') if getattr(company, 'created_at', None) else '-'

    subject = f'WorkMPT: обновлен статус компании "{company.name}"'
    plain_message = (
        f'Здравствуйте!\n\n'
        f'Статус компании "{company.name}" изменен.\n'
        f'Старый статус: {old_status_display}\n'
        f'Новый статус: {new_status_display}\n\n'
        f'{status_description}\n\n'
        f'Дата обновления: {updated_at}\n\n'
        f'Это автоматическое сообщение WorkMPT.'
    )

    html_message = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset=\"utf-8\"></head>
    <body style=\"font-family:Arial,sans-serif;background:#f8fafc;color:#1f2937;\">
      <div style=\"max-width:640px;margin:24px auto;background:#ffffff;border:1px solid #e5e7eb;border-radius:12px;padding:24px;\">
        <h2 style=\"margin:0 0 12px 0;color:#1d4ed8;\">{status_title}</h2>
        <p style=\"margin:0 0 14px 0;\">Здравствуйте! Статус компании <b>{company.name}</b> обновлен.</p>
        <p style=\"margin:0 0 8px 0;\"><b>Старый статус:</b> {old_status_display}</p>
        <p style=\"margin:0 0 8px 0;\"><b>Новый статус:</b> {new_status_display}</p>
        <p style=\"margin:0 0 14px 0;\"><b>Дата обновления:</b> {updated_at}</p>
        <p style=\"margin:0;\">{status_description}</p>
      </div>
    </body>
    </html>
    """

    from_email = (
        getattr(settings, 'DEFAULT_FROM_EMAIL', '')
        or getattr(settings, 'SERVER_EMAIL', '')
        or getattr(settings, 'EMAIL_HOST_USER', '')
        or None
    )

    try:
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=from_email,
            recipient_list=[recipient],
            html_message=html_message,
            fail_silently=False,
        )
        return True
    except Exception as exc:
        print(f"[EMAIL][company_status] send failed for company_id={company.id}: {exc}")
        return False
    
@user_passes_test(is_admin, login_url='/admin/login/')
def vacancy_management(request):
    context = get_admin_context(request)
    
    vacancies = Vacancy.objects.all().select_related('company', 'status').order_by('-created_date')
    
    status_filter = request.GET.get('status', '')
    if status_filter:
        vacancies = vacancies.filter(status__id=status_filter)
    
    search_query = request.GET.get('search', '')
    if search_query:
        vacancies = vacancies.filter(position__icontains=search_query)
    
    context.update({
        'vacancies': vacancies,
        'status_choices': StatusVacancies.objects.all(),
        'current_status': status_filter,
        'search_query': search_query,
    })
    return render(request, 'admin_panel/vacancy_management.html', context)

# views.py
# views.py
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, JsonResponse
from django.contrib.auth.decorators import user_passes_test
from django.core.files import File
import os


@user_passes_test(is_admin, login_url='/admin/login/')
def backup_dashboard(request):
    """Главная панель управления бэкапами"""
    context = get_admin_context(request)
    backup_manager = DjangoBackupManager()
    
    # Получаем информацию о системе
    system_info = backup_manager.get_system_info()
    
    # Получаем список бэкапов из БД
    backups = Backup.objects.all().order_by('-created_at')
    
    # Тестируем подключение к БД
    connection_test = backup_manager.test_connection()
    
    context.update({
        'system_info': system_info,
        'backups': backups,
        'connection_test': connection_test,
        'upload_form': BackupUploadForm(),
        'backup_types': Backup.BACKUP_TYPES,
    })
    
    return render(request, 'admin_panel/backup_management.html', context)

# Глобальная переменная для хранения прогресса (в продакшене используйте Redis или БД)
current_progress = {"message": "", "percent": 0}
@user_passes_test(is_admin, login_url='/admin/login/')
def create_backup_api(request):
    """API для создания бэкапа с отслеживанием прогресса"""
    if request.method == 'POST':
        backup_type = request.POST.get('type', 'database')
        custom_name = request.POST.get('custom_name', '')
        
        backup_manager = DjangoBackupManager()
        
        # Сбрасываем прогресс
        global current_progress
        current_progress = {"message": "Начинаем создание бэкапа...", "percent": 0}
        
        def progress_callback(message, percent=None):
            global current_progress
            current_progress = {
                "message": message,
                "percent": percent if percent is not None else current_progress["percent"]
            }
            print(f"Backup Progress: {percent}% - {message}")  # Логируем в консоль
        
        backup_manager.set_progress_callback(progress_callback)
        
        try:
            result = backup_manager.create_backup(
                backup_type=backup_type, 
                custom_name=custom_name,
                user=request.user
            )
            
            if result['success']:
                # Сохраняем в базу данных
                backup = Backup(
                    name=result['filename'],
                    backup_type=result.get('backup_type', backup_type),
                    file_size=result['file_size'],
                    created_by=request.user
                )
                
                try:
                    with open(result['filepath'], 'rb') as f:
                        backup.backup_file.save(result['filename'], File(f), save=False)
                    _save_backup_record_with_synced_sequence(backup_manager, backup)
                finally:
                    if os.path.exists(result['filepath']):
                        os.remove(result['filepath'])
                
                # Логируем - ИСПРАВЛЕНО
                action_type = get_or_create_action_type('backup_created', 'Бэкап создан')
                AdminLog.objects.create(
                    admin=request.user,
                    action=action_type,
                    details=f"Создан бэкап: {result['filename']}"
                )
                
                return JsonResponse({
                    'success': True, 
                    'message': 'Бэкап успешно создан',
                    'filename': result['filename']
                })
            else:
                return JsonResponse({
                    'success': False, 
                    'error': result.get('error', 'Ошибка при создании бэкапа')
                }, status=400)
                
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            print(f"Backup creation error: {error_details}")
            
            return JsonResponse({
                'success': False, 
                'error': f'Ошибка при создании бэкапа: {str(e)}'
            }, status=400)
    
    return JsonResponse({'error': 'Invalid method'}, status=405)

@user_passes_test(is_admin, login_url='/admin/login/')
def upload_backup_api(request):
    """API для загрузки бэкапа"""
    if request.method == 'POST':
        form = BackupUploadForm(request.POST, request.FILES)
        
        if form.is_valid():
            backup_file = request.FILES['backup_file']
            backup_manager = DjangoBackupManager()
            
            try:
                backup_info = backup_manager.inspect_backup(backup_file)
                if not backup_info.get('valid'):
                    return JsonResponse({
                        'success': False,
                        'error': backup_info.get('error') or 'Файл бэкапа поврежден или имеет неверный формат'
                    }, status=400)
                
                backup_type = backup_info.get('backup_type') or 'database'
                
                # Сохраняем бэкап
                backup = Backup(
                    name=backup_file.name,
                    backup_type=backup_type,
                    file_size=backup_file.size,
                    created_by=request.user
                )
                backup.backup_file.save(backup_file.name, backup_file, save=False)
                _save_backup_record_with_synced_sequence(backup_manager, backup)
                
                # Логируем - ИСПРАВЛЕНО
                action_type = get_or_create_action_type('backup_uploaded', 'Бэкап загружен')
                AdminLog.objects.create(
                    admin=request.user,
                    action=action_type,
                    details=f"Загружен бэкап: {backup_file.name}"
                )
                
                return JsonResponse({
                    'success': True,
                    'message': 'Бэкап успешно загружен'
                })
                
            except Exception as e:
                return JsonResponse({
                    'success': False,
                    'error': f'Ошибка загрузки бэкапа: {str(e)}'
                }, status=400)
        else:
            return JsonResponse({
                'success': False,
                'error': 'Ошибка валидации формы'
            }, status=400)
    
    return JsonResponse({'error': 'Invalid method'}, status=405)

@user_passes_test(is_admin, login_url='/admin/login/')
def media_stats_api(request):
    """API для получения статистики медиа файлов"""
    backup_manager = DjangoBackupManager()
    stats = backup_manager.get_media_stats()
    
    # Форматируем размеры для отображения
    stats['total_size_formatted'] = backup_manager._format_file_size(stats['total_size'])
    stats['largest_files_formatted'] = [
        (path, backup_manager._format_file_size(size)) 
        for path, size in stats['largest_files']
    ]
    
    return JsonResponse(stats)

@user_passes_test(is_admin, login_url='/admin/login/')
def restore_backup_api(request, backup_id):
    """API для восстановления из бэкапа"""
    if request.method == 'POST':
        backup = get_object_or_404(Backup, id=backup_id)
        backup_manager = DjangoBackupManager()
        backup_name = backup.name
        request_user_id = request.user.pk
        
        try:
            # Дополнительное подтверждение для критических операций
            if not request.POST.get('confirmed'):
                return JsonResponse({
                    'requires_confirmation': True,
                    'message': 'ВНИМАНИЕ: Восстановление базы данных перезапишет все текущие данные. Это действие нельзя отменить. Подтвердите восстановление.'
                })
            
            # Проверяем существование файла
            if not backup.backup_file:
                return JsonResponse({
                    'success': False,
                    'error': 'Файл бэкапа не найден'
                }, status=404)
            
            # Открываем файл для чтения
            with backup.backup_file.open('rb') as f:
                # Восстанавливаем бэкап
                result = backup_manager.restore_backup(f, request.user)
            
            if result['success']:
                if User.objects.filter(pk=request_user_id).exists():
                    action_type = get_or_create_action_type('backup_restored', 'Бэкап восстановлен')
                    AdminLog.objects.create(
                        admin_id=request_user_id,
                        action=action_type,
                        details=f"Восстановлен бэкап: {backup_name}"
                    )
                
                return JsonResponse({
                    'success': True, 
                    'message': result['message'] or 'База данных успешно восстановлена'
                })
            else:
                return JsonResponse({
                    'success': False,
                    'error': result.get('error', 'Ошибка при восстановлении')
                }, status=400)
                
        except Exception as e:
            error_message = str(e)
            print(f"Restore error: {error_message}")
            return JsonResponse({
                'success': False, 
                'error': f'Ошибка восстановления: {error_message}'
            }, status=500)
    
    return JsonResponse({'error': 'Invalid method'}, status=405)

@user_passes_test(is_admin, login_url='/admin/login/')
def download_backup_api(request, backup_id):
    """Скачивание бэкапа"""
    backup = get_object_or_404(Backup, id=backup_id)
    
    try:
        if not backup.backup_file:
            return JsonResponse({
                'success': False,
                'error': 'Файл бэкапа не найден'
            }, status=404)
        
        response = FileResponse(
            backup.backup_file.open('rb'),
            content_type='application/octet-stream',
            as_attachment=True,
            filename=backup.name,
        )
        
        # Логируем - ИСПРАВЛЕНО
        action_type = get_or_create_action_type('backup_downloaded', 'Бэкап скачан')
        AdminLog.objects.create(
            admin=request.user,
            action=action_type,
            details=f"Скачан бэкап: {backup.name}"
        )
        
        return response
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Ошибка скачивания: {str(e)}'
        }, status=400)

@user_passes_test(is_admin, login_url='/admin/login/')
def delete_backup_api(request, backup_id):
    """Удаление бэкапа"""
    if request.method == 'POST':
        backup = get_object_or_404(Backup, id=backup_id)
        
        try:
            backup_name = backup.name
            backup.delete()
            
            # Логируем - ИСПРАВЛЕНО
            action_type = get_or_create_action_type('backup_deleted', 'Бэкап удален')
            AdminLog.objects.create(
                admin=request.user,
                action=action_type,
                details=f"Удален бэкап: {backup_name}"
            )
            
            return JsonResponse({
                'success': True, 
                'message': 'Бэкап успешно удален'
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False, 
                'error': str(e)
            }, status=400)
    
    return JsonResponse({'error': 'Invalid method'}, status=405)

@user_passes_test(is_admin, login_url='/admin/login/')
def get_backups_list_api(request):
    """API для получения списка бэкапов"""
    try:
        backups = Backup.objects.all().order_by('-created_at')
        backups_data = []
        
        for backup in backups:
            creator = getattr(backup, 'created_by', None)
            created_by = '-'
            if creator is not None:
                created_by = creator.username or creator.email or '-'
            backups_data.append({
                'id': backup.id,
                'name': backup.name,
                'backup_type': backup.backup_type,
                'backup_type_display': backup.get_backup_type_display(),
                'file_size': backup.file_size,
                'file_size_display': backup.get_file_size_display(),
                'created_at': backup.created_at.strftime('%d.%m.%Y %H:%M'),
                'created_by': created_by,
                'download_url': reverse('admin_download_backup', args=[backup.id]),
            })
        
        return JsonResponse({
            'success': True,
            'backups': backups_data
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

@user_passes_test(is_admin, login_url='/admin/login/')
def system_status_api(request):
    """API для получения статуса системы"""
    backup_manager = DjangoBackupManager()
    system_info = backup_manager.get_system_info()
    
    return JsonResponse(system_info)

from django.db import models



@user_passes_test(is_admin, login_url='/admin/login/')
def admin_logs(request):
    """Просмотр логов администраторов"""
    context = get_admin_context(request)
    
    logs = AdminLog.objects.all().select_related('action', 'admin', 'target_company').order_by('-created_at')
    
    action_filter = request.GET.get('action', '')
    if action_filter:
        logs = logs.filter(action_id=action_filter)
    
    search_query = request.GET.get('search', '')
    if search_query:
        logs = logs.filter(
            models.Q(details__icontains=search_query) |
            models.Q(admin__username__icontains=search_query) |
            models.Q(admin__email__icontains=search_query) |
            models.Q(target_company__name__icontains=search_query)
        )
    
    # Получаем все типы действий для фильтра
    action_types = ActionType.objects.all()
    
    context.update({
        'logs': logs,
        'action_types': action_types,
        'current_action': action_filter,
        'search_query': search_query,
    })
    return render(request, 'admin_panel/admin_logs.html', context)

@user_passes_test(is_admin, login_url='/admin/login/')
def clear_logs(request):
    """Очистка логов"""
    if request.method == 'POST':
        days_old = int(request.POST.get('days_old', 30))
        cutoff_date = timezone.now() - timedelta(days=days_old)
        
        deleted_count = AdminLog.objects.filter(created_at__lt=cutoff_date).delete()[0]
        
        # Создаем запись в логах о очистке
        action_type = get_or_create_action_type('logs_cleared', 'Логи очищены')
        AdminLog.objects.create(
            admin=request.user,
            action=action_type,
            details=f'Очищено {deleted_count} логов старше {days_old} дней'
        )
        
        messages.success(request, f'Успешно очищено {deleted_count} логов старше {days_old} дней')
    
    return redirect('admin_logs')

@user_passes_test(is_admin, login_url='/admin/login/')
def api_company_stats(request):
    """API для получения статистики компаний"""
    stats = {
        'pending': Company.objects.filter(status=Company.STATUS_PENDING).count(),
        'approved': Company.objects.filter(status=Company.STATUS_APPROVED).count(),
        'rejected': Company.objects.filter(status=Company.STATUS_REJECTED).count(),
        'total': Company.objects.count(),
    }
    return JsonResponse(stats)

@user_passes_test(is_admin, login_url='/admin/login/')
def api_recent_activity(request):
    """API для получения последней активности"""
    logs = AdminLog.objects.all().order_by('-created_at')[:5]
    
    activity = []
    for log in logs:
        activity.append({
            'admin': log.admin.username,
            'action': log.action.name if log.action else 'Unknown',
            'details': log.details,
            'timestamp': log.created_at.strftime('%Y-%m-%d %H:%M'),
            'company': log.target_company.name if log.target_company else None,
        })
    
    return JsonResponse({'activity': activity})

@user_passes_test(is_superuser_only, login_url='/admin/login/')
def admin_management(request):
    """Управление администраторами сайта (только для superuser)"""
    context = get_admin_context(request)
    site_admins = User.objects.filter(user_type='adminsite').order_by('-date_joined')
    
    context.update({
        'site_admins': site_admins,
    })
    return render(request, 'admin_panel/admin_management.html', context)

@user_passes_test(is_superuser_only, login_url='/admin/login/')
def create_site_admin(request):
    """Создание нового администратора сайта"""
    context = get_admin_context(request)
    
    if request.method == 'POST':
        form = SiteAdminCreateForm(request.POST)
        if form.is_valid():
            try:
                admin = form.save()
                # Логируем - ИСПРАВЛЕНО
                action_type = get_or_create_action_type('admin_created', 'Администратор создан')
                AdminLog.objects.create(
                    admin=request.user,
                    action=action_type,
                    details=f'Создан администратор сайта: {admin.get_full_name()} ({admin.email})'
                )
                return redirect('admin_management')
            except Exception:
                messages.error(request, 'Не удалось создать администратора сайта.')
    else:
        form = SiteAdminCreateForm()
    
    context.update({
        'form': form,
    })
    return render(request, 'admin_panel/admin_form.html', context)

@user_passes_test(is_superuser_only, login_url='/admin/login/')
def edit_site_admin(request, admin_id):
    """Редактирование администратора сайта"""
    context = get_admin_context(request)
    admin_user = get_object_or_404(User, id=admin_id, user_type='adminsite')

    if request.method == 'POST':
        form = SiteAdminEditForm(request.POST, instance=admin_user)
        if form.is_valid():
            try:
                admin = form.save()
                # Логируем - ИСПРАВЛЕНО
                action_type = get_or_create_action_type('admin_updated', 'Администратор обновлен')
                AdminLog.objects.create(
                    admin=request.user,
                    action=action_type,
                    details=f'Обновлен администратор сайта: {admin.get_full_name()} ({admin.email})'
                )
                return redirect('admin_management')
            except Exception:
                messages.error(request, 'Не удалось обновить администратора сайта.')
    else:
        form = SiteAdminEditForm(instance=admin_user)
    
    context.update({
        'form': form,
        'admin': admin_user,
    })
    return render(request, 'admin_panel/admin_form.html', context)


def _delete_user_row_raw(user_id: int) -> int:
    """Fallback delete when ORM cascades break because legacy tables are missing."""
    with connection.cursor() as cursor:
        cursor.execute("DELETE FROM users WHERE id = %s", [user_id])
        return cursor.rowcount

@user_passes_test(is_superuser_only, login_url='/admin/login/')
def toggle_site_admin_status(request, admin_id):
    """Активация/деактивация администратора сайта"""
    admin_user = get_object_or_404(User, id=admin_id, user_type='adminsite')
    
    if admin_user == request.user:
        return redirect('admin_management')
    
    if admin_user.is_active:
        admin_user.is_active = False
        action_type = get_or_create_action_type('admin_deactivated', 'Администратор деактивирован')
        message = f'✅ Администратор сайта {admin_user.get_full_name()} деактивирован'
    else:
        admin_user.is_active = True
        action_type = get_or_create_action_type('admin_activated', 'Администратор активирован')
        message = f'✅ Администратор сайта {admin_user.get_full_name()} активирован'
    
    admin_user.save()
    
    AdminLog.objects.create(
        admin=request.user,
        action=action_type,
        details=f'Администратор сайта {admin_user.get_full_name()} {"деактивирован" if not admin_user.is_active else "активирован"}'
    )
    
    return redirect('admin_management')

@user_passes_test(is_superuser_only, login_url='/admin/login/')
def delete_site_admin(request, admin_id):
    """Удаление администратора сайта"""
    admin_user = get_object_or_404(User, id=admin_id, user_type='adminsite')
    
    if admin_user == request.user:
        return redirect('admin_management')
    
    admin_user_id = admin_user.id
    admin_name = admin_user.get_full_name()
    admin_email = admin_user.email

    fallback_used = False
    deleted = False
    try:
        admin_user.delete()
        deleted = True
    except ProgrammingError as exc:
        # Some deployments miss the legacy "employees" table, and ORM cascade fails.
        if 'employees' in str(exc).lower():
            deleted = _delete_user_row_raw(admin_user_id) > 0
            fallback_used = deleted
        else:
            raise

    if not deleted:
        messages.error(request, 'Не удалось удалить администратора сайта.')
        return redirect('admin_management')
    
    # Логируем - ИСПРАВЛЕНО
    action_type = get_or_create_action_type('admin_deleted', 'Администратор удален')
    details = f'Удален администратор сайта: {admin_name} ({admin_email})'
    if fallback_used:
        details += ' [raw-delete fallback]'
    AdminLog.objects.create(
        admin=request.user,
        action=action_type,
        details=details
    )
    messages.success(request, 'Администратор сайта удалён.')
    
    return redirect('admin_management')


from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Count, Q
from django.utils import timezone
from datetime import timedelta
from django.http import HttpResponse
import json
from home.models import User, Company, Vacancy, Applicant, Response
import io
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from openpyxl import Workbook
from django.views.decorators.http import require_http_methods

from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from functools import wraps

def admin_required(view_func):
    @wraps(view_func)
    @login_required
    def _wrapped_view(request, *args, **kwargs):

        if request.user.is_superuser:
            return view_func(request, *args, **kwargs)
        
        if request.user.user_type not in ['adminsite']:
            return HttpResponseForbidden("У вас нет прав для доступа к админ-панели")
        
        return view_func(request, *args, **kwargs)
    return _wrapped_view

from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
from django.contrib.auth.decorators import login_required, user_passes_test
import json
from datetime import datetime
from .statistics_service import StatisticsService

# Добавьте эти импорты для экспорта
import csv
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import io

@login_required
@user_passes_test(is_admin)
def admin_statistics(request):
    """Страница статистики с поддержкой периода"""
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    # Валидация дат
    if start_date and end_date:
        try:
            start_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
            end_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
            if start_obj > end_obj:
                start_date, end_date = None, None
        except ValueError:
            start_date, end_date = None, None
    
    main_stats = StatisticsService.get_main_statistics(start_date, end_date)
    user_distribution = StatisticsService.get_user_type_distribution(start_date, end_date)
    vacancy_stats = StatisticsService.get_vacancy_statistics(start_date, end_date)
    company_stats = StatisticsService.get_company_statistics(start_date, end_date)
    response_stats = StatisticsService.get_response_statistics(start_date, end_date)
    complaint_stats = StatisticsService.get_complaint_statistics(start_date, end_date)
    
    # Подготавливаем данные для круговых диаграмм
    user_chart_data = []
    cumulative_percent = 0
    for i, (label, count, percentage, color) in enumerate(zip(
        user_distribution['labels'],
        user_distribution['data'], 
        user_distribution['percentages'],
        user_distribution['colors']
    )):
        dash_length = percentage
        gap_length = 100 - percentage
        dash_offset = -cumulative_percent
        
        user_chart_data.append({
            'label': label,
            'count': count,
            'percentage': percentage,
            'color': color,
            'dash_array': f"{dash_length} {gap_length}",
            'dash_offset': dash_offset
        })
        cumulative_percent += percentage
    
    company_chart_data = []
    cumulative_percent = 0
    for i, (label, count, percentage, color) in enumerate(zip(
        company_stats['status_distribution']['labels'],
        company_stats['status_distribution']['data'],
        company_stats['status_distribution']['percentages'],
        company_stats['status_distribution']['colors']
    )):
        dash_length = percentage
        gap_length = 100 - percentage
        dash_offset = -cumulative_percent
        
        company_chart_data.append({
            'label': label,
            'count': count,
            'percentage': percentage,
            'color': color,
            'dash_array': f"{dash_length} {gap_length}",
            'dash_offset': dash_offset
        })
        cumulative_percent += percentage
    
    response_chart_data = []
    cumulative_percent = 0
    response_total = response_stats['status_distribution']['total']
    for i, (label, count, color) in enumerate(zip(
        response_stats['status_distribution']['labels'],
        response_stats['status_distribution']['data'],
        response_stats['status_distribution']['colors']
    )):
        percentage = round((count / response_total * 100), 1) if response_total > 0 else 0
        dash_length = percentage
        gap_length = 100 - percentage
        dash_offset = -cumulative_percent
        
        response_chart_data.append({
            'label': label,
            'count': count,
            'percentage': percentage,
            'color': color,
            'dash_array': f"{dash_length} {gap_length}",
            'dash_offset': dash_offset
        })
        cumulative_percent += percentage
    
    # Подготавливаем данные для столбчатых диаграмм
    vacancy_data = []
    if vacancy_stats['category']['data']:
        max_count = max(vacancy_stats['category']['data']) if vacancy_stats['category']['data'] else 1
        for label, count, color in zip(
            vacancy_stats['category']['labels'],
            vacancy_stats['category']['data'],
            vacancy_stats['category']['colors']
        ):
            if max_count > 0:
                height = (count / max_count) * 80
            else:
                height = 5
            vacancy_data.append((label, count, color, max(height, 5)))
    
    complaint_data = []
    if complaint_stats['type_distribution']['data']:
        max_count = max(complaint_stats['type_distribution']['data']) if complaint_stats['type_distribution']['data'] else 1
        for label, count, color in zip(
            complaint_stats['type_distribution']['labels'],
            complaint_stats['type_distribution']['data'],
            complaint_stats['type_distribution']['colors']
        ):
            if max_count > 0:
                height = (count / max_count) * 80
            else:
                height = 5
            complaint_data.append((label, count, color, max(height, 5)))
    
    response_daily_data = []
    if response_stats['daily_activity']:
        daily_counts = [day['count'] for day in response_stats['daily_activity']]
        max_count = max(daily_counts) if daily_counts else 1
        for day in response_stats['daily_activity']:
            if max_count > 0:
                height = (day['count'] / max_count) * 80
            else:
                height = 5
            response_daily_data.append((day['date'], day['count'], max(height, 5)))
    
    context = {
        **get_admin_context(request),
        'main_stats': main_stats,
        'user_total': user_distribution['total'],
        'company_total': company_stats['status_distribution']['total'],
        'response_total': response_stats['status_distribution']['total'],
        
        'user_chart_data': user_chart_data,
        'company_chart_data': company_chart_data,
        'response_chart_data': response_chart_data,
        
        'vacancy_data': vacancy_data,
        'complaint_data': complaint_data,
        'response_daily_data': response_daily_data,
        
        'start_date': start_date,
        'end_date': end_date,
    }
    
    return render(request, 'admin_panel/statistics.html', context)

from reportlab.platypus import Image
from reportlab.lib.units import inch

@login_required
@user_passes_test(is_admin)
def export_statistics_pdf(request):
    """Экспорт статистики в PDF с поддержкой периода"""
    try:
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')

        is_en = request.LANGUAGE_CODE == 'en'

        def tr(ru_text: str, en_text: str) -> str:
            return en_text if is_en else ru_text

        if start_date and end_date:
            try:
                start_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
                end_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
                if start_obj > end_obj:
                    start_date, end_date = None, None
            except ValueError:
                start_date, end_date = None, None

        main_stats = StatisticsService.get_main_statistics(start_date, end_date)
        user_distribution = StatisticsService.get_user_type_distribution(start_date, end_date)
        vacancy_stats = StatisticsService.get_vacancy_statistics(start_date, end_date)
        company_stats = StatisticsService.get_company_statistics(start_date, end_date)
        response_stats = StatisticsService.get_response_statistics(start_date, end_date)
        complaint_stats = StatisticsService.get_complaint_statistics(start_date, end_date)

        from reportlab.lib.utils import ImageReader
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont

        def _register_ttf_font(font_name: str, font_path: str) -> bool:
            if not font_path or not os.path.exists(font_path):
                return False
            try:
                if font_name not in pdfmetrics.getRegisteredFontNames():
                    pdfmetrics.registerFont(TTFont(font_name, font_path))
                return True
            except Exception:
                return False

        def _pdf_font_names() -> tuple[str, str]:
            windir = os.environ.get('WINDIR', r'C:\Windows')
            candidates = [
                (os.path.join(windir, 'Fonts', 'arial.ttf'), os.path.join(windir, 'Fonts', 'arialbd.ttf')),
                ('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'),
                ('/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf', '/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf'),
            ]

            for index, (regular_path, bold_path) in enumerate(candidates, start=1):
                regular_name = f'SiteReportSans{index}'
                bold_name = f'SiteReportSansBold{index}'
                regular_ok = _register_ttf_font(regular_name, regular_path)
                bold_ok = _register_ttf_font(bold_name, bold_path)

                if regular_ok and bold_ok:
                    return regular_name, bold_name
                if regular_ok:
                    return regular_name, regular_name

            return 'Helvetica', 'Helvetica-Bold'

        def _format_iso_date(date_value: str | None) -> str:
            if not date_value:
                return ''
            try:
                return datetime.strptime(date_value, '%Y-%m-%d').strftime('%d.%m.%Y')
            except Exception:
                return str(date_value)

        def _to_rows(labels, values) -> list[tuple[str, int]]:
            rows: list[tuple[str, int]] = []
            labels = labels or []
            values = values or []
            for idx, label in enumerate(labels):
                value = values[idx] if idx < len(values) else 0
                rows.append((str(label or tr('Без названия', 'Untitled')), int(value or 0)))
            return rows

        font_regular, font_bold = _pdf_font_names()
        buffer = io.BytesIO()
        pdf = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4
        margin = 28

        brand_name = 'WorkMPT'
        generated_at = datetime.now().strftime('%d.%m.%Y %H:%M')
        if start_date and end_date:
            period_text = tr(
                f"Период: {_format_iso_date(start_date)} — {_format_iso_date(end_date)}",
                f"Period: {_format_iso_date(start_date)} — {_format_iso_date(end_date)}",
            )
        else:
            period_text = tr('Период: за всё время', 'Period: all time')

        def _truncate(value: str, limit: int = 34) -> str:
            text = str(value or '')
            if len(text) <= limit:
                return text
            return text[: limit - 3] + '...'

        def _draw_card(x: float, y: float, w: float, h: float, title: str, value: int) -> None:
            pdf.setFillColor(colors.white)
            pdf.setStrokeColor(colors.HexColor('#dbe4f0'))
            pdf.roundRect(x, y, w, h, 10, fill=1, stroke=1)
            pdf.setFillColor(colors.HexColor('#64748b'))
            pdf.setFont(font_regular, 8)
            pdf.drawString(x + 10, y + h - 16, title)
            pdf.setFillColor(colors.HexColor('#0f172a'))
            pdf.setFont(font_bold, 17)
            pdf.drawString(x + 10, y + 14, str(int(value or 0)))

        def _draw_chart_box(x: float, y: float, w: float, h: float, title: str, chart_buffer) -> None:
            pdf.setFillColor(colors.white)
            pdf.setStrokeColor(colors.HexColor('#dbe4f0'))
            pdf.roundRect(x, y, w, h, 12, fill=1, stroke=1)
            pdf.setFillColor(colors.HexColor('#0f172a'))
            pdf.setFont(font_bold, 11)
            pdf.drawString(x + 12, y + h - 18, title)

            if not chart_buffer:
                pdf.setFillColor(colors.HexColor('#64748b'))
                pdf.setFont(font_regular, 9)
                pdf.drawString(x + 12, y + h - 40, tr('Нет данных', 'No data'))
                return

            try:
                image = ImageReader(chart_buffer)
                img_w, img_h = image.getSize()
                max_w = w - 18
                max_h = h - 34
                scale = min(max_w / float(img_w), max_h / float(img_h))
                draw_w = img_w * scale
                draw_h = img_h * scale
                draw_x = x + (w - draw_w) / 2
                draw_y = y + 8
                pdf.drawImage(image, draw_x, draw_y, draw_w, draw_h, preserveAspectRatio=True, mask='auto')
            except Exception:
                pdf.setFillColor(colors.HexColor('#64748b'))
                pdf.setFont(font_regular, 9)
                pdf.drawString(x + 12, y + h - 40, tr('Не удалось отрисовать график', 'Failed to render chart'))

        def _draw_table(x: float, y: float, w: float, h: float, title: str, rows: list[tuple[str, int]]) -> None:
            pdf.setFillColor(colors.white)
            pdf.setStrokeColor(colors.HexColor('#dbe4f0'))
            pdf.roundRect(x, y, w, h, 12, fill=1, stroke=1)

            pdf.setFillColor(colors.HexColor('#0f172a'))
            pdf.setFont(font_bold, 11)
            pdf.drawString(x + 12, y + h - 18, title)

            row_y = y + h - 34
            row_height = 20
            for idx, (name, count) in enumerate(rows[:7]):
                row_bg = colors.HexColor('#f8fafc') if idx % 2 == 0 else colors.white
                pdf.setFillColor(row_bg)
                pdf.rect(x + 10, row_y - row_height + 5, w - 20, row_height - 2, fill=1, stroke=0)
                pdf.setFillColor(colors.HexColor('#1e293b'))
                pdf.setFont(font_regular, 9)
                pdf.drawString(x + 14, row_y - 8, _truncate(name, 30))
                pdf.setFont(font_bold, 9)
                pdf.drawRightString(x + w - 14, row_y - 8, str(int(count or 0)))
                row_y -= row_height

            if not rows:
                pdf.setFillColor(colors.HexColor('#64748b'))
                pdf.setFont(font_regular, 9)
                pdf.drawString(x + 14, y + h - 58, tr('Нет данных', 'No data'))

        pdf.setTitle(tr('Отчёт по статистике сайта WorkMPT', 'WorkMPT Site Analytics Report'))
        pdf.setFillColor(colors.HexColor('#f5f8fc'))
        pdf.rect(0, 0, width, height, fill=1, stroke=0)

        header_h = 90
        header_x = margin
        header_y = height - margin - header_h
        header_w = width - margin * 2

        pdf.setFillColor(colors.HexColor('#0f172a'))
        pdf.roundRect(header_x, header_y, header_w, header_h, 14, fill=1, stroke=0)
        pdf.setFillColor(colors.HexColor('#f59e0b'))
        pdf.circle(header_x + 28, header_y + header_h / 2, 18, fill=1, stroke=0)
        pdf.setFillColor(colors.white)
        pdf.setFont(font_bold, 11)
        pdf.drawCentredString(header_x + 28, header_y + header_h / 2 - 4, 'WM')

        pdf.setFillColor(colors.white)
        pdf.setFont(font_bold, 22)
        pdf.drawString(header_x + 56, header_y + 55, brand_name)
        pdf.setFont(font_regular, 10)
        pdf.setFillColor(colors.HexColor('#cbd5e1'))
        pdf.drawString(header_x + 56, header_y + 38, tr('Аналитический отчёт по платформе', 'Platform analytics report'))
        pdf.drawString(header_x + 56, header_y + 24, f"{tr('Дата формирования', 'Generated at')}: {generated_at} · {period_text}")

        metrics = [
            (tr('Пользователи', 'Users'), main_stats.get('total_users', 0)),
            (tr('Компании', 'Companies'), main_stats.get('total_companies', 0)),
            (tr('Вакансии', 'Vacancies'), main_stats.get('total_vacancies', 0)),
            (tr('Отклики', 'Responses'), main_stats.get('total_responses', 0)),
            (tr('Жалобы', 'Complaints'), main_stats.get('total_complaints', 0)),
            (tr('Активные компании', 'Active companies'), main_stats.get('active_companies', 0)),
            (tr('На проверке', 'Pending moderation'), main_stats.get('pending_companies', 0)),
            (tr('Новые за неделю', 'New this week'), main_stats.get('new_users_week', 0)),
        ]

        card_w = (header_w - 30) / 4
        card_h = 60
        row_1_y = header_y - 14 - card_h
        row_2_y = row_1_y - 10 - card_h
        for idx, (title, value) in enumerate(metrics):
            row = 0 if idx < 4 else 1
            col = idx if idx < 4 else idx - 4
            card_x = margin + col * (card_w + 10)
            card_y = row_1_y if row == 0 else row_2_y
            _draw_card(card_x, card_y, card_w, card_h, title, value)

        response_chart_buffer = create_response_activity_chart(response_stats)
        user_chart_buffer = create_user_distribution_chart(user_distribution)

        chart_h = 220
        chart_y = row_2_y - 14 - chart_h
        left_chart_w = 340
        right_chart_w = header_w - left_chart_w - 12
        left_chart_x = margin
        right_chart_x = left_chart_x + left_chart_w + 12

        _draw_chart_box(
            left_chart_x,
            chart_y,
            left_chart_w,
            chart_h,
            tr('Активность откликов', 'Response activity'),
            response_chart_buffer,
        )
        _draw_chart_box(
            right_chart_x,
            chart_y,
            right_chart_w,
            chart_h,
            tr('Распределение пользователей', 'User distribution'),
            user_chart_buffer,
        )

        table_h = 185
        table_y = chart_y - 14 - table_h
        table_gap = 12
        table_w = (header_w - table_gap) / 2

        vacancy_rows = _to_rows(vacancy_stats.get('category', {}).get('labels'), vacancy_stats.get('category', {}).get('data'))
        complaint_rows = _to_rows(
            complaint_stats.get('type_distribution', {}).get('labels'),
            complaint_stats.get('type_distribution', {}).get('data'),
        )

        _draw_table(margin, table_y, table_w, table_h, tr('Категории вакансий', 'Vacancy categories'), vacancy_rows)
        _draw_table(
            margin + table_w + table_gap,
            table_y,
            table_w,
            table_h,
            tr('Типы жалоб', 'Complaint types'),
            complaint_rows,
        )

        pdf.setFillColor(colors.HexColor('#94a3b8'))
        pdf.setFont(font_regular, 8)
        pdf.drawString(margin, 18, tr('WorkMPT · Отчет по статистике сайта', 'WorkMPT · Site analytics report'))

        pdf.save()
        buffer.seek(0)
        filename = f"workmpt_site_stats_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

    except Exception as e:
        is_en = getattr(request, 'LANGUAGE_CODE', 'ru') == 'en'
        prefix = 'Failed to generate PDF' if is_en else 'Ошибка при создании PDF'
        return HttpResponse(f"{prefix}: {str(e)}")

@login_required
@user_passes_test(is_admin)
def export_statistics_excel(request):
    """Экспорт статистики в Excel (CSV) с поддержкой периода"""
    try:
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')
        
        # Валидация дат
        if start_date and end_date:
            try:
                start_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
                end_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
                if start_obj > end_obj:
                    start_date, end_date = None, None
            except ValueError:
                start_date, end_date = None, None
        
        # Собираем данные с учетом периода
        main_stats = StatisticsService.get_main_statistics(start_date, end_date)
        user_distribution = StatisticsService.get_user_type_distribution(start_date, end_date)
        vacancy_stats = StatisticsService.get_vacancy_statistics(start_date, end_date)
        company_stats = StatisticsService.get_company_statistics(start_date, end_date)
        response_stats = StatisticsService.get_response_statistics(start_date, end_date)
        complaint_stats = StatisticsService.get_complaint_statistics(start_date, end_date)
        
        response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
        
        filename = "statistics"
        if start_date and end_date:
            filename += f"_{start_date}_to_{end_date}"
        filename += f"_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        # Создаем CSV writer с поддержкой русского
        writer = csv.writer(response)
        
        # Заголовок
        writer.writerow(['Статистика платформы трудоустройства'])
        period_info = f"Дата экспорта: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
        if start_date and end_date:
            period_info += f" | Период: {start_date} - {end_date}"
        writer.writerow([period_info])
        writer.writerow([])
        
        # Основная статистика
        writer.writerow(['ОСНОВНАЯ СТАТИСТИКА'])
        writer.writerow(['Показатель', 'Значение'])
        writer.writerow(['Всего пользователей', main_stats['total_users']])
        writer.writerow(['Всего компаний', main_stats['total_companies']])
        writer.writerow(['Всего вакансий', main_stats['total_vacancies']])
        writer.writerow(['Всего откликов', main_stats['total_responses']])
        writer.writerow(['Активных компаний', main_stats['active_companies']])
        
        if not start_date or not end_date:
            writer.writerow(['Новых пользователей (неделя)', main_stats['new_users_week']])
            writer.writerow(['Новых компаний (неделя)', main_stats['new_companies_week']])
            writer.writerow(['Новых вакансий (неделя)', main_stats['new_vacancies_week']])
        
        writer.writerow([])
        
        # Распределение пользователей
        writer.writerow(['РАСПРЕДЕЛЕНИЕ ПОЛЬЗОВАТЕЛЕЙ ПО ТИПАМ'])
        writer.writerow(['Тип пользователя', 'Количество', 'Процент'])
        for i, label in enumerate(user_distribution['labels']):
            writer.writerow([
                label,
                user_distribution['data'][i],
                f"{user_distribution['percentages'][i]}%"
            ])
        writer.writerow([])
        
        # Статусы компаний
        writer.writerow(['СТАТУСЫ КОМПАНИЙ'])
        writer.writerow(['Статус', 'Количество', 'Процент'])
        for i, label in enumerate(company_stats['status_distribution']['labels']):
            writer.writerow([
                label,
                company_stats['status_distribution']['data'][i],
                f"{company_stats['status_distribution']['percentages'][i]}%"
            ])
        writer.writerow([])
        
        # Категории вакансий
        writer.writerow(['КАТЕГОРИИ ВАКАНСИЙ'])
        writer.writerow(['Категория', 'Количество'])
        for i, label in enumerate(vacancy_stats['category']['labels']):
            writer.writerow([label, vacancy_stats['category']['data'][i]])
        writer.writerow([])
        
        # Активность откликов
        writer.writerow(['АКТИВНОСТЬ ОТКЛИКОВ'])
        writer.writerow(['Дата', 'Количество откликов'])
        for day in response_stats['daily_activity']:
            writer.writerow([day['date'], day['count']])
        writer.writerow([])
        
        # Типы жалоб
        writer.writerow(['ТИПЫ ЖАЛОБ'])
        writer.writerow(['Тип жалобы', 'Количество'])
        for i, label in enumerate(complaint_stats['type_distribution']['labels']):
            writer.writerow([label, complaint_stats['type_distribution']['data'][i]])
        
        return response
        
    except Exception as e:
        return HttpResponse(f"Ошибка при создании Excel: {str(e)}")

# Функции для создания графиков (остаются без изменений)
def create_user_distribution_chart(user_distribution):
    """Создает круговую диаграмму распределения пользователей"""
    try:
        plt.figure(figsize=(8, 6))
        plt.pie(
            user_distribution['data'],
            labels=user_distribution['labels'],
            colors=user_distribution['colors'],
            autopct='%1.1f%%',
            startangle=90
        )
        plt.title('Распределение пользователей по типам', fontsize=14, fontweight='bold')
        plt.axis('equal')
        
        buffer = io.BytesIO()
        plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight')
        buffer.seek(0)
        plt.close()
        return buffer
    except Exception as e:
        print(f"Ошибка при создании графика пользователей: {e}")
        return None

def create_company_status_chart(company_stats):
    """Создает круговую диаграмму статусов компаний"""
    try:
        plt.figure(figsize=(8, 6))
        plt.pie(
            company_stats['status_distribution']['data'],
            labels=company_stats['status_distribution']['labels'],
            colors=company_stats['status_distribution']['colors'],
            autopct='%1.1f%%',
            startangle=90
        )
        plt.title('Статусы компаний', fontsize=14, fontweight='bold')
        plt.axis('equal')
        
        buffer = io.BytesIO()
        plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight')
        buffer.seek(0)
        plt.close()
        return buffer
    except Exception as e:
        print(f"Ошибка при создании графика компаний: {e}")
        return None

def create_vacancy_categories_chart(vacancy_stats):
    """Создает столбчатую диаграмму категорий вакансий"""
    try:
        plt.figure(figsize=(10, 6))
        bars = plt.bar(
            vacancy_stats['category']['labels'],
            vacancy_stats['category']['data'],
            color=vacancy_stats['category']['colors']
        )
        plt.title('Категории вакансий', fontsize=14, fontweight='bold')
        plt.xlabel('Категории')
        plt.ylabel('Количество вакансий')
        plt.xticks(rotation=45, ha='right')
        
        for bar in bars:
            height = bar.get_height()
            plt.text(bar.get_x() + bar.get_width()/2., height,
                    f'{int(height)}',
                    ha='center', va='bottom')
        
        plt.tight_layout()
        
        buffer = io.BytesIO()
        plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight')
        buffer.seek(0)
        plt.close()
        return buffer
    except Exception as e:
        print(f"Ошибка при создании графика вакансий: {e}")
        return None

def create_response_activity_chart(response_stats):
    """Создает линейный график активности откликов"""
    try:
        dates = [day['date'] for day in response_stats['daily_activity']]
        counts = [day['count'] for day in response_stats['daily_activity']]
        
        plt.figure(figsize=(10, 6))
        plt.plot(dates, counts, marker='o', linewidth=2, markersize=6)
        plt.title('Активность откликов', fontsize=14, fontweight='bold')
        plt.xlabel('Дата')
        plt.ylabel('Количество откликов')
        plt.grid(True, alpha=0.3)
        
        for i, count in enumerate(counts):
            plt.annotate(str(count), (dates[i], count), 
                        textcoords="offset points", 
                        xytext=(0,10), 
                        ha='center')
        
        plt.tight_layout()
        
        buffer = io.BytesIO()
        plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight')
        buffer.seek(0)
        plt.close()
        return buffer
    except Exception as e:
        print(f"Ошибка при создании графика откликов: {e}")
        return None
    
from django.core.paginator import Paginator
@login_required
@admin_required
def admin_complaints(request):
    # Получаем параметры фильтрации
    status_filter = (request.GET.get('status') or 'all').strip().lower()
    type_filter = (request.GET.get('type') or 'all').strip().lower()
    if status_filter == 'resolved':
        status_filter = Complaint.STATUS_REVIEWED
    if status_filter not in {'all', Complaint.STATUS_PENDING, Complaint.STATUS_REVIEWED, Complaint.STATUS_REJECTED}:
        status_filter = 'all'
    
    # Базовый запрос
    complaints = Complaint.objects.select_related(
        'vacancy', 'vacancy__company', 'complainant'
    ).order_by('-created_at')
    
    # Применяем фильтры
    if status_filter != 'all':
        complaints = complaints.filter(status=status_filter)
    
    if type_filter != 'all':
        complaints = complaints.filter(complaint_type=type_filter)
    
    # Пагинация
    paginator = Paginator(complaints, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        **get_admin_context(request),
        'page_obj': page_obj,
        'status_filter': status_filter,
        'type_filter': type_filter,
        'total_complaints': complaints.count(),
        'pending_count': Complaint.objects.filter(status=Complaint.STATUS_PENDING).count(),
        'reviewed_count': Complaint.objects.filter(status=Complaint.STATUS_REVIEWED).count(),
        'rejected_count': Complaint.objects.filter(status=Complaint.STATUS_REJECTED).count(),
    }
    
    return render(request, 'admin_panel/complaints.html', context)

@admin_required
def complaint_detail(request, complaint_id):
    complaint = get_object_or_404(
        Complaint.objects.select_related(
            'vacancy', 
            'vacancy__company', 
            'complainant',
            'vacancy__work_conditions'
        ), 
        id=complaint_id
    )
    
    context = {
        **get_admin_context(request),
        'complaint': complaint,
    }
    
    return render(request, 'admin_panel/complaint_detail.html', context)

@admin_required
@user_passes_test(is_admin, login_url='/admin/login/')
def update_complaint_status(request, complaint_id):
    if request.method == 'POST':
        complaint = get_object_or_404(Complaint, id=complaint_id)
        new_status = (request.POST.get('status') or '').strip().lower()
        admin_notes = request.POST.get('admin_notes', '')

        if new_status == 'resolved':
            new_status = Complaint.STATUS_REVIEWED

        if new_status in dict(Complaint.STATUS_CHOICES):
            old_status = complaint.status
            complaint.status = new_status
            complaint.admin_notes = admin_notes
            complaint.save()
            old_status_display = dict(Complaint.STATUS_CHOICES).get(old_status, old_status)
            
            # Логируем - ИСПРАВЛЕНО
            action_type = get_or_create_action_type('complaint_status_updated', 'Статус жалобы обновлен')
            AdminLog.objects.create(
                admin=request.user,
                action=action_type,
                details=f'Изменен статус жалобы #{complaint.id} с "{old_status_display}" на "{complaint.get_status_display()}"'
            )
            
            messages.success(request, f'Статус жалобы обновлен на "{complaint.get_status_display()}"')
        else:
            messages.error(request, 'Неверный статус')
    
    return redirect('complaint_detail', complaint_id=complaint_id)

def send_vacancy_archive_email(vacancy, archive_reason=""):
    """
    Отправляет email уведомление компании при архивации вакансии
    """
    company_email = vacancy.company.user.email
    company_name = vacancy.company.name
    vacancy_title = vacancy.position
    
    try:
        subject = f'Вакансия "{vacancy_title}" перемещена в архив - WorkMPT'
        
        html_message = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{
                    font-family: 'Inter', 'Arial', sans-serif;
                    line-height: 1.6;
                    color: #1e293b;
                    max-width: 600px;
                    margin: 0 auto;
                    padding: 0;
                    background: linear-gradient(135deg, #2563eb 0%, #1e293b 100%);
                }}
                .container {{
                    background: white;
                    margin: 20px;
                    border-radius: 20px;
                    overflow: hidden;
                    box-shadow: 0 15px 35px rgba(0, 0, 0, 0.2);
                }}
                .header {{
                    background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);
                    color: white;
                    padding: 40px 30px;
                    text-align: center;
                }}
                .header h1 {{
                    margin: 0;
                    font-size: 28px;
                    font-weight: 700;
                }}
                .header p {{
                    margin: 10px 0 0 0;
                    opacity: 0.9;
                    font-size: 16px;
                }}
                .content {{
                    padding: 40px 30px;
                }}
                .warning-card {{
                    background: rgba(245, 158, 11, 0.05);
                    border: 2px solid rgba(245, 158, 11, 0.3);
                    border-radius: 15px;
                    padding: 25px;
                    margin: 25px 0;
                    text-align: center;
                }}
                .warning-icon {{
                    font-size: 48px;
                    margin-bottom: 15px;
                }}
                .warning-title {{
                    font-size: 20px;
                    font-weight: 700;
                    color: #92400e;
                    margin-bottom: 10px;
                }}
                .warning-description {{
                    color: #92400e;
                    font-size: 16px;
                    line-height: 1.5;
                }}
                .vacancy-info {{
                    background: #f8fafc;
                    border-radius: 12px;
                    padding: 20px;
                    margin: 25px 0;
                }}
                .info-item {{
                    display: flex;
                    justify-content: space-between;
                    padding: 10px 0;
                    border-bottom: 1px solid #e2e8f0;
                }}
                .info-item:last-child {{
                    border-bottom: none;
                }}
                .info-label {{
                    color: #64748b;
                    font-weight: 500;
                }}
                .info-value {{
                    color: #1e293b;
                    font-weight: 600;
                }}
                .reason-section {{
                    background: rgba(239, 68, 68, 0.05);
                    border: 1px solid rgba(239, 68, 68, 0.2);
                    border-radius: 12px;
                    padding: 20px;
                    margin: 20px 0;
                }}
                .reason-title {{
                    color: #dc2626;
                    font-weight: 600;
                    margin-bottom: 10px;
                }}
                .action-buttons {{
                    text-align: center;
                    margin: 30px 0;
                }}
                .action-button {{
                    display: inline-block;
                    background: linear-gradient(45deg, #2563eb, #1e40af);
                    color: white;
                    padding: 14px 32px;
                    text-decoration: none;
                    border-radius: 25px;
                    font-weight: 600;
                    font-size: 16px;
                    margin: 10px;
                    transition: all 0.3s ease;
                }}
                .action-button:hover {{
                    background: linear-gradient(45deg, #1e40af, #2563eb);
                    transform: translateY(-2px);
                    box-shadow: 0 5px 15px rgba(37, 99, 235, 0.3);
                }}
                .secondary-button {{
                    background: linear-gradient(45deg, #64748b, #475569);
                }}
                .secondary-button:hover {{
                    background: linear-gradient(45deg, #475569, #64748b);
                }}
                .footer {{
                    background: #f1f5f9;
                    padding: 30px;
                    text-align: center;
                    border-top: 1px solid #e2e8f0;
                }}
                .footer p {{
                    margin: 5px 0;
                    color: #64748b;
                    font-size: 14px;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>📋 WorkMPT</h1>
                    <p>Уведомление об архивации вакансии</p>
                </div>
                
                <div class="content">
                    <h2 style="color: #1e293b; margin-top: 0;">Уважаемый представитель компании {company_name}!</h2>
                    
                    <div class="warning-card">
                        <div class="warning-icon">📁</div>
                        <div class="warning-title">Вакансия перемещена в архив</div>
                        <div class="warning-description">
                            Ваша вакансия "<strong>{vacancy_title}</strong>" была перемещена в архив модератором платформы.
                        </div>
                    </div>
                    
                    <div class="vacancy-info">
                        <div class="info-item">
                            <span class="info-label">Вакансия:</span>
                            <span class="info-value">{vacancy_title}</span>
                        </div>
                        <div class="info-item">
                            <span class="info-label">Компания:</span>
                            <span class="info-value">{company_name}</span>
                        </div>
                        <div class="info-item">
                            <span class="info-label">Дата архивации:</span>
                            <span class="info-value">{timezone.now().strftime('%d.%m.%Y в %H:%M')}</span>
                        </div>
                        <div class="info-item">
                            <span class="info-label">Статус:</span>
                            <span class="info-value" style="color: #f59e0b; font-weight: 700;">Архивирована</span>
                        </div>
                    </div>
                    
                    {f'''
                    <div class="reason-section">
                        <div class="reason-title">📝 Причина архивации:</div>
                        <p style="color: #1e293b; margin: 0; line-height: 1.5;">{archive_reason}</p>
                    </div>
                    ''' if archive_reason else ''}
                    
                    <div class="action-buttons">
                        <p style="color: #64748b; margin-bottom: 20px;">
                            Вы можете создать новую вакансию или связаться с поддержкой для уточнения деталей.
                        </p>
                        <a href="http://127.0.0.1:8000/create_vacancy/" class="action-button">
                            📝 Создать новую вакансию
                        </a>
                        <a href="http://127.0.0.1:8000/contact/" class="action-button secondary-button">
                            📞 Связаться с поддержкой
                        </a>
                    </div>
                    
                    <p style="color: #64748b; font-size: 14px; text-align: center;">
                        <strong>Важно:</strong> Архивные вакансии не отображаются в поиске и не получают откликов от соискателей.
                    </p>
                </div>
                
                <div class="footer">
                    <p><strong>С уважением, команда WorkMPT</strong></p>
                    <p>Мы заботимся о качестве вакансий на нашей платформе</p>
                    <div style="margin-top: 15px; padding-top: 15px; border-top: 1px solid #e2e8f0;">
                        <p>Email: hr-labogency@mail.ru</p>
                    </div>
                    <p style="font-size: 12px; margin-top: 20px; color: #94a3b8;">
                        Это автоматическое сообщение, пожалуйста, не отвечайте на него.
                    </p>
                </div>
            </div>
        </body>
        </html>
        """
        
        # Текстовая версия
        plain_message = f"""
        Уважаемый представитель компании "{company_name}"!

        Ваша вакансия "{vacancy_title}" была перемещена в архив модератором платформы WorkMPT.

        Информация о вакансии:
        - Вакансия: {vacancy_title}
        - Компания: {company_name}
        - Дата архивации: {timezone.now().strftime('%d.%m.%Y в %H:%M')}
        - Статус: Архивирована

        {f'Причина архивации: {archive_reason}' if archive_reason else ''}

        Важно: Архивные вакансии не отображаются в поиске и не получают откликов от соискателей.

        Вы можете:
        - Создать новую вакансию: http://127.0.0.1:8000/create_vacancy/
        - Связаться с поддержкой: http://127.0.0.1:8000/contact/

        С уважением,
        Команда WorkMPT

        ---
        Email: hr-labogency@mail.ru
        """

        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[company_email],
            html_message=html_message,
            fail_silently=False,
        )
        
        print(f"✅ [EMAIL] Уведомление об архивации отправлено для {vacancy_title}")
        return True
        
    except Exception as e:
        print(f"❌ [EMAIL] ОШИБКА при отправке уведомления об архивации: {str(e)}")
        return False
    
@admin_required
@user_passes_test(is_admin, login_url='/admin/login/')
def archive_vacancy(request, vacancy_id):
    """
    Архивация вакансии с отправкой email уведомления
    """
    vacancy = get_object_or_404(Vacancy, id=vacancy_id)
    
    try:
        archived_status = StatusVacancies.objects.get(status_vacancies_name='Архивирована')
    except StatusVacancies.DoesNotExist:
        messages.error(request, 'Статус "Архивирована" не найден в системе.')
        return redirect('admin_complaints')
    
    if request.method == 'POST':
        archive_reason = request.POST.get('archive_reason', '')
        
        # Сохраняем старый статус для лога
        old_status = vacancy.status.status_vacancies_name
        
        # Обновляем статус вакансии
        vacancy.status = archived_status
        vacancy.archived_at = timezone.now()
        vacancy.archive_reason = archive_reason
        vacancy.save()
        
        # Отправляем email уведомление
        email_sent = send_vacancy_archive_email(vacancy, archive_reason)
        
        # Создаем лог действия - ИСПРАВЛЕНО
        action_type = get_or_create_action_type('vacancy_archived', 'Вакансия архивирована')
        AdminLog.objects.create(
            admin=request.user,
            action=action_type,
            target_company=vacancy.company,
            details=f'Вакансия "{vacancy.position}" архивирована. Причина: {archive_reason or "Не указана"}. Email отправлен: {"Да" if email_sent else "Нет"}'
        )
        
        if email_sent:
            messages.success(request, f'Вакансия "{vacancy.position}" архивирована. Email уведомление отправлено компании.')
        else:
            messages.warning(request, f'Вакансия "{vacancy.position}" архивирована, но не удалось отправить email уведомление.')
        
        return redirect('admin_complaints')
    
    # GET запрос - показываем форму подтверждения
    return render(request, 'admin_panel/confirm_archive.html', {
        'vacancy': vacancy,
        'pending_complaints_count': Complaint.objects.filter(status='pending').count(),
        'pending_companies_count': Company.objects.filter(status='pending').count(),
    })

@admin_required
def unarchive_vacancy(request, vacancy_id):
    """
    Восстановление вакансии из архива
    """
    vacancy = get_object_or_404(Vacancy, id=vacancy_id)
    
    # Получаем активный статус (предположим, что он называется "Активная")
    try:
        active_status = StatusVacancies.objects.get(status_vacancies_name='Активная')
    except StatusVacancies.DoesNotExist:
        # Если нет "Активной", берем первый доступный статус кроме архивного
        active_status = StatusVacancies.objects.exclude(status_vacancies_name='Архивирована').first()
    
    if vacancy.status.status_vacancies_name == 'Архивирована':
        vacancy.status = active_status
        vacancy.archived_at = None
        vacancy.archive_reason = ''
        vacancy.save()
        
        # Создаем лог действия - ИСПРАВЛЕНО
        action_type = get_or_create_action_type('vacancy_unarchived', 'Вакансия восстановлена')
        AdminLog.objects.create(
            admin=request.user,
            action=action_type,
            target_company=vacancy.company,
            details=f'Вакансия "{vacancy.position}" восстановлена из архива'
        )
        
        messages.success(request, f'Вакансия "{vacancy.position}" восстановлена из архива.')
    
    return redirect('admin_complaints')

@login_required
def admin_profile(request):
    """Профиль администратора"""
    # Получаем статистику для отображения
    total_users = get_platform_users_queryset().count()
    total_companies = Company.objects.count()
    total_vacancies = Vacancy.objects.count()
    pending_complaints = Complaint.objects.filter(status='pending').count()
    recent_activity = AdminLog.objects.select_related('action', 'admin').order_by('-created_at')[:5]
    
    context = {
        **get_admin_context(request),
        'total_users': total_users,
        'total_companies': total_companies,
        'total_vacancies': total_vacancies,
        'pending_complaints': pending_complaints,
        'recent_activity': recent_activity,
    }
    
    return render(request, 'admin_panel/admin_profile.html', context)


@login_required
def admin_profile_edit(request):
    """Редактирование профиля администратора"""
    if request.user.is_superuser:
        messages.error(request, 'Редактирование профиля недоступно для суперпользователя.')
        return redirect('admin_profile')

    if request.method == 'POST':
        form = AdminProfileEditForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Профиль успешно обновлен!')
            return redirect('admin_profile')
        else:
            messages.error(request, 'Пожалуйста, исправьте ошибки в форме.')
    else:
        form = AdminProfileEditForm(instance=request.user)
    
    context = {
        **get_admin_context(request),
        'form': form,
    }
    
    return render(request, 'admin_panel/admin_profile_edit.html', context)
