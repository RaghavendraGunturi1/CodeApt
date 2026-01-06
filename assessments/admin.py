from django.contrib import admin
from django.urls import path
from django.shortcuts import render, redirect
from django.contrib import messages
from .models import Exam, ExamQuestion, ExamTestCase, StudentExamAttempt
from .forms import ExamUploadForm
import pandas as pd

# Inline for Test Cases (Keep this)
class TestCaseInline(admin.TabularInline):
    model = ExamTestCase
    extra = 1

@admin.register(Exam)
class ExamAdmin(admin.ModelAdmin):
    list_display = ('topic', 'duration_minutes', 'total_marks')
    change_list_template = "admin/assessments_changelist.html" # We will create this template

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
                
                count = 0
                
                # Loop through rows
                for index, row in df.iterrows():
                    # Identify the Exam (You need to specify which exam these belong to)
                    # Option A: In the Excel file, have a column 'exam_topic_name'
                    # Option B: For simplicity, we can just link to the LAST created exam or handle it differently.
                    # BETTER APPROACH: We will require an 'exam_id' or 'topic_name' column in the Excel.
                    
                    topic_name = str(row.get('topic_name', '')).strip()
                    if not topic_name: continue

                    try:
                        exam = Exam.objects.get(topic__name__iexact=topic_name)
                    except Exam.DoesNotExist:
                        continue # Skip if exam doesn't exist

                    # Clean Data
                    q_text = str(row['question_text']).replace('_x000D_', '').strip()
                    q_type = str(row['type']).strip().upper() # MCQ_SINGLE, MCQ_MULTI, CODE
                    marks = int(row.get('marks', 5))
                    
                    # Create Question
                    q = ExamQuestion.objects.create(
                        exam=exam,
                        q_type=q_type,
                        text=q_text,
                        marks=marks,
                        option_1=str(row.get('option_1', '')).strip(),
                        option_2=str(row.get('option_2', '')).strip(),
                        option_3=str(row.get('option_3', '')).strip(),
                        option_4=str(row.get('option_4', '')).strip(),
                        correct_options=str(row.get('correct_option', '')).strip(), # "1" or "1,2"
                        starter_code=str(row.get('starter_code', '')).replace('_x000D_', '').strip()
                    )

                    # Add Test Cases (If Coding)
                    if q_type == 'CODE':
                        for i in range(1, 6):
                            inp = str(row.get(f'input{i}', '')).replace('_x000D_', '').strip()
                            out = str(row.get(f'output{i}', '')).replace('_x000D_', '').strip()
                            if inp and out:
                                ExamTestCase.objects.create(
                                    question=q,
                                    input_data=inp,
                                    expected_output=out
                                )
                    count += 1
                
                messages.success(request, f"Successfully uploaded {count} questions.")
                return redirect("..")

            except Exception as e:
                messages.error(request, f"Error: {e}")

        form = ExamUploadForm()
        return render(request, "admin/exam_upload.html", {"form": form})

# Register other models
@admin.register(ExamQuestion)
class ExamQuestionAdmin(admin.ModelAdmin):
    list_display = ('text', 'q_type', 'exam')
    list_filter = ('exam', 'q_type')
    inlines = [TestCaseInline]

admin.site.register(StudentExamAttempt)