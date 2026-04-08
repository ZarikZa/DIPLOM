from django_filters import rest_framework as filters
from django.db.models import Exists, OuterRef, Q
from .models import Vacancy, Favorites, Applicant

class VacancyFilter(filters.FilterSet):
    city = filters.CharFilter(field_name='city', lookup_expr='icontains')
    category = filters.CharFilter(field_name='category')
    experience = filters.CharFilter(field_name='experience')
    employment = filters.CharFilter(method='filter_employment')

    salary_min = filters.NumberFilter(field_name='salary_min', lookup_expr='gte')
    salary_max = filters.NumberFilter(field_name='salary_max', lookup_expr='lte')

    no_experience = filters.BooleanFilter(method='filter_no_experience')
    only_favorites = filters.BooleanFilter(method='filter_only_favorites')

    def filter_employment(self, queryset, name, value):
        raw_values = []
        if isinstance(value, str):
            raw_values.extend([item.strip() for item in value.split(',') if item.strip()])

        if getattr(self, 'request', None):
            for item in self.request.query_params.getlist('employment'):
                if isinstance(item, str):
                    raw_values.extend([part.strip() for part in item.split(',') if part.strip()])

        if not raw_values:
            return queryset

        id_values = []
        name_values = []
        for item in raw_values:
            if str(item).isdigit():
                id_values.append(int(item))
            else:
                name_values.append(item)

        query = Q()
        if id_values:
            query |= Q(work_conditions_id__in=id_values)
        if name_values:
            query |= Q(work_conditions__work_conditions_name__in=name_values)

        if not query:
            return queryset
        return queryset.filter(query)

    def filter_no_experience(self, queryset, name, value):
        if value:
            return queryset.filter(experience='Без опыта')
        return queryset

    def filter_only_favorites(self, queryset, name, value):
        request = self.request
        if not value or not request.user.is_authenticated:
            return queryset

        try:
            applicant = request.user.applicant
        except Applicant.DoesNotExist:
            return queryset.none()

        favorites_subquery = Favorites.objects.filter(
            applicant=applicant,
            vacancy=OuterRef('pk')
        )

        return queryset.annotate(
            is_favorite=Exists(favorites_subquery)
        ).filter(is_favorite=True)

    class Meta:
        model = Vacancy
        fields = ['city', 'category', 'experience', 'salary_min', 'salary_max', 'employment']
