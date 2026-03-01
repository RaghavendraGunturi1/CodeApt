from django.contrib import admin
from .models import Program, Subject, Topic
# Check your top import line and add Enrollment
from .models import (
    Program, Subject, Topic, Question, Choice, 
    TopicProgress, Module, Enrollment, Job, JobApplication
)

@admin.register(Program)
class ProgramAdmin(admin.ModelAdmin):
    list_display = ('name',)

# Add this above SubjectAdmin
class EnrollmentInline(admin.TabularInline):
    model = Enrollment
    extra = 1  # Allows you to manually add a student via a new row
    autocomplete_fields = ['user']  # Recommended if you have many users

@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    # Added visibility and popularity to the list view
    list_display = ('name', 'program', 'price', 'is_visible', 'is_popular')
    
    # Allows you to toggle these directly in the list view
    list_editable = ('is_visible', 'is_popular')
    
    prepopulated_fields = {'slug': ('name',)}
    
    # Useful filters for managing content
    list_filter = ('program', 'is_visible', 'is_popular')
    search_fields = ('name',)
    inlines = [EnrollmentInline]
    # Optional: Shows the number of students in the list view
    def student_count(self, obj):
        return obj.enrollments.count() # Assumes related_name='enrollments' in your model
    student_count.short_description = "Students"

from django.contrib import admin
from django.urls import path
from django.shortcuts import render, redirect
from django.contrib import messages
from django import forms
import pandas as pd

from .models import Program, Subject, Topic, Question, Choice, TopicProgress, Module
from .utils import extract_video_id

# --- 1. Admin Upload Form ---
class TopicAdminUploadForm(forms.Form):
    subject = forms.ModelChoiceField(
        queryset=Subject.objects.all(), 
        label="Select Course/Subject",
        help_text="All topics in the Excel sheet will be added to this subject."
    )
    excel_file = forms.FileField(
        label="Upload Excel File",
        help_text="Columns needed: 'module', 'title', 'video_url', 'description', 'order'"
    )

# --- 2. Topic Admin with Upload Feature ---
@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    list_display = ('name', 'subject', 'module', 'topic_type', 'order')
    list_filter = ('subject', 'module', 'topic_type')
    search_fields = ('name', 'content')
    change_list_template = "admin/curriculum/topic/change_list.html"  # We will create this

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('upload-excel/', self.admin_site.admin_view(self.upload_excel_view), name='topic_upload_excel'),
        ]
        return custom_urls + urls

    def upload_excel_view(self, request):
        if request.method == "POST":
            form = TopicAdminUploadForm(request.POST, request.FILES)
            if form.is_valid():
                subject = form.cleaned_data['subject']
                file = request.FILES['excel_file']
                
                try:
                    df = pd.read_excel(file)
                    df = df.fillna('') # Handle empty cells
                    
                    # Normalize headers to lowercase to avoid case-sensitivity issues
                    df.columns = df.columns.str.lower().str.strip()

                    count = 0
                    for index, row in df.iterrows():
                        # 1. Handle Module (Get or Create)
                        module_name = str(row.get('module', '')).strip()
                        topic_module = None
                        
                        if module_name:
                            topic_module, _ = Module.objects.get_or_create(
                                subject=subject,
                                name=module_name
                            )

                        # 2. Extract Video ID from URL
                        raw_url = str(row.get('video_url', '')).strip()
                        vid_id = extract_video_id(raw_url)

                        # 3. Create Topic
                        # Only create if we have a title
                        title = str(row.get('title', '')).strip()
                        if title:
                            Topic.objects.create(
                                subject=subject,
                                module=topic_module,
                                name=title,
                                topic_type='video' if vid_id else 'text',
                                video_id=vid_id,
                                content=str(row.get('description', '')).strip(),
                                order=row.get('order', 0)
                            )
                            count += 1
                    
                    messages.success(request, f"Successfully uploaded {count} topics to '{subject.name}'!")
                    return redirect("..") # Return to Topic List

                except Exception as e:
                    messages.error(request, f"Error processing file: {e}")
        
        else:
            form = TopicAdminUploadForm()

        context = dict(
            self.admin_site.each_context(request),
            form=form,
            opts=self.model._meta,
        )
        return render(request, "admin/curriculum/topic/upload_form.html", context)

from django.contrib import admin
from .models import Program, Subject, Topic, Question, Choice


# New Quiz Admin Logic
class ChoiceInline(admin.TabularInline):
    model = Choice
    extra = 4  # Show 4 slots for options by default

@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('text', 'subject')
    list_filter = ('subject',)
    inlines = [ChoiceInline] # This puts choices inside the Question page


from .models import Program, Subject, Topic, Question, Choice, TopicProgress # Add TopicProgress

@admin.register(TopicProgress)
class TopicProgressAdmin(admin.ModelAdmin):
    list_display = ('user', 'topic', 'is_completed', 'updated_at')
    list_filter = ('is_completed', 'user')

from .models import Job, JobApplication

@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = ('title', 'company_name', 'is_active')

admin.site.register(JobApplication)

# In curriculum/admin.py

from .models import Module  # Ensure Module is imported at the top

@admin.register(Module)
class ModuleAdmin(admin.ModelAdmin):
    list_display = ('name', 'subject')
    list_filter = ('subject',)
    search_fields = ('name',)

class EnrollmentUploadForm(forms.Form):
    subjects = forms.ModelMultipleChoiceField(
        queryset=Subject.objects.all(),
        label="Select Subjects for Enrollment",
        help_text="All students in the Excel sheet will be enrolled in all selected subjects."
    )
    excel_file = forms.FileField(
        label="Upload Excel File",
        help_text="Columns needed: 'username', 'email', 'full_name', 'college_name', 'roll_number', 'phone_number', 'state', 'bio'"
    )

from django.contrib.auth.models import User
from core.models import Profile

@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ('user', 'subject', 'enrolled_at')
    list_filter = ('subject', 'enrolled_at')
    search_fields = ('user__username', 'user__email', 'subject__name')
    autocomplete_fields = ['user', 'subject']
    change_list_template = "admin/curriculum/enrollment/change_list.html"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('upload-excel/', self.admin_site.admin_view(self.upload_excel_view), name='enrollment_upload_excel'),
        ]
        return custom_urls + urls

    def upload_excel_view(self, request):
        if request.method == "POST":
            form = EnrollmentUploadForm(request.POST, request.FILES)
            if form.is_valid():
                subjects = form.cleaned_data['subjects']
                file = request.FILES['excel_file']
                
                try:
                    df = pd.read_excel(file)
                    df = df.fillna('')
                    df.columns = df.columns.str.lower().str.strip()

                    new_users_count = 0
                    enrollments_count = 0

                    for index, row in df.iterrows():
                        username = str(row.get('username', '')).strip()
                        email = str(row.get('email', '')).strip()
                        
                        if not username or not email:
                            continue # Skip invalid rows
                            
                        # 1. Get or Create User
                        user, created = User.objects.get_or_create(
                            username=username,
                            defaults={'email': email}
                        )
                        
                        if created:
                            user.set_password('CodeApt@123')
                            user.save()
                            new_users_count += 1
                            
                        # 2. Setup/Update Profile
                        profile, _ = Profile.objects.get_or_create(user=user)
                        
                        if created:
                            profile.force_password_change = True
                            
                        # Update fields if present in Excel
                        if 'full_name' in df.columns and str(row.get('full_name')).strip():
                            profile.full_name = str(row['full_name']).strip()
                        if 'college_name' in df.columns and str(row.get('college_name')).strip():
                            profile.college_name = str(row['college_name']).strip()
                        if 'roll_number' in df.columns and str(row.get('roll_number')).strip():
                            profile.roll_number = str(row['roll_number']).strip()
                        if 'phone_number' in df.columns and str(row.get('phone_number')).strip():
                            profile.phone_number = str(row['phone_number']).strip()
                        if 'state' in df.columns and str(row.get('state')).strip():
                            profile.state = str(row['state']).strip()
                        if 'bio' in df.columns and str(row.get('bio')).strip():
                            profile.bio = str(row['bio']).strip()
                            
                        profile.save()

                        # 3. Create Enrollment for each subject
                        for subject in subjects:
                            enrollment, enc_created = Enrollment.objects.get_or_create(
                                user=user,
                                subject=subject
                            )
                            if enc_created:
                                enrollments_count += 1
                            
                    subject_names = ", ".join([s.name for s in subjects])
                    messages.success(request, f"Upload complete! Created {enrollments_count} new enrollments across [{subject_names}]. (Created {new_users_count} new accounts).")
                    return redirect("..")
                    
                except Exception as e:
                    messages.error(request, f"Error processing file: {e}")
        else:
            form = EnrollmentUploadForm()

        context = dict(
            self.admin_site.each_context(request),
            form=form,
            opts=self.model._meta,
        )
        return render(request, "admin/curriculum/enrollment/upload_form.html", context)