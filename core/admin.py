from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import Profile

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

# 3. Replace the default User Admin with our customized version
admin.site.unregister(User)
admin.site.register(User, UserAdmin)

# 4. Also register Profile separately just in case you need it
@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'college_name', 'state', 'phone_number')
    search_fields = ('user__username', 'college_name', 'phone_number')