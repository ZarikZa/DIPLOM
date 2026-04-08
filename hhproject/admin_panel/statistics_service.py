from django.db.models import Count, Q
from django.utils import timezone
from datetime import timedelta, datetime
from home.models import (
    User, Company, Applicant, Vacancy, Response, 
    Complaint, Favorites, StatusVacancies, StatusResponse
)
import io
import csv
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg') 
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import user_passes_test
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch

class StatisticsService:
    
    @staticmethod
    def get_main_statistics(start_date=None, end_date=None):
        """Основная статистика с поддержкой периода"""
        today = timezone.now().date()
        week_ago = today - timedelta(days=7)
        
        # Базовые запросы
        base_filters = {}
        if start_date and end_date:
            base_filters = {
                'date_joined__date__range': [start_date, end_date]
            }
        
        user_count = User.objects.filter(**base_filters).count()
        
        # Для компаний, вакансий и откликов используем соответствующие поля дат
        company_filters = {}
        vacancy_filters = {}
        response_filters = {}
        
        if start_date and end_date:
            company_filters = {'created_at__date__range': [start_date, end_date]}
            vacancy_filters = {'created_date__date__range': [start_date, end_date]}
            response_filters = {'response_date__date__range': [start_date, end_date]}
        
        company_count = Company.objects.filter(**company_filters).count()
        vacancy_count = Vacancy.objects.filter(**vacancy_filters).count()
        response_count = Response.objects.filter(**response_filters).count()
        
        # Статистика за неделю (всегда за последние 7 дней)
        new_users_week = User.objects.filter(
            date_joined__date__gte=week_ago
        ).count()
        new_companies_week = Company.objects.filter(
            created_at__date__gte=week_ago
        ).count()
        new_vacancies_week = Vacancy.objects.filter(
            created_date__date__gte=week_ago
        ).count()
        new_responses_week = Response.objects.filter(
            response_date__date__gte=week_ago
        ).count()
        
        return {
            'total_users': user_count,
            'total_companies': company_count,
            'total_applicants': Applicant.objects.count(),  # Всего
            'total_vacancies': vacancy_count,
            'total_responses': response_count,
            'total_favorites': Favorites.objects.count(),  # Всего
            'total_complaints': Complaint.objects.count(),  # Всего
            
            'new_users_week': new_users_week,
            'new_companies_week': new_companies_week,
            'new_vacancies_week': new_vacancies_week,
            'new_responses_week': new_responses_week,
            
            'active_companies': Company.objects.filter(status='approved').count(),  # Всего
            'pending_companies': Company.objects.filter(status='pending').count(),  # Всего
            'rejected_companies': Company.objects.filter(status='rejected').count(),  # Всего
        }
    
    @staticmethod
    def get_user_type_distribution(start_date=None, end_date=None):
        """Распределение пользователей по типам с поддержкой периода"""
        base_filters = {}
        if start_date and end_date:
            base_filters = {'date_joined__date__range': [start_date, end_date]}
        
        distribution = User.objects.filter(**base_filters).values('user_type').annotate(
            count=Count('id')
        ).order_by('-count')
        
        colors = ['#3b82f6', '#f59e0b', '#10b981', '#ef4444', '#8b5cf6']
        
        labels = []
        data = []
        for item in distribution:
            labels.append(dict(User.USER_TYPE_CHOICES).get(item['user_type'], item['user_type']))
            data.append(item['count'])
        
        total = sum(data)
        percentages = [round((count / total * 100), 1) for count in data] if total > 0 else []
        
        return {
            'labels': labels,
            'data': data,
            'percentages': percentages,
            'colors': colors[:len(data)],
            'total': total
        }
    
    @staticmethod
    def get_vacancy_statistics(start_date=None, end_date=None):
        """Статистика по вакансиям с поддержкой периода"""
        base_filters = {}
        if start_date and end_date:
            base_filters = {'created_date__date__range': [start_date, end_date]}
        
        category_stats = Vacancy.objects.filter(**base_filters).values('category').annotate(
            count=Count('id')
        ).order_by('-count')
        
        category_colors = ['#3b82f6', '#f59e0b', '#10b981', '#8b5cf6', '#06b6d4', '#84cc16']
        
        category_labels = []
        category_data = []
        for item in category_stats:
            category_labels.append(item['category'])
            category_data.append(item['count'])
        
        if not category_data:
            category_labels = ['IT', 'Маркетинг', 'Продажи', 'HR']
            category_data = [10, 5, 3, 2]
        
        return {
            'category': {
                'labels': category_labels,
                'data': category_data,
                'colors': category_colors[:len(category_labels)],
                'max': max(category_data) if category_data else 1
            }
        }
    
    @staticmethod
    def get_company_statistics(start_date=None, end_date=None):
        """Статистика по компаниям с поддержкой периода"""
        base_filters = {}
        if start_date and end_date:
            base_filters = {'created_at__date__range': [start_date, end_date]}
        
        status_stats = Company.objects.filter(**base_filters).values('status').annotate(
            count=Count('id')
        )
        
        status_colors = {
            'approved': '#10b981',
            'pending': '#f59e0b',  
            'rejected': '#ef4444',
        }
        
        labels = []
        data = []
        colors = []
        for item in status_stats:
            status_key = item['status']
            label = dict(Company.STATUS_CHOICES).get(status_key, status_key)
            labels.append(label)
            data.append(item['count'])
            colors.append(status_colors.get(status_key, '#3b82f6'))
        
        total = sum(data)
        percentages = [round((count / total * 100), 1) for count in data] if total > 0 else []
        
        return {
            'status_distribution': {
                'labels': labels,
                'data': data,
                'percentages': percentages,
                'colors': colors,
                'total': total
            }
        }
    
    @staticmethod
    def get_response_statistics(start_date=None, end_date=None):
        """Статистика по откликам с поддержкой периода"""
        base_filters = {}
        if start_date and end_date:
            base_filters = {'response_date__date__range': [start_date, end_date]}
        
        status_stats = Response.objects.filter(**base_filters).values('status__status_response_name').annotate(
            count=Count('id')
        ).order_by('-count')
        
        today = timezone.now().date()
        daily_data = []
        
        # Если указан период, используем его для daily_activity
        if start_date and end_date:
            start = datetime.strptime(start_date, '%Y-%m-%d').date()
            end = datetime.strptime(end_date, '%Y-%m-%d').date()
            days_diff = (end - start).days
            
            for i in range(min(days_diff + 1, 30)):  # Ограничиваем 30 днями
                day = start + timedelta(days=i)
                if day <= end:
                    count = Response.objects.filter(response_date__date=day).count()
                    daily_data.append({
                        'date': day.strftime('%d.%m'),
                        'count': count
                    })
        else:
            # По умолчанию последние 7 дней
            for i in range(7):
                day = today - timedelta(days=6-i)
                count = Response.objects.filter(response_date__date=day).count()
                daily_data.append({
                    'date': day.strftime('%d.%m'),
                    'count': count
                })
        
        status_colors = ['#10b981', '#3b82f6', '#f59e0b', '#ef4444', '#8b5cf6']
        
        status_labels = []
        status_data = []
        for item in status_stats:
            status_labels.append(item['status__status_response_name'])
            status_data.append(item['count'])
        
        total = sum(status_data)
        
        return {
            'status_distribution': {
                'labels': status_labels,
                'data': status_data,
                'colors': status_colors[:len(status_labels)],
                'total': total
            },
            'daily_activity': daily_data,
            'daily_max': max([day['count'] for day in daily_data]) if daily_data else 1
        }
    
    @staticmethod
    def get_complaint_statistics(start_date=None, end_date=None):
        """Статистика по жалобам с поддержкой периода"""
        base_filters = {}
        if start_date and end_date:
            base_filters = {'created_at__date__range': [start_date, end_date]}
        
        type_stats = Complaint.objects.filter(**base_filters).values('complaint_type').annotate(
            count=Count('id')
        ).order_by('-count')
        
        type_colors = ['#3b82f6', '#f59e0b', '#ef4444', '#10b981', '#8b5cf6', '#06b6d4']
        
        type_labels = []
        type_data = []
        for item in type_stats:
            type_labels.append(dict(Complaint.COMPLAINT_TYPES).get(item['complaint_type'], item['complaint_type']))
            type_data.append(item['count'])
        
        # Если данных нет, создаем демо-данные для тестирования
        if not type_data:
            type_labels = ['Спам', 'Мошенничество', 'Неуместный контент']
            type_data = [5, 3, 2]
        
        return {
            'type_distribution': {
                'labels': type_labels,
                'data': type_data,
                'colors': type_colors[:len(type_labels)],
                'max': max(type_data) if type_data else 1
            }
        }