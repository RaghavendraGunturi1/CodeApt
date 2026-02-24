from django.contrib import admin
from django.urls import path
from django.shortcuts import render, redirect
from django.contrib import messages
from .models import Exam, ExamSection, ExamQuestion, ExamTestCase, StudentExamAttempt
from .forms import ExamUploadForm
import pandas as pd
# Add these imports at the top
import re  # <--- REQUIRED: Add this import at the top of your file if missing
import requests
from django.utils.safestring import mark_safe # <--- IMPORTANT NEW IMPORT
from django.core.files.base import ContentFile
from .models import PublicExamLink
from django.utils.html import format_html
import openpyxl
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from .models import PublicExamLink, StudentExamAttempt

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
    list_display = ('topic', 'total_marks')  # ✅ ADD THIS
    inlines = [SectionInline]                # Add Sections here
    change_list_template = "admin/assessments_changelist.html" 

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                'upload-exam-questions/',
                self.admin_site.admin_view(self.upload_excel),
                name='upload_exam_questions'
            ),
        ]
        return custom_urls + urls
    def change_view(self, request, object_id, form_url='', extra_context=None):
        extra_context = extra_context or {}
        extra_context['export_public_url'] = f"{object_id}/export-public-results/"
        return super().change_view(request, object_id, form_url, extra_context)

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
                    row_num = index + 2  # +2 because Excel header is row 1
                    
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

                        # --- HANDLE IMAGE (With Google Drive Logic) ---
                        if image_url:
                            # 1. Auto-Convert Google Drive Links
                            if "drive.google.com" in image_url:
                                file_id_match = re.search(r'/d/([a-zA-Z0-9_-]+)', image_url)
                                if file_id_match:
                                    file_id = file_id_match.group(1)
                                    image_url = f'https://drive.google.com/uc?export=download&id={file_id}'

                            # 2. Download and Save
                            try:
                                response = requests.get(image_url, timeout=10)
                                if response.status_code == 200:
                                    # Create a clean filename
                                    file_name = f"question_{q.id}.jpg"
                                    q.image.save(file_name, ContentFile(response.content), save=True)
                                else:
                                    errors.append(f"Row {row_num}: Question created, but Image download failed (Status {response.status_code})")
                            except Exception as img_err:
                                errors.append(f"Row {row_num}: Question created, but Image download error: {str(img_err)}")

                        # --- HANDLE TEST CASES ---
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
                    error_html = "<strong>Some rows were skipped or had warnings:</strong><br><ul style='margin-bottom:0;'>"
                    for err in errors[:15]:
                        error_html += f"<li>{err}</li>"
                    if len(errors) > 15:
                        error_html += f"<li>...and {len(errors) - 15} more errors.</li>"
                    error_html += "</ul>"
                    messages.warning(request, mark_safe(error_html))
                
                return redirect("..")

            except Exception as e:
                messages.error(request, f"Critical Error processing file: {str(e)}")
                return redirect("..")

        form = ExamUploadForm()
        return render(request, "admin/exam_upload.html", {"form": form})
        
# 3. Register Section Admin
@admin.register(ExamSection)
class ExamSectionAdmin(admin.ModelAdmin):
    list_display = ('name', 'exam', 'duration_minutes', 'order')
    list_filter = ('exam',)
    ordering = ('exam', 'order')

# 4. Final Question Admin Fix
@admin.register(ExamQuestion)
class ExamQuestionAdmin(admin.ModelAdmin):

    list_display = ('short_text', 'q_type', 'section', 'get_exam')
    list_filter = ('section__exam', 'q_type', 'section')
    inlines = [TestCaseInline]

    # 🔥 IMPORTANT: Optimize queries
    list_select_related = ('section', 'section__exam', 'section__exam__topic')

    def short_text(self, obj):
        return obj.text[:50] if obj.text else "Image Question"

    def get_exam(self, obj):
        if obj.section and obj.section.exam and obj.section.exam.topic:
            return obj.section.exam.topic.name
        return "No Exam"

    get_exam.short_description = 'Exam'

@admin.register(PublicExamLink)
class PublicExamLinkAdmin(admin.ModelAdmin):
    list_display = (
        'exam',
        'is_active',
        'view_link',
        'export_results_button',
        'created_at'
    )

    list_filter = ('exam', 'is_active')

    # ✅ Custom Admin URLs
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                '<int:link_id>/export-results/',
                self.admin_site.admin_view(self.export_link_results),
                name='public_link_export_results'
            ),
        ]
        return custom_urls + urls

    # ✅ Export Button (Correct URL)
    def export_results_button(self, obj):
        return format_html(
            '<a class="button" href="{}">Export Results</a>',
            f"/admin/assessments/publicexamlink/{obj.id}/export-results/"
        )
    export_results_button.short_description = "Export"

    # ✅ Public Exam Link
    def view_link(self, obj):
        return format_html(
            '<a href="/assessments/public/{}" target="_blank">Open Link</a>',
            obj.access_token
        )
    view_link.short_description = "Public URL"

    # ✅ Actual Export Logic (Per Link)
    def export_link_results(self, request, link_id):
        link = get_object_or_404(PublicExamLink, id=link_id)

        attempts = StudentExamAttempt.objects.filter(
            public_link=link,
            completed_at__isnull=False
        ).order_by('-score')

        workbook = openpyxl.Workbook()
        sheet = workbook.active
        sheet.title = "Public Results"

        sheet.append([
            "Rank",
            "Roll Number",
            "College",
            "Score",
            "Passed",
            "Completed At"
        ])

        rank = 1
        for attempt in attempts:
            sheet.append([
                rank,
                attempt.roll_number or "",
                attempt.college_name or "",
                attempt.score,
                "PASS" if attempt.passed else "FAIL",
                attempt.completed_at.strftime("%Y-%m-%d %H:%M") if attempt.completed_at else ""
            ])
            rank += 1

        response = HttpResponse(
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        filename = f"{link.exam.topic.name}_Link_{link.id}_Results.xlsx"
        response['Content-Disposition'] = f'attachment; filename={filename}'

        workbook.save(response)
        return response


@admin.register(StudentExamAttempt)
class StudentExamAttemptAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'exam',
        'user',
        'roll_number',
        'college_name',
        'score',
        'passed',
        'completed_at',
        'is_public_attempt'
    )

    list_filter = ('exam', 'passed', 'completed_at')
    search_fields = ('user__username', 'roll_number', 'college_name')
    ordering = ('-completed_at',)

    def is_public_attempt(self, obj):
        return obj.user is None
    is_public_attempt.boolean = True
    is_public_attempt.short_description = "Public?"

