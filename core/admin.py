from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import Profile, ExecutionJob
# --- ASYNC EXECUTION JOB ADMIN ---
@admin.register(ExecutionJob)
class ExecutionJobAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "job_type", "status", "queue_name", "created_at", "started_at", "finished_at", "retries")
    list_filter = ("job_type", "status", "queue_name", "created_at")
    search_fields = ("id", "user__username", "related_id")
    readonly_fields = ("id", "created_at", "started_at", "finished_at", "result", "error", "log")
    ordering = ("-created_at",)
from django.urls import path
from django.shortcuts import render
from django.http import HttpResponse
from django.utils import timezone
from django.db.models import Avg, Count, Q, F, Case, When, Value, DecimalField, Sum, FloatField, IntegerField, Expression
from django.db.models.functions import Coalesce, Cast
import pandas as pd

from curriculum.models import TopicProgress, QuizSubmission, Topic
from assessments.models import StudentExamAttempt, Exam, ExamAttemptCounter, ExamAttemptResetLog
from challenges.models import UserStreak

# 1. This makes the Profile fields appear inside the User page
class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    verbose_name_plural = 'Extra Student Info'
    fields = ('full_name','roll_number','college_name', 'phone_number', 'state', 'bio', 'avatar_url')

# 2. Customizing the User list view to show your new data
class UserAdmin(BaseUserAdmin):
    inlines = (ProfileInline,)
    list_display = ('username', 'email', 'get_college', 'get_roll_number', 'get_state', 'is_active')
    list_select_related = ('profile',)
    list_filter = ('is_staff', 'is_superuser', 'profile__state') # Filter by State!
    actions = ('reset_exam_attempt_counters',)

    def get_college(self, obj):
        return obj.profile.college_name if hasattr(obj, 'profile') else "-"
    get_college.short_description = 'College'

    def get_roll_number(self, obj):
        return obj.profile.roll_number if hasattr(obj, 'profile') else "-"
    get_roll_number.short_description = 'Roll Number'

    def get_state(self, obj):
        return obj.profile.state if hasattr(obj, 'profile') else "-"
    get_state.short_description = 'State'

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('export_performance/', self.admin_site.admin_view(self.export_performance_view), name='export_performance'),
        ]
        return custom_urls + urls

    def reset_exam_attempt_counters(self, request, queryset):
        reset_rows = 0
        for user in queryset:
            counters = ExamAttemptCounter.objects.filter(user=user, attempt_count__gt=0).select_related('exam')
            for counter in counters:
                previous = counter.attempt_count
                ExamAttemptResetLog.objects.create(
                    user=user,
                    exam=counter.exam,
                    reset_by=request.user if request.user.is_authenticated else None,
                    previous_attempt_count=previous,
                    new_attempt_count=0,
                    note='Reset from User admin action',
                )
                counter.attempt_count = 0
                counter.reset_events += 1
                counter.total_attempts_reset += previous
                counter.last_reset_at = timezone.now()
                counter.save(update_fields=['attempt_count', 'reset_events', 'total_attempts_reset', 'last_reset_at', 'updated_at'])
                reset_rows += 1

        self.message_user(request, f'Reset attempt counters for {reset_rows} user-exam counter record(s). Attempt data preserved.')
    reset_exam_attempt_counters.short_description = 'Reset exam attempt count for selected user(s)'

    def export_performance_view(self, request):
        if request.method == 'POST':
            college_names = request.POST.getlist('college_name')
            
            # ✅ OPTIMIZED: Single annotated query instead of N+1 queries
            users = (User.objects
                .filter(profile__college_name__in=college_names)
                .select_related('profile', 'streak')
                .annotate(
                    # Total topics completed
                    total_topics=Count('topic_progress', filter=Q(topic_progress__is_completed=True)),
                    # Videos watched
                    videos_watched=Count('topic_progress', filter=Q(topic_progress__is_completed=True, topic_progress__topic__topic_type='video')),
                    # Quiz stats - Cast to float to avoid type mismatch
                    quiz_count=Count('quiz_submissions'),
                    quiz_score_sum=Coalesce(Sum(Cast('quiz_submissions__score', FloatField())), Value(0.0, output_field=FloatField())),
                    quiz_total_sum=Coalesce(Sum(Cast('quiz_submissions__total_questions', FloatField())), Value(0.0, output_field=FloatField())),
                    # Exam stats
                    exam_count=Count('studentexamattempt', filter=Q(studentexamattempt__completed_at__isnull=False)),
                    avg_warnings=Coalesce(Avg('studentexamattempt__warnings_triggered'), Value(0.0, output_field=FloatField())),
                )
                .values(
                    'id', 'username', 'email', 'date_joined', 'last_login',
                    'profile__full_name', 'profile__roll_number', 'profile__college_name', 'profile__state',
                    'total_topics', 'videos_watched', 'quiz_count', 'quiz_score_sum', 'quiz_total_sum',
                    'exam_count', 'avg_warnings',
                    'streak__total_score', 'streak__current_streak', 'streak__max_streak'
                )
            )
            
            # ✅ Fetch exam names in batch (prevents querying individual attempts)
            exam_attempts = (StudentExamAttempt.objects
                .filter(user__profile__college_name__in=college_names, completed_at__isnull=False)
                .values('user__id', 'exam__topic__name')
                .annotate(attempt_count=Count('id'))
                .order_by('user__id')
            )
            
            # Build a lookup dict for exam attempts
            exam_attempts_by_user = {}
            for item in exam_attempts:
                user_id = item['user__id']
                exam_name = item['exam__topic__name'] or "Unknown"
                if user_id not in exam_attempts_by_user:
                    exam_attempts_by_user[user_id] = {}
                exam_attempts_by_user[user_id][exam_name] = item['attempt_count']
            
            # ✅ Fetch total exam time in batch (simplified approach)
            exam_times = (StudentExamAttempt.objects
                .filter(user__profile__college_name__in=college_names, completed_at__isnull=False, started_at__isnull=False)
                .values('user__id', 'completed_at', 'started_at')
            )
            
            exam_times_by_user = {}
            for item in exam_times:
                user_id = item['user__id']
                if user_id not in exam_times_by_user:
                    exam_times_by_user[user_id] = 0
                time_diff = (item['completed_at'] - item['started_at']).total_seconds() / 60
                exam_times_by_user[user_id] += time_diff

            # ✅ Fetch attempt counter + reset history in batch (preserves old attempt records)
            counter_stats = (ExamAttemptCounter.objects
                .filter(user__profile__college_name__in=college_names)
                .values('user__id')
                .annotate(
                    current_attempt_counter=Coalesce(Sum('attempt_count'), Value(0)),
                    reset_events_total=Coalesce(Sum('reset_events'), Value(0)),
                    attempts_reset_total=Coalesce(Sum('total_attempts_reset'), Value(0)),
                )
            )

            counter_stats_by_user = {
                item['user__id']: {
                    'current_attempt_counter': item['current_attempt_counter'],
                    'reset_events_total': item['reset_events_total'],
                    'attempts_reset_total': item['attempts_reset_total'],
                }
                for item in counter_stats
            }
            
            # Build data list
            data = []
            for u in users:
                user_id = u['id']
                
                # Calculate average quiz score
                if u['quiz_count'] > 0 and u['quiz_total_sum'] > 0:
                    avg_quiz_score = (u['quiz_score_sum'] / u['quiz_total_sum']) * 100
                else:
                    avg_quiz_score = 0
                
                # Build exam attempts string
                test_attempts_dict = exam_attempts_by_user.get(user_id, {})
                test_attempts_str = " | ".join([f"{k}: {v}" for k, v in test_attempts_dict.items()])
                
                # Get exam time
                total_exam_time_minutes = exam_times_by_user.get(user_id, 0)

                # Get attempt counter/reset history
                counter_info = counter_stats_by_user.get(user_id, {})
                current_attempt_counter = counter_info.get('current_attempt_counter', 0)
                reset_events_total = counter_info.get('reset_events_total', 0)
                attempts_reset_total = counter_info.get('attempts_reset_total', 0)
                
                # Get streak data (or defaults)
                total_score = u['streak__total_score'] or 0
                current_streak = u['streak__current_streak'] or 0
                longest_streak = u['streak__max_streak'] or 0
                
                data.append({
                    'Name': u['profile__full_name'],
                    'Email': u['email'],
                    'Roll Number': u['profile__roll_number'],
                    'College Name': u['profile__college_name'],
                    'State': u['profile__state'],
                    'Date Joined': u['date_joined'].strftime('%Y-%m-%d %H:%M') if u['date_joined'] else '',
                    'Last Login': u['last_login'].strftime('%Y-%m-%d %H:%M') if u['last_login'] else '',
                    
                    'Total Topics Completed': u['total_topics'],
                    'Videos Watched': u['videos_watched'],
                    'Average Quiz Score (%)': round(avg_quiz_score, 2),
                    
                    'Total Mock Attempts': u['exam_count'],
                    'Attempts per Test': test_attempts_str,
                    'Current Attempt Counter (Restriction)': current_attempt_counter,
                    'Attempt Reset Events': reset_events_total,
                    'Attempts Reset Total': attempts_reset_total,
                    'Total Exam Time (Mins)': round(total_exam_time_minutes, 2),
                    'Average Warnings': round(float(u['avg_warnings']), 2),
                    
                    'Challenges Score': total_score,
                    'Current Streak': current_streak,
                    'Longest Streak': longest_streak,
                })
            
            df = pd.DataFrame(data)
            
            # Create Excel Response
            response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            filename_suffix = "_".join([str(c)[:5] for c in college_names])[:20]
            response['Content-Disposition'] = f'attachment; filename="performance_report_{filename_suffix}.xlsx"'
            
            with pd.ExcelWriter(response, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='Performance')
                
            return response
            
        colleges = Profile.objects.exclude(college_name='').values_list('college_name', flat=True).distinct().order_by('college_name')
        
        context = dict(self.admin_site.each_context(request))
        context['colleges'] = colleges
        return render(request, "admin/core/user/export_performance.html", context)

# 3. Replace the default User Admin with our customized version
admin.site.unregister(User)
admin.site.register(User, UserAdmin)

# 4. Also register Profile separately just in case you need it
@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'college_name', 'state', 'phone_number')
    list_select_related = ('user',)
    search_fields = ('user__username', 'college_name', 'phone_number')