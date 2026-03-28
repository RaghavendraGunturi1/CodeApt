# assessments/forms.py
from django import forms
from django.contrib.admin.widgets import RelatedFieldWidgetWrapper
from django.db.models.functions import Lower

from curriculum.models import Topic
from .models import Exam

class ExamUploadForm(forms.Form):
    topic = forms.ModelChoiceField(
        queryset=Topic.objects.all().order_by(Lower("name"), "name"),
        label="Topic",
        required=True,
    )
    file = forms.FileField(label="Upload Excel File (.xlsx)")

    def __init__(self, *args, admin_site=None, **kwargs):
        super().__init__(*args, **kwargs)

        if admin_site:
            topic_rel = Exam._meta.get_field("topic").remote_field
            self.fields["topic"].widget = RelatedFieldWidgetWrapper(
                self.fields["topic"].widget,
                topic_rel,
                admin_site,
                can_add_related=True,
                can_change_related=False,
                can_delete_related=False,
                can_view_related=False,
            )