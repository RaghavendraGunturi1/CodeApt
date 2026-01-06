from django.contrib import admin
from .models import Exam, ExamQuestion, ExamTestCase, StudentExamAttempt

class TestCaseInline(admin.TabularInline):
    model = ExamTestCase
    extra = 1

class QuestionInline(admin.StackedInline):
    model = ExamQuestion
    extra = 1
    inlines = [TestCaseInline] # Note: Nested inlines require third-party packages usually, but we will keep it simple here.
    # To strictly allow Test Cases inside Questions inside Exams in Django Admin is hard. 
    # Recommendation: Edit Questions separately or use a custom form.
    # For now, we register ExamQuestion separately to add Test Cases.

@admin.register(Exam)
class ExamAdmin(admin.ModelAdmin):
    list_display = ('topic', 'duration_minutes', 'total_marks')

class TestCaseInline(admin.TabularInline):
    model = ExamTestCase
    extra = 2

@admin.register(ExamQuestion)
class ExamQuestionAdmin(admin.ModelAdmin):
    list_display = ('text', 'q_type', 'exam')
    list_filter = ('exam', 'q_type')
    inlines = [TestCaseInline] # Add test cases here

@admin.register(StudentExamAttempt)
class AttemptAdmin(admin.ModelAdmin):
    list_display = ('user', 'exam', 'score', 'passed', 'warnings_triggered')