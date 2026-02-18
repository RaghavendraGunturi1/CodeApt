from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from core.models import Profile  # <--- Note the 'core' import

class StudentRegisterForm(UserCreationForm):
    email = forms.EmailField(required=True)
    full_name = forms.CharField(max_length=100, required=True)
    roll_number = forms.CharField(max_length=50, required=True, label="University Roll Number") # Added
    college_name = forms.CharField(max_length=200, required=True)
    phone_number = forms.CharField(max_length=15, required=True)
    state = forms.CharField(max_length=100, required=True)

    class Meta(UserCreationForm.Meta):
        fields = UserCreationForm.Meta.fields + ('email',)

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("A user with this email already exists.")
        return email
    def clean_roll_number(self):
        roll = self.cleaned_data.get('roll_number')
        if Profile.objects.filter(roll_number=roll).exists():
            raise forms.ValidationError("This roll number is already registered.")
        return roll