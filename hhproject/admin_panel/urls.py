# urls.py
from django.urls import path
from .views import *

urlpatterns = [
    path('', admin_dashboard, name='admin_dashboard'),
    
    path('companies/', company_moderation, name='admin_company_moderation'),
    path('companies/<int:company_id>/', company_detail, name='admin_company_detail'),
    path('categories/', category_moderation, name='admin_category_moderation'),
    path('taxonomy/', taxonomy_management, name='admin_taxonomy_management'),
    
    path('backups/', backup_dashboard, name='admin_backup_management'),
    path('backups/create/', create_backup_api, name='admin_create_backup'),
    path('backups/upload/', upload_backup_api, name='admin_upload_backup'),
    path('backups/list/', get_backups_list_api, name='admin_backups_list'),
    path('backups/<int:backup_id>/download/', download_backup_api, name='admin_download_backup'),
    path('backups/<int:backup_id>/delete/', delete_backup_api, name='admin_delete_backup'),
    path('backups/<int:backup_id>/restore/', restore_backup_api, name='admin_restore_backup'),
    path('backups/system-status/', system_status_api, name='admin_system_status'),
    path('backups/media-stats/', media_stats_api, name='admin_media_stats'),

    path('logs/', admin_logs, name='admin_logs'),
    path('logs/clear/', clear_logs, name='admin_clear_logs'),
    
    path('api/company-stats/', api_company_stats, name='api_company_stats'),
    path('api/recent-activity/', api_recent_activity, name='api_recent_activity'),

    path('site-admins/', admin_management, name='admin_management'),
    path('site-admins/create/', create_site_admin, name='create_site_admin'),
    path('site-admins/<int:admin_id>/edit/', edit_site_admin, name='edit_site_admin'),
    path('site-admins/<int:admin_id>/toggle/', toggle_site_admin_status, name='toggle_site_admin_status'),
    path('site-admins/<int:admin_id>/delete/', delete_site_admin, name='delete_site_admin'),
    
    path('statistics/', admin_statistics, name='admin_statistics'),
    path('admin/statistics/export-pdf/', export_statistics_pdf, name='export_statistics_pdf'),
    path('admin/statistics/export-excel/', export_statistics_excel, name='export_statistics_excel'),

    path('complaints/', admin_complaints, name='admin_complaints'),
    path('complaints/<int:complaint_id>/', complaint_detail, name='complaint_detail'),
    path('complaints/<int:complaint_id>/update-status/', update_complaint_status, name='update_complaint_status'),
    path('vacancy/<int:vacancy_id>/archive/', archive_vacancy, name='admin_archive_vacancy'),
    path('vacancy/<int:vacancy_id>/unarchive/', unarchive_vacancy, name='admin_unarchive_vacancy'),
    path('profile/', admin_profile, name='admin_profile'),
    path('admin/profile/', admin_profile, name='admin_profile'),
    path('admin/profile/edit/', admin_profile_edit, name='admin_profile_edit'),
]
