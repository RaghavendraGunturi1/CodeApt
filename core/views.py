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



def about(request):
    return render(request, 'core/about.html')

from curriculum.models import Subject  # Import your new model

@login_required(login_url='login')
def dashboard(request):
    # Fetch ONLY the courses the user has enrolled in
    user_enrollments = Enrollment.objects.filter(user=request.user).select_related('subject')
    my_courses = [enrollment.subject for enrollment in user_enrollments]
    
    context = {
        'user': request.user,
        'subjects': my_courses  # Now this only contains enrolled courses
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

from django.shortcuts import render

def training(request):
    """
    Enhanced Training Page using Google's Stable Logo Service.
    """
    context = {
        'service_track': {
            'title': 'Service-Based Track (CRT)',
            'tagline': 'The Fast-Track to Mass Recruitment Success',
            'desc': 'Designed for speed and accuracy. Crack the high-volume hiring exams of TCS, Infosys, Wipro, and Accenture with our rigorous Aptitude and Fundamental Coding modules.',
            'icon': 'bi-briefcase',
            'color': 'primary',
            'stats': ['Average Package: 3.5 - 7 LPA', 'Focus: Speed & Fundamentals', 'Hiring Volume: High'],
            # UPDATED: Using Google's Icon Service (Reliable globally)
            'companies': [
                {'name': 'TCS', 'logo': 'https://www.google.com/s2/favicons?domain=tcs.com&sz=128'},
                {'name': 'Infosys', 'logo': 'https://www.google.com/s2/favicons?domain=infosys.com&sz=128'},
                {'name': 'Wipro', 'logo': 'https://www.google.com/s2/favicons?domain=wipro.com&sz=128'},
                {'name': 'Accenture', 'logo': 'https://www.google.com/s2/favicons?domain=accenture.com&sz=128'},
                {'name': 'Cognizant', 'logo': 'https://www.google.com/s2/favicons?domain=cognizant.com&sz=128'},
                {'name': 'HCL Tech', 'logo': 'https://www.google.com/s2/favicons?domain=hcltech.com&sz=128'},
            ],
            'modules': [
                {
                    'name': 'Quantitative Aptitude',
                    'details': ['Number Systems & Algebra', 'Time, Speed & Distance', 'Percentages & Profit/Loss', 'Geometry & Mensuration']
                },
                {
                    'name': 'Logical Reasoning',
                    'details': ['Seating Arrangements', 'Data Interpretation', 'Coding-Decoding', 'Puzzles & Syllogisms']
                },
                {
                    'name': 'Verbal Ability',
                    'details': ['Reading Comprehension', 'Error Spotting', 'Vocabulary Building', 'Resume & Email Writing']
                },
                {
                    'name': 'Technical Fundamentals',
                    'details': ['C / Java / Python Basics', 'SQL & DBMS Queries', 'Basic Data Structures', 'Pseudocode Logic']
                }
            ]
        },
        'product_track': {
            'title': 'Product-Based Track',
            'tagline': 'Build the Future with High-Paying Roles',
            'desc': 'Targeting the elite "Super Dream" offers? This track goes deep into Advanced DSA, System Design, and Competitive Programming needed for Amazon, Google, and Oracle.',
            'icon': 'bi-rocket-takeoff',
            'color': 'warning',
            'stats': ['Average Package: 10 - 45+ LPA', 'Focus: Logic & Optimization', 'Hiring Volume: Selective'],
            # UPDATED: Using Google's Icon Service
            'companies': [
                {'name': 'Amazon', 'logo': 'https://www.google.com/s2/favicons?domain=amazon.com&sz=128'},
                {'name': 'Microsoft', 'logo': 'https://www.google.com/s2/favicons?domain=microsoft.com&sz=128'},
                {'name': 'Google', 'logo': 'https://www.google.com/s2/favicons?domain=google.com&sz=128'},
                {'name': 'Oracle', 'logo': 'https://www.google.com/s2/favicons?domain=oracle.com&sz=128'},
                {'name': 'Zoho', 'logo': 'https://www.google.com/s2/favicons?domain=zoho.com&sz=128'},
                {'name': 'Salesforce', 'logo': 'https://www.google.com/s2/favicons?domain=salesforce.com&sz=128'},
            ],
            'modules': [
                {
                    'name': 'Advanced DSA',
                    'details': ['Trees, Graphs & Tries', 'Dynamic Programming (DP)', 'Greedy Algorithms', 'Backtracking & Recursion']
                },
                {
                    'name': 'Competitive Programming',
                    'details': ['LeetCode Medium/Hard Patterns', 'CodeChef Contest Strategy', 'Time & Space Complexity Analysis']
                },
                {
                    'name': 'CS Core Subjects',
                    'details': ['Operating Systems (OS)', 'DBMS & Normalization', 'Computer Networks', 'Object-Oriented Design (LLD)']
                },
                {
                    'name': 'Interview Readiness',
                    'details': ['Mock FAANG Interviews', 'System Design Basics', 'Whiteboard Coding', 'Behavioral Rounds']
                }
            ]
        }
    }
    return render(request, 'core/training.html', context)

def placements(request):
    """
    Corrected Placement Stats and Expanded Partner List.
    """
    context = {
        'partners': [
            "IARE, Hyderabad", "SR University, Warangal", "MRECW, Hyderabad",
            "ACEEC, Ghatkesar", "Pragati Engineering College, Kakinada",
            "Sreedevi Women's Engg. College", "SRIT, Anantapur",
            "KITS, Guntur", "KITS, Warangal", "KITS, Huzurabad",  # Added
            "KIET, Kakinada", "Vemu IT, Pakala",
            "Swaranandra Engg. College", "AITS, Tirupati",
            "PBR VITS, Kavali", "NEC, Narasaraopet",  # Added
            "MEC, Guntur",  # Added
            "AVNIET, Hyderabad",               # <--- NEW ADDITION
            "KGRCET, Hyderabad",               # <--- NEW ADDITION
            "KPRIT, Hyderabad",                # <--- NEW ADDITION
            "Sreerama Engg. College, Tirupati" # <--- NEW ADDITION
        ],
        'success_stories': [
            {
                'company': 'Infosys',
                'count': '201',
                'subtext': 'Selections from a Single College',
                'college': 'Malla Reddy Engg. College for Women (MRECW)'
            },
            {
                'company': 'Infosys',
                'count': '92',
                'subtext': 'Selections from a Single Group',
                'college': 'KITS Group, Guntur'  # <--- NEW RECORD ADDED HERE
            },
            {
                'company': 'Accenture',
                'count': '196',
                'subtext': 'Selections from a Single College',
                'college': 'ACE Engineering College'
            },
            {
                'company': 'Cognizant',
                'count': '100+',
                'subtext': 'Selections from a Single College',
                'college': 'SRIT Anantapur'
            },
            {
                'company': 'Cognizant (CTS)',
                'count': '85',
                'subtext': 'Selections from a Single College',
                'college': 'ACE Engineering College (ACEEC)'  # <--- NEW RECORD
            },
            {
                'company': 'HCL',
                'count': '50',
                'subtext': 'Special Recruitment Drive',
                'college': 'KITS Guntur'
            },
        ]
    }
    return render(request, 'core/placements.html', context)


from curriculum.models import Subject  # Ensure this is imported

def courses(request):
    """
    Public Course Catalog Page.
    """
    all_courses = Subject.objects.all()
    
    context = {
        'courses': all_courses
    }
    return render(request, 'core/courses.html', context)

def course_landing(request, slug):
    """
    Public Course Landing Page (Sales Page).
    """
    course = get_object_or_404(Subject, slug=slug)
    # Fetch syllabus preview
    topics = course.topics.all().order_by('order')
    
    context = {
        'course': course,
        'topics': topics
    }
    return render(request, 'core/course_landing.html', context)


from django.contrib import messages
from curriculum.models import Subject, Topic, Enrollment # Add Enrollment here

@login_required(login_url='login')
def enroll_course(request, slug):
    """
    Enrolls the current user in the selected course.
    """
    subject = get_object_or_404(Subject, slug=slug)
    
    # Check if already enrolled to prevent duplicates
    already_enrolled = Enrollment.objects.filter(user=request.user, subject=subject).exists()
    
    if not already_enrolled:
        Enrollment.objects.create(user=request.user, subject=subject)
        messages.success(request, f"Welcome to {subject.name}! You have successfully enrolled.")
    else:
        messages.info(request, f"You are already enrolled in {subject.name}.")
    
    return redirect('dashboard')