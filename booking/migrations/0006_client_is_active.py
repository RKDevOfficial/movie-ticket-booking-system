from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('booking', '0005_client_profile_picture'),
    ]

    operations = [
        migrations.AddField(
            model_name='client',
            name='is_active',
            field=models.BooleanField(default=True),
        ),
    ]
