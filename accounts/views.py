from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib import messages

def login_view(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                # Intercept for forced password change
                if hasattr(user, 'profile') and user.profile.force_password_change:
                    request.session['force_password_change_user_id'] = user.id
                    messages.warning(request, "For security reasons, you must change your default password before logging in.")
                    return redirect('force_password_change')
                    
                login(request, user)
                messages.success(request, f"Welcome back, {username}!")
                return redirect('index') # Redirect to home after login
            else:
                messages.error(request, "Invalid username or password.")
        else:
            messages.error(request, "Invalid username or password.")
    
    form = AuthenticationForm()
    return render(request, 'accounts/login.html', {'form': form})

from .forms import StudentRegisterForm
from core.models import Profile

def register_view(request):
    if request.method == 'POST':
        form = StudentRegisterForm(request.POST)
        if form.is_valid():
            # 1. Save the User
            user = form.save()
            
            # 2. Update/Create the Profile
            # Use get_or_create to avoid errors if a profile signal already exists
            profile, created = Profile.objects.get_or_create(user=user)
            profile.full_name = form.cleaned_data.get('full_name')
            profile.roll_number = form.cleaned_data.get('roll_number') # Save it here
            profile.college_name = form.cleaned_data.get('college_name')
            profile.phone_number = form.cleaned_data.get('phone_number')
            profile.state = form.cleaned_data.get('state')
            profile.save()

            username = form.cleaned_data.get('username')
            messages.success(request, f"Account created for {username}! You can now log in.")
            return redirect('login')
    else:
        form = StudentRegisterForm()
    return render(request, 'accounts/register.html', {'form': form})


def logout_view(request):
    logout(request)
    messages.info(request, "You have successfully logged out.")
    return redirect('login')


from django.contrib.auth.models import User

def force_password_change_view(request):
    user_id = request.session.get('force_password_change_user_id')
    if not user_id:
        return redirect('login')
        
    user = User.objects.get(id=user_id)
    
    if request.method == 'POST':
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')
        
        if new_password and new_password == confirm_password:
            # Check length or other validations if needed
            if len(new_password) < 8:
                messages.error(request, "Password must be at least 8 characters long.")
            else:
                user.set_password(new_password)
                user.save()
                
                # Turn off the force change flag
                user.profile.force_password_change = False
                user.profile.save()
                
                # Clear session
                del request.session['force_password_change_user_id']
                
                messages.success(request, "Password successfully updated! Please log in with your new password.")
                return redirect('login')
        else:
            messages.error(request, "Passwords do not match.")
            
    return render(request, 'accounts/force_password_change.html', {'user': user})