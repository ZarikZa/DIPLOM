def api_user(request):
    """Прокидываем пользователя из JWT-сессии во все шаблоны."""
    return {
        'api_user': request.session.get('api_user'),
        'ui_theme': request.session.get('ui_theme', 'light'),
    }
