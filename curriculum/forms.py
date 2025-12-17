from django import forms

class BulkUploadForm(forms.Form):
    excel_file = forms.FileField(
        label="Upload Excel Sheet", 
        help_text="Upload a .xlsx file with columns: module, order, name, type, content, video_id, duration"
    )