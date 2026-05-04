from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework import serializers
from .models import Company

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    # заставляем SimpleJWT принимать email вместо username
    username_field = "email"

    def validate(self, attrs):
        # превращаем {"email": "...", "password": "..."} в формат, который ждёт базовый сериализатор
        if "email" in attrs and "username" not in attrs:
            attrs["username"] = attrs["email"]

        data = super().validate(attrs)

        if self.user.user_type == "company":
            company = getattr(self.user, "company", None)
            if not company:
                raise serializers.ValidationError(
                    {"detail": "Профиль компании не найден. Обратитесь в поддержку."}
                )

            if company.status != Company.STATUS_APPROVED:
                status_name = dict(Company.STATUS_CHOICES).get(company.status, company.status)
                raise serializers.ValidationError(
                    {
                        "detail": (
                            f"Вход для компании недоступен. Текущий статус: {status_name}. "
                            "Авторизация возможна только после подтверждения компании."
                        )
                    }
                )

        data.update({
            'user_id': self.user.id,
            'username': self.user.username,
            'email': self.user.email,
            'user_type': self.user.user_type,
            'first_name': self.user.first_name,
            'last_name': self.user.last_name,
            'is_superuser': bool(self.user.is_superuser),
        })
        return data

class UserLoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)
