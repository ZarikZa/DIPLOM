from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('apihh_main', '0009_alter_vacancycategorysuggestion_company'),
    ]

    operations = [
        migrations.AddField(
            model_name='chat',
            name='is_archived_by_applicant',
            field=models.BooleanField(default=False, verbose_name='Архив соискателя'),
        ),
        migrations.AddField(
            model_name='chat',
            name='is_archived_by_company',
            field=models.BooleanField(default=False, verbose_name='Архив компании'),
        ),
    ]
