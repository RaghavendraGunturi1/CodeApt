from django.contrib import admin
from django.urls import path, reverse
from django.shortcuts import render, redirect
from django.contrib import messages
from django import forms
from django.db import models
from .models import (
    Exam,
    ExamSection,
    ExamQuestion,
    ExamTestCase,
    StudentExamAttempt,
    ExamAttemptCounter,
    ExamAttemptResetLog,
)
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
    fields = ('input_data', 'expected_output', 'is_hidden')
    formfield_overrides = {
        models.TextField: {
            'widget': forms.Textarea(attrs={'rows': 2, 'cols': 26, 'style': 'width: 260px;'})
        },
    }

# 2. Inline for Sections (Manage sections inside the Exam page)
class SectionInline(admin.TabularInline):
    model = ExamSection
    extra = 1

@admin.register(Exam)
class ExamAdmin(admin.ModelAdmin):
    list_display = ('topic', 'total_marks', 'max_attempts')  # ✅ ADD max_attempts
    inlines = [SectionInline]                # Add Sections here
    change_list_template = "admin/assessments_changelist.html"
    actions = ['reset_attempts_for_all_users']  # ✅ Add action 

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

    def reset_attempts_for_all_users(self, request, queryset):
        """Reset counters for selected exams, preserve StudentExamAttempt data."""
        for exam in queryset:
            counters = ExamAttemptCounter.objects.filter(exam=exam, attempt_count__gt=0)
            reset_rows = 0
            for counter in counters:
                previous = counter.attempt_count
                ExamAttemptResetLog.objects.create(
                    user=counter.user,
                    exam=counter.exam,
                    reset_by=request.user if request.user.is_authenticated else None,
                    previous_attempt_count=previous,
                    new_attempt_count=0,
                    note='Bulk reset from Exam admin action',
                )
                counter.attempt_count = 0
                counter.reset_events += 1
                counter.total_attempts_reset += previous
                from django.utils import timezone
                counter.last_reset_at = timezone.now()
                counter.save(update_fields=['attempt_count', 'reset_events', 'total_attempts_reset', 'last_reset_at', 'updated_at'])
                reset_rows += 1

            self.message_user(request, f"Reset attempt counters for {exam.topic.name}: {reset_rows} user counter(s) reset")
    reset_attempts_for_all_users.short_description = "Reset attempt counter for selected exams (keep attempt data)"

    def upload_excel(self, request):
        if request.method == "POST":
            form = ExamUploadForm(request.POST, request.FILES, admin_site=self.admin_site)
            if not form.is_valid():
                return render(request, "admin/exam_upload.html", {"form": form})

            selected_topic = form.cleaned_data["topic"]
            excel_file = form.cleaned_data["file"]
            try:
                # 1. Read Excel
                df = pd.read_excel(excel_file)
                # Normalize headers: handle spaces/case/hyphens from manual Excel edits.
                df.columns = [str(col).strip().lower().replace(' ', '_').replace('-', '_') for col in df.columns]
                df = df.fillna('')

                def get_col_value(row, *keys, default=''):
                    for key in keys:
                        if key in row.index:
                            return row.get(key, default)
                    return default
                
                success_count = 0
                errors = [] # List to track failures
                
                # Loop through rows
                for index, row in df.iterrows():
                    row_num = index + 2  # +2 because Excel header is row 1
                    
                    # --- VALIDATION 1: TOPIC NAME ---
                    topic_name = selected_topic.name if selected_topic else str(row.get('topic_name', '')).strip()
                    if not topic_name: 
                        errors.append(f"Row {row_num}: Skipped (Missing 'topic_name')")
                        continue

                    try:
                        exam = Exam.objects.get(topic__name__iexact=topic_name)
                    except Exam.DoesNotExist:
                        errors.append(f"Row {row_num}: Skipped (Exam Topic '{topic_name}' not found)")
                        continue

                    # --- PROCESS SECTION ---
                    sec_name = str(get_col_value(row, 'section_name', 'section', default='Part A - General')).strip()
                    try:
                        sec_duration = int(get_col_value(row, 'section_duration', 'duration', default=30))
                    except (ValueError, TypeError):
                        sec_duration = 30
                    
                    section, created = ExamSection.objects.get_or_create(
                        exam=exam,
                        name=sec_name,
                        defaults={'duration_minutes': sec_duration, 'order': 1}
                    )

                    # --- VALIDATION 2: CONTENT CHECK ---
                    raw_text = get_col_value(row, 'question_text', 'question', 'questiontext', 'q_text', default='')
                    q_text = str(raw_text).replace('_x000D_', '').strip()
                    if q_text.lower() == 'nan': q_text = ""

                    image_url = str(get_col_value(row, 'image_url', 'image', 'img_url', 'image_link', default='')).strip()
                    if image_url.lower() == 'nan': image_url = ""

                    # If BOTH text and image are empty, skip row
                    if not q_text and not image_url:
                        errors.append(f"Row {row_num}: Skipped (Both Question Text and Image URL are empty)")
                        continue

                    # --- CREATE QUESTION ---
                    try:
                        try:
                            marks = int(get_col_value(row, 'marks', default=5))
                        except (ValueError, TypeError):
                            marks = 5

                        q_type = str(get_col_value(row, 'type', 'question_type', default='')).strip().upper()
                        if not q_type:
                            errors.append(f"Row {row_num}: Skipped (Missing 'type')")
                            continue
                        
                        q = ExamQuestion.objects.create(
                            section=section,
                            q_type=q_type,
                            text=q_text,
                            marks=marks,
                            option_1=str(get_col_value(row, 'option_1', 'option1', default='')).strip(),
                            option_2=str(get_col_value(row, 'option_2', 'option2', default='')).strip(),
                            option_3=str(get_col_value(row, 'option_3', 'option3', default='')).strip(),
                            option_4=str(get_col_value(row, 'option_4', 'option4', default='')).strip(),
                            correct_options=str(get_col_value(row, 'correct_option', 'correct_options', 'correctanswer', default='')).strip(),
                            starter_code=str(get_col_value(row, 'starter_code', 'startercode', default='')).replace('_x000D_', '').strip()
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
                                inp = str(get_col_value(row, f'input{i}', default='')).replace('_x000D_', '').strip()
                                out = str(get_col_value(row, f'output{i}', default='')).replace('_x000D_', '').strip()
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

        form = ExamUploadForm(admin_site=self.admin_site)
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

        exam = link.exam

        attempts = StudentExamAttempt.objects.filter(
            public_link=link,
            completed_at__isnull=False
        ).order_by('-score', 'completed_at')

        sections = exam.sections.prefetch_related('questions').all()

        workbook = openpyxl.Workbook()
        sheet = workbook.active
        sheet.title = "Public Results"

        # ------------------------------
        # 1️⃣ Build Dynamic Header
        # ------------------------------
        header = ["Rank", "Roll Number", "College"]

        section_totals = {}

        for section in sections:
            total_marks = sum(q.marks for q in section.questions.all())
            section_totals[section.id] = total_marks
            header.append(f"{section.name} ({total_marks})")

        header += [f"Total ({exam.total_marks})", "Passed", "Completed At"]

        sheet.append(header)

        # ------------------------------
        # 2️⃣ Fill Rows
        # ------------------------------
        rank = 1

        for attempt in attempts:

            # Flatten answers
            flat_answers = {}
            if attempt.response_data:
                for sec_id, sec_data in attempt.response_data.items():
                    if sec_id != "metadata" and isinstance(sec_data, dict):
                        flat_answers.update(sec_data)

            row = [rank, attempt.roll_number or "", attempt.college_name or ""]

            # Section-wise scoring
            for section in sections:
                section_score = 0

                for question in section.questions.all():
                    user_ans = flat_answers.get(str(question.id))
                    if not user_ans:
                        continue

                    is_correct = False

                    # MCQ Single
                    if question.q_type == "MCQ_SINGLE":
                        if str(user_ans) == str(question.correct_options):
                            is_correct = True

                    # MCQ Multi
                    elif question.q_type == "MCQ_MULTI":
                        user_set = set(str(user_ans).split(","))
                        correct_set = set(str(question.correct_options).split(","))
                        if user_set == correct_set:
                            is_correct = True

                    # Coding
                    elif question.q_type == "CODE":
                        # Coding already calculated in final score.
                        # If full accuracy needed, section score can be stored during submission.
                        continue

                    if is_correct:
                        section_score += question.marks

                row.append(section_score)

            row += [
                attempt.score,
                "PASS" if attempt.passed else "FAIL",
                attempt.completed_at.strftime("%Y-%m-%d %H:%M") if attempt.completed_at else ""
            ]

            sheet.append(row)
            rank += 1

        # ------------------------------
        # 3️⃣ Return File
        # ------------------------------
        response = HttpResponse(
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        filename = f"{exam.topic.name}_Section_Wise_Results.xlsx"
        response["Content-Disposition"] = f'attachment; filename="{filename}"'

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


@admin.register(ExamAttemptCounter)
class ExamAttemptCounterAdmin(admin.ModelAdmin):
    list_display = ('user', 'exam', 'attempt_count', 'reset_events', 'total_attempts_reset', 'last_reset_at', 'updated_at', 'reset_counter_button')
    list_filter = ('exam',)
    search_fields = ('user__username', 'user__email', 'exam__topic__name')
    ordering = ('-updated_at',)
    actions = ['reset_selected_counters']
    readonly_fields = ('reset_counter_button',)

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                '<int:counter_id>/reset-counter/',
                self.admin_site.admin_view(self.reset_single_counter_view),
                name='assessments_examattemptcounter_reset_single',
            ),
        ]
        return custom_urls + urls

    def _reset_counter(self, counter, request, note):
        from django.utils import timezone

        previous = counter.attempt_count
        ExamAttemptResetLog.objects.create(
            user=counter.user,
            exam=counter.exam,
            reset_by=request.user if request.user.is_authenticated else None,
            previous_attempt_count=previous,
            new_attempt_count=0,
            note=note,
        )
        counter.attempt_count = 0
        counter.reset_events += 1
        counter.total_attempts_reset += previous
        counter.last_reset_at = timezone.now()
        counter.save(update_fields=['attempt_count', 'reset_events', 'total_attempts_reset', 'last_reset_at', 'updated_at'])

    def reset_single_counter_view(self, request, counter_id):
        counter = get_object_or_404(ExamAttemptCounter, id=counter_id)
        self._reset_counter(counter, request, 'Direct reset from counter detail button')
        self.message_user(
            request,
            f"Attempt counter reset for user '{counter.user.username}' in exam '{counter.exam}'. Attempt data was preserved.",
        )
        return redirect(reverse('admin:assessments_examattemptcounter_change', args=[counter.id]))

    def reset_counter_button(self, obj):
        if not obj or not obj.pk:
            return '-'
        url = reverse('admin:assessments_examattemptcounter_reset_single', args=[obj.pk])
        return format_html('<a class="button" href="{}">Reset This Counter</a>', url)
    reset_counter_button.short_description = 'Reset'

    def reset_selected_counters(self, request, queryset):
        reset_rows = 0

        for counter in queryset.select_related('user', 'exam'):
            self._reset_counter(counter, request, 'Reset from attempt counter admin action')
            reset_rows += 1

        self.message_user(request, f"Reset attempt counter for {reset_rows} selected record(s). Attempt data was preserved.")
    reset_selected_counters.short_description = "Reset attempt count to 0 (selected users/exams)"


@admin.register(ExamAttemptResetLog)
class ExamAttemptResetLogAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'user', 'exam', 'previous_attempt_count', 'new_attempt_count', 'reset_by', 'note')
    list_filter = ('exam', 'created_at')
    search_fields = ('user__username', 'user__email', 'exam__topic__name', 'note')
    ordering = ('-created_at',)
    readonly_fields = ('created_at', 'user', 'exam', 'previous_attempt_count', 'new_attempt_count', 'reset_by', 'note')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

