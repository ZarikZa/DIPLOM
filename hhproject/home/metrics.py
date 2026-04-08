from prometheus_client.core import GaugeMetricFamily

# GaugeMetricFamily одна из самых популярных
# Counter может только возрастать 
# Gauge может вырасти и упасть

class BackUpByTypeCollector:
    def collect(self):
        from django.db.models import Count
        from .models import Backup

        metric = GaugeMetricFamily(
            'hh_backup_by_type',
            'Число бэкапов по группе типов',
            labels=['backup_type']
        )

        for row in Backup.objects.values('backup_type').annotate(count=Count('id')):
            metric.add_metric([row['backup_type']], float(row['count']))
        
        existing = {row['backup_type'] for row in Backup.objects.values('backup_type')}
        for code, _ in Backup.BACKUP_TYPES:
            if code not in existing:
                metric.add_metric([code], 0.0)
        yield metric

class ResponseByStatusCollector:
    def collect(self):
        from django.db.models import Count
        from .models import Response, StatusResponse

        metric = GaugeMetricFamily(
            'hh_responce_by_status',
            'Число откликов по статусу',
            labels=['status']
        )

        for status in StatusResponse.objects.all():
            count = Response.objects.filter(status=status).count()
            metric.add_metric(value=count, labels=[status.status_response_name])

        yield metric

        
class ResponseByDateCollector:
    def collect(self):
        from .models import Response
        from django.db.models import Count
        
        metric = GaugeMetricFamily(
            'hh_responses_by_date',
            'Количество откликов по датам',
            labels=['date']
        )

        responses_by_date = Response.objects.extra({
            'response_day': "DATE(response_date)"
        }).values('response_day').annotate(
            count=Count('id')
        ).order_by('response_day')

        for item in responses_by_date:
            date_str = item['response_day'].strftime('%Y-%m-%d')
            metric.add_metric(labels=[date_str], value=item['count'])

        yield metric