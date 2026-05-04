from __future__ import annotations

import csv
import io
import os
import secrets
from collections import Counter
from datetime import datetime
from io import BytesIO
from functools import wraps
from urllib.parse import quote, urljoin

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import logout as auth_logout
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.urls import reverse
from django.shortcuts import redirect, render
from reportlab.graphics import renderPDF
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from home.api_client import api_base_url, api_delete, api_get, api_patch, api_post, clear_tokens
from .forms import CompanyRegistrationApiForm

ERROR_FIELD_LABELS = {
    'name': 'Название компании',
    'number': 'ИНН',
    'industry': 'Сфера деятельности',
    'description': 'Описание',
    'email': 'Email',
    'phone': 'Телефон',
    'password': 'Пароль',
    'password1': 'Пароль',
    'password2': 'Подтверждение пароля',
    'old_password': 'Старый пароль',
    'new_password': 'Новый пароль',
    'new_password_confirm': 'Подтверждение нового пароля',
    'verification_document': 'Документ',
    'username': 'Логин',
    'first_name': 'Имя',
    'last_name': 'Фамилия',
    'birth_date': 'Дата рождения',
    'resume': 'Резюме',
    'position': 'Должность',
    'city': 'Город',
    'category': 'Категория',
    'experience': 'Опыт',
    'salary_min': 'Зарплата от',
    'salary_max': 'Зарплата до',
    'requirements': 'Требования',
    'work_conditions_details': 'Детали условий',
}

COMPANY_PROFILE_EMAIL_CHANGE_SESSION_KEY = 'pending_company_profile_email_change'
COMPANY_PROFILE_EMAIL_CHANGE_TARGET_SESSION_KEY = 'pending_company_profile_email_change_target'
COMPANY_PROFILE_EMAIL_CHANGE_TARGET_OWNER = 'company'
COMPANY_PROFILE_EMAIL_CHANGE_TARGET_EMPLOYEE = 'employee'


def _safe_json(resp):
    try:
        return resp.json()
    except Exception:
        return None


def _absolute_api_media_url(value: str | None) -> str | None:
    if not value:
        return value

    text = str(value).strip()
    if not text:
        return None

    if text.startswith(('http://', 'https://')):
        return text

    if text.startswith('//'):
        return f'https:{text}'

    return urljoin(api_base_url(), text)


def _results(payload):
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


def _first_error(payload, default: str) -> str:
    if isinstance(payload, str) and payload.strip():
        return payload.strip()

    if isinstance(payload, list):
        for item in payload:
            text = _first_error(item, '')
            if text:
                return text

    if isinstance(payload, dict):
        for key in ('detail', 'error', 'message'):
            if key in payload:
                text = _first_error(payload.get(key), '')
                if text:
                    return text
        for key, value in payload.items():
            text = _first_error(value, '')
            if text:
                if key in ('non_field_errors', '__all__'):
                    return text
                label = ERROR_FIELD_LABELS.get(str(key), str(key))
                return f'{label}: {text}'

    return default


def _is_english_ui(request: HttpRequest) -> bool:
    return str(getattr(request, 'LANGUAGE_CODE', '') or '').lower().startswith('en')


def _ui_text(request: HttpRequest, ru_text: str, en_text: str) -> str:
    return en_text if _is_english_ui(request) else ru_text


def _apply_api_errors_to_company_form(form: CompanyRegistrationApiForm, payload, default_message: str) -> None:
    field_map = {
        'name': 'company_name',
        'number': 'company_number',
        'industry': 'industry',
        'description': 'description',
        'email': 'email',
        'phone': 'phone',
        'password': 'password1',
        'password1': 'password1',
        'password2': 'password2',
        'verification_document': 'verification_document',
        'username': 'email',
    }

    if not isinstance(payload, dict):
        form.add_error(None, _first_error(payload, default_message))
        return

    added = False
    for key, value in payload.items():
        message_text = _first_error(value, '')
        if not message_text:
            continue

        target_field = field_map.get(key)
        if key in ('detail', 'error', 'message', 'non_field_errors'):
            target_field = None

        form.add_error(target_field, message_text)
        added = True

    if not added:
        form.add_error(None, _first_error(payload, default_message))


def _api_user(request: HttpRequest) -> dict:
    return request.session.get('api_user') or {}


def _user_type(request: HttpRequest) -> str:
    return str(_api_user(request).get('user_type') or '').lower()


def _employee_role(request: HttpRequest) -> str:
    role = str(_api_user(request).get('employee_role') or '').lower()
    if role:
        return role

    if not request.session.get('api_access'):
        return ''

    profile, _ = _load_user_profile(request)
    if isinstance(profile, dict):
        role = str(profile.get('employee_role') or '').lower()
        if role:
            session_user = _api_user(request)
            session_user['employee_role'] = role
            session_user['company_id'] = profile.get('company_id')
            session_user['company_name'] = profile.get('company_name')
            request.session['api_user'] = session_user
            return role

    return ''


def _normalize_email(value: str | None) -> str:
    return str(value or '').strip().lower()


def _clear_pending_company_profile_email_change(request: HttpRequest) -> None:
    request.session.pop(COMPANY_PROFILE_EMAIL_CHANGE_SESSION_KEY, None)
    request.session.pop(COMPANY_PROFILE_EMAIL_CHANGE_TARGET_SESSION_KEY, None)


def _store_pending_company_profile_email_change(request: HttpRequest, email: str, target: str) -> None:
    request.session[COMPANY_PROFILE_EMAIL_CHANGE_SESSION_KEY] = _normalize_email(email)
    request.session[COMPANY_PROFILE_EMAIL_CHANGE_TARGET_SESSION_KEY] = target


def _resolve_company_profile_email_change_target(request: HttpRequest) -> str:
    target = str(request.session.get(COMPANY_PROFILE_EMAIL_CHANGE_TARGET_SESSION_KEY) or '').strip().lower()
    if target == COMPANY_PROFILE_EMAIL_CHANGE_TARGET_EMPLOYEE:
        return COMPANY_PROFILE_EMAIL_CHANGE_TARGET_EMPLOYEE
    return COMPANY_PROFILE_EMAIL_CHANGE_TARGET_OWNER


def _company_email_change_back_route(target: str) -> str:
    if target == COMPANY_PROFILE_EMAIL_CHANGE_TARGET_EMPLOYEE:
        return 'edit_employee_profile'
    return 'edit_company_profile'


def _company_email_change_done_route(target: str) -> str:
    if target == COMPANY_PROFILE_EMAIL_CHANGE_TARGET_EMPLOYEE:
        return 'employee_profile'
    return 'company_profile'


def api_login_required(view_func):
    @wraps(view_func)
    def _wrapped(request: HttpRequest, *args, **kwargs):
        if not request.session.get('api_access'):
            next_url = request.get_full_path() if request.get_full_path() else '/'
            return redirect(f"/login/?next={quote(next_url)}")
        return view_func(request, *args, **kwargs)

    return _wrapped


def company_staff_required(view_func):
    @wraps(view_func)
    @api_login_required
    def _wrapped(request: HttpRequest, *args, **kwargs):
        if _user_type(request) not in ('company', 'staff'):
            messages.error(request, 'Доступ только для компании и сотрудников')
            return redirect('home_comp')
        return view_func(request, *args, **kwargs)

    return _wrapped


def company_owner_required(view_func):
    @wraps(view_func)
    @api_login_required
    def _wrapped(request: HttpRequest, *args, **kwargs):
        if _user_type(request) != 'company':
            messages.error(request, 'Доступ только для владельца компании')
            return redirect('home_comp')
        return view_func(request, *args, **kwargs)

    return _wrapped


def content_manager_required(view_func):
    @wraps(view_func)
    @company_staff_required
    def _wrapped(request: HttpRequest, *args, **kwargs):
        if _user_type(request) != 'staff':
            messages.error(request, 'Раздел доступен только сотрудникам')
            return redirect('home_comp')

        if _employee_role(request) != 'content_manager':
            messages.error(request, 'Раздел доступен только контент-менеджеру')
            return redirect('home_comp')

        return view_func(request, *args, **kwargs)

    return _wrapped


def company_owner_or_hr_required(view_func):
    @wraps(view_func)
    @company_staff_required
    def _wrapped(request: HttpRequest, *args, **kwargs):
        user_type = _user_type(request)
        if user_type == 'company':
            return view_func(request, *args, **kwargs)

        if user_type == 'staff' and _employee_role(request) == 'hr':
            return view_func(request, *args, **kwargs)

        messages.error(request, 'Раздел недоступен для вашей роли')
        if user_type == 'staff' and _employee_role(request) == 'content_manager':
            return redirect('content_manager_videos')
        return redirect('home_comp')

    return _wrapped


def _load_company_me(request: HttpRequest) -> tuple[dict | None, str | None]:
    try:
        resp = api_get(request, 'company/me/')
        data = _safe_json(resp)
        if resp.status_code >= 400 or not isinstance(data, dict):
            return None, _first_error(data, 'Не удалось получить данные компании')
        return data, None
    except Exception:
        return None, 'Ошибка сети при получении данных компании'


def _load_user_profile(request: HttpRequest) -> tuple[dict | None, str | None]:
    try:
        resp = api_get(request, 'user/profile/')
        data = _safe_json(resp)
        if resp.status_code >= 400 or not isinstance(data, dict):
            return None, _first_error(data, 'Не удалось получить профиль пользователя')
        return data, None
    except Exception:
        return None, 'Ошибка сети при получении профиля пользователя'



def _extract_next_link(payload) -> str | None:
    if isinstance(payload, dict):
        next_link = payload.get('next')
        if isinstance(next_link, str) and next_link:
            return next_link
    return None


def _fetch_paginated(request: HttpRequest, path: str, params: dict | None = None, max_pages: int = 30) -> tuple[list, str | None]:
    rows: list = []
    current_path = path
    current_params = dict(params or {})
    page_count = 0

    while current_path and page_count < max_pages:
        try:
            response = api_get(request, current_path, params=current_params)
            payload = _safe_json(response) or {}
            if response.status_code >= 400:
                return rows, _first_error(payload, 'Не удалось получить данные из API')

            rows.extend(_results(payload))
            current_path = _extract_next_link(payload)
            current_params = None
            page_count += 1
        except Exception:
            return rows, 'Ошибка сети при обращении к API'

    return rows, None


def _parse_bool(value, default: bool = True) -> bool:
    if value is None:
        return default
    normalized = str(value).strip().lower()
    if normalized in ('1', 'true', 'yes', 'y', 'on', 'да', 'д'):
        return True
    if normalized in ('0', 'false', 'no', 'n', 'off', 'нет', 'н'):
        return False
    return default


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
    """Returns (regular, bold) font names suitable for Cyrillic in PDF."""
    windir = os.environ.get('WINDIR', r'C:\Windows')
    candidates = [
        (os.path.join(windir, 'Fonts', 'arial.ttf'), os.path.join(windir, 'Fonts', 'arialbd.ttf')),
        ('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'),
        ('/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf', '/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf'),
    ]

    for index, (regular_path, bold_path) in enumerate(candidates, start=1):
        regular_name = f'WorkMPTSans{index}'
        bold_name = f'WorkMPTSansBold{index}'

        regular_ok = _register_ttf_font(regular_name, regular_path)
        bold_ok = _register_ttf_font(bold_name, bold_path)

        if regular_ok and bold_ok:
            return regular_name, bold_name
        if regular_ok:
            return regular_name, regular_name

    return 'Helvetica', 'Helvetica-Bold'


def _finish_company_account_session(request: HttpRequest) -> HttpResponse:
    clear_tokens(request)
    request.session.pop('ui_theme', None)
    request.session.pop('ui_font_size', None)
    request.session.pop('font_size', None)
    request.session.pop('theme', None)
    auth_logout(request)
    response = redirect('home_page')
    response.set_cookie('reset_ui_preferences', '1', max_age=120, path='/', samesite='Lax')
    response.set_cookie(
        settings.LANGUAGE_COOKIE_NAME,
        'ru',
        max_age=60 * 60 * 24 * 365,
        path='/',
        samesite='Lax',
    )
    return response


def account_pending(request: HttpRequest) -> HttpResponse:
    return render(request, 'auth/account_pending.html')


def home_comp(request: HttpRequest) -> HttpResponse:
    active_applicants_count = 0
    successful_hires_count = 0
    returning_companies_percentage = 0
    avg_hire_time = 48

    try:
        applicants_resp = api_get(request, 'applicants/', params={'page': 1})
        applicants_data = _safe_json(applicants_resp) or {}
        if isinstance(applicants_data, dict):
            active_applicants_count = int(applicants_data.get('count') or 0)
    except Exception:
        pass

    try:
        responses_resp = api_get(request, 'responses/', params={'page': 1})
        responses_data = _safe_json(responses_resp) or {}
        if isinstance(responses_data, dict):
            successful_hires_count = int(responses_data.get('count') or 0)
    except Exception:
        pass

    try:
        companies_resp = api_get(request, 'companies/', params={'page': 1})
        companies_data = _safe_json(companies_resp) or {}
        if isinstance(companies_data, dict):
            companies_count = int(companies_data.get('count') or 0)
            returning_companies_percentage = 0 if companies_count == 0 else 100
    except Exception:
        pass

    return render(
        request,
        'compani/homeComp.html',
        {
            'active_applicants_count': active_applicants_count,
            'successful_hires_count': successful_hires_count,
            'returning_companies_percentage': returning_companies_percentage,
            'avg_hire_time': avg_hire_time,
            'api_user': _api_user(request),
        },
    )


def company_register(request: HttpRequest) -> HttpResponse:
    if request.method == 'POST':
        form = CompanyRegistrationApiForm(request.POST, request.FILES)
        if not form.is_valid():
            return render(request, 'auth/register_comp.html', {'form': form})

        submit_action = (request.POST.get('submit_action') or 'register').strip().lower()
        is_resubmit = submit_action == 'resubmit'
        api_endpoint = 'user/resubmit_company/' if is_resubmit else 'user/register_company/'

        cleaned = form.cleaned_data
        payload = {
            'name': cleaned['company_name'],
            'number': cleaned['company_number'],
            'industry': cleaned['industry'],
            'description': cleaned['description'],
            'email': cleaned['email'],
            'username': cleaned['email'],
            'phone': cleaned['phone'],
            'password': cleaned['password1'],
            'password2': cleaned['password2'],
        }

        try:
            resp = api_post(
                request,
                api_endpoint,
                data=payload,
                files={'verification_document': cleaned['verification_document']},
            )
            data = _safe_json(resp)
            if resp.status_code >= 400:
                _apply_api_errors_to_company_form(
                    form,
                    data,
                    'Не удалось зарегистрировать компанию. Проверьте введенные данные.',
                )
                return render(request, 'auth/register_comp.html', {'form': form})

            if is_resubmit:
                messages.success(request, 'Данные компании повторно отправлены на проверку администратором.')
            else:
                messages.success(request, 'Данные компании отправлены на проверку администратором.')
            return redirect('account_pending')
        except Exception:
            form.add_error(None, 'Ошибка сети при регистрации компании. Попробуйте еще раз.')
            return render(request, 'auth/register_comp.html', {'form': form})

    return render(request, 'auth/register_comp.html', {'form': CompanyRegistrationApiForm()})


@company_owner_or_hr_required
def company_profile(request: HttpRequest) -> HttpResponse:
    company, company_error = _load_company_me(request)
    if company_error:
        messages.error(request, company_error)
        company = {}

    vacancies = []
    employees = []

    try:
        vacancies_resp = api_get(request, 'company/vacancies/', params={'page': 1, 'archived': 1})
        vacancies_json = _safe_json(vacancies_resp) or {}
        if vacancies_resp.status_code < 400:
            vacancies = _results(vacancies_json)
    except Exception:
        pass

    try:
        employees_resp = api_get(request, 'company/employees/', params={'page': 1})
        employees_json = _safe_json(employees_resp) or {}
        if employees_resp.status_code < 400:
            employees = _results(employees_json)
    except Exception:
        employees = []

    return render(
        request,
        'compani/profile/company_profile.html',
        {
            'company': company,
            'vacancies': vacancies,
            'employees': employees,
            'is_owner': _user_type(request) == 'company',
            'api_user': _api_user(request),
        },
    )


@company_owner_required
def edit_company_profile(request: HttpRequest) -> HttpResponse:
    company, company_error = _load_company_me(request)
    user_profile, _ = _load_user_profile(request)
    if not user_profile:
        user_profile = {}

    if request.method == 'POST':
        requested_email = _normalize_email(request.POST.get('email'))
        current_email = _normalize_email(user_profile.get('email') or _api_user(request).get('email'))
        company_payload = {
            'name': request.POST.get('company_name') or '',
            'number': request.POST.get('company_number') or '',
            'industry': request.POST.get('industry') or '',
            'description': request.POST.get('description') or '',
        }
        company_payload = {k: v for k, v in company_payload.items() if v != ''}

        user_payload = {
            'phone': request.POST.get('phone') or '',
        }
        user_payload = {k: v for k, v in user_payload.items() if v != ''}

        try:
            company_updated = False
            contact_updated = False
            company_resp = api_patch(request, 'company/me/', json=company_payload)
            company_data = _safe_json(company_resp)
            if company_resp.status_code >= 400:
                messages.error(request, _first_error(company_data, 'Не удалось обновить профиль компании'))
                company = company_data if isinstance(company_data, dict) else company
                return render(
                    request,
                    'compani/profile/edit_company_profile.html',
                    {
                        'company': company if isinstance(company, dict) else {},
                        'user_profile': user_profile,
                        'pending_email_change': request.session.get(COMPANY_PROFILE_EMAIL_CHANGE_SESSION_KEY),
                        'api_user': _api_user(request),
                    },
                )

            if isinstance(company_data, dict):
                company = company_data
            company_updated = bool(company_payload)

            if user_payload:
                user_resp = api_patch(request, 'user/profile/', json=user_payload)
                user_data = _safe_json(user_resp)
                if user_resp.status_code >= 400:
                    messages.warning(request, _first_error(user_data, 'Контактные данные не обновлены.'))
                elif isinstance(user_data, dict):
                    user_profile = user_data
                    session_user = _api_user(request)
                    session_user['email'] = user_data.get('email', session_user.get('email'))
                    session_user['phone'] = user_data.get('phone', session_user.get('phone'))
                    request.session['api_user'] = session_user
                    contact_updated = True

            if requested_email and requested_email != current_email:
                change_resp = api_post(
                    request,
                    'user/profile/request-email-change/',
                    json={'email': requested_email},
                )
                change_data = _safe_json(change_resp)
                if change_resp.status_code >= 400:
                    if company_updated or contact_updated:
                        messages.success(request, 'Остальные данные профиля компании сохранены.')
                    messages.error(request, _first_error(change_data, 'Не удалось отправить код подтверждения на новый email.'))
                else:
                    _store_pending_company_profile_email_change(
                        request,
                        requested_email,
                        COMPANY_PROFILE_EMAIL_CHANGE_TARGET_OWNER,
                    )
                    messages.success(request, 'Код подтверждения отправлен на новый email.')
                    if company_updated or contact_updated:
                        messages.info(request, 'Остальные данные профиля компании уже сохранены.')
                    return redirect('company_profile_email_change_verify')
            elif company_updated or contact_updated:
                _clear_pending_company_profile_email_change(request)
                messages.success(request, 'Профиль компании обновлен.')
                return redirect('company_profile')
            else:
                messages.info(request, 'Изменений для сохранения нет.')
        except Exception:
            messages.error(request, 'Ошибка сети при обновлении профиля компании')

    if company_error:
        messages.error(request, company_error)
    if not company:
        company = {}
    if not user_profile:
        user_profile = {}

    return render(
        request,
        'compani/profile/edit_company_profile.html',
        {
            'company': company,
            'user_profile': user_profile,
            'pending_email_change': request.session.get(COMPANY_PROFILE_EMAIL_CHANGE_SESSION_KEY),
            'api_user': _api_user(request),
        },
    )


@company_staff_required
def company_profile_email_change_verify(request: HttpRequest) -> HttpResponse:
    pending_email = _normalize_email(request.session.get(COMPANY_PROFILE_EMAIL_CHANGE_SESSION_KEY))
    target = _resolve_company_profile_email_change_target(request)
    back_route = _company_email_change_back_route(target)
    done_route = _company_email_change_done_route(target)

    if request.GET.get('change') == '1':
        _clear_pending_company_profile_email_change(request)
        return redirect(back_route)

    if not pending_email:
        messages.info(request, 'Сначала укажите новый email в профиле.')
        return redirect(back_route)

    if request.method == 'POST':
        code = str(request.POST.get('code') or '').strip()
        if not code.isdigit() or len(code) != 6:
            messages.error(request, 'Введите корректный 6-значный код.')
        else:
            try:
                resp = api_post(
                    request,
                    'user/profile/confirm-email-change/',
                    json={'email': pending_email, 'code': code},
                )
                data = _safe_json(resp)
                if resp.status_code >= 400:
                    messages.error(request, _first_error(data, 'Не удалось подтвердить новый email.'))
                else:
                    session_user = _api_user(request)
                    session_user['email'] = (data or {}).get('email', pending_email)
                    request.session['api_user'] = session_user
                    _clear_pending_company_profile_email_change(request)
                    messages.success(request, 'Email успешно подтвержден и обновлен.')
                    return redirect(done_route)
            except Exception:
                messages.error(request, 'Ошибка сети при подтверждении нового email.')

    return render(
        request,
        'profile_verify_email.html',
        {
            'email': pending_email,
            'api_user': _api_user(request),
            'change_email_url': f"{reverse('company_profile_email_change_verify')}?change=1",
        },
    )


@company_owner_required
def verify_password_and_save(request: HttpRequest) -> HttpResponse:
    return redirect('edit_company_profile')


@company_staff_required
def change_password_request(request: HttpRequest) -> HttpResponse:
    password_form = {
        'old_password': '',
        'new_password': '',
        'new_password_confirm': '',
    }

    if request.method == 'POST':
        password_form = {
            'old_password': request.POST.get('old_password') or '',
            'new_password': request.POST.get('new_password') or '',
            'new_password_confirm': request.POST.get('new_password_confirm') or '',
        }

        if not all(password_form.values()):
            messages.error(request, 'Заполните все поля для смены пароля.')
        elif password_form['new_password'] != password_form['new_password_confirm']:
            messages.error(request, 'Новый пароль и подтверждение не совпадают.')
        else:
            try:
                password_resp = api_post(request, 'user/change-password/', json=password_form)
                password_data = _safe_json(password_resp)
                if password_resp.status_code >= 400:
                    messages.error(request, _first_error(password_data, 'Не удалось сменить пароль.'))
                else:
                    messages.success(request, _first_error(password_data, 'Пароль успешно изменен.'))
                    return redirect('company_profile')
            except Exception:
                messages.error(request, 'Ошибка сети при смене пароля.')

        password_form = {
            'old_password': '',
            'new_password': '',
            'new_password_confirm': '',
        }

    return render(
        request,
        'compani/profile/change_company_password.html',
        {
            'password_form': password_form,
            'api_user': _api_user(request),
        },
    )


def change_password_confirm(request: HttpRequest, uidb64: str, token: str) -> HttpResponse:
    return redirect('password_reset_request')


@company_owner_required
def hr_agents_list(request: HttpRequest) -> HttpResponse:
    company, _ = _load_company_me(request)

    if request.method == 'POST' and request.POST.get('delete') == 'true':
        employee_id = request.POST.get('employee_id')
        if employee_id:
            try:
                delete_resp = api_delete(request, f'company/employees/{employee_id}/')
                if delete_resp.status_code >= 400:
                    delete_data = _safe_json(delete_resp)
                    messages.error(request, _first_error(delete_data, 'Не удалось удалить HR-агента'))
                else:
                    messages.success(request, 'HR-агент удален')
            except Exception:
                messages.error(request, 'Ошибка сети при удалении HR-агента')
        return redirect('hr_agents_list')

    hr_agents = []
    try:
        resp = api_get(request, 'company/employees/', params={'page': 1})
        data = _safe_json(resp) or {}
        if resp.status_code >= 400:
            messages.error(request, _first_error(data, 'Не удалось получить список сотрудников'))
        else:
            employees = _results(data)
            hr_agents = [employee for employee in employees if employee.get('role') == 'hr']
    except Exception:
        messages.error(request, 'Ошибка сети при загрузке HR-агентов')

    search = (request.GET.get('search') or '').strip().lower()
    if search:
        hr_agents = [
            agent for agent in hr_agents
            if search in str(agent.get('first_name', '')).lower()
            or search in str(agent.get('last_name', '')).lower()
            or search in str(agent.get('email', '')).lower()
        ]

    return render(
        request,
        'compani/hrCRUD/hr_agents_list.html',
        {
            'company': company or {},
            'hr_agents': hr_agents,
            'search': request.GET.get('search', ''),
            'api_user': _api_user(request),
        },
    )


@company_owner_required
def hr_agent_create(request: HttpRequest) -> HttpResponse:
    form_data = {
        'first_name': '',
        'last_name': '',
        'email': '',
    }

    if request.method == 'POST':
        form_data = {
            'first_name': request.POST.get('first_name', ''),
            'last_name': request.POST.get('last_name', ''),
            'email': request.POST.get('email', ''),
        }
        password1 = request.POST.get('password1') or ''
        password2 = request.POST.get('password2') or ''

        if password1 != password2:
            messages.error(request, 'Пароли не совпадают')
            return render(
                request,
                'compani/hrCRUD/hr_agent_form.html',
                {'title': 'Создать HR-агента', 'form_data': form_data, 'is_edit': False, 'api_user': _api_user(request)},
            )

        payload = {
            'first_name': form_data['first_name'],
            'last_name': form_data['last_name'],
            'email': form_data['email'],
            'password': password1,
            'role': 'hr',
        }

        try:
            resp = api_post(request, 'company/employees/', json=payload)
            data = _safe_json(resp)
            if resp.status_code >= 400:
                messages.error(request, _first_error(data, 'Не удалось создать HR-агента'))
            else:
                messages.success(request, 'HR-агент создан')
                return redirect('hr_agents_list')
        except Exception:
            messages.error(request, 'Ошибка сети при создании HR-агента')

    return render(
        request,
        'compani/hrCRUD/hr_agent_form.html',
        {'title': 'Создать HR-агента', 'form_data': form_data, 'is_edit': False, 'api_user': _api_user(request)},
    )


@company_owner_required
def hr_agent_edit(request: HttpRequest, employee_id: int) -> HttpResponse:
    employee = None
    try:
        employee_resp = api_get(request, f'company/employees/{employee_id}/')
        employee_data = _safe_json(employee_resp)
        if employee_resp.status_code >= 400 or not isinstance(employee_data, dict):
            messages.error(request, _first_error(employee_data, 'HR-агент не найден'))
            return redirect('hr_agents_list')
        employee = employee_data
    except Exception:
        messages.error(request, 'Ошибка сети при загрузке HR-агента')
        return redirect('hr_agents_list')

    if request.method == 'POST':
        payload = {
            'first_name': request.POST.get('first_name') or employee.get('first_name') or '',
            'last_name': request.POST.get('last_name') or employee.get('last_name') or '',
            'role': 'hr',
            'is_active': request.POST.get('is_active') == 'on',
        }

        try:
            patch_resp = api_patch(request, f'company/employees/{employee_id}/', json=payload)
            patch_data = _safe_json(patch_resp)
            if patch_resp.status_code >= 400:
                messages.error(request, _first_error(patch_data, 'Не удалось обновить HR-агента'))
            else:
                messages.success(request, 'HR-агент обновлен')
                return redirect('hr_agents_list')
        except Exception:
            messages.error(request, 'Ошибка сети при обновлении HR-агента')

    return render(
        request,
        'compani/hrCRUD/hr_agent_form.html',
        {'title': 'Редактировать HR-агента', 'form_data': employee, 'is_edit': True, 'api_user': _api_user(request)},
    )


@company_owner_required
def content_managers_list(request: HttpRequest) -> HttpResponse:
    company, _ = _load_company_me(request)

    if request.method == 'POST' and request.POST.get('delete') == 'true':
        employee_id = request.POST.get('employee_id')
        if employee_id:
            try:
                delete_resp = api_delete(request, f'company/employees/{employee_id}/')
                if delete_resp.status_code >= 400:
                    delete_data = _safe_json(delete_resp)
                    messages.error(request, _first_error(delete_data, 'Не удалось удалить контент-менеджера'))
                else:
                    messages.success(request, 'Контент-менеджер удален')
            except Exception:
                messages.error(request, 'Ошибка сети при удалении контент-менеджера')
        return redirect('content_managers_list')

    content_managers = []
    try:
        resp = api_get(request, 'company/employees/', params={'page': 1})
        data = _safe_json(resp) or {}
        if resp.status_code >= 400:
            messages.error(request, _first_error(data, 'Не удалось получить список сотрудников'))
        else:
            employees = _results(data)
            content_managers = [employee for employee in employees if employee.get('role') == 'content_manager']
    except Exception:
        messages.error(request, 'Ошибка сети при загрузке контент-менеджеров')

    search = (request.GET.get('search') or '').strip().lower()
    if search:
        content_managers = [
            manager for manager in content_managers
            if search in str(manager.get('first_name', '')).lower()
            or search in str(manager.get('last_name', '')).lower()
            or search in str(manager.get('email', '')).lower()
        ]

    return render(
        request,
        'compani/hrCRUD/content_managers_list.html',
        {
            'company': company or {},
            'content_managers': content_managers,
            'search': request.GET.get('search', ''),
            'api_user': _api_user(request),
        },
    )


@company_owner_required
def content_manager_create(request: HttpRequest) -> HttpResponse:
    form_data = {
        'first_name': '',
        'last_name': '',
        'email': '',
    }

    if request.method == 'POST':
        form_data = {
            'first_name': request.POST.get('first_name', ''),
            'last_name': request.POST.get('last_name', ''),
            'email': request.POST.get('email', ''),
        }
        password1 = request.POST.get('password1') or ''
        password2 = request.POST.get('password2') or ''

        if password1 != password2:
            messages.error(request, 'Пароли не совпадают')
            return render(
                request,
                'compani/hrCRUD/content_manager_form.html',
                {'title': 'Создать контент-менеджера', 'form_data': form_data, 'is_edit': False, 'api_user': _api_user(request)},
            )

        payload = {
            'first_name': form_data['first_name'],
            'last_name': form_data['last_name'],
            'email': form_data['email'],
            'password': password1,
            'role': 'content_manager',
        }

        try:
            resp = api_post(request, 'company/employees/', json=payload)
            data = _safe_json(resp)
            if resp.status_code >= 400:
                messages.error(request, _first_error(data, 'Не удалось создать контент-менеджера'))
            else:
                messages.success(request, 'Контент-менеджер создан')
                return redirect('content_managers_list')
        except Exception:
            messages.error(request, 'Ошибка сети при создании контент-менеджера')

    return render(
        request,
        'compani/hrCRUD/content_manager_form.html',
        {'title': 'Создать контент-менеджера', 'form_data': form_data, 'is_edit': False, 'api_user': _api_user(request)},
    )


@company_owner_required
def content_manager_edit(request: HttpRequest, employee_id: int) -> HttpResponse:
    employee = None
    try:
        employee_resp = api_get(request, f'company/employees/{employee_id}/')
        employee_data = _safe_json(employee_resp)
        if employee_resp.status_code >= 400 or not isinstance(employee_data, dict):
            messages.error(request, _first_error(employee_data, 'Контент-менеджер не найден'))
            return redirect('content_managers_list')
        employee = employee_data
    except Exception:
        messages.error(request, 'Ошибка сети при загрузке контент-менеджера')
        return redirect('content_managers_list')

    if request.method == 'POST':
        payload = {
            'first_name': request.POST.get('first_name') or employee.get('first_name') or '',
            'last_name': request.POST.get('last_name') or employee.get('last_name') or '',
            'role': 'content_manager',
            'is_active': request.POST.get('is_active') == 'on',
        }

        try:
            patch_resp = api_patch(request, f'company/employees/{employee_id}/', json=payload)
            patch_data = _safe_json(patch_resp)
            if patch_resp.status_code >= 400:
                messages.error(request, _first_error(patch_data, 'Не удалось обновить контент-менеджера'))
            else:
                messages.success(request, 'Контент-менеджер обновлен')
                return redirect('content_managers_list')
        except Exception:
            messages.error(request, 'Ошибка сети при обновлении контент-менеджера')

    return render(
        request,
        'compani/hrCRUD/content_manager_form.html',
        {'title': 'Редактировать контент-менеджера', 'form_data': employee, 'is_edit': True, 'api_user': _api_user(request)},
    )


def _normalize_vacancy_categories(payload) -> list[str]:
    categories: list[str] = []
    for item in _results(payload):
        if isinstance(item, dict):
            name = str(item.get('name') or '').strip()
        else:
            name = str(item or '').strip()
        if name and name not in categories:
            categories.append(name)
    return categories


def _load_vacancy_meta(request: HttpRequest) -> tuple[list, list, list[str]]:
    work_conditions = []
    statuses = []
    categories: list[str] = []
    try:
        wc_resp = api_get(request, 'work-conditions/', params={'page': 1})
        wc_data = _safe_json(wc_resp) or {}
        if wc_resp.status_code < 400:
            work_conditions = _results(wc_data)
    except Exception:
        pass
    try:
        status_resp = api_get(request, 'status-vacancies/', params={'page': 1})
        status_data = _safe_json(status_resp) or {}
        if status_resp.status_code < 400:
            statuses = _results(status_data)
    except Exception:
        pass
    try:
        cat_resp = api_get(request, 'vacancy-categories/', params={'page': 1})
        cat_data = _safe_json(cat_resp) or {}
        if cat_resp.status_code < 400:
            categories = _normalize_vacancy_categories(cat_data)
    except Exception:
        pass

    if not categories:
        categories = ['IT', 'Маркетинг', 'Продажи', 'HR']

    return work_conditions, statuses, categories


def _load_company_category_suggestions(request: HttpRequest) -> list[dict]:
    try:
        resp = api_get(request, 'company/vacancy-category-suggestions/', params={'page': 1})
        data = _safe_json(resp) or {}
        if resp.status_code < 400:
            suggestions = _results(data)
            if isinstance(suggestions, list):
                return [item for item in suggestions if isinstance(item, dict)]
    except Exception:
        pass
    return []


@company_owner_or_hr_required
def create_vacancy(request: HttpRequest) -> HttpResponse:
    form_data = {
        'position': '',
        'city': '',
        'category': 'IT',
        'experience': '',
        'salary_min': '',
        'salary_max': '',
        'description': '',
        'requirements': '',
        'work_conditions_details': '',
        'work_conditions': '',
        'status': '',
    }
    new_category = ''

    work_conditions, statuses, categories = _load_vacancy_meta(request)
    category_suggestions = _load_company_category_suggestions(request)

    if request.method == 'POST':
        form_data = {k: request.POST.get(k, '') for k in form_data.keys()}
        new_category = (request.POST.get('new_category') or '').strip()
        form_action = (request.POST.get('form_action') or 'create_vacancy').strip()

        if form_action == 'request_category':
            if not new_category:
                messages.error(request, 'Введите категорию перед отправкой на проверку.')
            else:
                try:
                    resp = api_post(
                        request,
                        'company/vacancy-category-suggestions/',
                        json={'name': new_category},
                    )
                    data = _safe_json(resp)
                    if resp.status_code >= 400:
                        category_error = ''
                        if isinstance(data, dict) and 'name' in data:
                            category_error = _first_error(data.get('name'), '')
                        messages.error(
                            request,
                            f'Категория: {category_error}' if category_error else _first_error(data, 'Не удалось отправить категорию на проверку.')
                        )
                    else:
                        messages.success(
                            request,
                            'Категория отправлена администратору на проверку.'
                        )
                        new_category = ''
                except Exception:
                    messages.error(request, 'Ошибка сети при отправке категории на проверку.')

            work_conditions, statuses, categories = _load_vacancy_meta(request)
            category_suggestions = _load_company_category_suggestions(request)
        else:
            payload = dict(form_data)

            if not payload.get('status') and statuses:
                payload['status'] = statuses[0].get('id')
            if not payload.get('work_conditions') and work_conditions:
                payload['work_conditions'] = work_conditions[0].get('id')

            try:
                resp = api_post(request, 'company/vacancies/', json=payload)
                data = _safe_json(resp)
                if resp.status_code >= 400:
                    messages.error(request, _first_error(data, 'Не удалось создать вакансию'))
                else:
                    messages.success(request, 'Вакансия создана')
                    return redirect('vacancy_list')
            except Exception:
                messages.error(request, 'Ошибка сети при создании вакансии')

    return render(
        request,
        'compani/vacancy/create_vacancy.html',
        {
            'form_data': form_data,
            'work_conditions': work_conditions,
            'statuses': statuses,
            'categories': categories,
            'new_category': new_category,
            'category_suggestions': category_suggestions,
            'api_user': _api_user(request),
        },
    )


@company_owner_or_hr_required
def edit_vacancy(request: HttpRequest, vacancy_id: int) -> HttpResponse:
    work_conditions, statuses, categories = _load_vacancy_meta(request)

    vacancy = None
    try:
        get_resp = api_get(request, f'company/vacancies/{vacancy_id}/')
        get_data = _safe_json(get_resp)
        if get_resp.status_code >= 400 or not isinstance(get_data, dict):
            messages.error(request, _first_error(get_data, 'Вакансия не найдена'))
            return redirect('vacancy_list')
        vacancy = get_data
    except Exception:
        messages.error(request, 'Ошибка сети при загрузке вакансии')
        return redirect('vacancy_list')

    if request.method == 'POST':
        payload = {
            'position': request.POST.get('position') or vacancy.get('position') or '',
            'city': request.POST.get('city') or vacancy.get('city') or '',
            'category': request.POST.get('category') or vacancy.get('category') or 'IT',
            'experience': request.POST.get('experience') or vacancy.get('experience') or '',
            'salary_min': request.POST.get('salary_min') or vacancy.get('salary_min') or '',
            'salary_max': request.POST.get('salary_max') or vacancy.get('salary_max') or '',
            'description': request.POST.get('description') or vacancy.get('description') or '',
            'requirements': request.POST.get('requirements') or vacancy.get('requirements') or '',
            'work_conditions_details': request.POST.get('work_conditions_details') or vacancy.get('work_conditions_details') or '',
            'work_conditions': request.POST.get('work_conditions') or vacancy.get('work_conditions') or '',
            'status': request.POST.get('status') or vacancy.get('status') or '',
        }
        try:
            patch_resp = api_patch(request, f'company/vacancies/{vacancy_id}/', json=payload)
            patch_data = _safe_json(patch_resp)
            if patch_resp.status_code >= 400:
                messages.error(request, _first_error(patch_data, 'Не удалось обновить вакансию'))
            else:
                messages.success(request, 'Вакансия обновлена')
                return redirect('vacancy_list')
        except Exception:
            messages.error(request, 'Ошибка сети при обновлении вакансии')

        vacancy.update(payload)

    return render(
        request,
        'compani/vacancy/edit_vacancy.html',
        {
            'vacancy': vacancy,
            'work_conditions': work_conditions,
            'statuses': statuses,
            'categories': categories,
            'api_user': _api_user(request),
        },
    )


@company_owner_or_hr_required
def archive_vacancy(request: HttpRequest, vacancy_id: int) -> HttpResponse:
    try:
        resp = api_post(request, f'company/vacancies/{vacancy_id}/archive/')
        data = _safe_json(resp)
        if resp.status_code >= 400:
            messages.error(request, _first_error(data, 'Не удалось архивировать вакансию'))
        else:
            messages.success(request, 'Вакансия отправлена в архив')
    except Exception:
        messages.error(request, 'Ошибка сети при архивации вакансии')
    return redirect('vacancy_list')


@company_owner_or_hr_required
def unarchive_vacancy(request: HttpRequest, vacancy_id: int) -> HttpResponse:
    try:
        resp = api_post(request, f'company/vacancies/{vacancy_id}/unarchive/')
        data = _safe_json(resp)
        if resp.status_code >= 400:
            messages.error(request, _first_error(data, 'Не удалось разархивировать вакансию'))
        else:
            messages.success(request, 'Вакансия возвращена из архива')
    except Exception:
        messages.error(request, 'Ошибка сети при разархивации вакансии')
    return redirect('vacancy_list')


@company_owner_or_hr_required
def vacancy_list(request: HttpRequest) -> HttpResponse:
    search = (request.GET.get('search') or '').strip().lower()
    current_status = (request.GET.get('status') or 'all').lower()

    all_vacancies = []
    try:
        all_resp = api_get(request, 'company/vacancies/', params={'page': 1, 'archived': 1})
        all_data = _safe_json(all_resp) or {}
        if all_resp.status_code >= 400:
            messages.error(request, _first_error(all_data, 'Не удалось загрузить вакансии'))
        else:
            all_vacancies = _results(all_data)
    except Exception:
        messages.error(request, 'Ошибка сети при загрузке вакансий')

    vacancies = list(all_vacancies)
    if current_status == 'active':
        vacancies = [vac for vac in vacancies if not vac.get('is_archived')]
    elif current_status == 'archived':
        vacancies = [vac for vac in vacancies if vac.get('is_archived')]

    if search:
        vacancies = [
            vac for vac in vacancies
            if search in str(vac.get('position', '')).lower()
            or search in str(vac.get('city', '')).lower()
            or search in str(vac.get('description', '')).lower()
        ]

    counts = {
        'total': len(all_vacancies),
        'active': len([vac for vac in all_vacancies if not vac.get('is_archived')]),
        'archived': len([vac for vac in all_vacancies if vac.get('is_archived')]),
    }

    return render(
        request,
        'compani/vacancy/vacancy_list.html',
        {
            'vacancies': vacancies,
            'counts': counts,
            'current_status': current_status,
            'search': request.GET.get('search', ''),
            'api_user': _api_user(request),
        },
    )


@company_owner_or_hr_required
def responses_list(request: HttpRequest) -> HttpResponse:
    if request.method == 'POST':
        response_id = request.POST.get('response_id')
        status_id = request.POST.get('status')
        if not response_id or not status_id:
            missing_data_text = _ui_text(request, 'Не хватает данных', 'Missing required data')
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'status': 'error', 'message': missing_data_text}, status=400)
            messages.error(
                request,
                _ui_text(request, 'Не хватает данных для обновления статуса', 'Missing data to update response status'),
            )
            return redirect('responses_list')

        try:
            resp = api_post(request, f'responses/{response_id}/update-status/', json={'status_id': status_id})
            data = _safe_json(resp)
            if resp.status_code >= 400:
                text = _first_error(data, _ui_text(request, 'Не удалось обновить статус отклика', 'Failed to update response status'))
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'status': 'error', 'message': text}, status=resp.status_code)
                messages.error(request, text)
            else:
                text = _first_error(data, _ui_text(request, 'Статус отклика обновлён', 'Response status updated'))
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'status': 'success', 'message': text})
                messages.success(request, text)
        except Exception:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'status': 'error', 'message': _ui_text(request, 'Ошибка сети', 'Network error')}, status=502)
            messages.error(
                request,
                _ui_text(
                    request,
                    'Ошибка сети при обновлении статуса отклика',
                    'Network error while updating response status',
                ),
            )

        return redirect('responses_list')

    def _restore_mojibake(text_value: str | None) -> str:
        raw = str(text_value or '')
        if not raw:
            return ''
        try:
            restored = raw.encode('cp1251').decode('utf-8')
        except Exception:
            return raw
        return restored or raw

    def _status_alias(status_name: str | None) -> str:
        normalized = _restore_mojibake(status_name).strip().lower()
        if not normalized:
            return ''
        if any(
            token in normalized
            for token in (
                '\u043e\u0442\u043f\u0440\u0430\u0432',
                'sent',
            )
        ):
            return 'sent'
        if any(
            token in normalized
            for token in (
                '\u043f\u0440\u0438\u0433\u043b\u0430\u0448',
                'invite',
            )
        ):
            return 'invited'
        if any(
            token in normalized
            for token in (
                '\u043e\u0442\u043a\u0430\u0437',
                '\u043e\u0442\u043a\u043b\u043e\u043d',
                'reject',
            )
        ):
            return 'rejected'
        return ''

    allowed_status_aliases = ('sent', 'invited', 'rejected')

    statuses = []
    status_by_id = {}
    try:
        statuses_resp = api_get(request, 'status-responses/', params={'page': 1})
        statuses_data = _safe_json(statuses_resp) or {}
        if statuses_resp.status_code < 400:
            raw_statuses = _results(statuses_data)
            alias_map = {}
            for item in raw_statuses:
                status_name = _restore_mojibake(item.get('status_response_name'))
                alias = _status_alias(status_name)
                if alias and alias not in alias_map:
                    alias_map[alias] = {**item, 'status_response_name': status_name}
            statuses = [alias_map[alias] for alias in allowed_status_aliases if alias in alias_map]
            if not statuses:
                statuses = [{**item, 'status_response_name': _restore_mojibake(item.get('status_response_name'))} for item in raw_statuses[:3]]
            status_by_id = {item.get('id'): item.get('status_response_name') for item in statuses}
    except Exception:
        statuses = []

    responses = []
    try:
        responses_resp = api_get(request, 'company/responses/', params={'page': 1})
        responses_data = _safe_json(responses_resp) or {}
        if responses_resp.status_code >= 400:
            messages.error(request, _first_error(responses_data, _ui_text(request, 'Не удалось загрузить отклики', 'Failed to load responses')))
        else:
            responses = _results(responses_data)
    except Exception:
        messages.error(request, _ui_text(request, 'Ошибка сети при загрузке откликов', 'Network error while loading responses'))

    if not statuses:
        alias_map = {}
        for item in responses:
            status_id = item.get('status')
            status_name = _restore_mojibake(item.get('status_name'))
            alias = _status_alias(status_name)
            if not status_id or not alias or alias in alias_map:
                continue
            if alias == 'invited':
                label = _ui_text(request, 'Приглашение', 'Invited')
            elif alias == 'rejected':
                label = _ui_text(request, 'Отказ', 'Rejected')
            else:
                label = _ui_text(request, 'Отправлено', 'Sent')
            alias_map[alias] = {'id': status_id, 'status_response_name': label}
        statuses = [alias_map[alias] for alias in allowed_status_aliases if alias in alias_map]
        status_by_id = {item.get('id'): item.get('status_response_name') for item in statuses}

    def _as_int(value):
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    applicant_ids = sorted({_as_int(r.get('applicants')) for r in responses if _as_int(r.get('applicants'))})
    vacancy_ids = sorted({_as_int(r.get('vacancy_id')) for r in responses if _as_int(r.get('vacancy_id'))})

    applicant_map = {}
    for applicant_id in applicant_ids:
        try:
            applicant_resp = api_get(request, f'applicants/{applicant_id}/')
            applicant_data = _safe_json(applicant_resp)
            if applicant_resp.status_code < 400 and isinstance(applicant_data, dict):
                applicant_data['avatar'] = _absolute_api_media_url(applicant_data.get('avatar'))
                applicant_data['resume_file'] = _absolute_api_media_url(applicant_data.get('resume_file'))
                applicant_map[applicant_id] = applicant_data
        except Exception:
            continue

    vacancy_map = {}
    for vacancy_id in vacancy_ids:
        try:
            vacancy_resp = api_get(request, f'company/vacancies/{vacancy_id}/')
            vacancy_data = _safe_json(vacancy_resp)
            if vacancy_resp.status_code < 400 and isinstance(vacancy_data, dict):
                vacancy_map[vacancy_id] = vacancy_data
        except Exception:
            continue

    chats, _ = _fetch_paginated(request, 'chats/', params={'page': 1})
    chat_map = {}
    for chat in chats:
        if not isinstance(chat, dict):
            continue

        vacancy_key = _as_int(chat.get('vacancy'))
        if vacancy_key is None:
            vacancy_key = _as_int((chat.get('vacancy_info') or {}).get('id'))

        applicant_key = _as_int(chat.get('applicant'))
        if applicant_key is None:
            applicant_key = _as_int((chat.get('applicant_info') or {}).get('id'))

        chat_id = _as_int(chat.get('id'))
        if vacancy_key and applicant_key and chat_id:
            chat_map[(vacancy_key, applicant_key)] = chat_id

    enriched = []
    for item in responses:
        status_name = _restore_mojibake(
            item.get('status_name')
            or status_by_id.get(item.get('status'))
            or _ui_text(request, 'Без статуса', 'No status')
        )
        status_alias = _status_alias(status_name) or 'sent'
        if status_alias == 'invited':
            status_name = _ui_text(request, 'Приглашение', 'Invited')
        elif status_alias == 'rejected':
            status_name = _ui_text(request, 'Отказ', 'Rejected')
        else:
            status_name = _ui_text(request, 'Отправлено', 'Sent')
        applicant_id = _as_int(item.get('applicants'))
        vacancy_id = _as_int(item.get('vacancy_id'))
        applicant = applicant_map.get(applicant_id) or {}
        vacancy = vacancy_map.get(vacancy_id) or {}
        chat_id = chat_map.get((vacancy_id, applicant_id))
        enriched.append(
            {
                'id': item.get('id'),
                'response_date': item.get('response_date'),
                'status': item.get('status'),
                'status_name': status_name,
                'status_name_lc': str(status_name).lower(),
                'status_alias': status_alias,
                'applicant_id': applicant_id,
                'vacancy_id': vacancy_id,
                'chat_id': chat_id,
                'applicant': applicant,
                'vacancy': vacancy,
                'applicant_name': item.get('applicant_name') or '',
                'vacancy_position': item.get('vacancy_position') or '',
                'company_name': item.get('company_name') or '',
            }
        )

    search = (request.GET.get('search') or '').strip().lower()
    current_status = (request.GET.get('status') or 'all').lower()

    if search:
        enriched = [
            item for item in enriched
            if search in str(item.get('applicant_name', '')).lower()
            or search in str(item.get('vacancy_position', '')).lower()
            or search in str(((item.get('applicant') or {}).get('user') or {}).get('email', '')).lower()
        ]

    if current_status != 'all':
        if current_status in allowed_status_aliases:
            enriched = [item for item in enriched if item.get('status_alias') == current_status]
        else:
            current_status = 'all'

    def _status_alias_from_response(payload: dict) -> str:
        alias = _status_alias(payload.get('status_name'))
        return alias or 'sent'

    counts = {
        'total': len(responses),
        'sent': len([item for item in responses if _status_alias_from_response(item) == 'sent']),
        'invited': len([item for item in responses if _status_alias_from_response(item) == 'invited']),
        'rejected': len([item for item in responses if _status_alias_from_response(item) == 'rejected']),
    }

    company, _ = _load_company_me(request)

    return render(
        request,
        'compani/responses_list.html',
        {
            'company': company or {},
            'responses': enriched,
            'statuses': statuses,
            'counts': counts,
            'current_status': current_status,
            'search': request.GET.get('search', ''),
            'api_user': _api_user(request),
        },
    )


@company_staff_required
def employee_profile(request: HttpRequest) -> HttpResponse:
    if _user_type(request) != 'staff':
        messages.error(request, 'Профиль сотрудника доступен только для staff')
        return redirect('home_comp')

    profile, err = _load_user_profile(request)
    if err:
        messages.error(request, err)
        profile = {}

    vacancies = []
    try:
        vacancies_resp = api_get(request, 'company/vacancies/', params={'page': 1})
        vacancies_data = _safe_json(vacancies_resp) or {}
        if vacancies_resp.status_code < 400:
            vacancies = _results(vacancies_data)
    except Exception:
        pass

    return render(
        request,
        'compani/employee_profile.html',
        {
            'profile': profile,
            'vacancies': vacancies,
            'api_user': _api_user(request),
        },
    )


@company_staff_required
def edit_employee_profile(request: HttpRequest) -> HttpResponse:
    if _user_type(request) != 'staff':
        messages.error(request, 'Редактирование профиля сотрудника доступно только для staff')
        return redirect('home_comp')

    profile, _ = _load_user_profile(request)
    if not profile:
        profile = {}

    if request.method == 'POST':
        requested_email = _normalize_email(request.POST.get('email'))
        current_email = _normalize_email(profile.get('email') or _api_user(request).get('email'))
        payload = {
            'first_name': request.POST.get('first_name') or '',
            'last_name': request.POST.get('last_name') or '',
            'phone': request.POST.get('phone') or '',
        }
        payload = {k: v for k, v in payload.items() if v != ''}

        try:
            profile_updated = False
            if payload:
                resp = api_patch(request, 'user/profile/', json=payload)
                data = _safe_json(resp)
                if resp.status_code >= 400:
                    messages.error(request, _first_error(data, 'Не удалось обновить профиль сотрудника'))
                else:
                    profile = data if isinstance(data, dict) else profile
                    session_user = _api_user(request)
                    session_user['first_name'] = profile.get('first_name', session_user.get('first_name'))
                    session_user['last_name'] = profile.get('last_name', session_user.get('last_name'))
                    session_user['email'] = profile.get('email', session_user.get('email'))
                    session_user['phone'] = profile.get('phone', session_user.get('phone'))
                    request.session['api_user'] = session_user
                    profile_updated = True

            if requested_email and requested_email != current_email:
                change_resp = api_post(
                    request,
                    'user/profile/request-email-change/',
                    json={'email': requested_email},
                )
                change_data = _safe_json(change_resp)
                if change_resp.status_code >= 400:
                    if profile_updated:
                        messages.success(request, 'Остальные данные профиля сотрудника сохранены.')
                    messages.error(request, _first_error(change_data, 'Не удалось отправить код подтверждения на новый email.'))
                else:
                    _store_pending_company_profile_email_change(
                        request,
                        requested_email,
                        COMPANY_PROFILE_EMAIL_CHANGE_TARGET_EMPLOYEE,
                    )
                    messages.success(request, 'Код подтверждения отправлен на новый email.')
                    if profile_updated:
                        messages.info(request, 'Остальные данные профиля сотрудника уже сохранены.')
                    return redirect('company_profile_email_change_verify')
            elif profile_updated:
                _clear_pending_company_profile_email_change(request)
                messages.success(request, 'Профиль сотрудника обновлен.')
                return redirect('employee_profile')
            else:
                messages.info(request, 'Изменений для сохранения нет.')
        except Exception:
            messages.error(request, 'Ошибка сети при обновлении профиля сотрудника')

    return render(
        request,
        'compani/employee_edit_profile.html',
        {
            'profile': profile,
            'pending_email_change': request.session.get(COMPANY_PROFILE_EMAIL_CHANGE_SESSION_KEY),
            'api_user': _api_user(request),
        },
    )


@company_owner_required
def _legacy_delete_company_profile_placeholder(request: HttpRequest) -> HttpResponse:
    if request.method == 'POST':
        clear_tokens(request)
        messages.info(request, 'Удаление компании через API не реализовано. Вы вышли из системы.')
        return redirect('home_page')
    return redirect('company_profile')


@company_owner_required
def delete_company_profile(request: HttpRequest) -> HttpResponse:
    if request.method != 'POST':
        return redirect('company_profile')

    try:
        resp = api_delete(request, 'user/profile/')
        data = _safe_json(resp)
        if resp.status_code < 400:
            messages.success(request, 'Компания и связанные данные удалены без возможности восстановления.')
            return _finish_company_account_session(request)

        if resp.status_code == 401:
            messages.info(request, 'Сессия истекла. Войдите снова.')
            return _finish_company_account_session(request)

        messages.error(request, _first_error(data, 'Не удалось удалить компанию'))
    except Exception:
        messages.error(request, 'Ошибка сети при удалении компании')

    return redirect('company_profile')


@company_owner_required
def export_hr_agents_csv(request: HttpRequest) -> HttpResponse:
    employees, err = _fetch_paginated(request, 'company/employees/', params={'page': 1})
    if err and not employees:
        messages.error(request, err)
        return redirect('hr_agents_list')

    hr_agents = [item for item in employees if str(item.get('role') or '').lower() == 'hr']

    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="hr_agents.csv"'
    response.write('\ufeff')

    writer = csv.writer(response)
    writer.writerow(['first_name', 'last_name', 'email', 'role', 'is_active'])
    for agent in hr_agents:
        writer.writerow(
            [
                agent.get('first_name') or '',
                agent.get('last_name') or '',
                agent.get('email') or '',
                agent.get('role') or 'hr',
                '1' if agent.get('is_active') else '0',
            ]
        )

    return response


@company_owner_required
def import_hr_agents(request: HttpRequest) -> HttpResponse:
    import_errors = request.session.pop('import_errors', [])

    if request.method == 'POST':
        upload = request.FILES.get('csv_file')
        if not upload:
            messages.error(request, 'Выберите CSV-файл для импорта')
            return redirect('import_hr_agents')

        try:
            employees, err = _fetch_paginated(request, 'company/employees/', params={'page': 1})
            if err and not employees:
                messages.error(request, err)
                return redirect('import_hr_agents')
            employees_by_email = {
                str(item.get('email') or '').strip().lower(): item
                for item in employees
                if item.get('email')
            }

            text_stream = io.TextIOWrapper(upload.file, encoding='utf-8-sig')
            reader = csv.DictReader(text_stream)
            fieldnames = [name.strip() for name in (reader.fieldnames or []) if name]
            required = {'first_name', 'last_name', 'email'}
            if not required.issubset(set(fieldnames)):
                messages.error(request, 'CSV должен содержать колонки first_name,last_name,email')
                return redirect('import_hr_agents')

            created = 0
            updated = 0
            skipped = 0
            errors: list[str] = []

            for line_no, row in enumerate(reader, start=2):
                first_name = str(row.get('first_name') or '').strip()
                last_name = str(row.get('last_name') or '').strip()
                email = str(row.get('email') or '').strip().lower()

                if not first_name or not last_name or not email:
                    skipped += 1
                    errors.append(f'Строка {line_no}: пустые обязательные поля')
                    continue

                role = str(row.get('role') or 'hr').strip().lower() or 'hr'
                if role not in ('hr', 'content_manager'):
                    role = 'hr'

                is_active = _parse_bool(row.get('is_active'), default=True)
                existing = employees_by_email.get(email)

                if existing:
                    payload = {
                        'first_name': first_name,
                        'last_name': last_name,
                        'role': role,
                        'is_active': is_active,
                    }
                    response = api_patch(request, f"company/employees/{existing.get('id')}/", json=payload)
                    payload_json = _safe_json(response)
                    if response.status_code >= 400:
                        skipped += 1
                        errors.append(f"Строка {line_no}: {_first_error(payload_json, 'ошибка обновления')}")
                        continue
                    updated += 1
                    continue

                password = str(row.get('password') or '').strip()
                if not password:
                    password = secrets.token_urlsafe(10)

                payload = {
                    'first_name': first_name,
                    'last_name': last_name,
                    'email': email,
                    'password': password,
                    'role': role,
                }
                response = api_post(request, 'company/employees/', json=payload)
                payload_json = _safe_json(response)
                if response.status_code >= 400:
                    skipped += 1
                    errors.append(f"Строка {line_no}: {_first_error(payload_json, 'ошибка создания')}")
                    continue

                created += 1
                if isinstance(payload_json, dict):
                    employees_by_email[email] = payload_json
                    created_id = payload_json.get('id')
                    if created_id and not is_active:
                        api_patch(request, f'company/employees/{created_id}/', json={'is_active': False})

            request.session['import_errors'] = errors[:200]
            messages.success(
                request,
                f'Импорт завершен. Создано: {created}, обновлено: {updated}, пропущено: {skipped}.',
            )
            if errors:
                messages.warning(request, f'Есть ошибки в {len(errors)} строках. Проверьте список ниже.')
            return redirect('import_hr_agents')
        except Exception:
            messages.error(request, 'Ошибка обработки CSV-файла')
            return redirect('import_hr_agents')

    return render(
        request,
        'compani/hrCRUD/import_hr_agents.html',
        {'import_errors': import_errors, 'api_user': _api_user(request)},
    )


@content_manager_required
def content_manager_stats(request: HttpRequest) -> HttpResponse:
    payload: dict = {}
    try:
        response = api_get(request, 'content-manager/profile/stats/')
        data = _safe_json(response)
        if response.status_code >= 400 or not isinstance(data, dict):
            messages.error(request, _first_error(data, 'Не удалось получить статистику контент-менеджера'))
        else:
            payload = data
    except Exception:
        messages.error(request, 'Ошибка сети при получении статистики контент-менеджера')

    manager = payload.get('manager') if isinstance(payload, dict) else {}
    company = payload.get('company') if isinstance(payload, dict) else {}
    stats = payload.get('stats') if isinstance(payload, dict) else {}
    chart = payload.get('chart') if isinstance(payload, dict) else {}

    labels = chart.get('labels') if isinstance(chart, dict) else []
    values = chart.get('values') if isinstance(chart, dict) else []

    if not isinstance(labels, list):
        labels = []
    if not isinstance(values, list):
        values = []

    return render(
        request,
        'compani/content_manager/stats.html',
        {
            'manager': manager or {},
            'company': company or {},
            'stats': stats or {},
            'chart_labels': labels,
            'chart_values': values,
            'api_user': _api_user(request),
        },
    )


@content_manager_required
def content_manager_videos(request: HttpRequest) -> HttpResponse:
    company, _ = _load_company_me(request)
    vacancies, vacancies_err = _fetch_paginated(request, 'company/vacancies/', params={'page': 1, 'archived': 1})
    videos, videos_err = _fetch_paginated(request, 'content-manager/videos/', params={'page': 1})

    if vacancies_err and not vacancies:
        messages.error(request, vacancies_err)
    if videos_err and not videos:
        messages.error(request, videos_err)

    vacancy_video_counts: dict[str, int] = {}
    for video_item in videos:
        if not isinstance(video_item, dict):
            continue
        vacancy_id = video_item.get('vacancy')
        if vacancy_id in (None, ''):
            continue
        vacancy_key = str(vacancy_id)
        vacancy_video_counts[vacancy_key] = vacancy_video_counts.get(vacancy_key, 0) + 1

    upload_vacancies: list[dict] = []
    for vacancy_item in vacancies:
        if not isinstance(vacancy_item, dict):
            continue
        vacancy_key = str(vacancy_item.get('id') or '')
        video_count = vacancy_video_counts.get(vacancy_key, 0)
        vacancy_copy = dict(vacancy_item)
        vacancy_copy['video_count'] = video_count
        vacancy_copy['video_limit_reached'] = video_count >= 3
        upload_vacancies.append(vacancy_copy)

    if request.method == 'POST':
        action = (request.POST.get('action') or '').strip().lower()
        video_id = request.POST.get('video_id')

        try:
            if action == 'upload':
                vacancy_id = (request.POST.get('vacancy') or '').strip()
                description = (request.POST.get('description') or '').strip()
                video_file = request.FILES.get('video')
                selected_vacancy_count = vacancy_video_counts.get(vacancy_id, 0)

                if not vacancy_id or not video_file:
                    messages.error(request, 'Выберите вакансию и видеофайл')
                elif selected_vacancy_count >= 3:
                    messages.error(
                        request,
                        _ui_text(
                            request,
                            'Для этой вакансии уже загружено 3 видео. Удалите одно видео перед новой загрузкой.',
                            'This vacancy already has 3 videos. Delete one before uploading a new video.',
                        ),
                    )
                else:
                    response = api_post(
                        request,
                        'content-manager/videos/',
                        data={'vacancy': vacancy_id, 'description': description},
                        files={'video': video_file},
                    )
                    payload = _safe_json(response)
                    if response.status_code >= 400:
                        messages.error(request, _first_error(payload, 'Не удалось загрузить видео'))
                    else:
                        messages.success(request, 'Видео загружено')

            elif action == 'activate' and video_id:
                response = api_post(request, f'content-manager/videos/{video_id}/activate/')
                payload = _safe_json(response)
                if response.status_code >= 400:
                    messages.error(request, _first_error(payload, 'Не удалось активировать видео'))
                else:
                    messages.success(request, 'Видео активировано')

            elif action == 'deactivate' and video_id:
                response = api_post(request, f'content-manager/videos/{video_id}/deactivate/')
                payload = _safe_json(response)
                if response.status_code >= 400:
                    messages.error(request, _first_error(payload, 'Не удалось деактивировать видео'))
                else:
                    messages.success(request, 'Видео деактивировано')

            elif action == 'delete' and video_id:
                response = api_delete(request, f'content-manager/videos/{video_id}/')
                payload = _safe_json(response)
                if response.status_code >= 400:
                    messages.error(request, _first_error(payload, 'Не удалось удалить видео'))
                else:
                    messages.success(request, 'Видео удалено')

            else:
                messages.error(request, 'Некорректное действие')
        except Exception:
            messages.error(request, 'Ошибка сети при работе с видео')

        return redirect('content_manager_videos')

    vacancy_filter = (request.GET.get('vacancy') or '').strip()
    search = (request.GET.get('q') or '').strip().lower()

    if vacancy_filter:
        videos = [item for item in videos if str(item.get('vacancy') or '') == vacancy_filter]

    if search:
        videos = [
            item for item in videos
            if search in str(item.get('description') or '').lower()
            or search in str(item.get('vacancy_position') or '').lower()
        ]

    return render(
        request,
        'compani/content_manager/videos.html',
        {
            'company': company or {},
            'vacancies': vacancies,
            'upload_vacancies': upload_vacancies,
            'videos': videos,
            'vacancy_filter': vacancy_filter,
            'search': request.GET.get('q', ''),
            'api_user': _api_user(request),
        },
    )


@company_owner_or_hr_required
def company_chats(request: HttpRequest) -> HttpResponse:
    archived_raw = str(request.GET.get('archived') or '0').strip().lower()
    is_archived_view = archived_raw in {'1', 'true', 'yes', 'on'}
    archived_param = 1 if is_archived_view else 0

    chats, err = _fetch_paginated(request, 'chats/', params={'page': 1, 'archived': archived_param})
    if err and not chats:
        messages.error(request, err)

    query = (request.GET.get('q') or '').strip().lower()
    if query:
        chats = [
            chat for chat in chats
            if query in str(chat.get('company_name', '')).lower()
            or query in str(chat.get('vacancy_title', '')).lower()
            or query in str((chat.get('applicant_info') or {}).get('full_name', '')).lower()
            or query in str((chat.get('last_message') or {}).get('text', '')).lower()
        ]

    return render(
        request,
        'compani/chat_list.html',
        {
            'chats': chats,
            'query': request.GET.get('q', ''),
            'current_tab': 'archived' if is_archived_view else 'active',
            'api_user': _api_user(request),
        },
    )


def _safe_chat_next_url(request: HttpRequest) -> str | None:
    next_url = str(request.POST.get('next') or request.GET.get('next') or '').strip()
    if next_url.startswith('/'):
        return next_url
    return None


@company_owner_or_hr_required
def company_chat_archive(request: HttpRequest, chat_id: int) -> HttpResponse:
    if request.method != 'POST':
        return redirect('company_chats')

    try:
        response = api_post(request, f'chats/{chat_id}/archive/')
        payload = _safe_json(response)
        if response.status_code >= 400:
            messages.error(
                request,
                _first_error(payload, _ui_text(request, 'Не удалось архивировать чат', 'Failed to archive chat')),
            )
        else:
            messages.success(request, _ui_text(request, 'Чат перенесен в архив', 'Chat moved to archive'))
    except Exception:
        messages.error(request, _ui_text(request, 'Ошибка сети при архивации чата', 'Network error while archiving chat'))

    return redirect(_safe_chat_next_url(request) or 'company_chats')


@company_owner_or_hr_required
def company_chat_unarchive(request: HttpRequest, chat_id: int) -> HttpResponse:
    if request.method != 'POST':
        return redirect('company_chats')

    try:
        response = api_post(request, f'chats/{chat_id}/unarchive/')
        payload = _safe_json(response)
        if response.status_code >= 400:
            messages.error(
                request,
                _first_error(payload, _ui_text(request, 'Не удалось вернуть чат из архива', 'Failed to restore chat from archive')),
            )
        else:
            messages.success(request, _ui_text(request, 'Чат возвращен из архива', 'Chat restored from archive'))
    except Exception:
        messages.error(
            request,
            _ui_text(request, 'Ошибка сети при восстановлении чата', 'Network error while restoring chat'),
        )

    return redirect(_safe_chat_next_url(request) or 'company_chats')


@company_owner_or_hr_required
def company_chat_detail(request: HttpRequest, chat_id: int) -> HttpResponse:
    chat = None
    chat_messages = []

    try:
        chat_response = api_get(request, f'chats/{chat_id}/')
        chat_payload = _safe_json(chat_response)
        if chat_response.status_code >= 400 or not isinstance(chat_payload, dict):
            messages.error(request, _first_error(chat_payload, 'Чат не найден'))
            return redirect('company_chats')
        chat = chat_payload
    except Exception:
        messages.error(request, 'Ошибка сети при загрузке чата')
        return redirect('company_chats')

    try:
        messages_response = api_get(request, f'chats/{chat_id}/messages/')
        messages_payload = _safe_json(messages_response) or {}
        if messages_response.status_code >= 400:
            messages.error(request, _first_error(messages_payload, 'Не удалось получить сообщения'))
        else:
            chat_messages = _results(messages_payload)
            if not chat_messages and isinstance(messages_payload, list):
                chat_messages = messages_payload
    except Exception:
        messages.error(request, 'Ошибка сети при загрузке сообщений')

    return render(
        request,
        'compani/chat_detail.html',
        {
            'chat': chat,
            'chat_messages': chat_messages,
            'api_user': _api_user(request),
        },
    )


@company_owner_or_hr_required
def company_chat_send_message(request: HttpRequest, chat_id: int) -> HttpResponse:
    if request.method != 'POST':
        return redirect('company_chat_detail', chat_id=chat_id)

    text = (request.POST.get('text') or '').strip()
    if not text:
        messages.error(request, 'Введите текст сообщения')
        return redirect('company_chat_detail', chat_id=chat_id)

    try:
        response = api_post(request, f'chats/{chat_id}/send_message/', json={'text': text})
        payload = _safe_json(response)
        if response.status_code >= 400:
            messages.error(request, _first_error(payload, 'Не удалось отправить сообщение'))
    except Exception:
        messages.error(request, 'Ошибка сети при отправке сообщения')

    return redirect('company_chat_detail', chat_id=chat_id)


def _build_company_stats_payload(request: HttpRequest) -> dict:
    company, company_err = _load_company_me(request)
    vacancies, vacancies_err = _fetch_paginated(request, 'company/vacancies/', params={'page': 1, 'archived': 1})
    responses, responses_err = _fetch_paginated(request, 'company/responses/', params={'page': 1})
    employees, employees_err = _fetch_paginated(request, 'company/employees/', params={'page': 1})
    chats, chats_err = _fetch_paginated(request, 'chats/', params={'page': 1})

    errors = [err for err in (company_err, vacancies_err, responses_err, employees_err, chats_err) if err]

    active_vacancies = [item for item in vacancies if not item.get('is_archived')]
    archived_vacancies = [item for item in vacancies if item.get('is_archived')]

    status_counter = Counter()
    vacancy_counter = Counter()
    month_counter = Counter()

    for item in responses:
        status_name = str(item.get('status_name') or 'Без статуса').strip() or 'Без статуса'
        status_counter[status_name] += 1

        vacancy_id = item.get('vacancy_id')
        vacancy_name = item.get('vacancy_position') or f'Вакансия #{vacancy_id}'
        vacancy_counter[(vacancy_id, vacancy_name)] += 1

        response_date = str(item.get('response_date') or '')
        if len(response_date) >= 7 and response_date[4] == '-':
            month_counter[response_date[:7]] += 1

    if month_counter:
        month_keys = sorted(month_counter.keys())[-6:]
    else:
        month_keys = [datetime.now().strftime('%Y-%m')]
        month_counter[month_keys[0]] = 0

    activity_points = []
    for month_key in month_keys:
        month_label = f"{month_key[5:7]}.{month_key[:4]}"
        activity_points.append({'key': month_key, 'label': month_label, 'count': int(month_counter.get(month_key, 0))})

    top_vacancies = []
    for (vacancy_id, vacancy_name), responses_count in vacancy_counter.most_common(5):
        top_vacancies.append({'id': vacancy_id, 'name': vacancy_name, 'responses_count': int(responses_count)})

    employees_by_role = Counter(str(item.get('role') or 'unknown') for item in employees)

    summary = {
        'vacancies_total': len(vacancies),
        'vacancies_active': len(active_vacancies),
        'vacancies_archived': len(archived_vacancies),
        'responses_total': len(responses),
        'employees_total': len(employees),
        'hr_agents_total': int(employees_by_role.get('hr', 0)),
        'content_managers_total': int(employees_by_role.get('content_manager', 0)),
        'chats_total': len(chats),
    }

    return {
        'company': company or {},
        'summary': summary,
        'status_items': [{'name': name, 'count': int(count)} for name, count in status_counter.most_common()],
        'activity_points': activity_points,
        'top_vacancies': top_vacancies,
        'errors': errors,
    }


@company_owner_or_hr_required
def company_stats(request: HttpRequest) -> HttpResponse:
    payload = _build_company_stats_payload(request)
    for error_text in payload.get('errors', []):
        messages.warning(request, error_text)

    return render(
        request,
        'compani/stats/company_stats.html',
        {
            'company': payload.get('company') or {},
            'summary': payload.get('summary') or {},
            'status_items': payload.get('status_items') or [],
            'activity_points': payload.get('activity_points') or [],
            'top_vacancies': payload.get('top_vacancies') or [],
            'api_user': _api_user(request),
        },
    )


@company_owner_or_hr_required
def export_company_stats_csv(request: HttpRequest) -> HttpResponse:
    payload = _build_company_stats_payload(request)
    company = payload.get('company') or {}
    summary = payload.get('summary') or {}
    status_items = payload.get('status_items') or []
    top_vacancies = payload.get('top_vacancies') or []
    activity_points = payload.get('activity_points') or []

    response = HttpResponse(content_type='text/csv; charset=utf-8')
    filename = f"workmpt_company_stats_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    response.write('\ufeff')

    writer = csv.writer(response, delimiter=';')
    writer.writerow(['WorkMPT Analytics Report'])
    writer.writerow(['Дата формирования', datetime.now().strftime('%Y-%m-%d %H:%M:%S')])
    writer.writerow(['Компания', company.get('name') or 'WorkMPT'])
    writer.writerow([])

    writer.writerow(['Сводка'])
    writer.writerow(['Метрика', 'Значение'])
    writer.writerow(['Всего вакансий', summary.get('vacancies_total', 0)])
    writer.writerow(['Активные вакансии', summary.get('vacancies_active', 0)])
    writer.writerow(['Архивные вакансии', summary.get('vacancies_archived', 0)])
    writer.writerow(['Отклики', summary.get('responses_total', 0)])
    writer.writerow(['Сотрудники', summary.get('employees_total', 0)])
    writer.writerow(['HR-агенты', summary.get('hr_agents_total', 0)])
    writer.writerow(['Контент-менеджеры', summary.get('content_managers_total', 0)])
    writer.writerow(['Чаты', summary.get('chats_total', 0)])
    writer.writerow([])

    writer.writerow(['Отклики по статусам'])
    writer.writerow(['Статус', 'Количество'])
    if status_items:
        for item in status_items:
            writer.writerow([item.get('name') or 'Без статуса', item.get('count') or 0])
    else:
        writer.writerow(['Нет данных', 0])
    writer.writerow([])

    writer.writerow(['Активность откликов по месяцам'])
    writer.writerow(['Месяц', 'Количество'])
    if activity_points:
        for item in activity_points:
            writer.writerow([item.get('label') or '', item.get('count') or 0])
    else:
        writer.writerow(['Нет данных', 0])
    writer.writerow([])

    writer.writerow(['Топ вакансий по откликам'])
    writer.writerow(['Вакансия', 'Отклики'])
    if top_vacancies:
        for item in top_vacancies:
            writer.writerow([item.get('name') or 'Вакансия', item.get('responses_count') or 0])
    else:
        writer.writerow(['Нет данных', 0])

    return response


@company_owner_or_hr_required
def export_company_stats_pdf(request: HttpRequest) -> HttpResponse:
    payload = _build_company_stats_payload(request)
    company = payload.get('company') or {}
    summary = payload.get('summary') or {}
    status_items = payload.get('status_items') or []
    top_vacancies = payload.get('top_vacancies') or []
    activity_points = payload.get('activity_points') or []

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    margin = 28
    font_regular, font_bold = _pdf_font_names()

    brand_name = 'WorkMPT'
    company_name = company.get('name') or brand_name
    generated_at = datetime.now().strftime('%d.%m.%Y %H:%M')

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
        pdf.setFont(font_regular, 9)
        pdf.drawString(x + 10, y + h - 16, title)
        pdf.setFillColor(colors.HexColor('#0f172a'))
        pdf.setFont(font_bold, 18)
        pdf.drawString(x + 10, y + 14, str(int(value or 0)))

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
            pdf.drawString(x + 14, y + h - 58, 'Нет данных')

    pdf.setTitle(f'{brand_name} Company Analytics Report')
    pdf.setFillColor(colors.HexColor('#f5f8fc'))
    pdf.rect(0, 0, width, height, fill=1, stroke=0)

    # Brand header (symbolics WorkMPT)
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
    pdf.drawString(header_x + 56, header_y + 38, f'Аналитический отчет компании: {company_name}')
    pdf.drawString(header_x + 56, header_y + 24, f'Дата формирования: {generated_at}')

    # Summary cards
    metrics = [
        ('Вакансии', summary.get('vacancies_total', 0)),
        ('Активные', summary.get('vacancies_active', 0)),
        ('Архивные', summary.get('vacancies_archived', 0)),
        ('Отклики', summary.get('responses_total', 0)),
        ('Сотрудники', summary.get('employees_total', 0)),
        ('HR-агенты', summary.get('hr_agents_total', 0)),
        ('Контент-менеджеры', summary.get('content_managers_total', 0)),
        ('Чаты', summary.get('chats_total', 0)),
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

    # Chart blocks
    chart_h = 220
    chart_y = row_2_y - 14 - chart_h
    left_chart_w = 340
    right_chart_w = header_w - left_chart_w - 12
    left_chart_x = margin
    right_chart_x = left_chart_x + left_chart_w + 12

    for box_x, box_w in ((left_chart_x, left_chart_w), (right_chart_x, right_chart_w)):
        pdf.setFillColor(colors.white)
        pdf.setStrokeColor(colors.HexColor('#dbe4f0'))
        pdf.roundRect(box_x, chart_y, box_w, chart_h, 12, fill=1, stroke=1)

    pdf.setFillColor(colors.HexColor('#0f172a'))
    pdf.setFont(font_bold, 11)
    pdf.drawString(left_chart_x + 12, chart_y + chart_h - 18, 'Динамика откликов')
    pdf.drawString(right_chart_x + 12, chart_y + chart_h - 18, 'Структура статусов')

    activity_labels = [str(item.get('label') or '') for item in activity_points] or [datetime.now().strftime('%m.%Y')]
    activity_values = [int(item.get('count') or 0) for item in activity_points] or [0]
    max_activity = max(activity_values + [1])
    value_max = max(5, ((max_activity + 4) // 5) * 5)
    value_step = max(1, value_max // 5)

    activity_drawing = Drawing(left_chart_w - 16, chart_h - 34)
    bar_chart = VerticalBarChart()
    bar_chart.x = 28
    bar_chart.y = 28
    bar_chart.width = left_chart_w - 74
    bar_chart.height = chart_h - 84
    bar_chart.data = [activity_values]
    bar_chart.categoryAxis.categoryNames = activity_labels
    bar_chart.categoryAxis.labels.boxAnchor = 'ne'
    bar_chart.categoryAxis.labels.angle = 25
    bar_chart.categoryAxis.labels.dy = -2
    bar_chart.categoryAxis.labels.fontName = font_regular
    bar_chart.categoryAxis.labels.fontSize = 8
    bar_chart.valueAxis.valueMin = 0
    bar_chart.valueAxis.valueMax = value_max
    bar_chart.valueAxis.valueStep = value_step
    bar_chart.valueAxis.labels.fontName = font_regular
    bar_chart.valueAxis.labels.fontSize = 8
    bar_chart.bars[0].fillColor = colors.HexColor('#2563eb')
    bar_chart.bars[0].strokeColor = colors.HexColor('#1d4ed8')
    activity_drawing.add(bar_chart)
    renderPDF.draw(activity_drawing, pdf, left_chart_x + 8, chart_y + 8)

    pie_items = status_items[:6]
    if len(status_items) > 6:
        pie_items.append({'name': 'Остальные', 'count': sum(int(x.get('count') or 0) for x in status_items[6:])})

    pie_labels = [str(item.get('name') or 'Без статуса') for item in pie_items]
    pie_values = [int(item.get('count') or 0) for item in pie_items]
    if not pie_values or sum(pie_values) <= 0:
        pie_labels = ['Нет данных']
        pie_values = [1]

    pie_drawing = Drawing(right_chart_w - 16, chart_h - 34)
    pie_chart = Pie()
    pie_chart.x = 24
    pie_chart.y = 28
    pie_chart.width = min(140, right_chart_w - 100)
    pie_chart.height = min(140, chart_h - 100)
    pie_chart.data = pie_values
    pie_chart.labels = [_truncate(label, 12) for label in pie_labels]
    pie_chart.slices.strokeWidth = 0.5
    pie_chart.slices.strokeColor = colors.white
    pie_palette = [
        colors.HexColor('#2563eb'),
        colors.HexColor('#0ea5e9'),
        colors.HexColor('#10b981'),
        colors.HexColor('#f59e0b'),
        colors.HexColor('#ef4444'),
        colors.HexColor('#8b5cf6'),
        colors.HexColor('#14b8a6'),
    ]
    for idx in range(len(pie_values)):
        pie_chart.slices[idx].fillColor = pie_palette[idx % len(pie_palette)]
        pie_chart.slices[idx].fontName = font_regular
        pie_chart.slices[idx].fontSize = 8
    pie_drawing.add(pie_chart)
    renderPDF.draw(pie_drawing, pdf, right_chart_x + 8, chart_y + 8)

    table_h = 185
    table_y = chart_y - 14 - table_h
    table_gap = 12
    table_w = (header_w - table_gap) / 2

    vacancy_rows = [
        (str(item.get('name') or 'Вакансия'), int(item.get('responses_count') or 0))
        for item in top_vacancies
    ]
    status_rows = [
        (str(item.get('name') or 'Без статуса'), int(item.get('count') or 0))
        for item in status_items
    ]

    _draw_table(margin, table_y, table_w, table_h, 'Топ вакансий по откликам', vacancy_rows)
    _draw_table(margin + table_w + table_gap, table_y, table_w, table_h, 'Отклики по статусам', status_rows)

    # Footer
    pdf.setFillColor(colors.HexColor('#94a3b8'))
    pdf.setFont(font_regular, 8)
    pdf.drawString(margin, 18, 'WorkMPT · Company Analytics Report')

    pdf.save()
    buffer.seek(0)

    filename = f"workmpt_company_stats_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename=\"{filename}\"'
    return response


