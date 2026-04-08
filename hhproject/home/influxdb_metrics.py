import requests
from django.db.models import Count
from .models import Backup, Response, StatusResponse
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class InfluxDBSender:
    def __init__(self):
        self.url = "http://localhost:8164/api/v2/write"
        self.params = {
            "org": "Ya",
            "bucket": "metrics",
            "precision": "s"
        }
        self.headers = {
            "Authorization": "Token snTASJFmx7Smxc7tQiP6A_hTldBvT0s0Wi1qTikcqEGBSdKAAFeRLuuYleFQrtpSOmYufZEQuK_wW0p96_owLg=="
        }
    
    def send_backup_metrics(self):
        try:
            metrics = []
            
            backup_counts = Backup.objects.values('backup_type').annotate(count=Count('id'))
            
            for item in backup_counts:
                backup_type = str(item['backup_type']).replace(' ', '_').replace(',', '')
                count = item['count']
                metric = f"backup_stats,backup_type={backup_type} count={count}"
                metrics.append(metric)
            
            if metrics:
                data = "\n".join(metrics)
                response = requests.post(
                    self.url,
                    params=self.params,
                    headers=self.headers,
                    data=data,
                    timeout=10
                )
                return response.status_code == 204
                
        except Exception as e:
            print(e)
        return False

    def send_response_status_metrics(self):
        try:
            metrics = []
            
            for status in StatusResponse.objects.all():
                count = Response.objects.filter(status=status).count()
                status_name = str(status.status_response_name).replace(' ', '\\ ').replace(',', '\\,').replace('=', '\\=')
                metric = f"response_stats,status={status_name} count={count}"
                metrics.append(metric)
            
            if metrics:
                data = "\n".join(metrics)
                response = requests.post(
                    self.url,
                    params=self.params,
                    headers=self.headers,
                    data=data,
                    timeout=10
                )
                return response.status_code == 204
                
        except Exception as e:
            print(e)        
        return False

    def send_response_date_metrics(self):
        try:
            metrics = []
            
            responses_by_date = Response.objects.extra({
                'response_day': "DATE(response_date)"
            }).values('response_day').annotate(
                count=Count('id')
            ).order_by('response_day')

            for item in responses_by_date:
                date_str = item['response_day'].strftime('%Y-%m-%d')
                count = item['count']
                metric = f"response_daily,date={date_str} count={count}"
                metrics.append(metric)
            
            if metrics:
                data = "\n".join(metrics)
                response = requests.post(
                    self.url,
                    params=self.params,
                    headers=self.headers,
                    data=data,
                    timeout=10
                )
                return response.status_code == 204
                
        except Exception as e:
            print(e)
        
        return False

    def send_all_metrics(self):
        results = {
            'backup': self.send_backup_metrics(),
            'response_status': self.send_response_status_metrics(),
            'response_date': self.send_response_date_metrics()
        }
        return results