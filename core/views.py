from django.shortcuts import render, redirect
from django.contrib import messages # For success messages
from .forms import ContactForm
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404


def index(request):
    return render(request, 'core/index.html')

def contact(request):
    if request.method == 'POST':
        form = ContactForm(request.POST)
        if form.is_valid():
            # In the future, we will add code here to actually send the email.
            # For now, we just show a success message.
            name = form.cleaned_data['name']
            messages.success(request, f"Thank you, {name}! We have received your message.")
            return redirect('contact')
    else:
        form = ContactForm()

    return render(request, 'core/contact.html', {'form': form})

def training(request):
    return render(request, 'core/training.html')

def placements(request):
    return render(request, 'core/placements.html')

def about(request):
    return render(request, 'core/about.html')

from curriculum.models import Subject  # Import your new model

@login_required(login_url='login')
def dashboard(request):
    # Fetch all subjects (e.g., Python, Java)
    subjects = Subject.objects.all()
    
    context = {
        'user': request.user,
        'subjects': subjects  # Pass data to the template
    }
    return render(request, 'core/dashboard.html', context)

@login_required(login_url='login')
def course_detail(request, slug):
    # Find the specific subject by its URL slug (e.g., 'python')
    subject = get_object_or_404(Subject, slug=slug)
    
    # Get all topics for this subject, ordered by the 'order' field
    topics = subject.topics.all().order_by('order')
    
    context = {
        'subject': subject,
        'topics': topics
    }
    return render(request, 'core/course_detail.html', context)

from curriculum.models import Topic

@login_required(login_url='login')
def topic_detail(request, topic_id):
    topic = get_object_or_404(Topic, id=topic_id)
    subject = topic.subject
    
    # Optional: Logic to find next/prev topics could go here later
    
    context = {
        'topic': topic,
        'subject': subject
    }
    return render(request, 'core/topic_detail.html', context)

@login_required(login_url='login')
def arena(request):
    return render(request, 'core/arena.html')

import requests
import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

@csrf_exempt # Allow POST requests from the frontend
def run_code(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        code = data.get('code')
        language = data.get('language')
        
        # Map our frontend language names to Piston API versions
        # Piston needs specific version numbers or it might fail
        configs = {
            'python': {'language': 'python', 'version': '3.10.0'},
            'java': {'language': 'java', 'version': '15.0.2'},
            'c_cpp': {'language': 'cpp', 'version': '10.2.0'},
            'javascript': {'language': 'javascript', 'version': '18.15.0'},
        }
        
        config = configs.get(language)
        
        if not config:
            return JsonResponse({'output': 'Error: Unsupported language'})

        # Prepare payload for Piston API
        payload = {
            "language": config['language'],
            "version": config['version'],
            "files": [
                {
                    "content": code
                }
            ]
        }
        
        # Send to Public Piston API (You can change this URL to your self-hosted one later)
        try:
            response = requests.post('https://emkc.org/api/v2/piston/execute', json=payload)
            result = response.json()
            
            # Extract the output
            if 'run' in result:
                output = result['run']['stdout'] + result['run']['stderr']
            else:
                output = "Error: Could not execute code."
                
            return JsonResponse({'output': output})
            
        except Exception as e:
            return JsonResponse({'output': f"Server Error: {str(e)}"})

    return JsonResponse({'output': 'Invalid Request'})


from curriculum.models import Question # Import the model

@login_required(login_url='login')
def quiz_view(request, slug):
    subject = get_object_or_404(Subject, slug=slug)
    
    # Get all questions for this subject (Limit to 10 for a test)
    questions = Question.objects.filter(subject=subject)
    
    if request.method == 'POST':
        score = 0
        total = questions.count()
        
        for q in questions:
            # Get the selected option ID from the form
            selected_option_id = request.POST.get(str(q.id))
            if selected_option_id:
                # Check if the selected choice is the correct one
                choice = q.choices.filter(id=selected_option_id, is_correct=True)
                if choice.exists():
                    score += 1
        
        # Calculate Percentage
        percentage = int((score / total) * 100) if total > 0 else 0
        
        return render(request, 'core/quiz_result.html', {
            'subject': subject,
            'score': score,
            'total': total,
            'percentage': percentage
        })

    context = {
        'subject': subject,
        'questions': questions
    }
    return render(request, 'core/quiz.html', context)