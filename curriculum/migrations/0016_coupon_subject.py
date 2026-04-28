from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):

    dependencies = [
        ('curriculum', '0015_alter_coupon_id_alter_coupon_per_user_limit_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='coupon',
            name='subject',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='coupons', to='curriculum.subject'),
        ),
    ]
