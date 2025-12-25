from django.contrib import admin
from .models import Program, Subject, Topic

@admin.register(Program)
class ProgramAdmin(admin.ModelAdmin):
    list_display = ('name',)

@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ('name', 'program')
    prepopulated_fields = {'slug': ('name',)}

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