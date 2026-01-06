# assessments/forms.py
from django import forms

class ExamUploadForm(forms.Form):
    file = forms.FileField(label="Upload Excel File (.xlsx)")