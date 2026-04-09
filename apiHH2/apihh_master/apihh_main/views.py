import logging

logger = logging.getLogger(__name__)

from io import BytesIO

from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db.models import Exists, OuterRef, Count, Sum, F
from django.http import HttpResponse

from rest_framework import status, viewsets, mixins, serializers
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAuthenticatedOrReadOnly
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.views import APIView
from rest_framework.response import Response as DRFResponse
from rest_framework_simplejwt.views import TokenObtainPairView
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.generics import ListAPIView
from rest_framework.exceptions import ValidationError

from PIL import Image, ImageDraw, ImageFont

from .pagination import VacancyPagination
from .filters import VacancyFilter
from .permissions import IsContentManager, IsAdminSite, IsCompanyOwner, IsCompanyOwnerOrStaff

# ✅ ВАЖНО: разруливаем конфликт имён Response (DRF) vs Response (model)
from .models import (
    User, Company, Vacancy, Applicant, Employee, WorkConditions,
    StatusVacancies, StatusResponse, Complaint, Favorites,
    AdminLog, Backup, Chat, Message,
    VacancyVideo, VacancyVideoView, VacancyVideoLike,
    Response as ResponseModel, Skill, ApplicantSkill, ApplicantInterest,
    VacancyCategorySuggestion,
    get_available_vacancy_categories,
    PasswordResetCode,
)

from .serializers import (
    CompanySerializer,
    CompanyStatusSerializer,
    VacancyListSerializer, VacancyDetailSerializer, CompanyVacancySerializer,
    ApplicantSerializer, ApplicantSkillSerializer, ApplicantSkillUpsertSerializer,
    EmployeeSerializer,
    ComplaintSerializer,
    AdminComplaintSerializer,
    FavoritesSerializer,
    WorkConditionsSerializer,
    StatusVacanciesSerializer,
    StatusResponseSerializer,
    SkillSerializer,
    AdminLogSerializer,
    BackupSerializer,
    UserSerializer,
    ApplicantRegistrationSerializer,
    CompanyRegistrationSerializer,
    EmployeeRegistrationSerializer,
    UserProfileSerializer,
    ResponseSerializer, CreateResponseSerializer, CheckResponseSerializer,
    ChatSerializer, MessageSerializer, SendMessageSerializer,
    VacancyVideoAdminSerializer,
    ContentManagerVideoSerializer, ContentManagerVideoListSerializer,
    VacancyVideoFeedSerializer,
    PasswordResetRequestSerializer, PasswordResetConfirmSerializer,
    ChangePasswordSerializer,
    CompanyEmployeeCreateSerializer, CompanyEmployeeListSerializer, CompanyEmployeeUpdateSerializer,
    VacancyCategoryOptionSerializer,
    CompanyVacancyCategorySuggestionCreateSerializer,
    CompanyVacancyCategorySuggestionSerializer,
    AdminVacancyCategorySuggestionSerializer,
    AdminVacancyCategorySuggestionCreateSerializer,
    AdminVacancyCategorySuggestionUpdateSerializer,
)

from .jwt_serializers import CustomTokenObtainPairSerializer
from .email_service import send_email_message
from .utils import validate_video


logger = logging.getLogger(__name__)
UserModel = get_user_model()


def _vacancy_categories() -> list[str]:
    return get_available_vacancy_categories()


def _restore_mojibake(text_value: str | None) -> str:
    raw = str(text_value or '')
    if not raw:
        return ''
    try:
        restored = raw.encode('cp1251').decode('utf-8')
    except Exception:
        return raw
    return restored or raw


def _response_status_alias(status_name: str | None) -> str:
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


def build_cm_profile_stats(user):
    try:
        employee = user.employee
    except Employee.DoesNotExist:
        raise ValidationError({'detail': 'Пользователь не является сотрудником компании'})

    if employee.role != 'content_manager':
        raise ValidationError({'detail': 'Статистика доступна только контент-менеджеру'})

    company = employee.company
    if not company:
        raise ValidationError({'detail': 'Компания сотрудника не найдена'})

    vacancies_qs = Vacancy.objects.filter(company=company)
    videos_qs = VacancyVideo.objects.filter(company=company)
    responses_qs = ResponseModel.objects.filter(vacancy__company=company)

    responses_by_status = list(
        responses_qs
        .values('status__status_response_name')
        .annotate(count=Count('id'))
        .order_by('-count')
    )

    top_vacancies = list(
        responses_qs
        .values('vacancy_id', 'vacancy__position')
        .annotate(count=Count('id'))
        .order_by('-count')[:5]
    )

    stats = {
        'videos_count': videos_qs.count(),
        'vacancies_count': vacancies_qs.count(),
        'responses_count': responses_qs.count(),
        'video_views_count': VacancyVideoView.objects.filter(video__company=company).count(),
        'video_likes_count': VacancyVideoLike.objects.filter(video__company=company).count(),
        'vacancy_views_count': vacancies_qs.aggregate(total=Sum('views')).get('total') or 0,
    }

    manager_name = f"{user.first_name} {user.last_name}".strip() or user.email

    return {
        'manager': {
            'id': user.id,
            'full_name': manager_name,
            'role': employee.role,
            'email': user.email,
            'phone': user.phone,
        },
        'company': {
            'id': company.id,
            'name': company.name,
            'number': company.number,
            'industry': company.industry,
            'description': company.description,
        },
        'stats': stats,
        'responses_by_status': [
            {'status': item['status__status_response_name'], 'count': item['count']}
            for item in responses_by_status
        ],
        'top_vacancies': [
            {
                'vacancy_id': item['vacancy_id'],
                'position': item['vacancy__position'],
                'responses_count': item['count'],
            }
            for item in top_vacancies
        ],
        'chart': {
            'labels': ['Видео', 'Вакансии', 'Отклики', 'Просмотры видео', 'Лайки видео'],
            'values': [
                stats['videos_count'],
                stats['vacancies_count'],
                stats['responses_count'],
                stats['video_views_count'],
                stats['video_likes_count'],
            ],
        },
    }


# -------------------- Company --------------------

class CompanyViewSet(viewsets.ModelViewSet):
    queryset = Company.objects.all()
    serializer_class = CompanySerializer

    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return [AllowAny()]
        return [IsAuthenticated(), IsAdminSite()]


class CompanyMeAPIView(APIView):

    permission_classes = [IsAuthenticated, IsCompanyOwnerOrStaff]

    def _get_company(self, request):
        u = request.user
        if u.user_type == 'company':
            return getattr(u, 'company', None)
        return getattr(getattr(u, 'employee', None), 'company', None)

    def get(self, request):
        company = self._get_company(request)
        if not company:
            return DRFResponse({"detail": "Компания не найдена"}, status=status.HTTP_404_NOT_FOUND)
        return DRFResponse(CompanySerializer(company, context={'request': request}).data)

    def patch(self, request):
        company = self._get_company(request)
        if not company:
            return DRFResponse({"detail": "Компания не найдена"}, status=status.HTTP_404_NOT_FOUND)
        ser = CompanySerializer(company, data=request.data, partial=True, context={'request': request})
        ser.is_valid(raise_exception=True)
        ser.save()
        return DRFResponse(ser.data)


class CompanyVacancyViewSet(viewsets.ModelViewSet):
    """CRUD вакансий компании + архив/разархив."""

    permission_classes = [IsAuthenticated, IsCompanyOwnerOrStaff]
    serializer_class = CompanyVacancySerializer

    def _get_company(self, request):
        u = request.user
        return getattr(u, 'company', None) if u.user_type == 'company' else getattr(u.employee, 'company', None)

    def get_queryset(self):
        company = self._get_company(self.request)
        if not company:
            return Vacancy.objects.none()
        qs = Vacancy.objects.filter(company=company).select_related('company', 'work_conditions', 'status').order_by('-created_date')
        # archived=1 -> показать всё, иначе только неархивные
        # For detail/update/archive actions we must include archived records,
        # otherwise get_object() raises "No Vacancy matches the given query."
        archived = self.request.query_params.get('archived')
        include_archived_actions = {'retrieve', 'update', 'partial_update', 'archive', 'unarchive', 'destroy'}
        if archived in ('1', 'true', 'True', 'yes') or self.action in include_archived_actions:
            return qs
        return qs.filter(is_archived=False)

    def perform_create(self, serializer):
        company = self._get_company(self.request)
        serializer.save(company=company)

    @action(detail=True, methods=['post'])
    def archive(self, request, pk=None):
        obj = self.get_object()
        obj.is_archived = True
        obj.save(update_fields=['is_archived'])
        return DRFResponse({'status': 'archived', 'id': obj.id})

    @action(detail=True, methods=['post'])
    def unarchive(self, request, pk=None):
        obj = self.get_object()
        obj.is_archived = False
        obj.save(update_fields=['is_archived'])
        return DRFResponse({'status': 'unarchived', 'id': obj.id})


class CompanyResponsesViewSet(viewsets.ReadOnlyModelViewSet):
    """Отклики по вакансиям компании."""

    permission_classes = [IsAuthenticated, IsCompanyOwnerOrStaff]
    serializer_class = ResponseSerializer

    def _get_company(self, request):
        u = request.user
        return getattr(u, 'company', None) if u.user_type == 'company' else getattr(u.employee, 'company', None)

    def get_queryset(self):
        company = self._get_company(self.request)
        if not company:
            return ResponseModel.objects.none()
        return (ResponseModel.objects
                .select_related('applicants', 'vacancy', 'vacancy__company', 'status')
                .filter(vacancy__company=company)
                .order_by('-response_date'))


class CompanyComplaintsViewSet(viewsets.ReadOnlyModelViewSet):
    """Жалобы на вакансии компании."""

    permission_classes = [IsAuthenticated, IsCompanyOwnerOrStaff]
    serializer_class = ComplaintSerializer

    def _get_company(self, request):
        u = request.user
        return getattr(u, 'company', None) if u.user_type == 'company' else getattr(u.employee, 'company', None)

    def get_queryset(self):
        company = self._get_company(self.request)
        if not company:
            return Complaint.objects.none()
        return Complaint.objects.filter(vacancy__company=company).select_related('vacancy', 'vacancy__company', 'complainant').order_by('-created_at')


class CompanyEmployeesViewSet(viewsets.ModelViewSet):
    """Владелец компании управляет HR и Content Manager своей компании."""

    permission_classes = [IsAuthenticated, IsCompanyOwner]

    def get_queryset(self):
        company = self.request.user.company
        return Employee.objects.filter(company=company, role__in=['hr', 'content_manager']).select_related('user').order_by('id')

    def get_serializer_class(self):
        if self.action == 'create':
            return CompanyEmployeeCreateSerializer
        if self.action in ('update', 'partial_update'):
            return CompanyEmployeeUpdateSerializer
        return CompanyEmployeeListSerializer

    def create(self, request, *args, **kwargs):
        ser = self.get_serializer(data=request.data, context={'request': request})
        ser.is_valid(raise_exception=True)
        employee = ser.save()
        return DRFResponse(CompanyEmployeeListSerializer(employee).data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        employee = self.get_object()
        ser = self.get_serializer(employee, data=request.data, context={'request': request})
        ser.is_valid(raise_exception=True)
        employee = ser.save()
        return DRFResponse(CompanyEmployeeListSerializer(employee).data)

    def partial_update(self, request, *args, **kwargs):
        employee = self.get_object()
        ser = self.get_serializer(employee, data=request.data, partial=True, context={'request': request})
        ser.is_valid(raise_exception=True)
        employee = ser.save()
        return DRFResponse(CompanyEmployeeListSerializer(employee).data)

    def destroy(self, request, *args, **kwargs):
        employee = self.get_object()
        # мягкое удаление
        employee.user.is_active = False
        employee.user.save(update_fields=['is_active'])
        employee.delete()
        return DRFResponse(status=status.HTTP_204_NO_CONTENT)


# -------------------- Vacancy Categories --------------------

class VacancyCategoryViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticatedOrReadOnly]

    def list(self, request):
        categories = _vacancy_categories()
        search_query = str(request.query_params.get('search') or '').strip().lower()
        if search_query:
            categories = [item for item in categories if search_query in item.lower()]

        data = VacancyCategoryOptionSerializer(
            [{'name': item} for item in categories],
            many=True
        ).data
        return DRFResponse({'count': len(data), 'results': data}, status=status.HTTP_200_OK)


class CompanyVacancyCategorySuggestionViewSet(mixins.ListModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet):
    permission_classes = [IsAuthenticated, IsCompanyOwnerOrStaff]

    def _get_company(self, request):
        user = request.user
        if user.user_type == 'company':
            return getattr(user, 'company', None)
        employee = getattr(user, 'employee', None)
        return getattr(employee, 'company', None)

    def get_queryset(self):
        company = self._get_company(self.request)
        if not company:
            return VacancyCategorySuggestion.objects.none()
        return VacancyCategorySuggestion.objects.filter(company=company).order_by('-created_at')

    def get_serializer_class(self):
        if self.action == 'create':
            return CompanyVacancyCategorySuggestionCreateSerializer
        return CompanyVacancyCategorySuggestionSerializer

    def create(self, request, *args, **kwargs):
        company = self._get_company(request)
        if not company:
            return DRFResponse({'detail': 'Компания не найдена'}, status=status.HTTP_400_BAD_REQUEST)

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        suggestion = VacancyCategorySuggestion.objects.create(
            name=serializer.validated_data['name'],
            company=company,
            requested_by=request.user,
            status=VacancyCategorySuggestion.STATUS_PENDING,
        )
        response_data = CompanyVacancyCategorySuggestionSerializer(suggestion).data
        return DRFResponse(response_data, status=status.HTTP_201_CREATED)


class AdminVacancyCategorySuggestionViewSet(viewsets.ModelViewSet):
    queryset = VacancyCategorySuggestion.objects.all().select_related('company', 'requested_by', 'reviewed_by').order_by('-created_at')
    permission_classes = [IsAuthenticated, IsAdminSite]

    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
    filterset_fields = ['status', 'company']
    search_fields = ['name', 'company__name', 'company__user__email', 'requested_by__email']
    ordering_fields = ['created_at', 'reviewed_at', 'name']
    ordering = ['-created_at']

    def get_serializer_class(self):
        if self.action == 'create':
            return AdminVacancyCategorySuggestionCreateSerializer
        if self.action in ('update', 'partial_update'):
            return AdminVacancyCategorySuggestionUpdateSerializer
        return AdminVacancyCategorySuggestionSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        suggestion = VacancyCategorySuggestion.objects.create(
            name=serializer.validated_data['name'],
            company=None,
            requested_by=request.user,
            status=VacancyCategorySuggestion.STATUS_APPROVED,
            admin_notes=serializer.validated_data.get('admin_notes', ''),
            reviewed_by=request.user,
            reviewed_at=timezone.now(),
        )

        response_data = AdminVacancyCategorySuggestionSerializer(
            suggestion,
            context={'request': request},
        ).data
        return DRFResponse(response_data, status=status.HTTP_201_CREATED)

    def perform_update(self, serializer):
        suggestion = serializer.save()
        if 'status' in serializer.validated_data:
            suggestion.reviewed_by = self.request.user
            suggestion.reviewed_at = timezone.now()
            suggestion.save(update_fields=['reviewed_by', 'reviewed_at'])


# -------------------- Vacancy --------------------

class VacancyViewSet(viewsets.ModelViewSet):
    queryset = Vacancy.objects.all()
    serializer_class = VacancyListSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
    filterset_class = VacancyFilter
    search_fields = ['position', 'description', 'requirements', 'company__name', 'city', 'category']

    ordering_fields = ['created_date', 'salary_min', 'salary_max']
    ordering = ['-created_date']

    pagination_class = VacancyPagination

    def get_queryset(self):
        # Публичная выдача: не показываем архивные вакансии
        queryset = Vacancy.objects.select_related('company', 'work_conditions', 'status').filter(is_archived=False)
        search_query = (self.request.query_params.get('search') or '').strip()
        recommended_raw = (self.request.query_params.get('recommended') or '').strip().lower()
        use_recommended = recommended_raw in ('1', 'true', 'yes') and not search_query

        user = self.request.user
        if user.is_authenticated:
            try:
                applicant = user.applicant
                if use_recommended:
                    interest_categories = list(applicant.interests.values_list('category', flat=True))
                    if interest_categories:
                        queryset = queryset.filter(category__in=interest_categories)
                queryset = queryset.annotate(
                    is_favorite=Exists(
                        Favorites.objects.filter(applicant=applicant, vacancy=OuterRef('pk'))
                    ),
                    has_applied=Exists(
                        ResponseModel.objects.filter(applicants=applicant, vacancy=OuterRef('pk'))
                    )
                )
            except Applicant.DoesNotExist:
                pass

        return queryset

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return VacancyDetailSerializer
        return VacancyListSerializer

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        Vacancy.objects.filter(pk=instance.pk).update(views=F('views') + 1)
        instance.refresh_from_db(fields=['views'])
        serializer = self.get_serializer(instance)
        return DRFResponse(serializer.data)


# -------------------- Applicant --------------------

class ApplicantViewSet(viewsets.ModelViewSet):
    queryset = Applicant.objects.all()
    serializer_class = ApplicantSerializer
    permission_classes = [IsAuthenticated]

    def _build_interests_payload(self, applicant):
        return {
            'categories': list(applicant.interests.values_list('category', flat=True)),
            'available_categories': _vacancy_categories(),
        }

    @action(detail=False, methods=['get', 'put'], url_path='me/skills')
    def me_skills(self, request):
        try:
            applicant = request.user.applicant
        except Applicant.DoesNotExist:
            return DRFResponse({"detail": "Профиль соискателя не найден"}, status=status.HTTP_400_BAD_REQUEST)

        if request.method == 'GET':
            qs = (ApplicantSkill.objects
                  .filter(applicant=applicant)
                  .select_related('skill')
                  .order_by('skill__name'))
            return DRFResponse(ApplicantSkillSerializer(qs, many=True).data)

        skills = request.data.get('skills', None)
        if not isinstance(skills, list):
            return DRFResponse(
                {"detail": "Ожидается {\"skills\": [{\"skill_id\":1,\"level\":5}] }"},
                status=status.HTTP_400_BAD_REQUEST
            )

        ser = ApplicantSkillUpsertSerializer(data=skills, many=True)
        ser.is_valid(raise_exception=True)

        for item in ser.validated_data:
            skill_id = item['skill_id']
            level = item['level']

            try:
                skill = Skill.objects.get(id=skill_id)
            except Skill.DoesNotExist:
                return DRFResponse({"detail": f"Skill id={skill_id} не найден"}, status=status.HTTP_400_BAD_REQUEST)

            ApplicantSkill.objects.update_or_create(
                applicant=applicant,
                skill=skill,
                defaults={'level': level}
            )

        qs = (ApplicantSkill.objects
              .filter(applicant=applicant)
              .select_related('skill')
              .order_by('skill__name'))
        return DRFResponse(ApplicantSkillSerializer(qs, many=True).data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get', 'put'], url_path='me/interests')
    def me_interests(self, request):
        try:
            applicant = request.user.applicant
        except Applicant.DoesNotExist:
            return DRFResponse({"detail": "Профиль соискателя не найден"}, status=status.HTTP_400_BAD_REQUEST)

        if request.method == 'GET':
            return DRFResponse(self._build_interests_payload(applicant), status=status.HTTP_200_OK)

        categories = request.data.get('categories', [])
        if not isinstance(categories, list):
            return DRFResponse(
                {"detail": "Ожидается {\"categories\": [\"IT\", \"HR\"]}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        normalized_categories = []
        invalid_categories = []
        available_categories = _vacancy_categories()
        for raw_value in categories:
            category = str(raw_value or '').strip()
            if not category:
                continue
            if category not in available_categories:
                invalid_categories.append(category)
                continue
            if category not in normalized_categories:
                normalized_categories.append(category)

        if invalid_categories:
            return DRFResponse(
                {
                    'detail': 'Некорректные категории',
                    'invalid_categories': invalid_categories,
                    'available_categories': available_categories,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        applicant.interests.exclude(category__in=normalized_categories).delete()
        existing_categories = set(applicant.interests.values_list('category', flat=True))
        ApplicantInterest.objects.bulk_create(
            [
                ApplicantInterest(applicant=applicant, category=category)
                for category in normalized_categories
                if category not in existing_categories
            ]
        )

        return DRFResponse(self._build_interests_payload(applicant), status=status.HTTP_200_OK)


# -------------------- Employee --------------------

class EmployeeViewSet(viewsets.ModelViewSet):
    queryset = Employee.objects.all()
    serializer_class = EmployeeSerializer

    def get_permissions(self):
        return [IsAuthenticated(), IsAdminSite()]


# -------------------- Complaint --------------------

class ComplaintViewSet(viewsets.ModelViewSet):
    queryset = Complaint.objects.all()
    serializer_class = ComplaintSerializer

    def perform_create(self, serializer):
        serializer.save(complainant=self.request.user)

    def get_queryset(self):
        qs = Complaint.objects.filter(complainant=self.request.user)
        vacancy_id = self.request.query_params.get("vacancy")
        if vacancy_id:
            qs = qs.filter(vacancy_id=vacancy_id)
        return qs


# -------------------- Admin кабинеты --------------------

class AdminCompaniesViewSet(viewsets.ReadOnlyModelViewSet, mixins.UpdateModelMixin):
    """Модерация компаний: approved/rejected + admin_notes (+ лог через CompanyStatusSerializer)."""

    queryset = Company.objects.all().select_related('user').order_by('-created_at')
    permission_classes = [IsAuthenticated, IsAdminSite]

    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
    filterset_fields = ['status']
    search_fields = ['name', 'user__email']
    ordering_fields = ['created_at', 'name']
    ordering = ['-created_at']

    def get_serializer_class(self):
        if self.action in ('update', 'partial_update'):
            return CompanyStatusSerializer
        return CompanySerializer


class AdminComplaintsViewSet(viewsets.ModelViewSet):
    """Модерация жалоб: status/admin_notes/resolved_at."""

    queryset = Complaint.objects.all().select_related('vacancy', 'vacancy__company', 'complainant').order_by('-created_at')
    permission_classes = [IsAuthenticated, IsAdminSite]
    serializer_class = AdminComplaintSerializer

    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
    filterset_fields = ['status', 'complaint_type']
    search_fields = ['vacancy__position', 'vacancy__company__name', 'complainant__email']
    ordering_fields = ['created_at']
    ordering = ['-created_at']


class AdminSkillViewSet(viewsets.ModelViewSet):
    queryset = Skill.objects.all().order_by('name')
    serializer_class = SkillSerializer
    permission_classes = [IsAuthenticated, IsAdminSite]


# -------------------- Response (Отклики) --------------------

class ResponseViewSet(viewsets.ModelViewSet):
    """
    ViewSet для управления откликами.
    """
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user

        queryset = (ResponseModel.objects
                    .select_related('applicants', 'vacancy', 'vacancy__company', 'status')
                    .all())

        # ✅ Соискатель: только свои отклики
        if user.user_type == 'applicant':
            try:
                applicant = user.applicant
                return queryset.filter(applicants=applicant)
            except Applicant.DoesNotExist:
                logger.warning("Applicant profile not found for user %s", user.id)
                return ResponseModel.objects.none()

        # ✅ Компания-владелец или staff: отклики на вакансии их компании
        if user.user_type in ['company', 'staff']:
            company = None

            # company owner
            if user.user_type == 'company':
                try:
                    company = user.company
                except Exception:
                    company = None

            # staff
            if company is None:
                try:
                    company = user.employee.company
                except Exception:
                    company = None

            if not company:
                return ResponseModel.objects.none()

            return queryset.filter(vacancy__company=company)

        # ✅ adminsite: все отклики
        if user.user_type == 'adminsite' or user.is_superuser:
            return queryset

        return ResponseModel.objects.none()

    def get_serializer_class(self):
        if self.action == 'create':
            return CreateResponseSerializer
        return ResponseSerializer

    def perform_create(self, serializer):
        serializer.save()

    @action(detail=False, methods=['get'], url_path=r'check/(?P<vacancy_id>\d+)')
    def check_response(self, request, vacancy_id=None):
        user = request.user

        if user.user_type != 'applicant':
            return DRFResponse(
                {"error": "Только соискатели могут откликаться на вакансии"},
                status=status.HTTP_403_FORBIDDEN
            )

        try:
            applicant = user.applicant
            vacancy = Vacancy.objects.get(id=vacancy_id)

            resp = ResponseModel.objects.filter(applicants=applicant, vacancy=vacancy).first()
            if resp:
                data = {
                    'has_responded': True,
                    'response_id': resp.id,
                    'status': resp.status.status_response_name
                }
            else:
                data = {
                    'has_responded': False,
                    'response_id': None,
                    'status': None
                }

            serializer = CheckResponseSerializer(data)
            return DRFResponse(serializer.data)

        except Vacancy.DoesNotExist:
            return DRFResponse({"error": "Вакансия не найдена"}, status=status.HTTP_404_NOT_FOUND)
        except Applicant.DoesNotExist:
            return DRFResponse({"error": "Профиль соискателя не найден"}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception("Error in check_response: %s", e)
            return DRFResponse({"error": "Внутренняя ошибка сервера"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'], url_path='update-status')
    def update_status(self, request, pk=None):
        user = request.user

        if user.user_type not in ['company', 'staff', 'adminsite'] and not user.is_superuser:
            return DRFResponse(
                {"error": "Недостаточно прав для изменения статуса отклика"},
                status=status.HTTP_403_FORBIDDEN
            )

        response_obj = self.get_object()
        old_status_id = response_obj.status_id
        new_status_id = request.data.get('status_id')

        if not new_status_id:
            return DRFResponse({"error": "Не указан ID нового статуса"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            new_status = StatusResponse.objects.get(id=new_status_id)
        except StatusResponse.DoesNotExist:
            return DRFResponse({"error": "Указанный статус не найден"}, status=status.HTTP_400_BAD_REQUEST)

        if not _response_status_alias(new_status.status_response_name):
            return DRFResponse(
                {"error": "Разрешены только статусы: Отправлен, Приглашение, Отказ"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not (user.user_type == 'adminsite' or user.is_superuser):
            company = None
            if user.user_type == 'company':
                company = getattr(user, 'company', None)
            else:
                company = getattr(getattr(user, 'employee', None), 'company', None)

            if not company or response_obj.vacancy.company_id != company.id:
                return DRFResponse(
                    {"error": "Вы не можете изменять статус отклика на чужую вакансию"},
                    status=status.HTTP_403_FORBIDDEN
                )

        status_changed = old_status_id != new_status.id
        if status_changed:
            response_obj.status = new_status
            response_obj.save(update_fields=['status'])

        chat_id = None
        chat_message_sent = False
        if status_changed:
            try:
                chat, _ = Chat.objects.get_or_create(
                    vacancy=response_obj.vacancy,
                    applicant=response_obj.applicants,
                    defaults={
                        'company': response_obj.vacancy.company,
                        'is_active': True,
                    },
                )
                chat_id = chat.id

                status_message = (
                    f"Статус вашего отклика на вакансию "
                    f"'{response_obj.vacancy.position}' обновлен: {new_status.status_response_name}."
                )
                message = Message.objects.create(
                    chat=chat,
                    sender=user,
                    sender_type='company',
                    message_type='system',
                    text=status_message,
                    related_vacancy=response_obj.vacancy,
                    related_response=response_obj,
                    is_read_by_applicant=False,
                    is_read_by_company=True,
                )

                chat.last_message_at = message.created_at
                chat.save(update_fields=['last_message_at'])
                chat_message_sent = True
            except Exception as exc:
                logger.exception(
                    "Failed to send response status update message for response=%s: %s",
                    response_obj.id,
                    exc,
                )

        return DRFResponse({
            "message": "Статус отклика обновлен" if status_changed else "Статус отклика не изменился",
            "new_status": new_status.status_response_name,
            "response_id": response_obj.id,
            "chat_id": chat_id,
            "chat_message_sent": chat_message_sent,
        })


# -------------------- Favorites --------------------

class FavoritesViewSet(viewsets.ModelViewSet):
    serializer_class = FavoritesSerializer
    permission_classes = [IsAuthenticated]
    queryset = Favorites.objects.all()

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated or user.user_type != 'applicant':
            return Favorites.objects.none()

        try:
            applicant = user.applicant
        except Applicant.DoesNotExist:
            return Favorites.objects.none()

        return Favorites.objects.filter(applicant=applicant).select_related('vacancy', 'vacancy__company')

    def perform_create(self, serializer):
        user = self.request.user
        if user.user_type != 'applicant':
            raise PermissionDenied("Только соискатель может добавлять вакансии в избранное")
        serializer.save(applicant=user.applicant)

    @action(detail=False, methods=['post'], url_path='toggle')
    def toggle(self, request):
        user = request.user
        if user.user_type != 'applicant':
            return DRFResponse({"error": "Только для соискателя"}, status=status.HTTP_403_FORBIDDEN)

        vacancy_id = request.data.get('vacancy')
        if not vacancy_id:
            return DRFResponse({"error": "vacancy обязателен"}, status=status.HTTP_400_BAD_REQUEST)

        vacancy = get_object_or_404(Vacancy, id=vacancy_id)
        applicant = user.applicant

        fav = Favorites.objects.filter(applicant=applicant, vacancy=vacancy).first()
        if fav:
            fav.delete()
            return DRFResponse({"is_favorite": False}, status=status.HTTP_200_OK)

        Favorites.objects.create(applicant=applicant, vacancy=vacancy)
        return DRFResponse({"is_favorite": True}, status=status.HTTP_200_OK)


# -------------------- Dictionaries --------------------

class WorkConditionsViewSet(viewsets.ModelViewSet):
    queryset = WorkConditions.objects.all()
    serializer_class = WorkConditionsSerializer

    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return [AllowAny()]
        return [IsAuthenticated(), IsAdminSite()]

class StatusVacanciesViewSet(viewsets.ModelViewSet):
    queryset = StatusVacancies.objects.all()
    serializer_class = StatusVacanciesSerializer

    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return [AllowAny()]
        return [IsAuthenticated(), IsAdminSite()]

class StatusResponseViewSet(viewsets.ModelViewSet):
    queryset = StatusResponse.objects.all()
    serializer_class = StatusResponseSerializer

    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return [AllowAny()]
        return [IsAuthenticated(), IsAdminSite()]

class AdminLogViewSet(viewsets.ModelViewSet):
    queryset = AdminLog.objects.all()
    serializer_class = AdminLogSerializer

    def get_permissions(self):
        return [IsAuthenticated(), IsAdminSite()]

class BackupViewSet(viewsets.ModelViewSet):
    queryset = Backup.objects.all()
    serializer_class = BackupSerializer

    def get_permissions(self):
        return [IsAuthenticated(), IsAdminSite()]


# -------------------- User Registration/Profile --------------------

class UserViewSet(viewsets.GenericViewSet, mixins.RetrieveModelMixin):
    queryset = User.objects.all()
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get_permissions(self):
        if self.action in ['register_applicant', 'register_company', 'resubmit_company', 'register_employee']:
            return [AllowAny()]
        return [IsAuthenticated()]

    def get_serializer_class(self):
        if self.action == 'register_applicant':
            return ApplicantRegistrationSerializer
        if self.action == 'register_company':
            return CompanyRegistrationSerializer
        if self.action == 'register_employee':
            return EmployeeRegistrationSerializer
        if self.action in ['profile']:
            return UserProfileSerializer
        return UserSerializer

    @action(detail=False, methods=['post'], permission_classes=[AllowAny])
    def register_applicant(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return DRFResponse(
            {'user': UserSerializer(user).data, 'message': 'Соискатель успешно зарегистрирован'},
            status=status.HTTP_201_CREATED
        )

    @action(detail=False, methods=['post'], permission_classes=[AllowAny])
    def register_company(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return DRFResponse(
            {'user': UserSerializer(user).data, 'message': 'Данные компании отправлены на проверку'},
            status=status.HTTP_201_CREATED
        )

    @action(detail=False, methods=['post'], permission_classes=[AllowAny], url_path='resubmit_company')
    def resubmit_company(self, request):
        serializer = CompanyRegistrationSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)

        rejected_user = serializer.validated_data.get('_rejected_company_user')
        if not rejected_user:
            return DRFResponse(
                {
                    'email': [
                        'Повторная отправка доступна только для отклоненной компании с этим email.'
                    ]
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = serializer.save()
        return DRFResponse(
            {'user': UserSerializer(user).data, 'message': 'Данные компании повторно отправлены на проверку'},
            status=status.HTTP_200_OK
        )

    @action(detail=False, methods=['post'], permission_classes=[AllowAny])
    def register_employee(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return DRFResponse(
            {'user': UserSerializer(user).data, 'message': f'{user.get_user_type_display()} успешно зарегистрирован'},
            status=status.HTTP_201_CREATED
        )

    @action(detail=False, methods=['get', 'patch', 'put'], url_path='profile', permission_classes=[IsAuthenticated])
    def profile(self, request):
        user = request.user

        if request.method == 'GET':
            serializer = self.get_serializer(user)
            return DRFResponse(serializer.data)

        serializer = self.get_serializer(user, data=request.data, partial=(request.method == 'PATCH'))
        serializer.is_valid(raise_exception=True)
        updated_user = serializer.save()

        return DRFResponse(self.get_serializer(updated_user).data)

    @action(detail=False, methods=['post'], url_path='change-password', permission_classes=[IsAuthenticated])
    def change_password(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)

        request.user.set_password(serializer.validated_data['new_password'])
        request.user.save(update_fields=['password'])

        return DRFResponse({'detail': 'Пароль успешно изменён'}, status=status.HTTP_200_OK)


class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer


# -------------------- Chat --------------------

class ChatViewSet(viewsets.ModelViewSet):
    queryset = Chat.objects.all()
    serializer_class = ChatSerializer
    permission_classes = [IsAuthenticated]

    def _is_archived_request(self) -> bool:
        raw = str(self.request.query_params.get('archived', '0')).strip().lower()
        return raw in {'1', 'true', 'yes', 'on'}

    @staticmethod
    def _has_company_chat_access(user, chat: Chat) -> bool:
        if user.user_type == 'company':
            company = getattr(user, 'company', None)
        elif user.user_type == 'staff':
            company = getattr(getattr(user, 'employee', None), 'company', None)
        else:
            company = None
        return bool(company and chat.company_id == company.id)

    def get_queryset(self):
        user = self.request.user
        filter_by_archive = self.action == 'list'
        show_archived = self._is_archived_request()

        if user.user_type == 'applicant':
            try:
                queryset = Chat.objects.filter(applicant=user.applicant)
                if filter_by_archive:
                    queryset = queryset.filter(is_archived_by_applicant=show_archived)
                return queryset
            except Applicant.DoesNotExist:
                return Chat.objects.none()

        if user.user_type == 'company':
            company = getattr(user, 'company', None)
            if not company:
                return Chat.objects.none()
            queryset = Chat.objects.filter(company=company)
            if filter_by_archive:
                queryset = queryset.filter(is_archived_by_company=show_archived)
            return queryset

        if user.user_type == 'staff':
            try:
                company = user.employee.company
                if not company:
                    return Chat.objects.none()
                queryset = Chat.objects.filter(company=company)
                if filter_by_archive:
                    queryset = queryset.filter(is_archived_by_company=show_archived)
                return queryset
            except Employee.DoesNotExist:
                return Chat.objects.none()

        if user.user_type == 'adminsite' or user.is_superuser:
            return Chat.objects.all()

        return Chat.objects.none()

    @action(detail=True, methods=['get'])
    def messages(self, request, pk=None):
        chat = self.get_object()
        user = request.user

        if user.user_type == 'applicant':
            chat.messages.filter(sender_type='company', is_read_by_applicant=False).update(is_read_by_applicant=True)
        else:
            chat.messages.filter(sender_type='applicant', is_read_by_company=False).update(is_read_by_company=True)

        messages = chat.messages.all().order_by('created_at')
        serializer = MessageSerializer(messages, many=True, context={'request': request})
        return DRFResponse(serializer.data)

    @action(detail=True, methods=['post'])
    def send_message(self, request, pk=None):
        chat = self.get_object()
        user = request.user

        # проверка доступа
        if user.user_type == 'applicant':
            if chat.applicant.user_id != user.id:
                return DRFResponse({"error": "Нет доступа к этому чату"}, status=status.HTTP_403_FORBIDDEN)
            sender_type = 'applicant'
        else:
            # company/staff/admin
            if not (user.user_type == 'adminsite' or user.is_superuser):
                company = None
                if user.user_type == 'company':
                    company = getattr(user, 'company', None)
                else:
                    company = getattr(getattr(user, 'employee', None), 'company', None)

                if not company or chat.company_id != company.id:
                    return DRFResponse({"error": "Нет доступа к этому чату"}, status=status.HTTP_403_FORBIDDEN)

            sender_type = 'company'

        ser = SendMessageSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        message = ser.save(
            chat=chat,
            sender=user,
            sender_type=sender_type,
            is_read_by_applicant=(sender_type == 'applicant'),
            is_read_by_company=(sender_type == 'company')
        )

        chat.last_message_at = message.created_at
        chat.save(update_fields=['last_message_at'])

        return DRFResponse(MessageSerializer(message, context={'request': request}).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def archive(self, request, pk=None):
        chat = self.get_object()
        user = request.user

        if user.user_type == 'applicant':
            if chat.applicant.user_id != user.id:
                return DRFResponse({"error": "Нет доступа к этому чату"}, status=status.HTTP_403_FORBIDDEN)
            if not chat.is_archived_by_applicant:
                chat.is_archived_by_applicant = True
                chat.save(update_fields=['is_archived_by_applicant'])
            return DRFResponse({"status": "archived", "is_archived": True})

        if user.user_type in ('company', 'staff'):
            if not self._has_company_chat_access(user, chat):
                return DRFResponse({"error": "Нет доступа к этому чату"}, status=status.HTTP_403_FORBIDDEN)
            if not chat.is_archived_by_company:
                chat.is_archived_by_company = True
                chat.save(update_fields=['is_archived_by_company'])
            return DRFResponse({"status": "archived", "is_archived": True})

        if user.user_type == 'adminsite' or user.is_superuser:
            chat.is_archived_by_applicant = True
            chat.is_archived_by_company = True
            chat.save(update_fields=['is_archived_by_applicant', 'is_archived_by_company'])
            return DRFResponse({"status": "archived", "is_archived": True})

        return DRFResponse({"error": "Нет доступа к этому чату"}, status=status.HTTP_403_FORBIDDEN)

    @action(detail=True, methods=['post'])
    def unarchive(self, request, pk=None):
        chat = self.get_object()
        user = request.user

        if user.user_type == 'applicant':
            if chat.applicant.user_id != user.id:
                return DRFResponse({"error": "Нет доступа к этому чату"}, status=status.HTTP_403_FORBIDDEN)
            if chat.is_archived_by_applicant:
                chat.is_archived_by_applicant = False
                chat.save(update_fields=['is_archived_by_applicant'])
            return DRFResponse({"status": "active", "is_archived": False})

        if user.user_type in ('company', 'staff'):
            if not self._has_company_chat_access(user, chat):
                return DRFResponse({"error": "Нет доступа к этому чату"}, status=status.HTTP_403_FORBIDDEN)
            if chat.is_archived_by_company:
                chat.is_archived_by_company = False
                chat.save(update_fields=['is_archived_by_company'])
            return DRFResponse({"status": "active", "is_archived": False})

        if user.user_type == 'adminsite' or user.is_superuser:
            chat.is_archived_by_applicant = False
            chat.is_archived_by_company = False
            chat.save(update_fields=['is_archived_by_applicant', 'is_archived_by_company'])
            return DRFResponse({"status": "active", "is_archived": False})

        return DRFResponse({"error": "Нет доступа к этому чату"}, status=status.HTTP_403_FORBIDDEN)

    @action(detail=False, methods=['get'])
    def by_vacancy(self, request):
        vacancy_id = request.query_params.get('vacancy_id')
        user = request.user

        if not vacancy_id:
            return DRFResponse({"error": "vacancy_id обязателен"}, status=400)
        if user.user_type != 'applicant':
            return DRFResponse({"error": "Только для соискателей"}, status=403)

        vacancy = get_object_or_404(Vacancy, id=vacancy_id)
        applicant = user.applicant

        chat = Chat.objects.filter(vacancy=vacancy, applicant=applicant).first()
        if chat:
            return DRFResponse(ChatSerializer(chat, context={'request': request}).data)

        return DRFResponse({"exists": False, "message": "Чат не создан. Сначала откликнитесь на вакансию."})


class MessageViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Message.objects.all()
    serializer_class = MessageSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user

        if user.user_type == 'applicant':
            try:
                chats = Chat.objects.filter(applicant=user.applicant)
                return Message.objects.filter(chat__in=chats)
            except Applicant.DoesNotExist:
                return Message.objects.none()

        if user.user_type == 'company':
            company = getattr(user, 'company', None)
            if not company:
                return Message.objects.none()
            chats = Chat.objects.filter(company=company)
            return Message.objects.filter(chat__in=chats)

        if user.user_type == 'staff':
            try:
                company = user.employee.company
                if not company:
                    return Message.objects.none()
                chats = Chat.objects.filter(company=company)
                return Message.objects.filter(chat__in=chats)
            except Employee.DoesNotExist:
                return Message.objects.none()

        if user.user_type == 'adminsite' or user.is_superuser:
            return Message.objects.all()

        return Message.objects.none()


# -------------------- Vacancy Video Manage (admin/content manager) --------------------

class VacancyVideoManageViewSet(viewsets.ModelViewSet):
    queryset = VacancyVideo.objects.all()
    serializer_class = VacancyVideoAdminSerializer
    permission_classes = [IsAuthenticated, IsContentManager]
    parser_classes = (MultiPartParser, FormParser)

    def perform_create(self, serializer):
        employee = self.request.user.employee

        if serializer.validated_data['vacancy'].company != employee.company:
            raise PermissionDenied("Нельзя загружать видео для чужой компании")

        serializer.save(
            uploaded_by=employee,
            company=employee.company,
            is_active=False
        )

        # Debug: что реально прилетело в multipart
        try:
            logger.info(
                "[UPLOAD] VacancyVideoManage user=%s ct=%s len=%s files=%s data_keys=%s",
                getattr(self.request.user, 'id', None),
                self.request.content_type,
                self.request.META.get('CONTENT_LENGTH'),
                list(getattr(self.request, 'FILES', {}).keys()),
                list(getattr(self.request, 'data', {}).keys()),
            )
        except Exception:
            pass


import logging
import time
from django.utils.timezone import now
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response as DRFResponse
from rest_framework.exceptions import PermissionDenied

logger = logging.getLogger("upload_debug")



class ContentManagerVideoViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, IsContentManager]
    parser_classes = (MultiPartParser, FormParser)

    def dispatch(self, request, *args, **kwargs):
        logger.warning(
            "=== CM_UPLOAD DISPATCH ENTER === method=%s path=%s CT=%s CL=%s",
            request.method, request.path,
            request.META.get("CONTENT_TYPE"),
            request.META.get("CONTENT_LENGTH"),
        )
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        user = self.request.user
        if not hasattr(user, 'employee') or not user.employee or not user.employee.company_id:
            return VacancyVideo.objects.none()
        return VacancyVideo.objects.filter(vacancy__company=user.employee.company).order_by('-created_at')

    def get_serializer_class(self):
        if self.action in ['list', 'retrieve']:
            return ContentManagerVideoListSerializer
        return ContentManagerVideoSerializer

   
    def create(self, request, *args, **kwargs):
        logger.warning("=== CM_UPLOAD CREATE ENTER === before request.data")
        t0 = time.time()
        try:
            data = request.data  # тут обычно зависает
            dt = time.time() - t0
            logger.warning("=== CM_UPLOAD CREATE === request.data parsed in %.2fs keys=%s files=%s",
                           dt, list(data.keys()), list(request.FILES.keys()))
        except Exception as e:
            dt = time.time() - t0
            logger.exception("=== CM_UPLOAD CREATE FAIL after %.2fs === %s", dt, e)
            return DRFResponse({"detail": "parse failed", "err": str(e)}, status=400)

        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        print("=== CM_UPLOAD PERFORM_CREATE ENTER ===", flush=True)

        employee = self.request.user.employee
        vacancy = serializer.validated_data['vacancy']

        if vacancy.company != employee.company:
            raise PermissionDenied("Нельзя загружать видео для чужой компании")

        print("before serializer.save()", flush=True)
        t0 = time.time()
        obj = serializer.save(
            uploaded_by=employee,
            company=employee.company,
            is_active=False
        )
        print("after serializer.save() ms=", int((time.time()-t0)*1000),
              "id=", obj.id, flush=True)

    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        video = self.get_object()
        video.is_active = True
        video.save(update_fields=['is_active'])
        return DRFResponse({"status": "видео активировано", "video_id": video.id})

    @action(detail=True, methods=['post'])
    def deactivate(self, request, pk=None):
        video = self.get_object()
        video.is_active = False
        video.save(update_fields=['is_active'])
        return DRFResponse({"status": "видео деактивировано", "video_id": video.id})

class VacancyVideoFeedViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    serializer_class = VacancyVideoFeedSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        applicant = self.request.user.applicant
        params = self.request.query_params

        qs = VacancyVideo.objects.filter(is_active=True).select_related('vacancy', 'vacancy__company')

        viewed = VacancyVideoView.objects.filter(applicant=applicant).values_list('video_id', flat=True)
        qs = qs.exclude(id__in=viewed)

        if city := params.get('city'):
            qs = qs.filter(vacancy__city__iexact=city)
        if category := params.get('category'):
            qs = qs.filter(vacancy__category=category)
        if salary_from := params.get('salary_from'):
            qs = qs.filter(vacancy__salary_max__gte=salary_from)

        return qs

    @action(detail=True, methods=['post'])
    def view(self, request, pk=None):
        video = get_object_or_404(VacancyVideo, pk=pk)
        VacancyVideoView.objects.get_or_create(applicant=request.user.applicant, video=video)
        return DRFResponse({"status": "ok"})

    @action(detail=True, methods=['post'])
    def like(self, request, pk=None):
        video = get_object_or_404(VacancyVideo, pk=pk)
        applicant = request.user.applicant

        like_obj = VacancyVideoLike.objects.filter(applicant=applicant, video=video).first()
        if like_obj:
            like_obj.delete()
            return DRFResponse({"liked": False})

        VacancyVideoLike.objects.create(applicant=applicant, video=video)
        return DRFResponse({"liked": True})


class VacancyVideoFeedView(ListAPIView):
    serializer_class = VacancyVideoFeedSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        return VacancyVideo.objects.filter(is_active=True).select_related('vacancy', 'vacancy__company')


class SkillViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Skill.objects.all().order_by('name')
    serializer_class = SkillSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]


class ContentManagerVacancyViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated, IsContentManager]
    serializer_class = VacancyListSerializer

    def get_queryset(self):
        user = self.request.user
        if not hasattr(user, "employee") or not user.employee or not user.employee.company_id:
            return Vacancy.objects.none()
        return Vacancy.objects.filter(company=user.employee.company).order_by('-created_date')


class ContentManagerProfileStatsAPIView(APIView):
    permission_classes = [IsAuthenticated, IsContentManager]

    def get(self, request):
        data = build_cm_profile_stats(request.user)
        return DRFResponse(data, status=status.HTTP_200_OK)


class ContentManagerProfileStatsPdfAPIView(APIView):
    permission_classes = [IsAuthenticated, IsContentManager]

    def get(self, request):
        data = build_cm_profile_stats(request.user)

        manager = data['manager']
        company = data['company']
        stats = data['stats']

        pages = []
        current_page = Image.new('RGB', (1240, 1754), 'white')
        draw = ImageDraw.Draw(current_page)
        font = ImageFont.load_default()
        y = 40

        def write_line(text, step=24):
            nonlocal current_page, draw, y
            draw.text((40, y), str(text), fill='black', font=font)
            y += step
            if y > 1690:
                pages.append(current_page)
                current_page = Image.new('RGB', (1240, 1754), 'white')
                draw = ImageDraw.Draw(current_page)
                y = 40

        write_line("Content Manager Profile Report", step=32)
        write_line(f"Generated at: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}", step=28)

        write_line("Manager")
        write_line(f"Name: {manager.get('full_name')}")
        write_line(f"Role: {manager.get('role')}")
        write_line(f"Email: {manager.get('email')}")
        write_line(f"Phone: {manager.get('phone')}")

        write_line("Company")
        write_line(f"Name: {company.get('name')}")
        write_line(f"Number: {company.get('number')}")
        write_line(f"Industry: {company.get('industry')}")

        company_description = company.get('description') or ''
        if company_description:
            write_line("Description:")
            for i in range(0, len(company_description), 95):
                write_line(company_description[i:i + 95])

        write_line("Stats")
        write_line(f"Videos: {stats.get('videos_count', 0)}")
        write_line(f"Vacancies: {stats.get('vacancies_count', 0)}")
        write_line(f"Responses: {stats.get('responses_count', 0)}")
        write_line(f"Video views: {stats.get('video_views_count', 0)}")
        write_line(f"Video likes: {stats.get('video_likes_count', 0)}")
        write_line(f"Vacancy views: {stats.get('vacancy_views_count', 0)}")

        responses_by_status = data.get('responses_by_status', [])
        if responses_by_status:
            write_line("Responses by status")
            for item in responses_by_status:
                write_line(f"- {item.get('status')}: {item.get('count')}")

        top_vacancies = data.get('top_vacancies', [])
        if top_vacancies:
            write_line("Top vacancies by responses")
            for item in top_vacancies:
                write_line(f"- {item.get('position')}: {item.get('responses_count')}")

        pages.append(current_page)

        buffer = BytesIO()
        first_page = pages[0]
        other_pages = pages[1:] if len(pages) > 1 else []
        first_page.save(buffer, format='PDF', save_all=True, append_images=other_pages)

        buffer.seek(0)
        filename = f"cm_stats_{timezone.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response


class RecommendedVideoFeedViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = VacancyVideoFeedSerializer

    def get_queryset(self):
        qs = VacancyVideo.objects.filter(is_active=True).select_related('vacancy', 'vacancy__company').order_by('-id')
        params = self.request.query_params

        if city := params.get('city'):
            qs = qs.filter(vacancy__city__iexact=city)
        if category := params.get('category'):
            qs = qs.filter(vacancy__category=category)
        if salary_from := params.get('salary_from'):
            qs = qs.filter(vacancy__salary_max__gte=salary_from)

        try:
            applicant = self.request.user.applicant
        except Applicant.DoesNotExist:
            return qs

        interest_categories = list(applicant.interests.values_list('category', flat=True))
        if interest_categories:
            qs = qs.filter(vacancy__category__in=interest_categories)
        return qs


# -------------------- Password Reset --------------------

def build_reset_email(first_name: str, code: str):
    subject = f"Код восстановления пароля: {code}"
    html_message = f"""<!DOCTYPE html><html><head><meta charset="utf-8"></head><body>
    <p>Здравствуйте, {first_name}!</p><p>Код восстановления: <b>{code}</b></p>
    <p>Код действителен 10 минут.</p></body></html>"""
    plain_message = f"Здравствуйте, {first_name}!\n\nКод для восстановления пароля: {code}\n\nКод действителен 10 минут."
    return subject, plain_message, html_message


class PasswordResetRequestAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        ser = PasswordResetRequestSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        email = ser.validated_data["email"].strip().lower()
        user = UserModel.objects.filter(email=email).first()

        ok_response = DRFResponse({"status": "ok"}, status=status.HTTP_200_OK)
        if not user:
            return ok_response

        last = (PasswordResetCode.objects
                .filter(user=user)
                .order_by("-created_at")
                .first())
        if last and (timezone.now() - last.created_at).total_seconds() < 60:
            return ok_response

        code = PasswordResetCode.generate_code()
        PasswordResetCode.objects.create(
            user=user,
            code=code,
            expires_at=PasswordResetCode.default_expires_at(),
            is_used=False
        )

        first_name = (getattr(user, "first_name", "") or "").strip() or "пользователь"
        subject, plain_message, html_message = build_reset_email(first_name, code)

        send_email_message(
            recipient_email=user.email,
            subject=subject,
            plain_message=plain_message,
            html_message=html_message,
            fail_silently=False,
        )

        return ok_response


class PasswordResetConfirmAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        ser = PasswordResetConfirmSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        user = ser.validated_data["user"]
        prc = ser.validated_data["reset_obj"]
        new_password = ser.validated_data["new_password"]

        user.set_password(new_password)
        user.save(update_fields=["password"])

        prc.is_used = True
        prc.save(update_fields=["is_used"])

        PasswordResetCode.objects.filter(user=user, is_used=False).update(is_used=True)

        return DRFResponse({"status": "ok"}, status=status.HTTP_200_OK)
