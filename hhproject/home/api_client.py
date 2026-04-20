import os
from urllib.parse import urljoin

import requests


DEFAULT_TIMEOUT = 15


def api_base_url() -> str:
    base = os.getenv('API_BASE_URL', 'http://172.20.10.2:8001/api/')
    if not base.endswith('/'):
        base += '/'
    return base


def _make_url(path: str) -> str:
    return urljoin(api_base_url(), path.lstrip('/'))


def get_token(request):
    return request.session.get('api_access')


def set_tokens(request, access: str, refresh: str | None = None):
    request.session['api_access'] = access
    if refresh is not None:
        request.session['api_refresh'] = refresh


def clear_tokens(request):
    request.session.pop('api_access', None)
    request.session.pop('api_refresh', None)
    request.session.pop('api_user', None)


def _headers(request, extra: dict | None = None) -> dict:
    headers = {'Accept': 'application/json'}
    token = get_token(request)
    if token:
        headers['Authorization'] = f'Bearer {token}'
    if extra:
        headers.update(extra)
    return headers


def _is_auth_endpoint(path: str) -> bool:
    normalized = path.lstrip('/')
    return normalized.startswith('auth/login/') or normalized.startswith('token/refresh/')


def _refresh_access_token(request) -> bool:
    refresh = request.session.get('api_refresh')
    if not refresh:
        return False

    try:
        response = requests.post(
            _make_url('token/refresh/'),
            json={'refresh': refresh},
            headers={'Accept': 'application/json'},
            timeout=DEFAULT_TIMEOUT,
        )
    except Exception:
        return False

    if response.status_code >= 400:
        clear_tokens(request)
        return False

    try:
        payload = response.json() or {}
    except Exception:
        clear_tokens(request)
        return False

    access = payload.get('access')
    if not access:
        clear_tokens(request)
        return False

    set_tokens(request, access, payload.get('refresh'))
    return True


def _rewind_files(files) -> None:
    if not files:
        return

    file_objects = []
    if isinstance(files, dict):
        file_objects = list(files.values())
    elif isinstance(files, (list, tuple)):
        for item in files:
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                file_objects.append(item[1])

    for file_obj in file_objects:
        if hasattr(file_obj, 'seek'):
            try:
                file_obj.seek(0)
            except Exception:
                continue


def _request(request, method: str, path: str, *, params=None, json=None, data=None, files=None, headers: dict | None = None):
    url = _make_url(path)
    response = requests.request(
        method,
        url,
        params=params,
        json=json,
        data=data,
        files=files,
        headers=_headers(request, headers),
        timeout=DEFAULT_TIMEOUT,
    )

    if response.status_code != 401 or _is_auth_endpoint(path):
        return response

    if not _refresh_access_token(request):
        return response

    _rewind_files(files)
    return requests.request(
        method,
        url,
        params=params,
        json=json,
        data=data,
        files=files,
        headers=_headers(request, headers),
        timeout=DEFAULT_TIMEOUT,
    )


def api_get(request, path: str, params: dict | None = None, headers: dict | None = None):
    return _request(request, 'GET', path, params=params, headers=headers)


def api_post(request, path: str, json: dict | None = None, data=None, files=None, headers: dict | None = None):
    return _request(
        request,
        'POST',
        path,
        json=json,
        data=data,
        files=files,
        headers=headers,
    )


def api_put(request, path: str, json: dict | None = None, headers: dict | None = None):
    return _request(
        request,
        'PUT',
        path,
        json=json,
        headers=headers,
    )


def api_patch(request, path: str, json: dict | None = None, data=None, files=None, headers: dict | None = None):
    return _request(
        request,
        'PATCH',
        path,
        json=json,
        data=data,
        files=files,
        headers=headers,
    )


def api_delete(request, path: str, headers: dict | None = None):
    return _request(request, 'DELETE', path, headers=headers)
