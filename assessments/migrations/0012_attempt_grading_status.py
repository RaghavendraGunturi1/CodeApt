from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('assessments', '0011_examtestcase_is_hidden'),
    ]

    operations = [
        migrations.AddField(
            model_name='studentexamattempt',
            name='grading_status',
            field=models.CharField(choices=[('DONE', 'Done'), ('PROCESSING', 'Processing'), ('FAILED', 'Failed')], default='DONE', max_length=20),
        ),
        migrations.AddField(
            model_name='studentexamattempt',
            name='grading_error',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='studentexamattempt',
            name='graded_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
