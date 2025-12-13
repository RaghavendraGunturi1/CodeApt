from django.contrib import admin
from .models import Program, Subject, Topic

@admin.register(Program)
class ProgramAdmin(admin.ModelAdmin):
    list_display = ('name',)

@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ('name', 'program')
    prepopulated_fields = {'slug': ('name',)}

@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    list_display = ('name', 'subject', 'order')
    list_filter = ('subject',)

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