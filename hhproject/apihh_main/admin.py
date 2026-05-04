from django.contrib import admin
from django.utils import timezone

from .models import *
    
@admin.register(Applicant)
class AplicatAdmin(admin.ModelAdmin):
    pass

@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    pass

@admin.register(Vacancy)
class VacancyAdmin(admin.ModelAdmin):
    pass


@admin.register(VacancyCategorySuggestion)
class VacancyCategorySuggestionAdmin(admin.ModelAdmin):
    list_display = ("name", "company", "status", "created_at", "reviewed_at")
    list_filter = ("status", "created_at")
    search_fields = ("name", "company__name", "company__user__email")

@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    pass

@admin.register(StatusVacancies)
class StatusVacanciesAdmin(admin.ModelAdmin):
    pass

@admin.register(StatusResponse)
class StatusResponseAdmin(admin.ModelAdmin):
    pass

@admin.register(Response)
class ResponseAdmin(admin.ModelAdmin):
    pass

@admin.register(Backup)
class BackupAdmin(admin.ModelAdmin):
    pass

@admin.register(AdminLog)
class AdminLogAdmin(admin.ModelAdmin):
    pass

@admin.register(User)
class User(admin.ModelAdmin):
    pass


@admin.register(Complaint)
class ComplaintAdmin(admin.ModelAdmin):
    list_display = ['vacancy', 'complainant', 'complaint_type', 'status', 'created_at']
    list_filter = ['status', 'complaint_type', 'created_at']
    search_fields = ['vacancy__position', 'complainant__email', 'description']
    readonly_fields = ['created_at']
    actions = ['mark_as_reviewed', 'mark_as_rejected']
    
    def mark_as_reviewed(self, request, queryset):
        updated = queryset.update(status=Complaint.STATUS_REVIEWED, resolved_at=timezone.now())
        self.message_user(request, f'{updated} жалоб отмечено как рассмотренные')
    
    def mark_as_rejected(self, request, queryset):
        updated = queryset.update(status=Complaint.STATUS_REJECTED, resolved_at=timezone.now())
        self.message_user(request, f'{updated} жалоб отклонено')
    
    mark_as_reviewed.short_description = "Отметить выбранные жалобы как рассмотренные"
    mark_as_rejected.short_description = "Отклонить выбранные жалобы"

@admin.register(VacancyVideo)
class VacancyVideoAdmin(admin.ModelAdmin):
    pass

@admin.register(VacancyVideoView)
class VacancyVideoViewAdmin(admin.ModelAdmin):
    pass

@admin.register(VacancyVideoLike)
class VacancyVideoLikeAdmin(admin.ModelAdmin):
    pass

@admin.register(Skill)
class SkillAdmin(admin.ModelAdmin):
    pass

@admin.register(ApplicantSkillSuggestion)
class ApplicantSkillSuggestionAdmin(admin.ModelAdmin):
    list_display = ('name', 'applicant', 'status', 'created_at', 'reviewed_at')
    list_filter = ('status', 'created_at')
    search_fields = ('name', 'applicant__user__email', 'applicant__first_name', 'applicant__last_name')

@admin.register(Message)
class MessegeAdmin(admin.ModelAdmin):
    pass
