from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('assessments', '0010_studentexamattempt_public_link'),
    ]

    operations = [
        migrations.AddField(
            model_name='examtestcase',
            name='is_hidden',
            field=models.BooleanField(
                default=False,
                help_text="Hidden test cases are not shown in 'Run Tests' but are used for final scoring.",
            ),
        ),
    ]
