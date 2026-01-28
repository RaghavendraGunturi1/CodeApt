from django.contrib import admin
from django.urls import path
from django.shortcuts import render, redirect
from django.contrib import messages
from .models import Exam, ExamSection, ExamQuestion, ExamTestCase, StudentExamAttempt
from .forms import ExamUploadForm
import pandas as pd
# Add these imports at the top
import requests
from django.utils.safestring import mark_safe # <--- IMPORTANT NEW IMPORT
from django.core.files.base import ContentFile

# 1. Inline for Test Cases (unchanged)
class TestCaseInline(admin.TabularInline):
    model = ExamTestCase
    extra = 1

# 2. Inline for Sections (Manage sections inside the Exam page)
class SectionInline(admin.TabularInline):
    model = ExamSection
    extra = 1

@admin.register(Exam)
class ExamAdmin(admin.ModelAdmin):
    list_display = ('topic', 'total_marks')  # Removed duration_minutes (now in sections)
    inlines = [SectionInline]                # Add Sections here
    change_list_template = "admin/assessments_changelist.html" 

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('upload-exam-questions/', self.admin_site.admin_view(self.upload_excel), name='upload_exam_questions'),
        ]
        return custom_urls + urls

    def upload_excel(self, request):
        if request.method == "POST":
            excel_file = request.FILES["file"]
            try:
                # 1. Read Excel
                df = pd.read_excel(excel_file)
                df = df.fillna('')
                
                success_count = 0
                errors = [] # List to track failures
                
                # Loop through rows
                for index, row in df.iterrows():
                    row_num = index + 2  # +2 because Excel header is row 1, and index starts at 0
                    
                    # --- VALIDATION 1: TOPIC NAME ---
                    topic_name = str(row.get('topic_name', '')).strip()
                    if not topic_name: 
                        errors.append(f"Row {row_num}: Skipped (Missing 'topic_name')")
                        continue

                    try:
                        exam = Exam.objects.get(topic__name__iexact=topic_name)
                    except Exam.DoesNotExist:
                        errors.append(f"Row {row_num}: Skipped (Exam Topic '{topic_name}' not found)")
                        continue

                    # --- PROCESS SECTION ---
                    sec_name = str(row.get('section_name', 'Part A - General')).strip()
                    try:
                        sec_duration = int(row.get('section_duration', 30))
                    except (ValueError, TypeError):
                        sec_duration = 30
                    
                    section, created = ExamSection.objects.get_or_create(
                        exam=exam,
                        name=sec_name,
                        defaults={'duration_minutes': sec_duration, 'order': 1}
                    )

                    # --- VALIDATION 2: CONTENT CHECK ---
                    raw_text = row.get('question_text', '')
                    q_text = str(raw_text).replace('_x000D_', '').strip()
                    if q_text.lower() == 'nan': q_text = ""

                    image_url = str(row.get('image_url', '')).strip()
                    if image_url.lower() == 'nan': image_url = ""

                    # If BOTH text and image are empty, skip row
                    if not q_text and not image_url:
                        errors.append(f"Row {row_num}: Skipped (Both Question Text and Image URL are empty)")
                        continue

                    # --- CREATE QUESTION ---
                    try:
                        try:
                            marks = int(row.get('marks', 5))
                        except (ValueError, TypeError):
                            marks = 5

                        q_type = str(row['type']).strip().upper()
                        
                        q = ExamQuestion.objects.create(
                            section=section,
                            q_type=q_type,
                            text=q_text,
                            marks=marks,
                            option_1=str(row.get('option_1', '')).strip(),
                            option_2=str(row.get('option_2', '')).strip(),
                            option_3=str(row.get('option_3', '')).strip(),
                            option_4=str(row.get('option_4', '')).strip(),
                            correct_options=str(row.get('correct_option', '')).strip(),
                            starter_code=str(row.get('starter_code', '')).replace('_x000D_', '').strip()
                        )

                        # Handle Image
                        if image_url:
                            try:
                                response = requests.get(image_url, timeout=10)
                                if response.status_code == 200:
                                    file_name = f"question_{q.id}.jpg"
                                    q.image.save(file_name, ContentFile(response.content), save=True)
                                else:
                                    errors.append(f"Row {row_num}: Question created, but Image download failed (Status {response.status_code})")
                            except Exception as img_err:
                                errors.append(f"Row {row_num}: Question created, but Image download error: {str(img_err)}")

                        # Handle Code Test Cases
                        if q_type == 'CODE':
                            for i in range(1, 6):
                                inp = str(row.get(f'input{i}', '')).replace('_x000D_', '').strip()
                                out = str(row.get(f'output{i}', '')).replace('_x000D_', '').strip()
                                if inp and out:
                                    ExamTestCase.objects.create(question=q, input_data=inp, expected_output=out)
                        
                        success_count += 1

                    except Exception as row_err:
                        errors.append(f"Row {row_num}: System Error - {str(row_err)}")

                # --- FINAL REPORTING ---
                if success_count > 0:
                    messages.success(request, f"Successfully uploaded {success_count} questions.")
                
                if errors:
                    # Format errors as an HTML list
                    error_html = "<strong>Some rows were skipped:</strong><br><ul style='margin-bottom:0;'>"
                    # Limit to showing first 15 errors to prevent huge popups
                    for err in errors[:15]:
                        error_html += f"<li>{err}</li>"
                    
                    if len(errors) > 15:
                        error_html += f"<li>...and {len(errors) - 15} more errors.</li>"
                    error_html += "</ul>"
                    
                    # Use mark_safe to allow HTML rendering in the message
                    messages.warning(request, mark_safe(error_html))
                
                return redirect("..")

            except Exception as e:
                messages.error(request, f"Critical Error processing file: {str(e)}")
                return redirect("..")

        form = ExamUploadForm()
        return render(request, "admin/exam_upload.html", {"form": form})

# 3. Register Section Admin (Optional, but useful)
@admin.register(ExamSection)
class ExamSectionAdmin(admin.ModelAdmin):
    list_display = ('name', 'exam', 'duration_minutes', 'order')
    list_filter = ('exam',)
    ordering = ('exam', 'order')

# 4. Update Question Admin
@admin.register(ExamQuestion)
class ExamQuestionAdmin(admin.ModelAdmin):
    # Updated 'exam' -> 'section' to match new model structure
    list_display = ('text', 'q_type', 'section') 
    list_filter = ('section', 'q_type')
    inlines = [TestCaseInline]

admin.site.register(StudentExamAttempt)