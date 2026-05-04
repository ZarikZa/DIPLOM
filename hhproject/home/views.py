from __future__ import annotations

from datetime import date
from functools import wraps
import hashlib
import json
import re
import secrets
from urllib.parse import quote, urljoin

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login as auth_login, logout as auth_logout
from django.core.cache import cache
from django.core.files.storage import default_storage
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.urls import reverse
from django.shortcuts import redirect, render
from django.utils import timezone, translation
from django.views.decorators.http import require_POST

from apihh_main.email_service import send_email_message
from .api_client import api_base_url, api_delete, api_get, api_patch, api_post, api_put, clear_tokens, set_tokens
from .forms import CodeVerificationForm, PasswordResetRequestForm, SetNewPasswordForm


def api_login_required(view_func):
    """Access only with JWT token in session."""

    @wraps(view_func)
    def _wrapped(request: HttpRequest, *args, **kwargs):
        if not request.session.get('api_access'):
            next_url = request.get_full_path() if request.get_full_path() else '/'
            return redirect(f"/login/?next={quote(next_url)}")
        return view_func(request, *args, **kwargs)

    return _wrapped


def _safe_json(resp):
    try:
        return resp.json()
    except Exception:
        return None


def _is_local_path(value: str | None) -> bool:
    return bool(value) and value.startswith('/') and not value.startswith('//')


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


def _normalize_language_code(value: str | None) -> str:
    code = str(value or '').strip().lower()
    if code not in SUPPORTED_UI_LANGUAGES:
        return 'ru'
    return code


def _is_english_ui(request: HttpRequest) -> bool:
    return str(getattr(request, 'LANGUAGE_CODE', '') or '').lower().startswith('en')


def _ui_text(request: HttpRequest, ru_text: str, en_text: str) -> str:
    return en_text if _is_english_ui(request) else ru_text


CYRILLIC_NAME_PATTERN = re.compile(
    r"^[\u0410-\u042F\u0430-\u044F\u0401\u0451]+(?:[ -][\u0410-\u042F\u0430-\u044F\u0401\u0451]+)*$"
)
PHONE_INPUT_PATTERN = re.compile(r"^\+?[0-9()\-\s]+$")
VALID_COMPLAINT_TYPES = {'spam', 'fraud', 'inappropriate', 'discrimination', 'false_info', 'other'}
PASSWORD_RESET_EMAIL_SESSION_KEY = 'password_reset_email'
PASSWORD_RESET_CODE_SESSION_KEY = 'password_reset_code'
PASSWORD_RESET_ATTEMPTS_SESSION_KEY = 'password_reset_attempts_left'
REGISTRATION_PENDING_SESSION_KEY = 'pending_applicant_registration'
REGISTRATION_CODE_HASH_SESSION_KEY = 'pending_applicant_registration_code_hash'
REGISTRATION_EXPIRES_SESSION_KEY = 'pending_applicant_registration_expires_at'
REGISTRATION_ATTEMPTS_SESSION_KEY = 'pending_applicant_registration_attempts_left'
PROFILE_EMAIL_CHANGE_SESSION_KEY = 'pending_profile_email_change'
LANGUAGE_SESSION_KEY = 'django_language'
SUPPORTED_UI_LANGUAGES = {'ru', 'en'}
LOGIN_MAX_FAILED_ATTEMPTS = 3
LOGIN_BLOCK_SECONDS = 5 * 60
REGISTRATION_MAX_ATTEMPTS = 3
REGISTRATION_CODE_TTL_SECONDS = 10 * 60


def _clear_password_reset_session(request: HttpRequest) -> None:
    request.session.pop(PASSWORD_RESET_EMAIL_SESSION_KEY, None)
    request.session.pop(PASSWORD_RESET_CODE_SESSION_KEY, None)
    request.session.pop(PASSWORD_RESET_ATTEMPTS_SESSION_KEY, None)


def _generate_registration_code() -> str:
    return f"{secrets.randbelow(1000000):06d}"


def _registration_code_hash(email: str, code: str) -> str:
    identity = f"{str(email or '').strip().lower()}|{str(code or '').strip()}"
    return hashlib.sha256(identity.encode('utf-8')).hexdigest()


def _build_registration_email(first_name: str, code: str) -> tuple[str, str, str]:
    recipient_name = (first_name or '').strip() or 'пользователь'
    subject = f"Код подтверждения регистрации: {code}"
    html_message = f"""<!DOCTYPE html><html><head><meta charset="utf-8"></head><body>
    <p>Здравствуйте, {recipient_name}!</p><p>Код подтверждения регистрации: <b>{code}</b></p>
    <p>Код действителен 10 минут.</p></body></html>"""
    plain_message = (
        f"Здравствуйте, {recipient_name}!\n\n"
        f"Код подтверждения регистрации: {code}\n\n"
        f"Код действителен 10 минут."
    )
    return subject, plain_message, html_message


def _delete_pending_registration_file(pending_data: dict | None) -> None:
    if not isinstance(pending_data, dict):
        return

    file_path = str(pending_data.get('resume_file_path') or '').strip()
    if not file_path:
        return

    try:
        default_storage.delete(file_path)
    except Exception:
        pass


def _clear_pending_applicant_registration(request: HttpRequest) -> None:
    pending_data = request.session.get(REGISTRATION_PENDING_SESSION_KEY)
    _delete_pending_registration_file(pending_data)
    request.session.pop(REGISTRATION_PENDING_SESSION_KEY, None)
    request.session.pop(REGISTRATION_CODE_HASH_SESSION_KEY, None)
    request.session.pop(REGISTRATION_EXPIRES_SESSION_KEY, None)
    request.session.pop(REGISTRATION_ATTEMPTS_SESSION_KEY, None)


def _clear_pending_profile_email_change(request: HttpRequest) -> None:
    request.session.pop(PROFILE_EMAIL_CHANGE_SESSION_KEY, None)


def _store_pending_resume_file(resume_file) -> dict:
    file_name = str(getattr(resume_file, 'name', '') or 'resume')
    storage_path = default_storage.save(
        f"pending_registrations/applicants/{secrets.token_hex(16)}_{file_name}",
        resume_file,
    )
    return {
        'resume_file_path': storage_path,
        'resume_file_name': file_name,
        'resume_file_content_type': str(getattr(resume_file, 'content_type', '') or ''),
    }


def _get_pending_applicant_registration(request: HttpRequest) -> dict | None:
    pending_data = request.session.get(REGISTRATION_PENDING_SESSION_KEY)
    if not isinstance(pending_data, dict):
        return None

    expires_at = float(request.session.get(REGISTRATION_EXPIRES_SESSION_KEY) or 0)
    if expires_at and timezone.now().timestamp() >= expires_at:
        _clear_pending_applicant_registration(request)
        return None

    return pending_data


def _build_pending_registration_payload(pending_data: dict) -> dict:
    return {
        'first_name': str(pending_data.get('first_name') or ''),
        'last_name': str(pending_data.get('last_name') or ''),
        'phone': str(pending_data.get('phone') or ''),
        'email': str(pending_data.get('email') or ''),
        'username': str(pending_data.get('username') or ''),
        'birth_date': str(pending_data.get('birth_date') or ''),
        'resume': str(pending_data.get('resume') or ''),
        'password': str(pending_data.get('password') or ''),
        'password2': str(pending_data.get('password2') or ''),
    }


def _client_ip(request: HttpRequest) -> str:
    forwarded_for = str(request.META.get('HTTP_X_FORWARDED_FOR') or '').strip()
    if forwarded_for:
        return forwarded_for.split(',')[0].strip()
    return str(request.META.get('REMOTE_ADDR') or 'unknown')


def _login_rate_limit_keys(request: HttpRequest, email: str) -> tuple[str, str]:
    identity = f"{str(email or '').strip().lower()}|{_client_ip(request)}"
    digest = hashlib.sha256(identity.encode('utf-8')).hexdigest()
    return (
        f'login_attempts:{digest}',
        f'login_lock:{digest}',
    )


def _is_login_blocked(request: HttpRequest, email: str) -> bool:
    _, lock_key = _login_rate_limit_keys(request, email)
    return bool(cache.get(lock_key))


def _register_failed_login(request: HttpRequest, email: str) -> tuple[bool, int]:
    attempts_key, lock_key = _login_rate_limit_keys(request, email)
    current_attempts = int(cache.get(attempts_key) or 0) + 1
    if current_attempts >= LOGIN_MAX_FAILED_ATTEMPTS:
        cache.delete(attempts_key)
        cache.set(lock_key, 1, timeout=LOGIN_BLOCK_SECONDS)
        return True, 0

    cache.set(attempts_key, current_attempts, timeout=LOGIN_BLOCK_SECONDS)
    return False, LOGIN_MAX_FAILED_ATTEMPTS - current_attempts


def _reset_login_rate_limit(request: HttpRequest, email: str) -> None:
    attempts_key, lock_key = _login_rate_limit_keys(request, email)
    cache.delete(attempts_key)
    cache.delete(lock_key)


def _is_valid_cyrillic_name(value: str) -> bool:
    return bool(CYRILLIC_NAME_PATTERN.fullmatch(value))


def _normalize_ru_phone(value: str) -> str | None:
    raw = (value or '').strip()
    if not raw or not PHONE_INPUT_PATTERN.fullmatch(raw):
        return None

    digits = re.sub(r"\D", "", raw)
    if len(digits) == 10:
        digits = f"7{digits}"
    elif len(digits) == 11 and digits.startswith("8"):
        digits = f"7{digits[1:]}"

    if len(digits) != 11 or not digits.startswith("7"):
        return None

    return f"+{digits}"


def _is_at_least_14_years_old(value: str) -> bool:
    try:
        birth_date = date.fromisoformat(value)
    except ValueError:
        return False

    today = date.today()
    if birth_date > today:
        return False

    age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
    return age >= 14


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
        for value in payload.values():
            text = _first_error(value, '')
            if text:
                return text

    return default


def _extract_results(payload):
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


def _extract_page_meta(payload, rows: list):
    count = len(rows)
    next_url = None
    prev_url = None

    if isinstance(payload, dict):
        count = payload.get('count') or payload.get('total') or payload.get('total_count') or count
        next_url = payload.get('next') or payload.get('next_page')
        prev_url = payload.get('previous') or payload.get('prev') or payload.get('previous_page')

        nested = payload.get('data')
        if isinstance(nested, dict):
            count = nested.get('count') or nested.get('total') or nested.get('total_count') or count
            next_url = nested.get('next') or nested.get('next_page') or next_url
            prev_url = nested.get('previous') or nested.get('prev') or nested.get('previous_page') or prev_url

    try:
        count = int(count)
    except Exception:
        count = len(rows)

    return count, next_url, prev_url


def _is_applicant_user(request: HttpRequest) -> bool:
    api_user = request.session.get('api_user') or {}
    return str(api_user.get('user_type') or '').lower() == 'applicant'


def _redirect_for_current_role(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        if getattr(request.user, 'is_superuser', False) or str(getattr(request.user, 'user_type', '') or '').lower() == 'adminsite':
            return redirect('admin_dashboard')

    api_user = request.session.get('api_user') or {}
    user_type = str(api_user.get('user_type') or '').lower()
    if user_type in {'company', 'staff'}:
        return redirect('home_comp')
    return redirect('home_page')


def _require_applicant_route_access(request: HttpRequest, ru_message: str, en_message: str) -> HttpResponse | None:
    if _is_applicant_user(request):
        return None

    messages.error(
        request,
        _ui_text(
            request,
            ru_message,
            en_message,
        ),
    )
    return _redirect_for_current_role(request)


def _load_interest_preferences(request: HttpRequest) -> tuple[list[str], list[str]]:
    default_categories = ['IT', '\u041c\u0430\u0440\u043a\u0435\u0442\u0438\u043d\u0433', '\u041f\u0440\u043e\u0434\u0430\u0436\u0438', 'HR']
    selected_categories: list[str] = []

    if not request.session.get('api_access') or not _is_applicant_user(request):
        return selected_categories, default_categories

    try:
        resp = api_get(request, 'applicants/me/interests/')
        payload = _safe_json(resp) or {}
        if resp.status_code >= 400 or not isinstance(payload, dict):
            return selected_categories, default_categories

        raw_selected = payload.get('categories')
        if isinstance(raw_selected, list):
            selected_categories = [str(item).strip() for item in raw_selected if str(item).strip()]

        raw_available = payload.get('available_categories')
        if isinstance(raw_available, list):
            available_categories = [str(item).strip() for item in raw_available if str(item).strip()]
            if available_categories:
                default_categories = available_categories
    except Exception:
        pass

    return selected_categories, default_categories


def _load_applicant_skills(request: HttpRequest) -> list[dict]:
    if not request.session.get('api_access') or not _is_applicant_user(request):
        return []

    try:
        resp = api_get(request, 'applicants/me/skills/')
        payload = _safe_json(resp)
        if resp.status_code >= 400:
            return []

        if isinstance(payload, list):
            rows = payload
        elif isinstance(payload, dict):
            rows = _extract_results(payload)
        else:
            rows = []

        skills: list[dict] = []
        for item in rows:
            if not isinstance(item, dict):
                continue

            skill_id = item.get('skill')
            try:
                skill_id = int(skill_id)
            except (TypeError, ValueError):
                skill_id = None

            skill_name = str(item.get('skill_name') or '').strip()
            if not skill_name and item.get('skill') is not None:
                skill_name = str(item.get('skill')).strip()
            if not skill_name:
                continue

            level = item.get('level')
            try:
                level = int(level)
            except (TypeError, ValueError):
                level = None

            skill_data = {
                'skill_id': skill_id,
                'skill_name': skill_name,
                'level': level,
            }
            skills.append(skill_data)

        skills.sort(key=lambda row: str(row.get('skill_name') or '').lower())
        return skills
    except Exception:
        return []


def _load_available_skills(request: HttpRequest) -> list[dict]:
    try:
        options: list[dict] = []
        seen_ids: set[int] = set()
        page = 1

        while page <= 20:
            resp = api_get(request, 'skills/', params={'page': page})
            payload = _safe_json(resp)
            if resp.status_code >= 400:
                return []

            rows = _extract_results(payload)
            for item in rows:
                if not isinstance(item, dict):
                    continue

                skill_id = item.get('id')
                try:
                    skill_id = int(skill_id)
                except (TypeError, ValueError):
                    continue
                if skill_id in seen_ids:
                    continue

                name = str(item.get('name') or '').strip()
                if not name:
                    continue

                seen_ids.add(skill_id)
                options.append({'id': skill_id, 'name': name})

            next_url = payload.get('next') if isinstance(payload, dict) else None
            if not next_url:
                break
            page += 1

        options.sort(key=lambda row: row['name'].lower())
        return options
    except Exception:
        return []


def _load_applicant_skill_suggestions(request: HttpRequest) -> list[dict]:
    if not request.session.get('api_access') or not _is_applicant_user(request):
        return []

    try:
        resp = api_get(request, 'applicants/me/skill-suggestions/')
        payload = _safe_json(resp)
        if resp.status_code >= 400:
            return []

        if isinstance(payload, list):
            rows = payload
        elif isinstance(payload, dict):
            rows = _extract_results(payload)
        else:
            rows = []

        suggestions: list[dict] = []
        for item in rows:
            if not isinstance(item, dict):
                continue

            name = str(item.get('name') or '').strip()
            if not name:
                continue

            status = str(item.get('status') or '').strip().lower()
            if status not in {'pending', 'approved', 'rejected'}:
                status = 'pending'

            suggestions.append(
                {
                    'id': item.get('id'),
                    'name': name,
                    'status': status,
                    'admin_notes': str(item.get('admin_notes') or '').strip(),
                    'created_at': str(item.get('created_at') or '')[:10],
                    'reviewed_at': str(item.get('reviewed_at') or '')[:10],
                }
            )

        return suggestions
    except Exception:
        return []


def brendbook(request: HttpRequest) -> HttpResponse:
    return render(request, 'brandbook.html')


def home_page(request: HttpRequest) -> HttpResponse:
    active_vacancies_count = 0
    approved_companies_count = 0
    applicants_count = 0
    successful_responses_count = 0

    try:
        vacancies_resp = api_get(request, 'vacancies/', params={'page': 1})
        vacancies_json = _safe_json(vacancies_resp) or {}
        if isinstance(vacancies_json, dict):
            active_vacancies_count = int(vacancies_json.get('count') or 0)
    except Exception:
        pass

    try:
        companies_resp = api_get(request, 'companies/', params={'page': 1})
        companies_json = _safe_json(companies_resp) or {}
        if isinstance(companies_json, dict):
            approved_companies_count = int(companies_json.get('count') or 0)
    except Exception:
        pass

    try:
        applicants_resp = api_get(request, 'applicants/', params={'page': 1})
        applicants_json = _safe_json(applicants_resp) or {}
        if isinstance(applicants_json, dict):
            applicants_count = int(applicants_json.get('count') or 0)
    except Exception:
        pass

    try:
        responses_resp = api_get(request, 'responses/', params={'page': 1})
        responses_json = _safe_json(responses_resp) or {}
        if isinstance(responses_json, dict):
            successful_responses_count = int(responses_json.get('count') or 0)
    except Exception:
        pass

    satisfaction_rate = 0
    if active_vacancies_count:
        satisfaction_rate = min(99, int((successful_responses_count / active_vacancies_count) * 100))

    return render(
        request,
        'home.html',
        {
            'active_vacancies_count': active_vacancies_count,
            'approved_companies_count': approved_companies_count,
            'applicants_count': applicants_count,
            'successful_responses_count': successful_responses_count,
            'satisfaction_rate': satisfaction_rate,
            'api_user': request.session.get('api_user'),
        },
    )


def custom_login(request: HttpRequest) -> HttpResponse:
    next_url = request.POST.get('next') or request.GET.get('next')

    if request.session.get('api_access'):
        if _is_local_path(next_url):
            return redirect(next_url)
        return redirect('home_page')

    if request.method == 'POST':
        email = (request.POST.get('username') or request.POST.get('email') or '').strip()
        password = request.POST.get('password') or ''

        if not email or not password:
            messages.error(request, 'Введите email и пароль')
            return render(request, 'auth/login.html', {'next': next_url, 'email': email})

        if _is_login_blocked(request, email):
            messages.error(request, 'Слишком много неудачных попыток. Попробуйте снова через 5 минут.')
            return render(request, 'auth/login.html', {'next': next_url, 'email': email})

        try:
            resp = api_post(request, 'auth/login/', json={'email': email, 'password': password})
            data = _safe_json(resp)
            if resp.status_code >= 400 or not isinstance(data, dict) or 'access' not in data:
                if resp.status_code >= 500:
                    messages.error(request, 'Сервис входа временно недоступен. Попробуйте позже.')
                    return render(request, 'auth/login.html', {'next': next_url, 'email': email})

                is_locked, attempts_left = _register_failed_login(request, email)
                if is_locked:
                    messages.error(request, 'Слишком много неудачных попыток. Попробуйте снова через 5 минут.')
                else:
                    messages.error(request, f'Неверный email или пароль. Осталось попыток: {attempts_left}.')
                return render(request, 'auth/login.html', {'next': next_url, 'email': email})

            _reset_login_rate_limit(request, email)
            set_tokens(request, data.get('access'), data.get('refresh'))
            session_user = {
                'user_id': data.get('user_id'),
                'email': data.get('email'),
                'username': data.get('username'),
                'user_type': data.get('user_type'),
                'first_name': data.get('first_name'),
                'last_name': data.get('last_name'),
            }

            # Для staff-пользователей (HR / content manager) нужна роль сотрудника.
            # Берём её из /user/profile/ после успешной авторизации.
            try:
                profile_resp = api_get(request, 'user/profile/')
                profile_data = _safe_json(profile_resp)
                if profile_resp.status_code < 400 and isinstance(profile_data, dict):
                    session_user['employee_role'] = profile_data.get('employee_role')
                    session_user['company_id'] = profile_data.get('company_id')
                    session_user['company_name'] = profile_data.get('company_name')
            except Exception:
                pass

            # Для доступа в custom admin_panel нужен Django-auth request.user.
            # Если это superuser/adminsite — синхронизируем JWT-вход с Django-сессией.
            local_admin_user = None
            try:
                user_model = get_user_model()
                local_user = user_model.objects.filter(email=email).first()
                if local_user and local_user.is_active:
                    session_user['is_superuser'] = bool(getattr(local_user, 'is_superuser', False))
                    if local_user.is_superuser or str(getattr(local_user, 'user_type', '')).lower() == 'adminsite':
                        local_user.backend = 'django.contrib.auth.backends.ModelBackend'
                        auth_login(request, local_user)
                        local_admin_user = local_user
            except Exception:
                pass

            request.session['api_user'] = session_user

            if _is_local_path(next_url):
                return redirect(next_url)

            user_type = str(session_user.get('user_type') or '').lower()
            employee_role = str(session_user.get('employee_role') or '').lower()

            if local_admin_user and (
                local_admin_user.is_superuser
                or str(getattr(local_admin_user, 'user_type', '')).lower() == 'adminsite'
            ):
                return redirect('admin_dashboard')
            if user_type == 'adminsite':
                return redirect('admin_dashboard')
            if user_type == 'company':
                return redirect('home_comp')
            if user_type == 'staff':
                if employee_role == 'content_manager':
                    return redirect('content_manager_videos')
                return redirect('home_comp')
            return redirect('home_page')
        except Exception:
            messages.error(request, 'Не удалось подключиться к API. Проверьте API_BASE_URL и доступность сервера.')
            return render(request, 'auth/login.html', {'next': next_url, 'email': email})

    return render(request, 'auth/login.html', {'next': next_url, 'email': request.GET.get('email', '')})


def custom_logout(request: HttpRequest) -> HttpResponse:
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


def _finish_account_session(request: HttpRequest) -> HttpResponse:
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


def _custom_register_with_email_verification(request: HttpRequest) -> HttpResponse:
    if request.method == 'GET' and request.GET.get('restart'):
        _clear_pending_applicant_registration(request)

    if request.method == 'POST':
        _clear_pending_applicant_registration(request)

        first_name = (request.POST.get('first_name') or '').strip()
        last_name = (request.POST.get('last_name') or '').strip()
        phone = (request.POST.get('phone') or '').strip()
        email = (request.POST.get('email') or '').strip().lower()
        birth_date = (request.POST.get('birth_date') or '').strip()
        resume = (request.POST.get('resume') or '').strip()
        resume_file = request.FILES.get('resume_file')
        password = request.POST.get('password1') or ''
        password2 = request.POST.get('password2') or ''
        agreement = request.POST.get('personal_data_agreement')

        if not agreement:
            messages.error(request, 'Нужно согласие на обработку персональных данных')
            return render(request, 'auth/register_api.html', {'form_data': request.POST})

        required_fields = {
            'Имя': first_name,
            'Фамилия': last_name,
            'Телефон': phone,
            'Email': email,
            'Дата рождения': birth_date,
            'Пароль': password,
            'Подтверждение пароля': password2,
        }
        missing = [label for label, value in required_fields.items() if not value]
        if missing:
            messages.error(request, f"Заполните поля: {', '.join(missing)}")
            return render(request, 'auth/register_api.html', {'form_data': request.POST})

        if not _is_valid_cyrillic_name(first_name):
            messages.error(request, 'Имя должно содержать только кириллицу, пробел или дефис.')
            return render(request, 'auth/register_api.html', {'form_data': request.POST})

        if not _is_valid_cyrillic_name(last_name):
            messages.error(request, 'Фамилия должна содержать только кириллицу, пробел или дефис.')
            return render(request, 'auth/register_api.html', {'form_data': request.POST})

        normalized_phone = _normalize_ru_phone(phone)
        if not normalized_phone:
            messages.error(request, 'Введите телефон в формате +7XXXXXXXXXX.')
            return render(request, 'auth/register_api.html', {'form_data': request.POST})
        phone = normalized_phone

        if not _is_at_least_14_years_old(birth_date):
            messages.error(request, 'Регистрация доступна только с 14 лет. Проверьте дату рождения.')
            return render(request, 'auth/register_api.html', {'form_data': request.POST})

        if len(password) < 8:
            messages.error(request, 'Пароль должен содержать не менее 8 символов.')
            return render(request, 'auth/register_api.html', {'form_data': request.POST})

        if password != password2:
            messages.error(request, 'Пароли не совпадают.')
            return render(request, 'auth/register_api.html', {'form_data': request.POST})

        user_model = get_user_model()
        if user_model.objects.filter(email__iexact=email).exists():
            messages.error(request, 'Пользователь с таким email уже зарегистрирован.')
            return render(request, 'auth/register_api.html', {'form_data': request.POST})

        pending_data = {
            'first_name': first_name,
            'last_name': last_name,
            'phone': phone,
            'email': email,
            'username': email,
            'birth_date': birth_date,
            'resume': resume,
            'password': password,
            'password2': password2,
            'resume_file_path': '',
            'resume_file_name': '',
            'resume_file_content_type': '',
        }

        try:
            if resume_file:
                pending_data.update(_store_pending_resume_file(resume_file))

            code = _generate_registration_code()
            subject, plain_message, html_message = _build_registration_email(first_name, code)
            send_email_message(
                recipient_email=email,
                subject=subject,
                plain_message=plain_message,
                html_message=html_message,
                fail_silently=False,
            )
        except Exception:
            _delete_pending_registration_file(pending_data)
            messages.error(request, 'Не удалось отправить код подтверждения на почту.')
            return render(request, 'auth/register_api.html', {'form_data': request.POST})

        request.session[REGISTRATION_PENDING_SESSION_KEY] = pending_data
        request.session[REGISTRATION_CODE_HASH_SESSION_KEY] = _registration_code_hash(email, code)
        request.session[REGISTRATION_EXPIRES_SESSION_KEY] = timezone.now().timestamp() + REGISTRATION_CODE_TTL_SECONDS
        request.session[REGISTRATION_ATTEMPTS_SESSION_KEY] = REGISTRATION_MAX_ATTEMPTS

        messages.success(request, 'Код подтверждения отправлен на указанный email.')
        return redirect('registration_verify_email')

    return render(request, 'auth/register_api.html', {'form_data': {}})


def custom_register(request: HttpRequest) -> HttpResponse:
    return _custom_register_with_email_verification(request)


def registration_verify_email(request: HttpRequest) -> HttpResponse:
    pending_data = _get_pending_applicant_registration(request)
    if not pending_data:
        messages.info(request, 'Сначала заполните форму регистрации и получите код подтверждения.')
        return redirect('registration_user')

    form = CodeVerificationForm(request.POST or None)
    attempts = int(request.session.get(REGISTRATION_ATTEMPTS_SESSION_KEY, REGISTRATION_MAX_ATTEMPTS) or REGISTRATION_MAX_ATTEMPTS)
    email = str(pending_data.get('email') or '')

    if request.method == 'POST' and form.is_valid():
        entered_code = str(form.cleaned_data.get('code') or '').strip()
        expected_hash = str(request.session.get(REGISTRATION_CODE_HASH_SESSION_KEY) or '')
        if _registration_code_hash(email, entered_code) != expected_hash:
            attempts = max(0, attempts - 1)
            request.session[REGISTRATION_ATTEMPTS_SESSION_KEY] = attempts
            if attempts <= 0:
                _clear_pending_applicant_registration(request)
                messages.error(request, 'Количество попыток исчерпано. Заполните форму регистрации заново.')
                return redirect('registration_user')
            form.add_error('code', 'Неверный код подтверждения.')
        else:
            payload = _build_pending_registration_payload(pending_data)
            temp_file = None
            try:
                if pending_data.get('resume_file_path'):
                    temp_file = default_storage.open(str(pending_data.get('resume_file_path')), 'rb')
                    register_resp = api_post(
                        request,
                        'user/register_applicant/',
                        data=payload,
                        files={
                            'resume_file': (
                                str(pending_data.get('resume_file_name') or 'resume'),
                                temp_file,
                                str(pending_data.get('resume_file_content_type') or 'application/octet-stream'),
                            )
                        },
                    )
                else:
                    register_resp = api_post(request, 'user/register_applicant/', json=payload)
            except Exception:
                if temp_file:
                    try:
                        temp_file.close()
                    except Exception:
                        pass
                form.add_error(None, 'Ошибка сети при завершении регистрации.')
            else:
                if temp_file:
                    try:
                        temp_file.close()
                    except Exception:
                        pass

                register_data = _safe_json(register_resp)
                if register_resp.status_code >= 400:
                    _clear_pending_applicant_registration(request)
                    messages.error(request, _first_error(register_data, 'Не удалось завершить регистрацию. Заполните форму ещё раз.'))
                    return redirect('registration_user')

                password = str(pending_data.get('password') or '')
                _clear_pending_applicant_registration(request)

                try:
                    login_resp = api_post(request, 'auth/login/', json={'email': email, 'password': password})
                    login_data = _safe_json(login_resp)
                    if (
                        login_resp.status_code < 400
                        and isinstance(login_data, dict)
                        and login_data.get('access')
                    ):
                        set_tokens(request, login_data.get('access'), login_data.get('refresh'))
                        request.session['api_user'] = {
                            'user_id': login_data.get('user_id'),
                            'email': login_data.get('email'),
                            'username': login_data.get('username'),
                            'user_type': login_data.get('user_type'),
                            'first_name': login_data.get('first_name'),
                            'last_name': login_data.get('last_name'),
                        }
                        request.session['show_interests_modal'] = True
                        messages.success(request, 'Регистрация завершена. Выберите интересующие сферы.')
                        return redirect('applicant_profile')
                except Exception:
                    pass

                messages.success(request, 'Регистрация завершена. Войдите в аккаунт.')
                return redirect(f"/login/?email={email}")

    return render(
        request,
        'auth/register_verify_email.html',
        {
            'form': form,
            'email': email,
            'attempts': attempts,
            'api_user': request.session.get('api_user'),
        },
    )


def _legacy_custom_register_direct_api(request: HttpRequest) -> HttpResponse:
    if request.method == 'POST':
        first_name = (request.POST.get('first_name') or '').strip()
        last_name = (request.POST.get('last_name') or '').strip()
        phone = (request.POST.get('phone') or '').strip()
        email = (request.POST.get('email') or '').strip()
        birth_date = (request.POST.get('birth_date') or '').strip()
        resume = (request.POST.get('resume') or '').strip()
        resume_file = request.FILES.get('resume_file')
        password = request.POST.get('password1') or ''
        password2 = request.POST.get('password2') or ''
        agreement = request.POST.get('personal_data_agreement')

        if not agreement:
            messages.error(request, 'Нужно согласие на обработку персональных данных')
            return render(request, 'auth/register_api.html', {'form_data': request.POST})

        required_fields = {
            'Имя': first_name,
            'Фамилия': last_name,
            'Телефон': phone,
            'Email': email,
            'Дата рождения': birth_date,
            'Пароль': password,
            'Подтверждение пароля': password2,
        }
        missing = [label for label, value in required_fields.items() if not value]
        if missing:
            messages.error(request, f"Заполните поля: {', '.join(missing)}")
            return render(request, 'auth/register_api.html', {'form_data': request.POST})

        if not _is_valid_cyrillic_name(first_name):
            messages.error(request, 'Имя должно содержать только кириллицу (разрешены пробел и дефис).')
            return render(request, 'auth/register_api.html', {'form_data': request.POST})

        if not _is_valid_cyrillic_name(last_name):
            messages.error(request, 'Фамилия должна содержать только кириллицу (разрешены пробел и дефис).')
            return render(request, 'auth/register_api.html', {'form_data': request.POST})

        normalized_phone = _normalize_ru_phone(phone)
        if not normalized_phone:
            messages.error(request, 'Введите телефон в формате +7XXXXXXXXXX.')
            return render(request, 'auth/register_api.html', {'form_data': request.POST})
        phone = normalized_phone

        if not _is_at_least_14_years_old(birth_date):
            messages.error(request, 'Регистрация доступна только с 14 лет. Проверьте дату рождения.')
            return render(request, 'auth/register_api.html', {'form_data': request.POST})

        payload = {
            'first_name': first_name,
            'last_name': last_name,
            'phone': phone,
            'email': email,
            'username': email,
            'birth_date': birth_date,
            'resume': resume,
            'password': password,
            'password2': password2,
        }

        try:
            if resume_file:
                resp = api_post(
                    request,
                    'user/register_applicant/',
                    data=payload,
                    files={'resume_file': resume_file},
                )
            else:
                resp = api_post(request, 'user/register_applicant/', json=payload)
            data = _safe_json(resp)
            if resp.status_code >= 400:
                messages.error(request, _first_error(data, 'Не удалось зарегистрироваться через API'))
                return render(request, 'auth/register_api.html', {'form_data': request.POST})

            try:
                login_resp = api_post(request, 'auth/login/', json={'email': email, 'password': password})
                login_data = _safe_json(login_resp)
                if (
                    login_resp.status_code < 400
                    and isinstance(login_data, dict)
                    and login_data.get('access')
                ):
                    set_tokens(request, login_data.get('access'), login_data.get('refresh'))
                    request.session['api_user'] = {
                        'user_id': login_data.get('user_id'),
                        'email': login_data.get('email'),
                        'username': login_data.get('username'),
                        'user_type': login_data.get('user_type'),
                        'first_name': login_data.get('first_name'),
                        'last_name': login_data.get('last_name'),
                    }
                    request.session['show_interests_modal'] = True
                    messages.success(request, 'Регистрация завершена. Выберите интересующие сферы.')
                    return redirect('applicant_profile')
            except Exception:
                pass

            messages.success(request, 'Регистрация завершена. Войдите в аккаунт.')
            return redirect(f"/login/?email={email}")
        except Exception:
            messages.error(request, 'Не удалось подключиться к API. Проверь API_BASE_URL и доступность сервера.')
            return render(request, 'auth/register_api.html', {'form_data': request.POST})

    return render(request, 'auth/register_api.html', {'form_data': {}})


def vakansii_page(request: HttpRequest) -> HttpResponse:
    page = request.GET.get('page') or 1
    params = {'page': page}
    search_query = (request.GET.get('search') or '').strip()

    if search_query:
        params['search'] = search_query
    elif _is_applicant_user(request):
        params['recommended'] = '1'

    if request.GET.get('salary_from'):
        params['salary_min'] = request.GET.get('salary_from')
    if request.GET.get('salary_to'):
        params['salary_max'] = request.GET.get('salary_to')

    exp_list = request.GET.getlist('experience')
    if exp_list:
        params['experience'] = exp_list[0]

    employment_list = request.GET.getlist('employment')
    if employment_list:
        params['employment'] = ','.join(employment_list)

    sort_by = request.GET.get('sort', 'newest')
    if sort_by == 'salary_high':
        params['ordering'] = '-salary_max'
    elif sort_by == 'salary_low':
        params['ordering'] = 'salary_min'
    else:
        params['ordering'] = '-created_date'

    vacancies = []
    count = 0
    next_url = None
    prev_url = None

    try:
        resp = api_get(request, 'vacancies/', params=params)
        data = _safe_json(resp) or {}
        if isinstance(data, dict):
            vacancies = data.get('results') or []
            count = data.get('count') or 0
            next_url = data.get('next')
            prev_url = data.get('previous')
    except Exception:
        messages.error(request, 'Не удалось получить список вакансий из API')

    work_conditions = []
    try:
        wc = api_get(request, 'work-conditions/', params={'page': 1})
        wc_json = _safe_json(wc) or {}
        if isinstance(wc_json, dict):
            work_conditions = wc_json.get('results') or []
    except Exception:
        pass

    applicant_interests, interest_categories = _load_interest_preferences(request)

    return render(
        request,
        'vakans.html',
        {
            'page_obj': {
                'object_list': vacancies,
                'count': count,
                'next': next_url,
                'previous': prev_url,
                'number': int(page) if str(page).isdigit() else 1,
            },
            'work_conditions': work_conditions,
            'selected_employments': request.GET.getlist('employment'),
            'selected_experiences': request.GET.getlist('experience'),
            'salary_from': request.GET.get('salary_from', ''),
            'salary_to': request.GET.get('salary_to', ''),
            'search_query': search_query,
            'applicant_interests': applicant_interests,
            'interest_categories': interest_categories,
            'recommendations_enabled': bool(_is_applicant_user(request) and not search_query),
            'api_user': request.session.get('api_user'),
        },
    )


def vacancy_detail(request: HttpRequest, vacancy_id: int) -> HttpResponse:
    vacancy = None
    try:
        resp = api_get(request, f'vacancies/{vacancy_id}/')
        if resp.status_code < 400:
            vacancy = _safe_json(resp)
    except Exception:
        vacancy = None

    if not vacancy:
        messages.error(request, 'Вакансия не найдена')
        return redirect('vakansi_page')

    chat_id = None
    if request.session.get('api_access'):
        try:
            by_vacancy_resp = api_get(request, 'chats/by_vacancy/', params={'vacancy_id': vacancy_id})
            by_vacancy_data = _safe_json(by_vacancy_resp) or {}
            if isinstance(by_vacancy_data, dict):
                chat_id = by_vacancy_data.get('id')
        except Exception:
            chat_id = None

    return render(
        request,
        'vacancy_detail.html',
        {
            'vacancy': vacancy,
            'is_favorite': bool(vacancy.get('is_favorite')),
            'has_response': bool(vacancy.get('has_applied')),
            'chat_id': chat_id,
            'api_user': request.session.get('api_user'),
        },
    )


@api_login_required
def apply_to_vacancy(request: HttpRequest, vacancy_id: int) -> HttpResponse:
    redirect_to = request.POST.get('next') or request.GET.get('next') or request.META.get('HTTP_REFERER') or '/vakansii/'
    if not _is_local_path(redirect_to):
        redirect_to = '/vakansii/'

    resp = api_post(request, 'responses/', json={'vacancy': vacancy_id})
    data = _safe_json(resp)
    if resp.status_code >= 400:
        messages.error(request, _first_error(data, 'Не удалось отправить отклик'))
    else:
        messages.success(request, 'Отклик отправлен')
    return redirect(redirect_to)


@api_login_required
def add_to_favorites(request: HttpRequest, vacancy_id: int) -> HttpResponse:
    resp = api_post(request, 'favorites/toggle/', json={'vacancy': vacancy_id})
    if resp.status_code >= 400:
        messages.error(request, 'Не удалось изменить избранное')
    return redirect('vacancy_detail', vacancy_id=vacancy_id)


@api_login_required
def remove_from_favorites(request: HttpRequest, vacancy_id: int) -> HttpResponse:
    return add_to_favorites(request, vacancy_id)


@api_login_required
def applicant_profile(request: HttpRequest) -> HttpResponse:
    denied_response = _require_applicant_route_access(
        request,
        'Профиль соискателя доступен только соискателям.',
        'Applicant profile is available only to applicants.',
    )
    if denied_response is not None:
        return denied_response

    profile = {}
    favorites = []
    responses = []
    chats = []
    applicant_interests, interest_categories = _load_interest_preferences(request)
    applicant_skills = _load_applicant_skills(request)
    applicant_skill_suggestions = _load_applicant_skill_suggestions(request)
    available_skills = _load_available_skills(request)
    selected_skill_levels: dict[int, int] = {}
    for skill in applicant_skills:
        skill_id = skill.get('skill_id')
        level = skill.get('level')
        if isinstance(skill_id, int) and isinstance(level, int):
            selected_skill_levels[skill_id] = level
    skill_options = [
        {
            'id': option['id'],
            'name': option['name'],
            'selected_level': selected_skill_levels.get(option['id']),
        }
        for option in available_skills
    ]
    show_interests_modal = bool(request.session.pop('show_interests_modal', False))

    try:
        profile_resp = api_get(request, 'user/profile/')
        if profile_resp.status_code < 400:
            profile = _safe_json(profile_resp) or {}
            if isinstance(profile, dict):
                profile['avatar'] = _absolute_api_media_url(profile.get('avatar'))
                profile['resume_file'] = _absolute_api_media_url(profile.get('resume_file'))
    except Exception:
        pass

    try:
        favorites_resp = api_get(request, 'favorites/', params={'page': 1})
        favorites_json = _safe_json(favorites_resp) or {}
        favorites = _extract_results(favorites_json)
    except Exception:
        pass

    try:
        responses_resp = api_get(request, 'responses/', params={'page': 1})
        responses_json = _safe_json(responses_resp) or {}
        responses = _extract_results(responses_json)
    except Exception:
        pass

    try:
        chats_resp = api_get(request, 'chats/', params={'page': 1})
        chats_json = _safe_json(chats_resp) or {}
        chats = _extract_results(chats_json)
    except Exception:
        pass

    return render(
        request,
        'profile.html',
        {
            'applicant': profile,
            'favorites': favorites,
            'responses': responses,
            'chats_count': len(chats),
            'applicant_interests': applicant_interests,
            'applicant_skills': applicant_skills,
            'applicant_skill_suggestions': applicant_skill_suggestions,
            'skill_options': skill_options,
            'interest_categories': interest_categories,
            'show_interests_modal': show_interests_modal,
            'api_user': request.session.get('api_user'),
        },
    )


@api_login_required
def edit_applicant_profile(request: HttpRequest) -> HttpResponse:
    profile = {}
    try:
        profile_resp = api_get(request, 'user/profile/')
        if profile_resp.status_code < 400:
            profile = _safe_json(profile_resp) or {}
            if isinstance(profile, dict):
                profile['avatar'] = _absolute_api_media_url(profile.get('avatar'))
                profile['resume_file'] = _absolute_api_media_url(profile.get('resume_file'))
    except Exception:
        pass

    if request.method == 'POST':
        payload = {
            'first_name': request.POST.get('first_name') or '',
            'last_name': request.POST.get('last_name') or '',
            'phone': request.POST.get('phone') or '',
            'birth_date': request.POST.get('birth_date') or '',
            'resume': request.POST.get('resume') or '',
        }
        payload = {k: v for k, v in payload.items() if v}

        files = {}
        avatar = request.FILES.get('avatar')
        resume_file = request.FILES.get('resume_file')
        if avatar:
            files['avatar'] = avatar
        if resume_file:
            files['resume_file'] = resume_file

        try:
            if files:
                resp = api_patch(request, 'user/profile/', data=payload, files=files)
            else:
                resp = api_patch(request, 'user/profile/', json=payload)
            data = _safe_json(resp)
            if resp.status_code >= 400:
                messages.error(request, _first_error(data, 'Не удалось обновить профиль'))
            else:
                updated = data or {}
                current_user = request.session.get('api_user') or {}
                current_user['first_name'] = updated.get('first_name', current_user.get('first_name'))
                current_user['last_name'] = updated.get('last_name', current_user.get('last_name'))
                current_user['email'] = updated.get('email', current_user.get('email'))
                request.session['api_user'] = current_user
                messages.success(request, 'Профиль обновлён')
                return redirect('applicant_profile')
        except Exception:
            messages.error(request, 'Ошибка сети при обновлении профиля')

    profile = {}
    try:
        profile_resp = api_get(request, 'user/profile/')
        if profile_resp.status_code < 400:
            profile = _safe_json(profile_resp) or {}
            if isinstance(profile, dict):
                profile['avatar'] = _absolute_api_media_url(profile.get('avatar'))
                profile['resume_file'] = _absolute_api_media_url(profile.get('resume_file'))
    except Exception:
        pass

    return render(request, 'edit_applicant_profile.html', {'profile': profile, 'api_user': request.session.get('api_user')})


@api_login_required
def edit_applicant_profile(request: HttpRequest) -> HttpResponse:
    denied_response = _require_applicant_route_access(
        request,
        'Редактирование профиля доступно только соискателям.',
        'Profile editing is available only to applicants.',
    )
    if denied_response is not None:
        return denied_response

    profile = {}
    try:
        profile_resp = api_get(request, 'user/profile/')
        if profile_resp.status_code < 400:
            profile = _safe_json(profile_resp) or {}
            if isinstance(profile, dict):
                profile['avatar'] = _absolute_api_media_url(profile.get('avatar'))
                profile['resume_file'] = _absolute_api_media_url(profile.get('resume_file'))
    except Exception:
        pass

    if request.method == 'POST':
        requested_email = (request.POST.get('email') or '').strip().lower()
        current_email = str(
            profile.get('email')
            or ((request.session.get('api_user') or {}).get('email'))
            or ''
        ).strip().lower()
        payload = {
            'first_name': request.POST.get('first_name') or '',
            'last_name': request.POST.get('last_name') or '',
            'phone': request.POST.get('phone') or '',
            'birth_date': request.POST.get('birth_date') or '',
            'resume': request.POST.get('resume') or '',
        }
        payload = {k: v for k, v in payload.items() if v}

        files = {}
        avatar = request.FILES.get('avatar')
        resume_file = request.FILES.get('resume_file')
        if avatar:
            files['avatar'] = avatar
        if resume_file:
            files['resume_file'] = resume_file

        profile_updated = False
        try:
            if payload or files:
                if files:
                    resp = api_patch(request, 'user/profile/', data=payload, files=files)
                else:
                    resp = api_patch(request, 'user/profile/', json=payload)
                data = _safe_json(resp)
                if resp.status_code >= 400:
                    messages.error(request, _first_error(data, 'Не удалось обновить профиль.'))
                    return render(
                        request,
                        'edit_applicant_profile.html',
                        {
                            'profile': profile,
                            'api_user': request.session.get('api_user'),
                            'pending_email_change': request.session.get(PROFILE_EMAIL_CHANGE_SESSION_KEY),
                        },
                    )

                updated = data or {}
                current_user = request.session.get('api_user') or {}
                current_user['first_name'] = updated.get('first_name', current_user.get('first_name'))
                current_user['last_name'] = updated.get('last_name', current_user.get('last_name'))
                current_user['email'] = updated.get('email', current_user.get('email'))
                request.session['api_user'] = current_user
                if isinstance(updated, dict):
                    updated['avatar'] = _absolute_api_media_url(updated.get('avatar'))
                    updated['resume_file'] = _absolute_api_media_url(updated.get('resume_file'))
                    profile = updated
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
                        messages.success(request, 'Остальные данные профиля обновлены.')
                    messages.error(request, _first_error(change_data, 'Не удалось отправить код подтверждения на новый email.'))
                else:
                    request.session[PROFILE_EMAIL_CHANGE_SESSION_KEY] = requested_email
                    messages.success(request, 'Код подтверждения отправлен на новый email.')
                    if profile_updated:
                        messages.info(request, 'Остальные данные профиля уже сохранены.')
                    return redirect('applicant_profile_email_change_verify')
            elif profile_updated:
                _clear_pending_profile_email_change(request)
                messages.success(request, 'Профиль обновлен.')
                return redirect('applicant_profile')
            else:
                messages.info(request, 'Изменений для сохранения нет.')
        except Exception:
            messages.error(request, 'Ошибка сети при обновлении профиля.')

    return render(
        request,
        'edit_applicant_profile.html',
        {
            'profile': profile,
            'api_user': request.session.get('api_user'),
            'pending_email_change': request.session.get(PROFILE_EMAIL_CHANGE_SESSION_KEY),
        },
    )


@api_login_required
def applicant_profile_email_change_verify(request: HttpRequest) -> HttpResponse:
    denied_response = _require_applicant_route_access(
        request,
        'Подтверждение email доступно только соискателям.',
        'Email confirmation is available only to applicants.',
    )
    if denied_response is not None:
        return denied_response

    pending_email = str(request.session.get(PROFILE_EMAIL_CHANGE_SESSION_KEY) or '').strip().lower()
    if request.GET.get('change') == '1':
        _clear_pending_profile_email_change(request)
        return redirect('edit_applicant_profile')

    if not pending_email:
        messages.info(request, 'Сначала укажите новый email в профиле.')
        return redirect('edit_applicant_profile')

    if request.method == 'POST':
        code = str(request.POST.get('code') or '').strip()
        if not re.fullmatch(r'\d{6}', code):
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
                    current_user = request.session.get('api_user') or {}
                    current_user['email'] = (data or {}).get('email', pending_email)
                    request.session['api_user'] = current_user
                    _clear_pending_profile_email_change(request)
                    messages.success(request, 'Email успешно подтвержден и обновлен.')
                    return redirect('applicant_profile')
            except Exception:
                messages.error(request, 'Ошибка сети при подтверждении нового email.')

    return render(
        request,
        'profile_verify_email.html',
        {
            'email': pending_email,
            'api_user': request.session.get('api_user'),
            'change_email_url': f"{reverse('applicant_profile_email_change_verify')}?change=1",
        },
    )


@api_login_required
def _legacy_delete_applicant_profile_placeholder(request: HttpRequest) -> HttpResponse:
    if request.method == 'POST':
        clear_tokens(request)
        messages.info(request, 'Удаление аккаунта через API не реализовано. Вы вышли из системы.')
        return redirect('home_page')
    return redirect('applicant_profile')


@api_login_required
def delete_applicant_profile(request: HttpRequest) -> HttpResponse:
    denied_response = _require_applicant_route_access(
        request,
        'Удаление аккаунта доступно только соискателям.',
        'Account deletion is available only to applicants.',
    )
    if denied_response is not None:
        return denied_response

    if request.method != 'POST':
        return redirect('applicant_profile')

    if not _is_applicant_user(request):
        messages.error(request, 'Удаление аккаунта доступно только соискателю.')
        return redirect('home_page')

    try:
        resp = api_delete(request, 'user/profile/')
        data = _safe_json(resp)
        if resp.status_code < 400:
            messages.success(request, 'Аккаунт удалён без возможности восстановления.')
            return _finish_account_session(request)

        if resp.status_code == 401:
            messages.info(request, 'Сессия истекла. Войдите снова.')
            return _finish_account_session(request)

        messages.error(request, _first_error(data, 'Не удалось удалить аккаунт'))
    except Exception:
        messages.error(request, 'Ошибка сети при удалении аккаунта')

    return redirect('applicant_profile')


@api_login_required
def update_theme(request: HttpRequest) -> HttpResponse:
    theme = request.POST.get('theme') or request.GET.get('theme')
    if theme:
        request.session['ui_theme'] = theme
    return redirect(request.META.get('HTTP_REFERER', 'home_page'))


@require_POST
def update_language(request: HttpRequest) -> HttpResponse:
    payload = {}
    if request.content_type and 'application/json' in request.content_type:
        try:
            payload = json.loads(request.body.decode('utf-8') or '{}')
        except Exception:
            payload = {}

    requested = (
        request.POST.get('language')
        or request.POST.get('lang')
        or payload.get('language')
        or payload.get('lang')
    )
    language_code = _normalize_language_code(requested)
    translation.activate(language_code)
    request.session[LANGUAGE_SESSION_KEY] = language_code

    response = JsonResponse({'ok': True, 'language': language_code})
    response.set_cookie(
        'django_language',
        language_code,
        max_age=60 * 60 * 24 * 365,
        samesite='Lax',
    )
    return response


@api_login_required
def update_applicant_interests(request: HttpRequest) -> HttpResponse:
    redirect_to = request.POST.get('next') or request.META.get('HTTP_REFERER') or '/vakansii/'
    if not _is_local_path(redirect_to):
        redirect_to = '/vakansii/'

    if request.method != 'POST':
        return redirect(redirect_to)

    if not _is_applicant_user(request):
        messages.error(request, 'Изменение интересов доступно только соискателю')
        return redirect(redirect_to)

    categories = [item for item in request.POST.getlist('interests') if item]

    try:
        resp = api_put(request, 'applicants/me/interests/', json={'categories': categories})
        data = _safe_json(resp)
        if resp.status_code >= 400:
            messages.error(request, _first_error(data, 'Не удалось сохранить интересы'))
        else:
            messages.success(request, 'Интересы обновлены')
    except Exception:
        messages.error(request, 'Ошибка сети при сохранении интересов')

    return redirect(redirect_to)


@api_login_required
def update_applicant_skills(request: HttpRequest) -> HttpResponse:
    redirect_to = request.POST.get('next') or request.META.get('HTTP_REFERER') or '/profile/'
    if not _is_local_path(redirect_to):
        redirect_to = '/profile/'

    if request.method != 'POST':
        return redirect(redirect_to)

    if not _is_applicant_user(request):
        messages.error(request, 'Изменение навыков доступно только соискателю')
        return redirect(redirect_to)

    available_skills = _load_available_skills(request)
    available_skill_ids = {item['id'] for item in available_skills if isinstance(item.get('id'), int)}

    selected_raw = request.POST.getlist('skill_ids')
    selected_ids: list[int] = []
    invalid_ids = False
    for raw in selected_raw:
        try:
            skill_id = int(str(raw).strip())
        except (TypeError, ValueError):
            invalid_ids = True
            continue
        if skill_id not in available_skill_ids:
            invalid_ids = True
            continue
        if skill_id not in selected_ids:
            selected_ids.append(skill_id)

    if invalid_ids:
        messages.error(request, 'Обнаружены некорректные навыки в форме. Обновите страницу и попробуйте снова.')
        return redirect(redirect_to)

    payload_skills: list[dict] = []
    for skill_id in selected_ids:
        level_raw = request.POST.get(f'skill_level_{skill_id}', '')
        try:
            level = int(str(level_raw).strip())
        except (TypeError, ValueError):
            messages.error(request, f'Укажите уровень 1..5 для навыка ID {skill_id}.')
            return redirect(redirect_to)

        if level < 1 or level > 5:
            messages.error(request, f'Уровень навыка (ID {skill_id}) должен быть от 1 до 5.')
            return redirect(redirect_to)

        payload_skills.append({'skill_id': skill_id, 'level': level})

    try:
        resp = api_put(request, 'applicants/me/skills/', json={'skills': payload_skills})
        data = _safe_json(resp)
        if resp.status_code >= 400:
            messages.error(request, _first_error(data, 'Не удалось сохранить навыки'))
        else:
            messages.success(request, 'Навыки обновлены')
    except Exception:
        messages.error(request, 'Ошибка сети при сохранении навыков')

    return redirect(redirect_to)


@api_login_required
def submit_applicant_skill_suggestion(request: HttpRequest) -> HttpResponse:
    redirect_to = request.POST.get('next') or request.META.get('HTTP_REFERER') or '/profile/'
    if not _is_local_path(redirect_to):
        redirect_to = '/profile/'

    if request.method != 'POST':
        return redirect(redirect_to)

    if not _is_applicant_user(request):
        messages.error(
            request,
            _ui_text(
                request,
                'Отправка навыка доступна только соискателю',
                'Only applicants can submit skill suggestions',
            ),
        )
        return redirect(redirect_to)

    skill_name = str(request.POST.get('suggested_skill_name') or '').strip()
    if not skill_name:
        messages.error(
            request,
            _ui_text(
                request,
                'Укажите название навыка',
                'Enter a skill name',
            ),
        )
        return redirect(redirect_to)

    try:
        resp = api_post(request, 'applicants/me/skill-suggestions/', json={'name': skill_name})
        data = _safe_json(resp)
        if resp.status_code >= 400:
            messages.error(
                request,
                _first_error(
                    data,
                    _ui_text(
                        request,
                        'Не удалось отправить навык на проверку',
                        'Failed to submit skill for review',
                    ),
                ),
            )
        else:
            messages.success(
                request,
                _ui_text(
                    request,
                    'Навык отправлен на проверку администратору',
                    'Skill suggestion has been sent to admin review',
                ),
            )
    except Exception:
        messages.error(
            request,
            _ui_text(
                request,
                'Ошибка сети при отправке навыка',
                'Network error while submitting skill suggestion',
            ),
        )

    return redirect(redirect_to)


@api_login_required
def create_complaint(request: HttpRequest, vacancy_id: int) -> HttpResponse:
    if request.method != 'POST':
        return redirect('vacancy_detail', vacancy_id=vacancy_id)

    complaint_type = (request.POST.get('complaint_type') or 'other').strip()
    description = (request.POST.get('description') or '').strip()

    if complaint_type not in VALID_COMPLAINT_TYPES:
        messages.error(request, 'Выберите причину жалобы')
        return redirect('vacancy_detail', vacancy_id=vacancy_id)

    resp = api_post(
        request,
        'complaints/',
        json={'vacancy': vacancy_id, 'complaint_type': complaint_type, 'description': description},
    )
    data = _safe_json(resp)
    if resp.status_code >= 400:
        messages.error(request, _first_error(data, 'Не удалось отправить жалобу'))
        return redirect('vacancy_detail', vacancy_id=vacancy_id)

    return redirect('complaint_success', vacancy_id=vacancy_id)


@api_login_required
def complaint_success(request: HttpRequest, vacancy_id: int) -> HttpResponse:
    vacancy = {'id': vacancy_id, 'position': f'Вакансия #{vacancy_id}'}
    try:
        vacancy_resp = api_get(request, f'vacancies/{vacancy_id}/')
        vacancy_json = _safe_json(vacancy_resp)
        if vacancy_resp.status_code < 400 and isinstance(vacancy_json, dict):
            vacancy = vacancy_json
    except Exception:
        pass
    return render(request, 'complaints/complaint_success.html', {'vacancy': vacancy, 'api_user': request.session.get('api_user')})


@api_login_required
def check_existing_complaint(request: HttpRequest, vacancy_id: int) -> HttpResponse:
    try:
        resp = api_get(request, 'complaints/', params={'vacancy': vacancy_id})
        data = _safe_json(resp) or {}
        complaints = _extract_results(data)
        if complaints:
            messages.info(request, 'Вы уже отправляли жалобу на эту вакансию')
    except Exception:
        pass
    return redirect('vacancy_detail', vacancy_id=vacancy_id)


def send_metrics(request: HttpRequest) -> HttpResponse:
    return redirect('home_page')


def password_reset_request(request: HttpRequest) -> HttpResponse:
    form = PasswordResetRequestForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        email = str(form.cleaned_data.get('email') or '').strip().lower()
        try:
            resp = api_post(request, 'auth/password-reset/request/', json={'email': email})
            payload = _safe_json(resp)
            if resp.status_code >= 400:
                messages.error(request, _first_error(payload, 'Не удалось отправить код восстановления.'))
            else:
                request.session[PASSWORD_RESET_EMAIL_SESSION_KEY] = email
                request.session[PASSWORD_RESET_CODE_SESSION_KEY] = ''
                request.session[PASSWORD_RESET_ATTEMPTS_SESSION_KEY] = 3
                messages.success(request, 'Если email существует, код отправлен на почту.')
                return redirect('password_reset_verify')
        except Exception:
            messages.error(request, 'Ошибка сети при отправке кода восстановления.')

    return render(
        request,
        'password_reset_request.html',
        {
            'form': form,
            'api_user': request.session.get('api_user'),
        },
    )


def password_reset_verify(request: HttpRequest) -> HttpResponse:
    email = request.session.get(PASSWORD_RESET_EMAIL_SESSION_KEY)
    if not email:
        messages.info(request, 'Сначала укажите email для восстановления пароля.')
        return redirect('password_reset_request')

    form = CodeVerificationForm(request.POST or None)
    attempts = int(request.session.get(PASSWORD_RESET_ATTEMPTS_SESSION_KEY, 3) or 3)

    if request.method == 'POST' and form.is_valid():
        code = str(form.cleaned_data.get('code') or '').strip()
        request.session[PASSWORD_RESET_CODE_SESSION_KEY] = code
        return redirect('password_reset_new')

    return render(
        request,
        'password_reset_verify.html',
        {
            'form': form,
            'email': email,
            'attempts': attempts,
            'api_user': request.session.get('api_user'),
        },
    )


def password_reset_new(request: HttpRequest) -> HttpResponse:
    email = request.session.get(PASSWORD_RESET_EMAIL_SESSION_KEY)
    code = request.session.get(PASSWORD_RESET_CODE_SESSION_KEY)
    if not email:
        messages.info(request, 'Сначала укажите email для восстановления пароля.')
        return redirect('password_reset_request')
    if not code:
        messages.info(request, 'Введите код подтверждения из письма.')
        return redirect('password_reset_verify')

    form = SetNewPasswordForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        new_password = str(form.cleaned_data.get('new_password1') or '')
        try:
            resp = api_post(
                request,
                'auth/password-reset/confirm/',
                json={
                    'email': email,
                    'code': code,
                    'new_password': new_password,
                },
            )
            payload = _safe_json(resp)
            if resp.status_code >= 400:
                error_text = _first_error(payload, 'Не удалось сменить пароль.')
                if isinstance(payload, dict) and 'code' in payload:
                    messages.error(request, error_text)
                    request.session.pop(PASSWORD_RESET_CODE_SESSION_KEY, None)
                    attempts_left = int(request.session.get(PASSWORD_RESET_ATTEMPTS_SESSION_KEY, 3) or 3)
                    request.session[PASSWORD_RESET_ATTEMPTS_SESSION_KEY] = max(0, attempts_left - 1)
                    return redirect('password_reset_verify')
                form.add_error(None, error_text)
            else:
                _clear_password_reset_session(request)
                messages.success(request, 'Пароль успешно изменен. Теперь можно войти.')
                return redirect('login_user')
        except Exception:
            form.add_error(None, 'Ошибка сети при смене пароля.')

    return render(
        request,
        'password_reset_new.html',
        {
            'form': form,
            'api_user': request.session.get('api_user'),
        },
    )


@api_login_required
def applicant_video_feed(request: HttpRequest) -> HttpResponse:
    requested_page = str(request.GET.get('page') or '1')
    params = {'page': requested_page}
    for key in ('city', 'category', 'salary_from'):
        value = request.GET.get(key)
        if value:
            params[key] = value
    show_all = str(request.GET.get('all') or '').strip().lower() in ('1', 'true', 'yes')

    videos = []
    next_url = None
    prev_url = None
    count = 0
    feed_source = 'feed/videos/'
    has_filters = any(request.GET.get(k) for k in ('city', 'category', 'salary_from'))
    prefer_recommended = bool(_is_applicant_user(request) and not show_all and not has_filters)

    def _load_feed(endpoint: str, endpoint_params: dict) -> tuple[bool, str]:
        nonlocal videos, next_url, prev_url, count, feed_source
        resp = api_get(request, endpoint, params=endpoint_params)
        data = _safe_json(resp) or {}
        if resp.status_code >= 400:
            return False, _first_error(data, '')

        rows = _extract_results(data)
        if not rows:
            return False, ''

        count, next_url, prev_url = _extract_page_meta(data, rows)
        videos = rows
        feed_source = endpoint
        return True, ''

    try:
        if show_all:
            primary_endpoint = 'vacancy-videos/feed/'
            fallback_endpoints = ['feed/videos/']
        else:
            primary_endpoint = 'feed/videos/recommended/' if prefer_recommended else 'feed/videos/'
            fallback_endpoints = ['feed/videos/' if prefer_recommended else 'feed/videos/recommended/', 'vacancy-videos/feed/']

        loaded, err = _load_feed(primary_endpoint, params)
        if err:
            messages.warning(request, err)

        for endpoint in fallback_endpoints:
            if loaded:
                break
            loaded, _ = _load_feed(endpoint, params)

        if not loaded and (has_filters or requested_page != '1'):
            reset_params = {'page': 1}
            loaded, _ = _load_feed(primary_endpoint, reset_params)
            for endpoint in fallback_endpoints:
                if loaded:
                    break
                loaded, _ = _load_feed(endpoint, reset_params)
    except Exception:
        messages.error(request, 'Ошибка сети при загрузке видео-ленты')

    return render(
        request,
        'video_feed.html',
        {
            'videos': videos,
            'count': count,
            'next_url': next_url,
            'prev_url': prev_url,
            'feed_source': feed_source,
            'show_all_videos': show_all,
            'has_video_filters': has_filters,
            'api_user': request.session.get('api_user'),
        },
    )

@api_login_required
def video_view_mark(request: HttpRequest, video_id: int) -> JsonResponse:
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Method not allowed'}, status=405)

    try:
        resp = api_post(request, f'feed/videos/{video_id}/view/')
        data = _safe_json(resp)
        if resp.status_code >= 400:
            return JsonResponse({'ok': False, 'error': _first_error(data, 'Ошибка API')}, status=resp.status_code)
        return JsonResponse({'ok': True})
    except Exception:
        return JsonResponse({'ok': False, 'error': 'Ошибка сети'}, status=502)


@api_login_required
def video_toggle_like(request: HttpRequest, video_id: int) -> JsonResponse:
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Method not allowed'}, status=405)

    try:
        resp = api_post(request, f'feed/videos/{video_id}/like/')
        data = _safe_json(resp)
        if resp.status_code >= 400:
            return JsonResponse({'ok': False, 'error': _first_error(data, 'Ошибка API')}, status=resp.status_code)
        liked = bool(data.get('liked')) if isinstance(data, dict) else False
        return JsonResponse({'ok': True, 'liked': liked})
    except Exception:
        return JsonResponse({'ok': False, 'error': 'Ошибка сети'}, status=502)


@api_login_required
def applicant_chats(request: HttpRequest) -> HttpResponse:
    denied_response = _require_applicant_route_access(
        request,
        'Чаты соискателя доступны только соискателям.',
        'Applicant chats are available only to applicants.',
    )
    if denied_response is not None:
        return denied_response

    page = request.GET.get('page') or 1
    archived_raw = str(request.GET.get('archived') or '0').strip().lower()
    is_archived_view = archived_raw in {'1', 'true', 'yes', 'on'}
    params = {'page': page, 'archived': 1 if is_archived_view else 0}
    chats = []
    count = 0
    next_url = None
    prev_url = None

    try:
        resp = api_get(request, 'chats/', params=params)
        data = _safe_json(resp) or {}
        if resp.status_code >= 400:
            messages.error(request, _first_error(data, 'Не удалось загрузить чаты'))
        elif isinstance(data, dict):
            chats = data.get('results') or []
            count = data.get('count') or len(chats)
            next_url = data.get('next')
            prev_url = data.get('previous')
        elif isinstance(data, list):
            chats = data
            count = len(chats)
    except Exception:
        messages.error(request, 'Ошибка сети при загрузке чатов')

    query = (request.GET.get('q') or '').strip().lower()
    if query:
        chats = [
            chat for chat in chats
            if query in str(chat.get('company_name', '')).lower()
            or query in str(chat.get('vacancy_title', '')).lower()
            or query in str((chat.get('last_message') or {}).get('text', '')).lower()
        ]

    return render(
        request,
        'chat_list.html',
        {
            'chats': chats,
            'count': count,
            'query': request.GET.get('q', ''),
            'current_tab': 'archived' if is_archived_view else 'active',
            'next_url': next_url,
            'prev_url': prev_url,
            'api_user': request.session.get('api_user'),
        },
    )


def _safe_chat_next_url(request: HttpRequest) -> str | None:
    next_url = str(request.POST.get('next') or request.GET.get('next') or '').strip()
    if next_url.startswith('/'):
        return next_url
    return None


@api_login_required
def applicant_chat_archive(request: HttpRequest, chat_id: int) -> HttpResponse:
    denied_response = _require_applicant_route_access(
        request,
        'Чаты соискателя доступны только соискателям.',
        'Applicant chats are available only to applicants.',
    )
    if denied_response is not None:
        return denied_response

    if request.method != 'POST':
        return redirect('applicant_chats')

    try:
        resp = api_post(request, f'chats/{chat_id}/archive/')
        data = _safe_json(resp)
        if resp.status_code >= 400:
            messages.error(
                request,
                _first_error(data, _ui_text(request, 'Не удалось архивировать чат', 'Failed to archive chat')),
            )
        else:
            messages.success(request, _ui_text(request, 'Чат перенесен в архив', 'Chat moved to archive'))
    except Exception:
        messages.error(request, _ui_text(request, 'Ошибка сети при архивации чата', 'Network error while archiving chat'))

    return redirect(_safe_chat_next_url(request) or 'applicant_chats')


@api_login_required
def applicant_chat_unarchive(request: HttpRequest, chat_id: int) -> HttpResponse:
    denied_response = _require_applicant_route_access(
        request,
        'Чаты соискателя доступны только соискателям.',
        'Applicant chats are available only to applicants.',
    )
    if denied_response is not None:
        return denied_response

    if request.method != 'POST':
        return redirect('applicant_chats')

    try:
        resp = api_post(request, f'chats/{chat_id}/unarchive/')
        data = _safe_json(resp)
        if resp.status_code >= 400:
            messages.error(
                request,
                _first_error(data, _ui_text(request, 'Не удалось вернуть чат из архива', 'Failed to restore chat from archive')),
            )
        else:
            messages.success(request, _ui_text(request, 'Чат возвращен из архива', 'Chat restored from archive'))
    except Exception:
        messages.error(
            request,
            _ui_text(request, 'Ошибка сети при восстановлении чата', 'Network error while restoring chat'),
        )

    return redirect(_safe_chat_next_url(request) or 'applicant_chats')


@api_login_required
def applicant_chat_detail(request: HttpRequest, chat_id: int) -> HttpResponse:
    denied_response = _require_applicant_route_access(
        request,
        'Чаты соискателя доступны только соискателям.',
        'Applicant chats are available only to applicants.',
    )
    if denied_response is not None:
        return denied_response

    chat = None
    chat_messages = []

    try:
        chat_resp = api_get(request, f'chats/{chat_id}/')
        chat_data = _safe_json(chat_resp)
        if chat_resp.status_code >= 400 or not isinstance(chat_data, dict):
            messages.error(request, _first_error(chat_data, 'Чат не найден'))
            return redirect('applicant_chats')
        chat = chat_data
    except Exception:
        messages.error(request, 'Ошибка сети при загрузке чата')
        return redirect('applicant_chats')

    try:
        messages_resp = api_get(request, f'chats/{chat_id}/messages/')
        messages_data = _safe_json(messages_resp)
        if messages_resp.status_code < 400:
            chat_messages = _extract_results(messages_data)
            if not chat_messages and isinstance(messages_data, list):
                chat_messages = messages_data
        else:
            messages.error(request, _first_error(messages_data, 'Не удалось получить сообщения'))
    except Exception:
        messages.error(request, 'Ошибка сети при загрузке сообщений')

    return render(
        request,
        'chat_detail.html',
        {
            'chat': chat,
            'chat_messages': chat_messages,
            'api_user': request.session.get('api_user'),
        },
    )


@api_login_required
def applicant_chat_send_message(request: HttpRequest, chat_id: int) -> HttpResponse:
    denied_response = _require_applicant_route_access(
        request,
        'Чаты соискателя доступны только соискателям.',
        'Applicant chats are available only to applicants.',
    )
    if denied_response is not None:
        return denied_response

    if request.method != 'POST':
        return redirect('applicant_chat_detail', chat_id=chat_id)

    text = (request.POST.get('text') or '').strip()
    if not text:
        messages.error(request, 'Введите текст сообщения')
        return redirect('applicant_chat_detail', chat_id=chat_id)

    try:
        resp = api_post(request, f'chats/{chat_id}/send_message/', json={'text': text})
        data = _safe_json(resp)
        if resp.status_code >= 400:
            messages.error(request, _first_error(data, 'Не удалось отправить сообщение'))
    except Exception:
        messages.error(request, 'Ошибка сети при отправке сообщения')

    return redirect('applicant_chat_detail', chat_id=chat_id)


@api_login_required
def open_chat_for_vacancy(request: HttpRequest, vacancy_id: int) -> HttpResponse:
    denied_response = _require_applicant_route_access(
        request,
        'Чаты соискателя доступны только соискателям.',
        'Applicant chats are available only to applicants.',
    )
    if denied_response is not None:
        return denied_response

    try:
        resp = api_get(request, 'chats/by_vacancy/', params={'vacancy_id': vacancy_id})
        data = _safe_json(resp)
        if resp.status_code >= 400:
            messages.error(request, _first_error(data, 'Не удалось открыть чат по вакансии'))
            return redirect('vacancy_detail', vacancy_id=vacancy_id)

        if isinstance(data, dict) and data.get('id'):
            return redirect('applicant_chat_detail', chat_id=data['id'])

        messages.info(request, _first_error(data, 'Сначала откликнитесь на вакансию, чтобы открыть чат'))
        return redirect('vacancy_detail', vacancy_id=vacancy_id)
    except Exception:
        messages.error(request, 'Ошибка сети при открытии чата')
        return redirect('vacancy_detail', vacancy_id=vacancy_id)
