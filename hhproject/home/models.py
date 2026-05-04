from django.db import models

from apihh_main.models import (
    ActionType,
    AdminLog,
    Applicant,
    ApplicantInterest,
    ApplicantSkill,
    ApplicantSkillSuggestion,
    Backup,
    Chat,
    Company,
    Complaint,
    Employee,
    Favorites,
    Message,
    PasswordResetCode,
    Response,
    Skill,
    StatusResponse,
    StatusVacancies,
    User,
    Vacancy,
    VacancyCategorySuggestion,
    VacancyVideo,
    VacancyVideoLike,
    VacancyVideoView,
    WorkConditions,
    get_available_vacancy_categories,
)


class Role(models.Model):
    role_name = models.CharField(max_length=100)

    class Meta:
        db_table = "roles"
        verbose_name = "Роль"
        verbose_name_plural = "Роли"
        managed = False

    def __str__(self):
        return self.role_name


__all__ = [
    "ActionType",
    "AdminLog",
    "Applicant",
    "ApplicantInterest",
    "ApplicantSkill",
    "ApplicantSkillSuggestion",
    "Backup",
    "Chat",
    "Company",
    "Complaint",
    "Employee",
    "Favorites",
    "Message",
    "PasswordResetCode",
    "Response",
    "Role",
    "Skill",
    "StatusResponse",
    "StatusVacancies",
    "User",
    "Vacancy",
    "VacancyCategorySuggestion",
    "VacancyVideo",
    "VacancyVideoLike",
    "VacancyVideoView",
    "WorkConditions",
    "get_available_vacancy_categories",
]
