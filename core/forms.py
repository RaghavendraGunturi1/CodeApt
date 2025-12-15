from django import forms

class ContactForm(forms.Form):
    name = forms.CharField(max_length=100, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Your Name'}))
    email = forms.EmailField(widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Your Email'}))
    subject = forms.CharField(max_length=200, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Subject'}))
    message = forms.CharField(widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 5, 'placeholder': 'How can we help you?'}))

from django import forms
from .models import Profile
from django.contrib.auth.models import User

from django import forms
from django.contrib.auth.models import User
from .models import Profile

class UserUpdateForm(forms.ModelForm):
    email = forms.EmailField(required=True) # Email MUST be required

    class Meta:
        model = User
        fields = ['email']

class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ['full_name', 'college_name', 'phone_number', 'bio']
        widgets = {
            'full_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Official Name for Certificate'}),
            'college_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Your College/University'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+91...'}),
            'bio': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Tell us about yourself'}),
        }

    # Force fields to be optional
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['full_name'].required = False
        self.fields['college_name'].required = False
        self.fields['phone_number'].required = False
        self.fields['bio'].required = False