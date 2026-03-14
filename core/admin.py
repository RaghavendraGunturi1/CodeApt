from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import Profile
from django.urls import path
from django.shortcuts import render
from django.http import HttpResponse
from django.db.models import Avg
import pandas as pd

from curriculum.models import TopicProgress, QuizSubmission, Topic
from assessments.models import StudentExamAttempt, Exam
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
    list_filter = ('is_staff', 'is_superuser', 'profile__state') # Filter by State!

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

    def export_performance_view(self, request):
        if request.method == 'POST':
            college_names = request.POST.getlist('college_name')
            users = User.objects.filter(profile__college_name__in=college_names)
            
            data = []
            for u in users:
                prof = getattr(u, 'profile', None)
                if not prof:
                    continue
                
                # 1. Course Status & Progress
                total_topics = TopicProgress.objects.filter(user=u, is_completed=True).count()
                videos_watched = TopicProgress.objects.filter(user=u, is_completed=True, topic__topic_type='video').count()
                
                # 2. Quiz Performance
                quizzes = QuizSubmission.objects.filter(user=u)
                avg_quiz_score = sum(q.percentage for q in quizzes) / quizzes.count() if quizzes.exists() else 0
                
                # 3. Exam Performance
                attempts = StudentExamAttempt.objects.filter(user=u)
                total_mock_attempts = attempts.count()
                avg_warnings = attempts.aggregate(Avg('warnings_triggered'))['warnings_triggered__avg'] or 0
                
                # Exam time
                total_exam_time_minutes = 0
                test_attempts = {}
                for att in attempts:
                    exam_name = str(att.exam) if att.exam else "Unknown"
                    test_attempts[exam_name] = test_attempts.get(exam_name, 0) + 1
                    
                    if att.completed_at and att.started_at:
                        diff = (att.completed_at - att.started_at).total_seconds() / 60.0
                        total_exam_time_minutes += diff
                
                test_attempts_str = " | ".join([f"{k}: {v}" for k, v in test_attempts.items()])
                
                # 4. Engagement Metrics
                try:
                    streak = UserStreak.objects.get(user=u)
                    total_score = streak.total_score
                    current_streak = streak.current_streak
                    longest_streak = streak.max_streak
                except UserStreak.DoesNotExist:
                    total_score = 0
                    current_streak = 0
                    longest_streak = 0
                
                data.append({
                    'Name': prof.full_name,
                    'Email': u.email,
                    'Roll Number': prof.roll_number,
                    'College Name': prof.college_name,
                    'State': prof.state,
                    'Date Joined': u.date_joined.strftime('%Y-%m-%d %H:%M') if u.date_joined else '',
                    'Last Login': u.last_login.strftime('%Y-%m-%d %H:%M') if u.last_login else '',
                    
                    'Total Topics Completed': total_topics,
                    'Videos Watched': videos_watched,
                    'Average Quiz Score (%)': round(avg_quiz_score, 2),
                    
                    'Total Mock Attempts': total_mock_attempts,
                    'Attempts per Test': test_attempts_str,
                    'Total Exam Time (Mins)': round(total_exam_time_minutes, 2),
                    'Average Warnings': round(avg_warnings, 2),
                    
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
    search_fields = ('user__username', 'college_name', 'phone_number')