# Generated by Django 5.2.2 on 2025-07-26 17:03

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0002_passwordresettoken'),
    ]

    operations = [
        migrations.AddField(
            model_name='customuser',
            name='login_attempts',
            field=models.PositiveIntegerField(default=0),
        ),
    ]
