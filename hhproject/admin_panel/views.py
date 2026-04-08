from pathlib import Path
import subprocess
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import user_passes_test
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.core.files import File
from datetime import timedelta
import os
from urllib.parse import urlencode

from django.urls import reverse
from matplotlib import pyplot as plt

from .procedure_manager import DjangoBackupManager
from .forms import AdminProfileEditForm, BackupUploadForm, SiteAdminCreateForm, SiteAdminEditForm
from home.models import *
from home.models import Company, Complaint, User, Vacancy, StatusVacancies
from home.models import Backup, AdminLog, ActionType
from home.api_client import api_get, api_patch
from .forms import CompanyModerationForm

def is_admin(user):
    """РџСЂРѕРІРµСЂРєР° С‡С‚Рѕ РїРѕР»СЊР·РѕРІР°С‚РµР»СЊ Р°РґРјРёРЅРёСЃС‚СЂР°С‚РѕСЂ (СЃСѓРїРµСЂРїРѕР»СЊР·РѕРІР°С‚РµР»СЊ РёР»Рё adminsite)"""
    return user.is_authenticated and (user.is_superuser or user.user_type == 'adminsite')

def is_superuser_only(user):
    """РџСЂРѕРІРµСЂРєР° С‡С‚Рѕ РїРѕР»СЊР·РѕРІР°С‚РµР»СЊ РўРћР›Р¬РљРћ СЃСѓРїРµСЂРїРѕР»СЊР·РѕРІР°С‚РµР»СЊ"""
    return user.is_authenticated and user.is_superuser

def get_admin_context(request):
    pending_count = Company.objects.filter(status=Company.STATUS_PENDING).count()
    site_admins_count = User.objects.filter(user_type='adminsite', is_active=True).count()
    pending_category_suggestions_count = _fetch_suggestions_count(request, 'pending')
    
    return {
        'pending_companies_count': pending_count,
        'pending_category_suggestions_count': pending_category_suggestions_count,
        'site_admins_count': site_admins_count,
        'is_superuser': request.user.is_superuser,
    }

def get_or_create_action_type(code, name=None):
    """
    Р’СЃРїРѕРјРѕРіР°С‚РµР»СЊРЅР°СЏ С„СѓРЅРєС†РёСЏ РґР»СЏ РїРѕР»СѓС‡РµРЅРёСЏ РёР»Рё СЃРѕР·РґР°РЅРёСЏ С‚РёРїР° РґРµР№СЃС‚РІРёСЏ
    РСЃРїРѕР»СЊР·СѓРµС‚СЃСЏ РїСЂРё СЃРѕР·РґР°РЅРёРё Р»РѕРіРѕРІ
    """
    if name is None:
        # Р“РµРЅРµСЂРёСЂСѓРµРј С‡РёС‚Р°РµРјРѕРµ РёРјСЏ РёР· РєРѕРґР°
        name = ' '.join(word.capitalize() for word in code.split('_'))
    
    try:
        action_type = ActionType.objects.get(code=code)
    except ActionType.DoesNotExist:
        action_type = ActionType.objects.create(
            code=code,
            name=name,
            description=f'РђРІС‚РѕРјР°С‚РёС‡РµСЃРєРё СЃРѕР·РґР°РЅРЅС‹Р№ С‚РёРї РґРµР№СЃС‚РІРёСЏ: {name}'
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

@user_passes_test(is_admin, login_url='/admin/login/')
def admin_dashboard(request):
    """Р“Р»Р°РІРЅР°СЏ СЃС‚СЂР°РЅРёС†Р° Р°РґРјРёРЅРєРё"""
    context = get_admin_context(request)
    
    pending_companies = Company.objects.filter(status=Company.STATUS_PENDING)
    total_companies = Company.objects.count()
    approved_companies = Company.objects.filter(status=Company.STATUS_APPROVED).count()
    rejected_companies = Company.objects.filter(status=Company.STATUS_REJECTED).count()
    pending_complaints_count = Complaint.objects.filter(status='pending').count()
    
    # РџРѕСЃР»РµРґРЅРёРµ Р»РѕРіРё
    recent_logs = AdminLog.objects.all().order_by('-created_at')[:10]
    
    # РЎС‚Р°С‚РёСЃС‚РёРєР° РїРѕР»СЊР·РѕРІР°С‚РµР»РµР№
    total_users = User.objects.count()
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
        suggestion_id = (request.POST.get('suggestion_id') or '').strip()
        new_status = (request.POST.get('status') or '').strip().lower()
        admin_notes = (request.POST.get('admin_notes') or '').strip()

        if not suggestion_id:
            messages.error(request, 'Не найдена заявка категории для обработки.')
        elif new_status not in {'approved', 'rejected'}:
            messages.error(request, 'Выбран некорректный статус.')
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
                        _api_first_error(data, 'Не удалось обновить статус категории.')
                    )
                else:
                    action_type = get_or_create_action_type(
                        'vacancy_category_approved' if new_status == 'approved' else 'vacancy_category_rejected',
                        'Категория вакансии одобрена' if new_status == 'approved' else 'Категория вакансии отклонена',
                    )
                    category_name = ''
                    if isinstance(data, dict):
                        category_name = str(data.get('name') or '').strip()
                    details = (
                        f'Категория "{category_name}" '
                        f'{"одобрена" if new_status == "approved" else "отклонена"} администратором'
                    )
                    if admin_notes:
                        details += f'. Комментарий: {admin_notes}'
                    AdminLog.objects.create(
                        admin=request.user,
                        action=action_type,
                        details=details,
                    )
                    messages.success(
                        request,
                        'Категория одобрена.' if new_status == 'approved' else 'Категория отклонена.'
                    )
            except Exception:
                messages.error(request, 'Ошибка сети при обновлении статуса категории.')

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

    context.update({
        'company': company,
        'form': form,
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

    subject = f'HR-Lab: обновлен статус компании "{company.name}"'
    plain_message = (
        f'Здравствуйте!\n\n'
        f'Статус компании "{company.name}" изменен.\n'
        f'Старый статус: {old_status_display}\n'
        f'Новый статус: {new_status_display}\n\n'
        f'{status_description}\n\n'
        f'Дата обновления: {updated_at}\n\n'
        f'Это автоматическое сообщение HR-Lab.'
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
    """Р“Р»Р°РІРЅР°СЏ РїР°РЅРµР»СЊ СѓРїСЂР°РІР»РµРЅРёСЏ Р±СЌРєР°РїР°РјРё"""
    context = get_admin_context(request)
    backup_manager = DjangoBackupManager()
    
    # РџРѕР»СѓС‡Р°РµРј РёРЅС„РѕСЂРјР°С†РёСЋ Рѕ СЃРёСЃС‚РµРјРµ
    system_info = backup_manager.get_system_info()
    
    # РџРѕР»СѓС‡Р°РµРј СЃРїРёСЃРѕРє Р±СЌРєР°РїРѕРІ РёР· Р‘Р”
    backups = Backup.objects.all().order_by('-created_at')
    
    # РўРµСЃС‚РёСЂСѓРµРј РїРѕРґРєР»СЋС‡РµРЅРёРµ Рє Р‘Р”
    connection_test = backup_manager.test_connection()
    
    context.update({
        'system_info': system_info,
        'backups': backups,
        'connection_test': connection_test,
        'upload_form': BackupUploadForm(),
        'backup_types': Backup.BACKUP_TYPES,
    })
    
    return render(request, 'admin_panel/backup_management.html', context)

# Р“Р»РѕР±Р°Р»СЊРЅР°СЏ РїРµСЂРµРјРµРЅРЅР°СЏ РґР»СЏ С…СЂР°РЅРµРЅРёСЏ РїСЂРѕРіСЂРµСЃСЃР° (РІ РїСЂРѕРґР°РєС€РµРЅРµ РёСЃРїРѕР»СЊР·СѓР№С‚Рµ Redis РёР»Рё Р‘Р”)
current_progress = {"message": "", "percent": 0}
@user_passes_test(is_admin, login_url='/admin/login/')
def create_backup_api(request):
    """API РґР»СЏ СЃРѕР·РґР°РЅРёСЏ Р±СЌРєР°РїР° СЃ РѕС‚СЃР»РµР¶РёРІР°РЅРёРµРј РїСЂРѕРіСЂРµСЃСЃР°"""
    if request.method == 'POST':
        backup_type = request.POST.get('type', 'database')
        custom_name = request.POST.get('custom_name', '')
        
        backup_manager = DjangoBackupManager()
        
        # РЎР±СЂР°СЃС‹РІР°РµРј РїСЂРѕРіСЂРµСЃСЃ
        global current_progress
        current_progress = {"message": "РќР°С‡РёРЅР°РµРј СЃРѕР·РґР°РЅРёРµ Р±СЌРєР°РїР°...", "percent": 0}
        
        def progress_callback(message, percent=None):
            global current_progress
            current_progress = {
                "message": message,
                "percent": percent if percent is not None else current_progress["percent"]
            }
            print(f"Backup Progress: {percent}% - {message}")  # Р›РѕРіРёСЂСѓРµРј РІ РєРѕРЅСЃРѕР»СЊ
        
        backup_manager.set_progress_callback(progress_callback)
        
        try:
            result = backup_manager.create_backup(
                backup_type=backup_type, 
                custom_name=custom_name,
                user=request.user
            )
            
            if result['success']:
                # РЎРѕС…СЂР°РЅСЏРµРј РІ Р±Р°Р·Сѓ РґР°РЅРЅС‹С…
                backup = Backup(
                    name=result['filename'],
                    backup_type=backup_type,
                    file_size=result['file_size'],
                    created_by=request.user
                )
                
                # РЎРѕС…СЂР°РЅСЏРµРј С„Р°Р№Р»
                with open(result['filepath'], 'rb') as f:
                    backup.backup_file.save(result['filename'], File(f))
                backup.save()
                
                # РЈРґР°Р»СЏРµРј РІСЂРµРјРµРЅРЅС‹Р№ С„Р°Р№Р»
                if os.path.exists(result['filepath']):
                    os.remove(result['filepath'])
                
                # Р›РѕРіРёСЂСѓРµРј - РРЎРџР РђР’Р›Р•РќРћ
                action_type = get_or_create_action_type('backup_created', 'Р‘СЌРєР°Рї СЃРѕР·РґР°РЅ')
                AdminLog.objects.create(
                    admin=request.user,
                    action=action_type,
                    details=f"РЎРѕР·РґР°РЅ Р±СЌРєР°Рї: {result['filename']}"
                )
                
                return JsonResponse({
                    'success': True, 
                    'message': 'Р‘СЌРєР°Рї СѓСЃРїРµС€РЅРѕ СЃРѕР·РґР°РЅ',
                    'filename': result['filename']
                })
            else:
                return JsonResponse({
                    'success': False, 
                    'error': result.get('error', 'РћС€РёР±РєР° РїСЂРё СЃРѕР·РґР°РЅРёРё Р±СЌРєР°РїР°')
                }, status=400)
                
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            print(f"Backup creation error: {error_details}")
            
            return JsonResponse({
                'success': False, 
                'error': f'РћС€РёР±РєР° РїСЂРё СЃРѕР·РґР°РЅРёРё Р±СЌРєР°РїР°: {str(e)}'
            }, status=400)
    
    return JsonResponse({'error': 'Invalid method'}, status=405)

@user_passes_test(is_admin, login_url='/admin/login/')
def upload_backup_api(request):
    """API РґР»СЏ Р·Р°РіСЂСѓР·РєРё Р±СЌРєР°РїР°"""
    if request.method == 'POST':
        form = BackupUploadForm(request.POST, request.FILES)
        
        if form.is_valid():
            backup_file = request.FILES['backup_file']
            backup_manager = DjangoBackupManager()
            
            try:
                # РџСЂРѕРІРµСЂСЏРµРј Р±СЌРєР°Рї
                if not backup_manager.validate_backup(backup_file):
                    return JsonResponse({
                        'success': False,
                        'error': 'Р¤Р°Р№Р» Р±СЌРєР°РїР° РїРѕРІСЂРµР¶РґРµРЅ РёР»Рё РёРјРµРµС‚ РЅРµРІРµСЂРЅС‹Р№ С„РѕСЂРјР°С‚'
                    }, status=400)
                
                # РћРїСЂРµРґРµР»СЏРµРј С‚РёРї Р±СЌРєР°РїР° РїРѕ СЂР°СЃС€РёСЂРµРЅРёСЋ
                backup_type = 'database'
                if backup_file.name.endswith('.zip'):
                    backup_type = 'full'
                
                # РЎРѕС…СЂР°РЅСЏРµРј Р±СЌРєР°Рї
                backup = Backup(
                    name=backup_file.name,
                    backup_type=backup_type,
                    file_size=backup_file.size,
                    created_by=request.user
                )
                backup.backup_file.save(backup_file.name, backup_file)
                backup.save()
                
                # Р›РѕРіРёСЂСѓРµРј - РРЎРџР РђР’Р›Р•РќРћ
                action_type = get_or_create_action_type('backup_uploaded', 'Р‘СЌРєР°Рї Р·Р°РіСЂСѓР¶РµРЅ')
                AdminLog.objects.create(
                    admin=request.user,
                    action=action_type,
                    details=f"Р—Р°РіСЂСѓР¶РµРЅ Р±СЌРєР°Рї: {backup_file.name}"
                )
                
                return JsonResponse({
                    'success': True,
                    'message': 'Р‘СЌРєР°Рї СѓСЃРїРµС€РЅРѕ Р·Р°РіСЂСѓР¶РµРЅ'
                })
                
            except Exception as e:
                return JsonResponse({
                    'success': False,
                    'error': f'РћС€РёР±РєР° Р·Р°РіСЂСѓР·РєРё Р±СЌРєР°РїР°: {str(e)}'
                }, status=400)
        else:
            return JsonResponse({
                'success': False,
                'error': 'РћС€РёР±РєР° РІР°Р»РёРґР°С†РёРё С„РѕСЂРјС‹'
            }, status=400)
    
    return JsonResponse({'error': 'Invalid method'}, status=405)

def get_media_stats(self):
    """РџРѕР»СѓС‡РµРЅРёРµ СЃС‚Р°С‚РёСЃС‚РёРєРё РјРµРґРёР° С„Р°Р№Р»РѕРІ"""
    media_dir = Path(settings.MEDIA_ROOT)
    stats = {
        'exists': False,
        'total_files': 0,
        'total_size': 0,
        'file_types': {},
        'largest_files': []
    }
    
    if media_dir.exists():
        stats['exists'] = True
        media_files = []
        
        try:
            # РЎРѕР±РёСЂР°РµРј РёРЅС„РѕСЂРјР°С†РёСЋ Рѕ С„Р°Р№Р»Р°С…
            for file_path in media_dir.rglob('*'):
                if file_path.is_file():
                    try:
                        file_size = file_path.stat().st_size
                        file_ext = file_path.suffix.lower()
                        
                        stats['total_files'] += 1
                        stats['total_size'] += file_size
                        
                        # РЎС‡РёС‚Р°РµРј С‚РёРїС‹ С„Р°Р№Р»РѕРІ
                        stats['file_types'][file_ext] = stats['file_types'].get(file_ext, 0) + 1
                        
                        # РЎРѕС…СЂР°РЅСЏРµРј РёРЅС„РѕСЂРјР°С†РёСЋ Рѕ С„Р°Р№Р»Рµ РґР»СЏ РєСЂСѓРїРЅРµР№С€РёС…
                        media_files.append((file_path, file_size))
                        
                    except Exception as e:
                        print(f"Error processing file {file_path}: {e}")
                        continue
            
            # РЎРѕСЂС‚РёСЂСѓРµРј РїРѕ СЂР°Р·РјРµСЂСѓ Рё Р±РµСЂРµРј 10 РєСЂСѓРїРЅРµР№С€РёС…
            media_files.sort(key=lambda x: x[1], reverse=True)
            stats['largest_files'] = [(str(path), size) for path, size in media_files[:10]]
            
        except Exception as e:
            print(f"Error scanning media directory: {e}")
    
    return stats

@user_passes_test(is_admin, login_url='/admin/login/')
def media_stats_api(request):
    """API РґР»СЏ РїРѕР»СѓС‡РµРЅРёСЏ СЃС‚Р°С‚РёСЃС‚РёРєРё РјРµРґРёР° С„Р°Р№Р»РѕРІ"""
    backup_manager = DjangoBackupManager()
    stats = backup_manager.get_media_stats()
    
    # Р¤РѕСЂРјР°С‚РёСЂСѓРµРј СЂР°Р·РјРµСЂС‹ РґР»СЏ РѕС‚РѕР±СЂР°Р¶РµРЅРёСЏ
    stats['total_size_formatted'] = backup_manager._format_file_size(stats['total_size'])
    stats['largest_files_formatted'] = [
        (path, backup_manager._format_file_size(size)) 
        for path, size in stats['largest_files']
    ]
    
    return JsonResponse(stats)

@user_passes_test(is_admin, login_url='/admin/login/')
def restore_backup_api(request, backup_id):
    """API РґР»СЏ РІРѕСЃСЃС‚Р°РЅРѕРІР»РµРЅРёСЏ РёР· Р±СЌРєР°РїР°"""
    if request.method == 'POST':
        backup = get_object_or_404(Backup, id=backup_id)
        backup_manager = DjangoBackupManager()
        
        try:
            # Р”РѕРїРѕР»РЅРёС‚РµР»СЊРЅРѕРµ РїРѕРґС‚РІРµСЂР¶РґРµРЅРёРµ РґР»СЏ РєСЂРёС‚РёС‡РµСЃРєРёС… РѕРїРµСЂР°С†РёР№
            if not request.POST.get('confirmed'):
                return JsonResponse({
                    'requires_confirmation': True,
                    'message': 'Р’РќРРњРђРќРР•: Р’РѕСЃСЃС‚Р°РЅРѕРІР»РµРЅРёРµ Р±Р°Р·С‹ РґР°РЅРЅС‹С… РїРµСЂРµР·Р°РїРёС€РµС‚ РІСЃРµ С‚РµРєСѓС‰РёРµ РґР°РЅРЅС‹Рµ. Р­С‚Рѕ РґРµР№СЃС‚РІРёРµ РЅРµР»СЊР·СЏ РѕС‚РјРµРЅРёС‚СЊ. РџРѕРґС‚РІРµСЂРґРёС‚Рµ РІРѕСЃСЃС‚Р°РЅРѕРІР»РµРЅРёРµ.'
                })
            
            # РџСЂРѕРІРµСЂСЏРµРј СЃСѓС‰РµСЃС‚РІРѕРІР°РЅРёРµ С„Р°Р№Р»Р°
            if not backup.backup_file:
                return JsonResponse({
                    'success': False,
                    'error': 'Р¤Р°Р№Р» Р±СЌРєР°РїР° РЅРµ РЅР°Р№РґРµРЅ'
                }, status=404)
            
            # РћС‚РєСЂС‹РІР°РµРј С„Р°Р№Р» РґР»СЏ С‡С‚РµРЅРёСЏ
            with backup.backup_file.open('rb') as f:
                # Р’РѕСЃСЃС‚Р°РЅР°РІР»РёРІР°РµРј Р±СЌРєР°Рї
                result = backup_manager.restore_backup(f, request.user)
            
            if result['success']:
                # Р›РѕРіРёСЂСѓРµРј - РРЎРџР РђР’Р›Р•РќРћ
                action_type = get_or_create_action_type('backup_restored', 'Р‘СЌРєР°Рї РІРѕСЃСЃС‚Р°РЅРѕРІР»РµРЅ')
                AdminLog.objects.create(
                    admin=request.user,
                    action=action_type,
                    details=f"Р’РѕСЃСЃС‚Р°РЅРѕРІР»РµРЅ Р±СЌРєР°Рї: {backup.name}"
                )
                
                return JsonResponse({
                    'success': True, 
                    'message': result['message'] or 'Р‘Р°Р·Р° РґР°РЅРЅС‹С… СѓСЃРїРµС€РЅРѕ РІРѕСЃСЃС‚Р°РЅРѕРІР»РµРЅР°'
                })
            else:
                return JsonResponse({
                    'success': False,
                    'error': result.get('error', 'РћС€РёР±РєР° РїСЂРё РІРѕСЃСЃС‚Р°РЅРѕРІР»РµРЅРёРё')
                }, status=400)
                
        except Exception as e:
            error_message = str(e)
            print(f"Restore error: {error_message}")
            return JsonResponse({
                'success': False, 
                'error': f'РћС€РёР±РєР° РІРѕСЃСЃС‚Р°РЅРѕРІР»РµРЅРёСЏ: {error_message}'
            }, status=500)
    
    return JsonResponse({'error': 'Invalid method'}, status=405)

@user_passes_test(is_admin, login_url='/admin/login/')
def download_backup_api(request, backup_id):
    """РЎРєР°С‡РёРІР°РЅРёРµ Р±СЌРєР°РїР°"""
    backup = get_object_or_404(Backup, id=backup_id)
    
    try:
        if not backup.backup_file:
            return JsonResponse({
                'success': False,
                'error': 'Р¤Р°Р№Р» Р±СЌРєР°РїР° РЅРµ РЅР°Р№РґРµРЅ'
            }, status=404)
        
        response = HttpResponse(backup.backup_file, content_type='application/octet-stream')
        response['Content-Disposition'] = f'attachment; filename="{backup.name}"'
        response['Content-Length'] = backup.backup_file.size
        
        # Р›РѕРіРёСЂСѓРµРј - РРЎРџР РђР’Р›Р•РќРћ
        action_type = get_or_create_action_type('backup_downloaded', 'Р‘СЌРєР°Рї СЃРєР°С‡Р°РЅ')
        AdminLog.objects.create(
            admin=request.user,
            action=action_type,
            details=f"РЎРєР°С‡Р°РЅ Р±СЌРєР°Рї: {backup.name}"
        )
        
        return response
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'РћС€РёР±РєР° СЃРєР°С‡РёРІР°РЅРёСЏ: {str(e)}'
        }, status=400)

@user_passes_test(is_admin, login_url='/admin/login/')
def delete_backup_api(request, backup_id):
    """РЈРґР°Р»РµРЅРёРµ Р±СЌРєР°РїР°"""
    if request.method == 'POST':
        backup = get_object_or_404(Backup, id=backup_id)
        
        try:
            backup_name = backup.name
            backup.delete()
            
            # Р›РѕРіРёСЂСѓРµРј - РРЎРџР РђР’Р›Р•РќРћ
            action_type = get_or_create_action_type('backup_deleted', 'Р‘СЌРєР°Рї СѓРґР°Р»РµРЅ')
            AdminLog.objects.create(
                admin=request.user,
                action=action_type,
                details=f"РЈРґР°Р»РµРЅ Р±СЌРєР°Рї: {backup_name}"
            )
            
            return JsonResponse({
                'success': True, 
                'message': 'Р‘СЌРєР°Рї СѓСЃРїРµС€РЅРѕ СѓРґР°Р»РµРЅ'
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False, 
                'error': str(e)
            }, status=400)
    
    return JsonResponse({'error': 'Invalid method'}, status=405)

@user_passes_test(is_admin, login_url='/admin/login/')
def get_backups_list_api(request):
    """API РґР»СЏ РїРѕР»СѓС‡РµРЅРёСЏ СЃРїРёСЃРєР° Р±СЌРєР°РїРѕРІ"""
    try:
        backups = Backup.objects.all().order_by('-created_at')
        backups_data = []
        
        for backup in backups:
            backups_data.append({
                'id': backup.id,
                'name': backup.name,
                'backup_type': backup.backup_type,
                'backup_type_display': backup.get_backup_type_display(),
                'file_size': backup.file_size,
                'file_size_display': backup.get_file_size_display(),
                'created_at': backup.created_at.strftime('%d.%m.%Y %H:%M'),
                'created_by': backup.created_by.username,
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
    """API РґР»СЏ РїРѕР»СѓС‡РµРЅРёСЏ СЃС‚Р°С‚СѓСЃР° СЃРёСЃС‚РµРјС‹"""
    backup_manager = DjangoBackupManager()
    system_info = backup_manager.get_system_info()
    
    return JsonResponse(system_info)

from django.db import models



@user_passes_test(is_admin, login_url='/admin/login/')
def admin_logs(request):
    """РџСЂРѕСЃРјРѕС‚СЂ Р»РѕРіРѕРІ Р°РґРјРёРЅРёСЃС‚СЂР°С‚РѕСЂРѕРІ"""
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
    
    # РџРѕР»СѓС‡Р°РµРј РІСЃРµ С‚РёРїС‹ РґРµР№СЃС‚РІРёР№ РґР»СЏ С„РёР»СЊС‚СЂР°
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
    """РћС‡РёСЃС‚РєР° Р»РѕРіРѕРІ"""
    if request.method == 'POST':
        days_old = int(request.POST.get('days_old', 30))
        cutoff_date = timezone.now() - timedelta(days=days_old)
        
        deleted_count = AdminLog.objects.filter(created_at__lt=cutoff_date).delete()[0]
        
        # РЎРѕР·РґР°РµРј Р·Р°РїРёСЃСЊ РІ Р»РѕРіР°С… Рѕ РѕС‡РёСЃС‚РєРµ
        action_type = get_or_create_action_type('logs_cleared', 'Р›РѕРіРё РѕС‡РёС‰РµРЅС‹')
        AdminLog.objects.create(
            admin=request.user,
            action=action_type,
            details=f'РћС‡РёС‰РµРЅРѕ {deleted_count} Р»РѕРіРѕРІ СЃС‚Р°СЂС€Рµ {days_old} РґРЅРµР№'
        )
        
        messages.success(request, f'РЈСЃРїРµС€РЅРѕ РѕС‡РёС‰РµРЅРѕ {deleted_count} Р»РѕРіРѕРІ СЃС‚Р°СЂС€Рµ {days_old} РґРЅРµР№')
    
    return redirect('admin_logs')

@user_passes_test(is_admin, login_url='/admin/login/')
def api_company_stats(request):
    """API РґР»СЏ РїРѕР»СѓС‡РµРЅРёСЏ СЃС‚Р°С‚РёСЃС‚РёРєРё РєРѕРјРїР°РЅРёР№"""
    stats = {
        'pending': Company.objects.filter(status=Company.STATUS_PENDING).count(),
        'approved': Company.objects.filter(status=Company.STATUS_APPROVED).count(),
        'rejected': Company.objects.filter(status=Company.STATUS_REJECTED).count(),
        'total': Company.objects.count(),
    }
    return JsonResponse(stats)

@user_passes_test(is_admin, login_url='/admin/login/')
def api_recent_activity(request):
    """API РґР»СЏ РїРѕР»СѓС‡РµРЅРёСЏ РїРѕСЃР»РµРґРЅРµР№ Р°РєС‚РёРІРЅРѕСЃС‚Рё"""
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
    """РЈРїСЂР°РІР»РµРЅРёРµ Р°РґРјРёРЅРёСЃС‚СЂР°С‚РѕСЂР°РјРё СЃР°Р№С‚Р° (С‚РѕР»СЊРєРѕ РґР»СЏ superuser)"""
    context = get_admin_context(request)
    site_admins = User.objects.filter(user_type='adminsite').order_by('-date_joined')
    
    context.update({
        'site_admins': site_admins,
    })
    return render(request, 'admin_panel/admin_management.html', context)

@user_passes_test(is_superuser_only, login_url='/admin/login/')
def create_site_admin(request):
    """РЎРѕР·РґР°РЅРёРµ РЅРѕРІРѕРіРѕ Р°РґРјРёРЅРёСЃС‚СЂР°С‚РѕСЂР° СЃР°Р№С‚Р°"""
    context = get_admin_context(request)
    
    if request.method == 'POST':
        form = SiteAdminCreateForm(request.POST)
        if form.is_valid():
            try:
                admin = form.save()
                # Р›РѕРіРёСЂСѓРµРј - РРЎРџР РђР’Р›Р•РќРћ
                action_type = get_or_create_action_type('admin_created', 'РђРґРјРёРЅРёСЃС‚СЂР°С‚РѕСЂ СЃРѕР·РґР°РЅ')
                AdminLog.objects.create(
                    admin=request.user,
                    action=action_type,
                    details=f'РЎРѕР·РґР°РЅ Р°РґРјРёРЅРёСЃС‚СЂР°С‚РѕСЂ СЃР°Р№С‚Р°: {admin.get_full_name()} ({admin.email})'
                )
                return redirect('admin_management')
            except Exception as e:
                pass
    else:
        form = SiteAdminCreateForm()
    
    context.update({
        'form': form,
        'title': 'РЎРѕР·РґР°РЅРёРµ Р°РґРјРёРЅРёСЃС‚СЂР°С‚РѕСЂР° СЃР°Р№С‚Р°'
    })
    return render(request, 'admin_panel/admin_form.html', context)

@user_passes_test(is_superuser_only, login_url='/admin/login/')
def edit_site_admin(request, admin_id):
    """Р РµРґР°РєС‚РёСЂРѕРІР°РЅРёРµ Р°РґРјРёРЅРёСЃС‚СЂР°С‚РѕСЂР° СЃР°Р№С‚Р°"""
    context = get_admin_context(request)
    admin_user = get_object_or_404(User, id=admin_id, user_type='adminsite')

    if request.method == 'POST':
        form = SiteAdminEditForm(request.POST, instance=admin_user)
        if form.is_valid():
            try:
                admin = form.save()
                # Р›РѕРіРёСЂСѓРµРј - РРЎРџР РђР’Р›Р•РќРћ
                action_type = get_or_create_action_type('admin_updated', 'РђРґРјРёРЅРёСЃС‚СЂР°С‚РѕСЂ РѕР±РЅРѕРІР»РµРЅ')
                AdminLog.objects.create(
                    admin=request.user,
                    action=action_type,
                    details=f'РћР±РЅРѕРІР»РµРЅ Р°РґРјРёРЅРёСЃС‚СЂР°С‚РѕСЂ СЃР°Р№С‚Р°: {admin.get_full_name()} ({admin.email})'
                )
                return redirect('admin_management')
            except Exception as e:
                pass
    else:
        form = SiteAdminEditForm(instance=admin_user)
    
    context.update({
        'form': form,
        'admin': admin_user,
        'title': 'Р РµРґР°РєС‚РёСЂРѕРІР°РЅРёРµ Р°РґРјРёРЅРёСЃС‚СЂР°С‚РѕСЂР° СЃР°Р№С‚Р°'
    })
    return render(request, 'admin_panel/admin_form.html', context)

@user_passes_test(is_superuser_only, login_url='/admin/login/')
def toggle_site_admin_status(request, admin_id):
    """РђРєС‚РёРІР°С†РёСЏ/РґРµР°РєС‚РёРІР°С†РёСЏ Р°РґРјРёРЅРёСЃС‚СЂР°С‚РѕСЂР° СЃР°Р№С‚Р°"""
    admin_user = get_object_or_404(User, id=admin_id, user_type='adminsite')
    
    if admin_user == request.user:
        return redirect('admin_management')
    
    if admin_user.is_active:
        admin_user.is_active = False
        action_type = get_or_create_action_type('admin_deactivated', 'РђРґРјРёРЅРёСЃС‚СЂР°С‚РѕСЂ РґРµР°РєС‚РёРІРёСЂРѕРІР°РЅ')
        message = f'вњ… РђРґРјРёРЅРёСЃС‚СЂР°С‚РѕСЂ СЃР°Р№С‚Р° {admin_user.get_full_name()} РґРµР°РєС‚РёРІРёСЂРѕРІР°РЅ'
    else:
        admin_user.is_active = True
        action_type = get_or_create_action_type('admin_activated', 'РђРґРјРёРЅРёСЃС‚СЂР°С‚РѕСЂ Р°РєС‚РёРІРёСЂРѕРІР°РЅ')
        message = f'вњ… РђРґРјРёРЅРёСЃС‚СЂР°С‚РѕСЂ СЃР°Р№С‚Р° {admin_user.get_full_name()} Р°РєС‚РёРІРёСЂРѕРІР°РЅ'
    
    admin_user.save()
    
    AdminLog.objects.create(
        admin=request.user,
        action=action_type,
        details=f'РђРґРјРёРЅРёСЃС‚СЂР°С‚РѕСЂ СЃР°Р№С‚Р° {admin_user.get_full_name()} {"РґРµР°РєС‚РёРІРёСЂРѕРІР°РЅ" if not admin_user.is_active else "Р°РєС‚РёРІРёСЂРѕРІР°РЅ"}'
    )
    
    return redirect('admin_management')

@user_passes_test(is_superuser_only, login_url='/admin/login/')
def delete_site_admin(request, admin_id):
    """РЈРґР°Р»РµРЅРёРµ Р°РґРјРёРЅРёСЃС‚СЂР°С‚РѕСЂР° СЃР°Р№С‚Р°"""
    admin_user = get_object_or_404(User, id=admin_id, user_type='adminsite')
    
    if admin_user == request.user:
        return redirect('admin_management')
    
    admin_name = admin_user.get_full_name()
    admin_email = admin_user.email
    
    admin_user.delete()
    
    # Р›РѕРіРёСЂСѓРµРј - РРЎРџР РђР’Р›Р•РќРћ
    action_type = get_or_create_action_type('admin_deleted', 'РђРґРјРёРЅРёСЃС‚СЂР°С‚РѕСЂ СѓРґР°Р»РµРЅ')
    AdminLog.objects.create(
        admin=request.user,
        action=action_type,
        details=f'РЈРґР°Р»РµРЅ Р°РґРјРёРЅРёСЃС‚СЂР°С‚РѕСЂ СЃР°Р№С‚Р°: {admin_name} ({admin_email})'
    )
    
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
            return HttpResponseForbidden("РЈ РІР°СЃ РЅРµС‚ РїСЂР°РІ РґР»СЏ РґРѕСЃС‚СѓРїР° Рє Р°РґРјРёРЅ-РїР°РЅРµР»Рё")
        
        return view_func(request, *args, **kwargs)
    return _wrapped_view

from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
from django.contrib.auth.decorators import login_required, user_passes_test
import json
from datetime import datetime
from .statistics_service import StatisticsService

# Р”РѕР±Р°РІСЊС‚Рµ СЌС‚Рё РёРјРїРѕСЂС‚С‹ РґР»СЏ СЌРєСЃРїРѕСЂС‚Р°
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
    """РЎС‚СЂР°РЅРёС†Р° СЃС‚Р°С‚РёСЃС‚РёРєРё СЃ РїРѕРґРґРµСЂР¶РєРѕР№ РїРµСЂРёРѕРґР°"""
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    # Р’Р°Р»РёРґР°С†РёСЏ РґР°С‚
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
    
    # РџРѕРґРіРѕС‚Р°РІР»РёРІР°РµРј РґР°РЅРЅС‹Рµ РґР»СЏ РєСЂСѓРіРѕРІС‹С… РґРёР°РіСЂР°РјРј
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
    
    # РџРѕРґРіРѕС‚Р°РІР»РёРІР°РµРј РґР°РЅРЅС‹Рµ РґР»СЏ СЃС‚РѕР»Р±С‡Р°С‚С‹С… РґРёР°РіСЂР°РјРј
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
    """Р­РєСЃРїРѕСЂС‚ СЃС‚Р°С‚РёСЃС‚РёРєРё РІ PDF СЃ РїРѕРґРґРµСЂР¶РєРѕР№ РїРµСЂРёРѕРґР°"""
    try:
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')
        
        # Р’Р°Р»РёРґР°С†РёСЏ РґР°С‚
        if start_date and end_date:
            try:
                start_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
                end_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
                if start_obj > end_obj:
                    start_date, end_date = None, None
            except ValueError:
                start_date, end_date = None, None
        
        # РЎРѕР±РёСЂР°РµРј РґР°РЅРЅС‹Рµ СЃ СѓС‡РµС‚РѕРј РїРµСЂРёРѕРґР°
        main_stats = StatisticsService.get_main_statistics(start_date, end_date)
        user_distribution = StatisticsService.get_user_type_distribution(start_date, end_date)
        vacancy_stats = StatisticsService.get_vacancy_statistics(start_date, end_date)
        company_stats = StatisticsService.get_company_statistics(start_date, end_date)
        response_stats = StatisticsService.get_response_statistics(start_date, end_date)
        complaint_stats = StatisticsService.get_complaint_statistics(start_date, end_date)
        
        # РЎРѕР·РґР°РµРј PDF
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=30)
        elements = []
        
        # Р РµРіРёСЃС‚СЂРёСЂСѓРµРј С€СЂРёС„С‚С‹
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.lib.fonts import addMapping
        
        font_name = 'Times-Roman'
        bold_font_name = 'Times-Bold'
        
        try:
            # РџСЂРѕР±СѓРµРј РЅР°Р№С‚Рё Рё Р·Р°СЂРµРіРёСЃС‚СЂРёСЂРѕРІР°С‚СЊ Times New Roman
            font_variants = [
                'times.ttf', 'timesbd.ttf', 'timesi.ttf', 'timesbi.ttf',
                'Times New Roman.ttf', 'Times New Roman Bold.ttf',
                '/usr/share/fonts/truetype/msttcorefonts/Times_New_Roman.ttf',
                '/Library/Fonts/Times New Roman.ttf',
            ]
            
            for font_variant in font_variants:
                try:
                    if 'timesbd' in font_variant or 'Bold' in font_variant:
                        pdfmetrics.registerFont(TTFont('TimesNewRoman-Bold', font_variant))
                        bold_font_name = 'TimesNewRoman-Bold'
                    else:
                        pdfmetrics.registerFont(TTFont('TimesNewRoman', font_variant))
                        font_name = 'TimesNewRoman'
                except:
                    continue
            
            if font_name == 'TimesNewRoman' and bold_font_name == 'TimesNewRoman-Bold':
                addMapping('TimesNewRoman', 0, 0, 'TimesNewRoman')
                addMapping('TimesNewRoman', 1, 0, 'TimesNewRoman-Bold')
            else:
                font_name = 'Times-Roman'
                bold_font_name = 'Times-Bold'
                
        except Exception as e:
            print(f"Font registration error: {e}")
            font_name = 'Times-Roman'
            bold_font_name = 'Times-Bold'
        
        # РЎС‚РёР»Рё
        styles = getSampleStyleSheet()
        
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontName=bold_font_name,
            fontSize=16,
            spaceAfter=30,
            alignment=1
        )
        
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontName=bold_font_name,
            fontSize=12,
            spaceAfter=12
        )
        
        normal_style = ParagraphStyle(
            'CustomNormal',
            parent=styles['Normal'],
            fontName=font_name,
            fontSize=10
        )
        
        # Р—Р°РіРѕР»РѕРІРѕРє
        title = Paragraph("РЎС‚Р°С‚РёСЃС‚РёРєР° РїР»Р°С‚С„РѕСЂРјС‹ С‚СЂСѓРґРѕСѓСЃС‚СЂРѕР№СЃС‚РІР°", title_style)
        elements.append(title)
        
        period_info = f"Р”Р°С‚Р° СЌРєСЃРїРѕСЂС‚Р°: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
        if start_date and end_date:
            period_info += f" | РџРµСЂРёРѕРґ: {start_date} - {end_date}"
        
        elements.append(Paragraph(period_info, normal_style))
        elements.append(Spacer(1, 20))
        
        # РћСЃРЅРѕРІРЅР°СЏ СЃС‚Р°С‚РёСЃС‚РёРєР°
        elements.append(Paragraph("РћСЃРЅРѕРІРЅР°СЏ СЃС‚Р°С‚РёСЃС‚РёРєР°", heading_style))
        
        main_data = [
            ['РџРѕРєР°Р·Р°С‚РµР»СЊ', 'Р—РЅР°С‡РµРЅРёРµ'],
            ['Р’СЃРµРіРѕ РїРѕР»СЊР·РѕРІР°С‚РµР»РµР№', str(main_stats['total_users'])],
            ['Р’СЃРµРіРѕ РєРѕРјРїР°РЅРёР№', str(main_stats['total_companies'])],
            ['Р’СЃРµРіРѕ РІР°РєР°РЅСЃРёР№', str(main_stats['total_vacancies'])],
            ['Р’СЃРµРіРѕ РѕС‚РєР»РёРєРѕРІ', str(main_stats['total_responses'])],
            ['РђРєС‚РёРІРЅС‹С… РєРѕРјРїР°РЅРёР№', str(main_stats['active_companies'])],
        ]
        
        # Р”РѕР±Р°РІР»СЏРµРј РёРЅС„РѕСЂРјР°С†РёСЋ Рѕ РїРµСЂРёРѕРґРµ, РµСЃР»Рё РѕРЅ СѓРєР°Р·Р°РЅ
        if not start_date or not end_date:
            main_data.extend([
                ['РќРѕРІС‹С… РїРѕР»СЊР·РѕРІР°С‚РµР»РµР№ (РЅРµРґРµР»СЏ)', str(main_stats['new_users_week'])],
                ['РќРѕРІС‹С… РєРѕРјРїР°РЅРёР№ (РЅРµРґРµР»СЏ)', str(main_stats['new_companies_week'])],
                ['РќРѕРІС‹С… РІР°РєР°РЅСЃРёР№ (РЅРµРґРµР»СЏ)', str(main_stats['new_vacancies_week'])],
            ])
        
        main_table = Table(main_data, colWidths=[250, 100])
        main_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), bold_font_name),
            ('FONTNAME', (0, 1), (-1, -1), font_name),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        elements.append(main_table)
        elements.append(Spacer(1, 20))
        
        # РћСЃС‚Р°Р»СЊРЅС‹Рµ РіСЂР°С„РёРєРё Рё С‚Р°Р±Р»РёС†С‹ (Р°РЅР°Р»РѕРіРёС‡РЅРѕ РІР°С€РµРјСѓ РєРѕРґСѓ)
        # Р“СЂР°С„РёРє СЂР°СЃРїСЂРµРґРµР»РµРЅРёСЏ РїРѕР»СЊР·РѕРІР°С‚РµР»РµР№
        elements.append(Paragraph("Р Р°СЃРїСЂРµРґРµР»РµРЅРёРµ РїРѕР»СЊР·РѕРІР°С‚РµР»РµР№ РїРѕ С‚РёРїР°Рј", heading_style))
        user_chart_buffer = create_user_distribution_chart(user_distribution)
        if user_chart_buffer:
            user_chart = Image(user_chart_buffer, width=6*inch, height=4*inch)
            elements.append(user_chart)
        elements.append(Spacer(1, 10))
        
        # РўР°Р±Р»РёС†Р° СЂР°СЃРїСЂРµРґРµР»РµРЅРёСЏ РїРѕР»СЊР·РѕРІР°С‚РµР»РµР№
        user_data = [['РўРёРї РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ', 'РљРѕР»РёС‡РµСЃС‚РІРѕ', 'РџСЂРѕС†РµРЅС‚']]
        for i, label in enumerate(user_distribution['labels']):
            user_data.append([
                label,
                str(user_distribution['data'][i]),
                f"{user_distribution['percentages'][i]}%"
            ])
        
        user_table = Table(user_data, colWidths=[200, 80, 80])
        user_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), bold_font_name),
            ('FONTNAME', (0, 1), (-1, -1), font_name),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        elements.append(user_table)
        elements.append(Spacer(1, 20))
        
        # Р“СЂР°С„РёРє СЃС‚Р°С‚СѓСЃРѕРІ РєРѕРјРїР°РЅРёР№
        elements.append(Paragraph("РЎС‚Р°С‚СѓСЃС‹ РєРѕРјРїР°РЅРёР№", heading_style))
        company_chart_buffer = create_company_status_chart(company_stats)
        if company_chart_buffer:
            company_chart = Image(company_chart_buffer, width=6*inch, height=4*inch)
            elements.append(company_chart)
        elements.append(Spacer(1, 10))
        
        # РўР°Р±Р»РёС†Р° СЃС‚Р°С‚СѓСЃРѕРІ РєРѕРјРїР°РЅРёР№
        company_data = [['РЎС‚Р°С‚СѓСЃ', 'РљРѕР»РёС‡РµСЃС‚РІРѕ', 'РџСЂРѕС†РµРЅС‚']]
        for i, label in enumerate(company_stats['status_distribution']['labels']):
            company_data.append([
                label,
                str(company_stats['status_distribution']['data'][i]),
                f"{company_stats['status_distribution']['percentages'][i]}%"
            ])
        
        company_table = Table(company_data, colWidths=[200, 80, 80])
        company_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), bold_font_name),
            ('FONTNAME', (0, 1), (-1, -1), font_name),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        elements.append(company_table)
        elements.append(Spacer(1, 20))
        
        # Р“СЂР°С„РёРє РєР°С‚РµРіРѕСЂРёР№ РІР°РєР°РЅСЃРёР№
        elements.append(Paragraph("РљР°С‚РµРіРѕСЂРёРё РІР°РєР°РЅСЃРёР№", heading_style))
        vacancy_chart_buffer = create_vacancy_categories_chart(vacancy_stats)
        if vacancy_chart_buffer:
            vacancy_chart = Image(vacancy_chart_buffer, width=6*inch, height=4*inch)
            elements.append(vacancy_chart)
        elements.append(Spacer(1, 10))
        
        # РўР°Р±Р»РёС†Р° РєР°С‚РµРіРѕСЂРёР№ РІР°РєР°РЅСЃРёР№
        vacancy_data = [['РљР°С‚РµРіРѕСЂРёСЏ', 'РљРѕР»РёС‡РµСЃС‚РІРѕ']]
        for i, label in enumerate(vacancy_stats['category']['labels']):
            vacancy_data.append([
                label,
                str(vacancy_stats['category']['data'][i])
            ])
        
        vacancy_table = Table(vacancy_data, colWidths=[200, 80])
        vacancy_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), bold_font_name),
            ('FONTNAME', (0, 1), (-1, -1), font_name),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        elements.append(vacancy_table)
        elements.append(Spacer(1, 20))
        
        # Р“СЂР°С„РёРє Р°РєС‚РёРІРЅРѕСЃС‚Рё РѕС‚РєР»РёРєРѕРІ
        elements.append(Paragraph("РђРєС‚РёРІРЅРѕСЃС‚СЊ РѕС‚РєР»РёРєРѕРІ", heading_style))
        response_chart_buffer = create_response_activity_chart(response_stats)
        if response_chart_buffer:
            response_chart = Image(response_chart_buffer, width=6*inch, height=4*inch)
            elements.append(response_chart)
        
        # РЎРѕР±РёСЂР°РµРј PDF
        doc.build(elements)
        
        # Р’РѕР·РІСЂР°С‰Р°РµРј С„Р°Р№Р»
        buffer.seek(0)
        filename = "statistics"
        if start_date and end_date:
            filename += f"_{start_date}_to_{end_date}"
        filename += f"_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        
        response = HttpResponse(buffer, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
        
    except Exception as e:
        return HttpResponse(f"РћС€РёР±РєР° РїСЂРё СЃРѕР·РґР°РЅРёРё PDF: {str(e)}")

@login_required
@user_passes_test(is_admin)
def export_statistics_excel(request):
    """Р­РєСЃРїРѕСЂС‚ СЃС‚Р°С‚РёСЃС‚РёРєРё РІ Excel (CSV) СЃ РїРѕРґРґРµСЂР¶РєРѕР№ РїРµСЂРёРѕРґР°"""
    try:
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')
        
        # Р’Р°Р»РёРґР°С†РёСЏ РґР°С‚
        if start_date and end_date:
            try:
                start_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
                end_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
                if start_obj > end_obj:
                    start_date, end_date = None, None
            except ValueError:
                start_date, end_date = None, None
        
        # РЎРѕР±РёСЂР°РµРј РґР°РЅРЅС‹Рµ СЃ СѓС‡РµС‚РѕРј РїРµСЂРёРѕРґР°
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
        
        # РЎРѕР·РґР°РµРј CSV writer СЃ РїРѕРґРґРµСЂР¶РєРѕР№ СЂСѓСЃСЃРєРѕРіРѕ
        writer = csv.writer(response)
        
        # Р—Р°РіРѕР»РѕРІРѕРє
        writer.writerow(['РЎС‚Р°С‚РёСЃС‚РёРєР° РїР»Р°С‚С„РѕСЂРјС‹ С‚СЂСѓРґРѕСѓСЃС‚СЂРѕР№СЃС‚РІР°'])
        period_info = f"Р”Р°С‚Р° СЌРєСЃРїРѕСЂС‚Р°: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
        if start_date and end_date:
            period_info += f" | РџРµСЂРёРѕРґ: {start_date} - {end_date}"
        writer.writerow([period_info])
        writer.writerow([])
        
        # РћСЃРЅРѕРІРЅР°СЏ СЃС‚Р°С‚РёСЃС‚РёРєР°
        writer.writerow(['РћРЎРќРћР’РќРђРЇ РЎРўРђРўРРЎРўРРљРђ'])
        writer.writerow(['РџРѕРєР°Р·Р°С‚РµР»СЊ', 'Р—РЅР°С‡РµРЅРёРµ'])
        writer.writerow(['Р’СЃРµРіРѕ РїРѕР»СЊР·РѕРІР°С‚РµР»РµР№', main_stats['total_users']])
        writer.writerow(['Р’СЃРµРіРѕ РєРѕРјРїР°РЅРёР№', main_stats['total_companies']])
        writer.writerow(['Р’СЃРµРіРѕ РІР°РєР°РЅСЃРёР№', main_stats['total_vacancies']])
        writer.writerow(['Р’СЃРµРіРѕ РѕС‚РєР»РёРєРѕРІ', main_stats['total_responses']])
        writer.writerow(['РђРєС‚РёРІРЅС‹С… РєРѕРјРїР°РЅРёР№', main_stats['active_companies']])
        
        if not start_date or not end_date:
            writer.writerow(['РќРѕРІС‹С… РїРѕР»СЊР·РѕРІР°С‚РµР»РµР№ (РЅРµРґРµР»СЏ)', main_stats['new_users_week']])
            writer.writerow(['РќРѕРІС‹С… РєРѕРјРїР°РЅРёР№ (РЅРµРґРµР»СЏ)', main_stats['new_companies_week']])
            writer.writerow(['РќРѕРІС‹С… РІР°РєР°РЅСЃРёР№ (РЅРµРґРµР»СЏ)', main_stats['new_vacancies_week']])
        
        writer.writerow([])
        
        # Р Р°СЃРїСЂРµРґРµР»РµРЅРёРµ РїРѕР»СЊР·РѕРІР°С‚РµР»РµР№
        writer.writerow(['Р РђРЎРџР Р•Р”Р•Р›Р•РќРР• РџРћР›Р¬Р—РћР’РђРўР•Р›Р•Р™ РџРћ РўРРџРђРњ'])
        writer.writerow(['РўРёРї РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ', 'РљРѕР»РёС‡РµСЃС‚РІРѕ', 'РџСЂРѕС†РµРЅС‚'])
        for i, label in enumerate(user_distribution['labels']):
            writer.writerow([
                label,
                user_distribution['data'][i],
                f"{user_distribution['percentages'][i]}%"
            ])
        writer.writerow([])
        
        # РЎС‚Р°С‚СѓСЃС‹ РєРѕРјРїР°РЅРёР№
        writer.writerow(['РЎРўРђРўРЈРЎР« РљРћРњРџРђРќРР™'])
        writer.writerow(['РЎС‚Р°С‚СѓСЃ', 'РљРѕР»РёС‡РµСЃС‚РІРѕ', 'РџСЂРѕС†РµРЅС‚'])
        for i, label in enumerate(company_stats['status_distribution']['labels']):
            writer.writerow([
                label,
                company_stats['status_distribution']['data'][i],
                f"{company_stats['status_distribution']['percentages'][i]}%"
            ])
        writer.writerow([])
        
        # РљР°С‚РµРіРѕСЂРёРё РІР°РєР°РЅСЃРёР№
        writer.writerow(['РљРђРўР•Р“РћР РР Р’РђРљРђРќРЎРР™'])
        writer.writerow(['РљР°С‚РµРіРѕСЂРёСЏ', 'РљРѕР»РёС‡РµСЃС‚РІРѕ'])
        for i, label in enumerate(vacancy_stats['category']['labels']):
            writer.writerow([label, vacancy_stats['category']['data'][i]])
        writer.writerow([])
        
        # РђРєС‚РёРІРЅРѕСЃС‚СЊ РѕС‚РєР»РёРєРѕРІ
        writer.writerow(['РђРљРўРР’РќРћРЎРўР¬ РћРўРљР›РРљРћР’'])
        writer.writerow(['Р”Р°С‚Р°', 'РљРѕР»РёС‡РµСЃС‚РІРѕ РѕС‚РєР»РёРєРѕРІ'])
        for day in response_stats['daily_activity']:
            writer.writerow([day['date'], day['count']])
        writer.writerow([])
        
        # РўРёРїС‹ Р¶Р°Р»РѕР±
        writer.writerow(['РўРРџР« Р–РђР›РћР‘'])
        writer.writerow(['РўРёРї Р¶Р°Р»РѕР±С‹', 'РљРѕР»РёС‡РµСЃС‚РІРѕ'])
        for i, label in enumerate(complaint_stats['type_distribution']['labels']):
            writer.writerow([label, complaint_stats['type_distribution']['data'][i]])
        
        return response
        
    except Exception as e:
        return HttpResponse(f"РћС€РёР±РєР° РїСЂРё СЃРѕР·РґР°РЅРёРё Excel: {str(e)}")

# Р¤СѓРЅРєС†РёРё РґР»СЏ СЃРѕР·РґР°РЅРёСЏ РіСЂР°С„РёРєРѕРІ (РѕСЃС‚Р°СЋС‚СЃСЏ Р±РµР· РёР·РјРµРЅРµРЅРёР№)
def create_user_distribution_chart(user_distribution):
    """РЎРѕР·РґР°РµС‚ РєСЂСѓРіРѕРІСѓСЋ РґРёР°РіСЂР°РјРјСѓ СЂР°СЃРїСЂРµРґРµР»РµРЅРёСЏ РїРѕР»СЊР·РѕРІР°С‚РµР»РµР№"""
    try:
        plt.figure(figsize=(8, 6))
        plt.pie(
            user_distribution['data'],
            labels=user_distribution['labels'],
            colors=user_distribution['colors'],
            autopct='%1.1f%%',
            startangle=90
        )
        plt.title('Р Р°СЃРїСЂРµРґРµР»РµРЅРёРµ РїРѕР»СЊР·РѕРІР°С‚РµР»РµР№ РїРѕ С‚РёРїР°Рј', fontsize=14, fontweight='bold')
        plt.axis('equal')
        
        buffer = io.BytesIO()
        plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight')
        buffer.seek(0)
        plt.close()
        return buffer
    except Exception as e:
        print(f"РћС€РёР±РєР° РїСЂРё СЃРѕР·РґР°РЅРёРё РіСЂР°С„РёРєР° РїРѕР»СЊР·РѕРІР°С‚РµР»РµР№: {e}")
        return None

def create_company_status_chart(company_stats):
    """РЎРѕР·РґР°РµС‚ РєСЂСѓРіРѕРІСѓСЋ РґРёР°РіСЂР°РјРјСѓ СЃС‚Р°С‚СѓСЃРѕРІ РєРѕРјРїР°РЅРёР№"""
    try:
        plt.figure(figsize=(8, 6))
        plt.pie(
            company_stats['status_distribution']['data'],
            labels=company_stats['status_distribution']['labels'],
            colors=company_stats['status_distribution']['colors'],
            autopct='%1.1f%%',
            startangle=90
        )
        plt.title('РЎС‚Р°С‚СѓСЃС‹ РєРѕРјРїР°РЅРёР№', fontsize=14, fontweight='bold')
        plt.axis('equal')
        
        buffer = io.BytesIO()
        plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight')
        buffer.seek(0)
        plt.close()
        return buffer
    except Exception as e:
        print(f"РћС€РёР±РєР° РїСЂРё СЃРѕР·РґР°РЅРёРё РіСЂР°С„РёРєР° РєРѕРјРїР°РЅРёР№: {e}")
        return None

def create_vacancy_categories_chart(vacancy_stats):
    """РЎРѕР·РґР°РµС‚ СЃС‚РѕР»Р±С‡Р°С‚СѓСЋ РґРёР°РіСЂР°РјРјСѓ РєР°С‚РµРіРѕСЂРёР№ РІР°РєР°РЅСЃРёР№"""
    try:
        plt.figure(figsize=(10, 6))
        bars = plt.bar(
            vacancy_stats['category']['labels'],
            vacancy_stats['category']['data'],
            color=vacancy_stats['category']['colors']
        )
        plt.title('РљР°С‚РµРіРѕСЂРёРё РІР°РєР°РЅСЃРёР№', fontsize=14, fontweight='bold')
        plt.xlabel('РљР°С‚РµРіРѕСЂРёРё')
        plt.ylabel('РљРѕР»РёС‡РµСЃС‚РІРѕ РІР°РєР°РЅСЃРёР№')
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
        print(f"РћС€РёР±РєР° РїСЂРё СЃРѕР·РґР°РЅРёРё РіСЂР°С„РёРєР° РІР°РєР°РЅСЃРёР№: {e}")
        return None

def create_response_activity_chart(response_stats):
    """РЎРѕР·РґР°РµС‚ Р»РёРЅРµР№РЅС‹Р№ РіСЂР°С„РёРє Р°РєС‚РёРІРЅРѕСЃС‚Рё РѕС‚РєР»РёРєРѕРІ"""
    try:
        dates = [day['date'] for day in response_stats['daily_activity']]
        counts = [day['count'] for day in response_stats['daily_activity']]
        
        plt.figure(figsize=(10, 6))
        plt.plot(dates, counts, marker='o', linewidth=2, markersize=6)
        plt.title('РђРєС‚РёРІРЅРѕСЃС‚СЊ РѕС‚РєР»РёРєРѕРІ', fontsize=14, fontweight='bold')
        plt.xlabel('Р”Р°С‚Р°')
        plt.ylabel('РљРѕР»РёС‡РµСЃС‚РІРѕ РѕС‚РєР»РёРєРѕРІ')
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
        print(f"РћС€РёР±РєР° РїСЂРё СЃРѕР·РґР°РЅРёРё РіСЂР°С„РёРєР° РѕС‚РєР»РёРєРѕРІ: {e}")
        return None
    
from django.core.paginator import Paginator
@login_required
@admin_required
def admin_complaints(request):
    # РџРѕР»СѓС‡Р°РµРј РїР°СЂР°РјРµС‚СЂС‹ С„РёР»СЊС‚СЂР°С†РёРё
    status_filter = request.GET.get('status', 'all')
    type_filter = request.GET.get('type', 'all')
    
    # Р‘Р°Р·РѕРІС‹Р№ Р·Р°РїСЂРѕСЃ
    complaints = Complaint.objects.select_related(
        'vacancy', 'vacancy__company', 'complainant'
    ).order_by('-created_at')
    
    # РџСЂРёРјРµРЅСЏРµРј С„РёР»СЊС‚СЂС‹
    if status_filter != 'all':
        complaints = complaints.filter(status=status_filter)
    
    if type_filter != 'all':
        complaints = complaints.filter(complaint_type=type_filter)
    
    # РџР°РіРёРЅР°С†РёСЏ
    paginator = Paginator(complaints, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # РЎС‚Р°С‚РёСЃС‚РёРєР° РґР»СЏ Р±РѕРєРѕРІРѕРіРѕ РјРµРЅСЋ
    pending_complaints_count = Complaint.objects.filter(status='pending').count()
    
    context = {
        'page_obj': page_obj,
        'status_filter': status_filter,
        'type_filter': type_filter,
        'pending_complaints_count': pending_complaints_count,
        'total_complaints': complaints.count(),
        'pending_count': Complaint.objects.filter(status='pending').count(),
        'resolved_count': Complaint.objects.filter(status='resolved').count(),
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
    
    # РџРѕР»СѓС‡Р°РµРј СЃС‚Р°С‚РёСЃС‚РёРєСѓ РґР»СЏ Р±РѕРєРѕРІРѕРіРѕ РјРµРЅСЋ
    pending_complaints_count = Complaint.objects.filter(status='pending').count()
    pending_companies_count = Company.objects.filter(status='pending').count()
    
    context = {
        'complaint': complaint,
        'pending_complaints_count': pending_complaints_count,
        'pending_companies_count': pending_companies_count,
    }
    
    return render(request, 'admin_panel/complaint_detail.html', context)

@admin_required
@user_passes_test(is_admin, login_url='/admin/login/')
def update_complaint_status(request, complaint_id):
    if request.method == 'POST':
        complaint = get_object_or_404(Complaint, id=complaint_id)
        new_status = request.POST.get('status')
        admin_notes = request.POST.get('admin_notes', '')
        
        if new_status in dict(Complaint.STATUS_CHOICES):
            old_status = complaint.status
            complaint.status = new_status
            complaint.admin_notes = admin_notes
            complaint.resolved_at = timezone.now() if new_status in ['resolved', 'rejected'] else None
            complaint.save()
            
            # Р›РѕРіРёСЂСѓРµРј - РРЎРџР РђР’Р›Р•РќРћ
            action_type = get_or_create_action_type('complaint_status_updated', 'РЎС‚Р°С‚СѓСЃ Р¶Р°Р»РѕР±С‹ РѕР±РЅРѕРІР»РµРЅ')
            AdminLog.objects.create(
                admin=request.user,
                action=action_type,
                details=f'РР·РјРµРЅРµРЅ СЃС‚Р°С‚СѓСЃ Р¶Р°Р»РѕР±С‹ #{complaint.id} СЃ "{dict(Complaint.STATUS_CHOICES).get(old_status)}" РЅР° "{complaint.get_status_display()}"'
            )
            
            messages.success(request, f'РЎС‚Р°С‚СѓСЃ Р¶Р°Р»РѕР±С‹ РѕР±РЅРѕРІР»РµРЅ РЅР° "{complaint.get_status_display()}"')
        else:
            messages.error(request, 'РќРµРІРµСЂРЅС‹Р№ СЃС‚Р°С‚СѓСЃ')
    
    return redirect('complaint_detail', complaint_id=complaint_id)

def send_vacancy_archive_email(vacancy, archive_reason=""):
    """
    РћС‚РїСЂР°РІР»СЏРµС‚ email СѓРІРµРґРѕРјР»РµРЅРёРµ РєРѕРјРїР°РЅРёРё РїСЂРё Р°СЂС…РёРІР°С†РёРё РІР°РєР°РЅСЃРёРё
    """
    company_email = vacancy.company.user.email
    company_name = vacancy.company.name
    vacancy_title = vacancy.position
    
    try:
        subject = f'Р’Р°РєР°РЅСЃРёСЏ "{vacancy_title}" РїРµСЂРµРјРµС‰РµРЅР° РІ Р°СЂС…РёРІ - HR-Lab'
        
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
                    <h1>рџ“‹ HR-Lab</h1>
                    <p>РЈРІРµРґРѕРјР»РµРЅРёРµ РѕР± Р°СЂС…РёРІР°С†РёРё РІР°РєР°РЅСЃРёРё</p>
                </div>
                
                <div class="content">
                    <h2 style="color: #1e293b; margin-top: 0;">РЈРІР°Р¶Р°РµРјС‹Р№ РїСЂРµРґСЃС‚Р°РІРёС‚РµР»СЊ РєРѕРјРїР°РЅРёРё {company_name}!</h2>
                    
                    <div class="warning-card">
                        <div class="warning-icon">рџ“Ѓ</div>
                        <div class="warning-title">Р’Р°РєР°РЅСЃРёСЏ РїРµСЂРµРјРµС‰РµРЅР° РІ Р°СЂС…РёРІ</div>
                        <div class="warning-description">
                            Р’Р°С€Р° РІР°РєР°РЅСЃРёСЏ "<strong>{vacancy_title}</strong>" Р±С‹Р»Р° РїРµСЂРµРјРµС‰РµРЅР° РІ Р°СЂС…РёРІ РјРѕРґРµСЂР°С‚РѕСЂРѕРј РїР»Р°С‚С„РѕСЂРјС‹.
                        </div>
                    </div>
                    
                    <div class="vacancy-info">
                        <div class="info-item">
                            <span class="info-label">Р’Р°РєР°РЅСЃРёСЏ:</span>
                            <span class="info-value">{vacancy_title}</span>
                        </div>
                        <div class="info-item">
                            <span class="info-label">РљРѕРјРїР°РЅРёСЏ:</span>
                            <span class="info-value">{company_name}</span>
                        </div>
                        <div class="info-item">
                            <span class="info-label">Р”Р°С‚Р° Р°СЂС…РёРІР°С†РёРё:</span>
                            <span class="info-value">{timezone.now().strftime('%d.%m.%Y РІ %H:%M')}</span>
                        </div>
                        <div class="info-item">
                            <span class="info-label">РЎС‚Р°С‚СѓСЃ:</span>
                            <span class="info-value" style="color: #f59e0b; font-weight: 700;">РђСЂС…РёРІРёСЂРѕРІР°РЅР°</span>
                        </div>
                    </div>
                    
                    {f'''
                    <div class="reason-section">
                        <div class="reason-title">рџ“ќ РџСЂРёС‡РёРЅР° Р°СЂС…РёРІР°С†РёРё:</div>
                        <p style="color: #1e293b; margin: 0; line-height: 1.5;">{archive_reason}</p>
                    </div>
                    ''' if archive_reason else ''}
                    
                    <div class="action-buttons">
                        <p style="color: #64748b; margin-bottom: 20px;">
                            Р’С‹ РјРѕР¶РµС‚Рµ СЃРѕР·РґР°С‚СЊ РЅРѕРІСѓСЋ РІР°РєР°РЅСЃРёСЋ РёР»Рё СЃРІСЏР·Р°С‚СЊСЃСЏ СЃ РїРѕРґРґРµСЂР¶РєРѕР№ РґР»СЏ СѓС‚РѕС‡РЅРµРЅРёСЏ РґРµС‚Р°Р»РµР№.
                        </p>
                        <a href="http://127.0.0.1:8000/create_vacancy/" class="action-button">
                            рџ“ќ РЎРѕР·РґР°С‚СЊ РЅРѕРІСѓСЋ РІР°РєР°РЅСЃРёСЋ
                        </a>
                        <a href="http://127.0.0.1:8000/contact/" class="action-button secondary-button">
                            рџ“ћ РЎРІСЏР·Р°С‚СЊСЃСЏ СЃ РїРѕРґРґРµСЂР¶РєРѕР№
                        </a>
                    </div>
                    
                    <p style="color: #64748b; font-size: 14px; text-align: center;">
                        <strong>Р’Р°Р¶РЅРѕ:</strong> РђСЂС…РёРІРЅС‹Рµ РІР°РєР°РЅСЃРёРё РЅРµ РѕС‚РѕР±СЂР°Р¶Р°СЋС‚СЃСЏ РІ РїРѕРёСЃРєРµ Рё РЅРµ РїРѕР»СѓС‡Р°СЋС‚ РѕС‚РєР»РёРєРѕРІ РѕС‚ СЃРѕРёСЃРєР°С‚РµР»РµР№.
                    </p>
                </div>
                
                <div class="footer">
                    <p><strong>РЎ СѓРІР°Р¶РµРЅРёРµРј, РєРѕРјР°РЅРґР° HR-Lab</strong></p>
                    <p>РњС‹ Р·Р°Р±РѕС‚РёРјСЃСЏ Рѕ РєР°С‡РµСЃС‚РІРµ РІР°РєР°РЅСЃРёР№ РЅР° РЅР°С€РµР№ РїР»Р°С‚С„РѕСЂРјРµ</p>
                    <div style="margin-top: 15px; padding-top: 15px; border-top: 1px solid #e2e8f0;">
                        <p>Email: hr-labogency@mail.ru</p>
                    </div>
                    <p style="font-size: 12px; margin-top: 20px; color: #94a3b8;">
                        Р­С‚Рѕ Р°РІС‚РѕРјР°С‚РёС‡РµСЃРєРѕРµ СЃРѕРѕР±С‰РµРЅРёРµ, РїРѕР¶Р°Р»СѓР№СЃС‚Р°, РЅРµ РѕС‚РІРµС‡Р°Р№С‚Рµ РЅР° РЅРµРіРѕ.
                    </p>
                </div>
            </div>
        </body>
        </html>
        """
        
        # РўРµРєСЃС‚РѕРІР°СЏ РІРµСЂСЃРёСЏ
        plain_message = f"""
        РЈРІР°Р¶Р°РµРјС‹Р№ РїСЂРµРґСЃС‚Р°РІРёС‚РµР»СЊ РєРѕРјРїР°РЅРёРё "{company_name}"!

        Р’Р°С€Р° РІР°РєР°РЅСЃРёСЏ "{vacancy_title}" Р±С‹Р»Р° РїРµСЂРµРјРµС‰РµРЅР° РІ Р°СЂС…РёРІ РјРѕРґРµСЂР°С‚РѕСЂРѕРј РїР»Р°С‚С„РѕСЂРјС‹ HR-Lab.

        РРЅС„РѕСЂРјР°С†РёСЏ Рѕ РІР°РєР°РЅСЃРёРё:
        - Р’Р°РєР°РЅСЃРёСЏ: {vacancy_title}
        - РљРѕРјРїР°РЅРёСЏ: {company_name}
        - Р”Р°С‚Р° Р°СЂС…РёРІР°С†РёРё: {timezone.now().strftime('%d.%m.%Y РІ %H:%M')}
        - РЎС‚Р°С‚СѓСЃ: РђСЂС…РёРІРёСЂРѕРІР°РЅР°

        {f'РџСЂРёС‡РёРЅР° Р°СЂС…РёРІР°С†РёРё: {archive_reason}' if archive_reason else ''}

        Р’Р°Р¶РЅРѕ: РђСЂС…РёРІРЅС‹Рµ РІР°РєР°РЅСЃРёРё РЅРµ РѕС‚РѕР±СЂР°Р¶Р°СЋС‚СЃСЏ РІ РїРѕРёСЃРєРµ Рё РЅРµ РїРѕР»СѓС‡Р°СЋС‚ РѕС‚РєР»РёРєРѕРІ РѕС‚ СЃРѕРёСЃРєР°С‚РµР»РµР№.

        Р’С‹ РјРѕР¶РµС‚Рµ:
        - РЎРѕР·РґР°С‚СЊ РЅРѕРІСѓСЋ РІР°РєР°РЅСЃРёСЋ: http://127.0.0.1:8000/create_vacancy/
        - РЎРІСЏР·Р°С‚СЊСЃСЏ СЃ РїРѕРґРґРµСЂР¶РєРѕР№: http://127.0.0.1:8000/contact/

        РЎ СѓРІР°Р¶РµРЅРёРµРј,
        РљРѕРјР°РЅРґР° HR-Lab

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
        
        print(f"вњ… [EMAIL] РЈРІРµРґРѕРјР»РµРЅРёРµ РѕР± Р°СЂС…РёРІР°С†РёРё РѕС‚РїСЂР°РІР»РµРЅРѕ РґР»СЏ {vacancy_title}")
        return True
        
    except Exception as e:
        print(f"вќЊ [EMAIL] РћРЁРР‘РљРђ РїСЂРё РѕС‚РїСЂР°РІРєРµ СѓРІРµРґРѕРјР»РµРЅРёСЏ РѕР± Р°СЂС…РёРІР°С†РёРё: {str(e)}")
        return False
    
@admin_required
@user_passes_test(is_admin, login_url='/admin/login/')
def archive_vacancy(request, vacancy_id):
    """
    РђСЂС…РёРІР°С†РёСЏ РІР°РєР°РЅСЃРёРё СЃ РѕС‚РїСЂР°РІРєРѕР№ email СѓРІРµРґРѕРјР»РµРЅРёСЏ
    """
    vacancy = get_object_or_404(Vacancy, id=vacancy_id)
    
    try:
        archived_status = StatusVacancies.objects.get(status_vacancies_name='РђСЂС…РёРІРёСЂРѕРІР°РЅР°')
    except StatusVacancies.DoesNotExist:
        messages.error(request, 'РЎС‚Р°С‚СѓСЃ "РђСЂС…РёРІРёСЂРѕРІР°РЅР°" РЅРµ РЅР°Р№РґРµРЅ РІ СЃРёСЃС‚РµРјРµ.')
        return redirect('admin_complaints')
    
    if request.method == 'POST':
        archive_reason = request.POST.get('archive_reason', '')
        
        # РЎРѕС…СЂР°РЅСЏРµРј СЃС‚Р°СЂС‹Р№ СЃС‚Р°С‚СѓСЃ РґР»СЏ Р»РѕРіР°
        old_status = vacancy.status.status_vacancies_name
        
        # РћР±РЅРѕРІР»СЏРµРј СЃС‚Р°С‚СѓСЃ РІР°РєР°РЅСЃРёРё
        vacancy.status = archived_status
        vacancy.archived_at = timezone.now()
        vacancy.archive_reason = archive_reason
        vacancy.save()
        
        # РћС‚РїСЂР°РІР»СЏРµРј email СѓРІРµРґРѕРјР»РµРЅРёРµ
        email_sent = send_vacancy_archive_email(vacancy, archive_reason)
        
        # РЎРѕР·РґР°РµРј Р»РѕРі РґРµР№СЃС‚РІРёСЏ - РРЎРџР РђР’Р›Р•РќРћ
        action_type = get_or_create_action_type('vacancy_archived', 'Р’Р°РєР°РЅСЃРёСЏ Р°СЂС…РёРІРёСЂРѕРІР°РЅР°')
        AdminLog.objects.create(
            admin=request.user,
            action=action_type,
            target_company=vacancy.company,
            details=f'Р’Р°РєР°РЅСЃРёСЏ "{vacancy.position}" Р°СЂС…РёРІРёСЂРѕРІР°РЅР°. РџСЂРёС‡РёРЅР°: {archive_reason or "РќРµ СѓРєР°Р·Р°РЅР°"}. Email РѕС‚РїСЂР°РІР»РµРЅ: {"Р”Р°" if email_sent else "РќРµС‚"}'
        )
        
        if email_sent:
            messages.success(request, f'Р’Р°РєР°РЅСЃРёСЏ "{vacancy.position}" Р°СЂС…РёРІРёСЂРѕРІР°РЅР°. Email СѓРІРµРґРѕРјР»РµРЅРёРµ РѕС‚РїСЂР°РІР»РµРЅРѕ РєРѕРјРїР°РЅРёРё.')
        else:
            messages.warning(request, f'Р’Р°РєР°РЅСЃРёСЏ "{vacancy.position}" Р°СЂС…РёРІРёСЂРѕРІР°РЅР°, РЅРѕ РЅРµ СѓРґР°Р»РѕСЃСЊ РѕС‚РїСЂР°РІРёС‚СЊ email СѓРІРµРґРѕРјР»РµРЅРёРµ.')
        
        return redirect('admin_complaints')
    
    # GET Р·Р°РїСЂРѕСЃ - РїРѕРєР°Р·С‹РІР°РµРј С„РѕСЂРјСѓ РїРѕРґС‚РІРµСЂР¶РґРµРЅРёСЏ
    return render(request, 'admin_panel/confirm_archive.html', {
        'vacancy': vacancy,
        'pending_complaints_count': Complaint.objects.filter(status='pending').count(),
        'pending_companies_count': Company.objects.filter(status='pending').count(),
    })

@admin_required
def unarchive_vacancy(request, vacancy_id):
    """
    Р’РѕСЃСЃС‚Р°РЅРѕРІР»РµРЅРёРµ РІР°РєР°РЅСЃРёРё РёР· Р°СЂС…РёРІР°
    """
    vacancy = get_object_or_404(Vacancy, id=vacancy_id)
    
    # РџРѕР»СѓС‡Р°РµРј Р°РєС‚РёРІРЅС‹Р№ СЃС‚Р°С‚СѓСЃ (РїСЂРµРґРїРѕР»РѕР¶РёРј, С‡С‚Рѕ РѕРЅ РЅР°Р·С‹РІР°РµС‚СЃСЏ "РђРєС‚РёРІРЅР°СЏ")
    try:
        active_status = StatusVacancies.objects.get(status_vacancies_name='РђРєС‚РёРІРЅР°СЏ')
    except StatusVacancies.DoesNotExist:
        # Р•СЃР»Рё РЅРµС‚ "РђРєС‚РёРІРЅРѕР№", Р±РµСЂРµРј РїРµСЂРІС‹Р№ РґРѕСЃС‚СѓРїРЅС‹Р№ СЃС‚Р°С‚СѓСЃ РєСЂРѕРјРµ Р°СЂС…РёРІРЅРѕРіРѕ
        active_status = StatusVacancies.objects.exclude(status_vacancies_name='РђСЂС…РёРІРёСЂРѕРІР°РЅР°').first()
    
    if vacancy.status.status_vacancies_name == 'РђСЂС…РёРІРёСЂРѕРІР°РЅР°':
        vacancy.status = active_status
        vacancy.archived_at = None
        vacancy.archive_reason = ''
        vacancy.save()
        
        # РЎРѕР·РґР°РµРј Р»РѕРі РґРµР№СЃС‚РІРёСЏ - РРЎРџР РђР’Р›Р•РќРћ
        action_type = get_or_create_action_type('vacancy_unarchived', 'Р’Р°РєР°РЅСЃРёСЏ РІРѕСЃСЃС‚Р°РЅРѕРІР»РµРЅР°')
        AdminLog.objects.create(
            admin=request.user,
            action=action_type,
            target_company=vacancy.company,
            details=f'Р’Р°РєР°РЅСЃРёСЏ "{vacancy.position}" РІРѕСЃСЃС‚Р°РЅРѕРІР»РµРЅР° РёР· Р°СЂС…РёРІР°'
        )
        
        messages.success(request, f'Р’Р°РєР°РЅСЃРёСЏ "{vacancy.position}" РІРѕСЃСЃС‚Р°РЅРѕРІР»РµРЅР° РёР· Р°СЂС…РёРІР°.')
    
    return redirect('admin_complaints')

@login_required
def admin_profile(request):
    """РџСЂРѕС„РёР»СЊ Р°РґРјРёРЅРёСЃС‚СЂР°С‚РѕСЂР°"""
    # РџРѕР»СѓС‡Р°РµРј СЃС‚Р°С‚РёСЃС‚РёРєСѓ РґР»СЏ РѕС‚РѕР±СЂР°Р¶РµРЅРёСЏ
    total_users = User.objects.count()
    total_companies = Company.objects.count()
    total_vacancies = Vacancy.objects.count()
    pending_complaints = Complaint.objects.filter(status='pending').count()
    pending_companies_count = Company.objects.filter(status='pending').count()
    pending_complaints_count = Complaint.objects.filter(status='pending').count()
    
    # РџРѕР»СѓС‡Р°РµРј РїРѕСЃР»РµРґРЅРёРµ РґРµР№СЃС‚РІРёСЏ (РїСЂРёРјРµСЂ)
    recent_activity = [
        {
            'icon': 'user-check',
            'description': 'РћРґРѕР±СЂРµРЅР° РєРѕРјРїР°РЅРёСЏ "РўРµС…РЅРѕРџР°СЂРє"',
            'timestamp': timezone.now() - timedelta(hours=2)
        },
        {
            'icon': 'flag',
            'description': 'Р Р°СЃСЃРјРѕС‚СЂРµРЅР° Р¶Р°Р»РѕР±Р° РЅР° РІР°РєР°РЅСЃРёСЋ',
            'timestamp': timezone.now() - timedelta(hours=4)
        },
        {
            'icon': 'database',
            'description': 'РЎРѕР·РґР°РЅ СЂРµР·РµСЂРІРЅС‹Р№ Р±СЌРєР°Рї',
            'timestamp': timezone.now() - timedelta(days=1)
        }
    ]
    
    context = {
        'total_users': total_users,
        'total_companies': total_companies,
        'total_vacancies': total_vacancies,
        'pending_complaints': pending_complaints,
        'pending_companies_count': pending_companies_count,
        'pending_complaints_count': pending_complaints_count,
        'recent_activity': recent_activity,
    }
    
    return render(request, 'admin_panel/admin_profile.html', context)


@login_required
def admin_profile_edit(request):
    """Р РµРґР°РєС‚РёСЂРѕРІР°РЅРёРµ РїСЂРѕС„РёР»СЏ Р°РґРјРёРЅРёСЃС‚СЂР°С‚РѕСЂР°"""
    if request.method == 'POST':
        form = AdminProfileEditForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'РџСЂРѕС„РёР»СЊ СѓСЃРїРµС€РЅРѕ РѕР±РЅРѕРІР»РµРЅ!')
            return redirect('admin_profile')
        else:
            messages.error(request, 'РџРѕР¶Р°Р»СѓР№СЃС‚Р°, РёСЃРїСЂР°РІСЊС‚Рµ РѕС€РёР±РєРё РІ С„РѕСЂРјРµ.')
    else:
        form = AdminProfileEditForm(instance=request.user)
    
    # РЎС‚Р°С‚РёСЃС‚РёРєР° РґР»СЏ СЃР°Р№РґР±Р°СЂР°
    pending_companies_count = Company.objects.filter(status='pending').count()
    pending_complaints_count = Complaint.objects.filter(status='pending').count()
    
    context = {
        'form': form,
        'pending_companies_count': pending_companies_count,
        'pending_complaints_count': pending_complaints_count,
    }
    
    return render(request, 'admin_panel/admin_profile_edit.html', context)



