from django.db import migrations, models


def normalize_complaint_statuses(apps, schema_editor):
    Complaint = apps.get_model('apihh_main', 'Complaint')
    Complaint.objects.filter(status='resolved').update(status='reviewed')


class Migration(migrations.Migration):

    dependencies = [
        ('apihh_main', '0011_applicantskillsuggestion'),
    ]

    operations = [
        migrations.RunPython(normalize_complaint_statuses, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='complaint',
            name='status',
            field=models.CharField(
                choices=[
                    ('pending', 'На рассмотрении'),
                    ('reviewed', 'Рассмотрено'),
                    ('rejected', 'Отклонено'),
                ],
                default='pending',
                max_length=20,
                verbose_name='Статус',
            ),
        ),
    ]
