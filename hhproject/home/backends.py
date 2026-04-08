# backends.py
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model
from django.db.models import Q

class EmailBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        UserModel = get_user_model()
        try:
            print(f"🔍 Ищем пользователя с email: {username}")  # отладка
            
            # Ищем по email (username - это email в форме)
            user = UserModel.objects.get(email=username)
            print(f"✅ Найден пользователь: {user.email}")  # отладка
            
            # Проверяем пароль
            if user.check_password(password):
                print("✅ Пароль верный")  # отладка
                return user
            else:
                print("❌ Неверный пароль")  # отладка
                return None
                
        except UserModel.DoesNotExist:
            print(f"❌ Пользователь с email {username} не найден")  # отладка
            return None
        except Exception as e:
            print(f"❌ Ошибка аутентификации: {e}")  # отладка
            return None