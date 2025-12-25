from django.shortcuts import render, redirect
from django.contrib import messages # For success messages
from .forms import ContactForm
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
import base64
import hashlib
import json
import requests
import uuid
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from curriculum.models import Order # We just created this

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

def terms(request):
    return render(request, 'core/terms.html')

def privacy(request):
    return render(request, 'core/privacy.html')

def refund_policy(request):
    return render(request, 'core/refund_policy.html')

from curriculum.models import Subject  # Import your new model

from django.db.models import Count, Q
from curriculum.models import Enrollment, TopicProgress, QuizSubmission
from curriculum.models import JobApplication
@login_required(login_url='login')
def dashboard(request):
    # Fetch enrolled courses
    user_enrollments = Enrollment.objects.filter(user=request.user).select_related('subject')
    
    course_data = []
    total_lessons_completed = 0
    
    for enrollment in user_enrollments:
        subject = enrollment.subject
        
        # 1. Total Topics in this course
        total_topics = subject.topics.count()
        
        # 2. Completed Topics by this user in this course
        completed_topics = TopicProgress.objects.filter(
            user=request.user, 
            topic__subject=subject, 
            is_completed=True
        ).count()
        
        # 3. Calculate Percentage
        if total_topics > 0:
            progress_percent = int((completed_topics / total_topics) * 100)
        else:
            progress_percent = 0
            
        total_lessons_completed += completed_topics
        
        # Append data to list
        course_data.append({
            'subject': subject,
            'progress': progress_percent,
            'completed': completed_topics,
            'total': total_topics
        })
        # --- NEW: CALCULATE QUIZ STATS ---
    user_submissions = QuizSubmission.objects.filter(user=request.user)
    
    # 1. Total Tests Attempted
    total_tests_attempted = user_submissions.count()
    
    # 2. Average Score across all tests
    # We calculate the average percentage manually to be safe
    avg_score = 0
    if total_tests_attempted > 0:
        total_percentage = sum([sub.percentage for sub in user_submissions])
        avg_score = int(total_percentage / total_tests_attempted)
    # ---------------------------------
    pending_orders = Order.objects.filter(user=request.user, status='PENDING').select_related('subject')
    my_applications = JobApplication.objects.filter(user=request.user).select_related('job').order_by('-applied_at')
    context = {
        'user': request.user,
        'course_data': course_data,
        'total_lessons_completed': total_lessons_completed,
        'total_courses': user_enrollments.count(),
        'total_tests_attempted': total_tests_attempted,
        'avg_score': avg_score,
        'pending_orders': pending_orders, # Add this
        'my_applications': my_applications, # <--- CRITICAL FOR DASHBOARD
    }
    return render(request, 'core/dashboard.html', context)

@login_required(login_url='login')
def course_detail(request, slug):
    # Find the specific subject by its URL slug (e.g., 'python')
    subject = get_object_or_404(Subject, slug=slug)
    modules = subject.modules.prefetch_related('topics').order_by('order')
    orphan_topics = subject.topics.filter(module__isnull=True).order_by('order')
    # Get all topics for this subject, ordered by the 'order' field
    topics = subject.topics.all().order_by('order')
    
    context = {
        'course': subject,
        'subject': subject,
        'modules': modules,       # Send modules
        'orphan_topics': orphan_topics, # Send topics with no module
        'is_enrolled': Enrollment.objects.filter(user=request.user, subject=subject).exists()
    }
    return render(request, 'core/course_detail.html', context)

from curriculum.models import Topic

# In core/views.py

@login_required(login_url='login')
def topic_detail(request, topic_id):
    topic = get_object_or_404(Topic, id=topic_id)
    subject = topic.subject
    
    # Check if this topic is already completed by the user
    is_completed = False
    if request.user.is_authenticated:
        is_completed = TopicProgress.objects.filter(user=request.user, topic=topic, is_completed=True).exists()
    
    context = {
        'topic': topic,
        'subject': subject,
        'is_completed': is_completed, # Pass this to the template
    }
    return render(request, 'core/topic_detail.html', context)

@login_required(login_url='login')
def arena(request):
    return render(request, 'core/arena.html')

import requests
import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

import requests
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json

@csrf_exempt
def run_code(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            code = data.get('code', '')
            language = data.get('language', 'python')
            input_data = data.get('input', '')

            # Map your frontend languages to Piston API versions
            # Piston supports: python, java, c++, javascript, etc.
            language_map = {
                'python': {'language': 'python', 'version': '3.10.0'},
                'java': {'language': 'java', 'version': '15.0.2'},
                'cpp': {'language': 'c++', 'version': '10.2.0'},
                'c': {'language': 'c', 'version': '10.2.0'},  # <--- ADDED C HERE
                'javascript': {'language': 'javascript', 'version': '18.15.0'},
            }
            
            config = language_map.get(language, language_map['python'])

            # Prepare payload for Piston API
            payload = {
                "language": config['language'],
                "version": config['version'],
                "files": [
                    {
                        "content": code
                    }
                ],
                "stdin": input_data
            }

            # Send to Piston (Free Public API)
            response = requests.post('https://emkc.org/api/v2/piston/execute', json=payload)
            result = response.json()
            
            output = result.get('run', {}).get('output', '')
            return JsonResponse({'output': output})

        except Exception as e:
            return JsonResponse({'output': f"Error: {str(e)}"}, status=500)
    
    return JsonResponse({'error': 'Invalid request'}, status=400)

from curriculum.models import Question # Import the model
@login_required(login_url='login')
def quiz_view(request, slug):
    subject = get_object_or_404(Subject, slug=slug)
    questions = Question.objects.filter(subject=subject)
    
    if request.method == 'POST':
        score = 0
        total = questions.count()
        
        for q in questions:
            selected_option_id = request.POST.get(str(q.id))
            if selected_option_id:
                choice = q.choices.filter(id=selected_option_id, is_correct=True)
                if choice.exists():
                    score += 1
        
        # --- NEW: SAVE TO DATABASE ---
        submission = QuizSubmission.objects.create(
            user=request.user,
            subject=subject,
            score=score,
            total_questions=total
        )
        # -----------------------------
        
        return render(request, 'core/quiz_result.html', {
            'subject': subject,
            'score': score,
            'total': total,
            'percentage': submission.percentage # Use the model property
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
    Corrected Placement Stats and Expanded Partner List (Sorted Alphabetically).
    """
    # Define the list first
    partners_list = [
        "IARE, Hyderabad", "SR University, Warangal", "MRECW, Hyderabad",
        "ACEEC, Ghatkesar", "Pragati Engineering College, Kakinada",
        "Sreedevi Women's Engg. College", "SRIT, Anantapur",
        "KITS, Guntur", "KITS, Warangal", "KITS, Huzurabad",
        "KIET, Kakinada", "Vemu IT, Pakala",
        "Swaranandra Engg. College", "AITS, Tirupati",
        "PBR VITS, Kavali", "NEC, Narasaraopet",
        "MEC, Guntur",
        "AVNIET, Hyderabad",
        "KGRCET, Hyderabad",
        "KPRIT, Hyderabad",
        "Sreerama Engg. College, Tirupati",
        "Pydah College of Engineering, Kakinada"
    ]

    context = {
        # This one line sorts them A-Z automatically
        'partners': sorted(partners_list),
        
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
                'college': 'KITS Group, Guntur'
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
                'college': 'ACE Engineering College (ACEEC)'
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
    topics = course.topics.all().order_by('order')
    
    # CHECK IF ENROLLED (Crucial for the Button Logic)
    is_enrolled = False
    if request.user.is_authenticated:
        is_enrolled = Enrollment.objects.filter(user=request.user, subject=course).exists()
    
    context = {
        'course': course,
        'topics': topics,
        'is_enrolled': is_enrolled # This passes True/False to the template
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


from django.http import JsonResponse
from curriculum.models import TopicProgress, Topic # Ensure TopicProgress is imported

@login_required(login_url='login')
def toggle_topic_completion(request, topic_id):
    if request.method == "POST":
        topic = get_object_or_404(Topic, id=topic_id)
        
        # Get or Create the progress record
        progress, created = TopicProgress.objects.get_or_create(user=request.user, topic=topic)
        
        # Toggle status
        progress.is_completed = not progress.is_completed
        progress.save()
        
        return JsonResponse({
            'status': 'success', 
            'is_completed': progress.is_completed
        })
    
    return JsonResponse({'status': 'error'}, status=400)


from django.contrib import messages
from .forms import UserUpdateForm, ProfileUpdateForm # Import the forms

@login_required(login_url='login')
def profile(request):
    if request.method == 'POST':
        u_form = UserUpdateForm(request.POST, instance=request.user)
        p_form = ProfileUpdateForm(request.POST, instance=request.user.profile)

        if u_form.is_valid() and p_form.is_valid():
            u_form.save()
            p_form.save()
            messages.success(request, 'Your profile has been updated!')
            return redirect('profile') # Redirect back to profile page

    else:
        u_form = UserUpdateForm(instance=request.user)
        p_form = ProfileUpdateForm(instance=request.user.profile)

    context = {
        'u_form': u_form,
        'p_form': p_form
    }
    return render(request, 'core/profile.html', context)

import requests
import uuid
import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from curriculum.models import Subject, Enrollment, Order

# --- HELPER: Generate OAuth Token ---
def get_phonepe_token():
    """
    Generates the O-Bearer Token required for V2 API calls.
    """
    url = f"{settings.PHONEPE_BASE_URL}/v1/oauth/token"
    
    payload = {
        "client_id": settings.PHONEPE_CLIENT_ID,
        "client_secret": settings.PHONEPE_CLIENT_SECRET,
        "grant_type": "client_credentials",
        "client_version": settings.PHONEPE_CLIENT_VERSION
    }
    
    try:
        response = requests.post(url, data=payload)
        data = response.json()
        
        if response.status_code == 200 and "access_token" in data:
            return data["access_token"]
        else:
            print(f"Token Error: {data}")
            return None
    except Exception as e:
        print(f"Token Connection Error: {e}")
        return None

# --- PAYMENT VIEWS ---
import uuid
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required

# Models
from curriculum.models import Subject, Enrollment, Order

# --- PHONEPE SDK IMPORTS ---
from core.phonepe import get_phonepe_client
from phonepe.sdk.pg.payments.v2.models.request.standard_checkout_pay_request import StandardCheckoutPayRequest
from phonepe.sdk.pg.common.models.request.meta_info import MetaInfo

# --- VIEWS ---
# In core/views.py
@login_required(login_url='login')
def initiate_payment(request, subject_slug):
    subject = get_object_or_404(Subject, slug=subject_slug)
    
    # 1. Generate Order ID
    merchant_order_id = str(uuid.uuid4())
    
    # 2. Save Pending Order
    Order.objects.create(
        user=request.user,
        subject=subject,
        order_id=merchant_order_id,
        amount=subject.price,
        status='PENDING'
    )
    
    try:
        client = get_phonepe_client()
        amount_in_paise = int(float(subject.price) * 100)
        
        # --- FIX: Embed Order ID in the URL ---
        # This creates: https://yourdomain.com/payment/callback/ORDER_ID_HERE/
        callback_path = f'/payment/callback/{merchant_order_id}/'
        redirect_url = request.build_absolute_uri(callback_path)
        
        meta_info = MetaInfo(udf1="CoursePayment", udf2=str(subject.id))
        
        pay_request = StandardCheckoutPayRequest.build_request(
            merchant_order_id=merchant_order_id,
            amount=amount_in_paise,
            redirect_url=redirect_url,
            meta_info=meta_info,
            message=f"Payment for {subject.name}"
        )
        
        standard_pay_response = client.pay(pay_request)
        
        if standard_pay_response.redirect_url:
            return redirect(standard_pay_response.redirect_url)
        else:
            messages.error(request, "Error: No redirect URL received.")
            return redirect('course_landing', slug=subject.slug)

    except Exception as e:
        print(f"SDK Payment Init Error: {e}")
        messages.error(request, "Could not initiate payment.")
        return redirect('course_landing', slug=subject.slug)

@csrf_exempt
def payment_callback(request, order_id):
    """
    Handles the redirect from PhonePe.
    Now receives 'order_id' directly from the URL for 100% reliability.
    """
    try:
        print(f"\nCallback received for Order: {order_id}")

        # 1. Get SDK Client
        client = get_phonepe_client()
        
        # 2. Check Status Immediately
        # We don't wait for POST data. We actively ask PhonePe "What happened?"
        status_response = client.get_order_status(order_id)
        
        print(f"Callback Status Check: {status_response.state}")

        # 3. Update Database
        order = get_object_or_404(Order, order_id=order_id)
        
        # Prevent duplicate enrollment if user refreshes page
        if order.status == 'SUCCESS':
            return redirect('dashboard')

        if status_response.state == "COMPLETED":
            order.status = 'SUCCESS'
            
            # Save Transaction ID safely
            if status_response.payment_details:
                last_attempt = status_response.payment_details[-1]
                if hasattr(last_attempt, 'transaction_id'):
                    order.transaction_id = last_attempt.transaction_id
                elif hasattr(last_attempt, 'payment_id'):
                    order.transaction_id = last_attempt.payment_id
            
            order.save()
            
            # Enroll User
            Enrollment.objects.get_or_create(user=order.user, subject=order.subject)
            
            messages.success(request, f"Payment Successful! Enrolled in {order.subject.name}.")
            return redirect('dashboard')
        
        elif status_response.state == "FAILED":
            order.status = 'FAILED'
            order.save()
            messages.error(request, "Payment Failed.")
            return redirect('course_landing', slug=order.subject.slug)
        
        else:
            # Still Pending?
            messages.warning(request, "Payment is processing. Check status in dashboard.")
            return redirect('dashboard')

    except Exception as e:
        print(f"Callback Error: {e}")
        messages.error(request, "Verification Error.")
        return redirect('dashboard')



# In core/views.py
@login_required(login_url='login')
def check_payment_status(request, order_id):
    """
    Manually checks the status of a specific order with PhonePe.
    """
    try:
        # 1. Get the Order from DB
        order = get_object_or_404(Order, order_id=order_id, user=request.user)
        
        # If already successful, just redirect
        if order.status == 'SUCCESS':
            messages.info(request, "This order is already completed.")
            return redirect('dashboard')

        # 2. Ask PhonePe for Status
        client = get_phonepe_client()
        status_response = client.get_order_status(order.order_id)
        
        print(f"Manual Check Status: {status_response.state}")

        # 3. Update Status
        if status_response.state == "COMPLETED":
            order.status = 'SUCCESS'
            
            # --- FIX FOR THE ERROR ---
            # payment_details is a LIST of attempts. We take the last one.
            if status_response.payment_details:
                # Get the last payment attempt (the successful one)
                last_attempt = status_response.payment_details[-1]
                
                # Extract ID safely
                if hasattr(last_attempt, 'transaction_id'):
                    order.transaction_id = last_attempt.transaction_id
                elif hasattr(last_attempt, 'payment_id'):
                    order.transaction_id = last_attempt.payment_id
            
            order.save()
            
            # 4. Enroll User
            Enrollment.objects.get_or_create(user=order.user, subject=order.subject)
            
            messages.success(request, f"Payment Verified! You are now enrolled in {order.subject.name}.")
            return redirect('dashboard')
            
        elif status_response.state == "FAILED":
            order.status = 'FAILED'
            order.save()
            messages.error(request, "Payment Failed.")
        else:
            messages.warning(request, f"Payment is still {status_response.state}. Please try again in a moment.")

    except Exception as e:
        print(f"Manual Check Error: {e}")
        messages.error(request, "Error checking payment status.")

    return redirect('dashboard')


# In core/views.py
from curriculum.models import Job, JobApplication

def careers(request):
    """
    New separate page for Job Openings.
    """
    jobs = Job.objects.filter(is_active=True).order_by('-posted_at')
    
    applied_job_ids = []
    if request.user.is_authenticated:
        applied_job_ids = JobApplication.objects.filter(user=request.user).values_list('job_id', flat=True)

    context = {
        'jobs': jobs,
        'applied_job_ids': applied_job_ids
    }
    return render(request, 'core/careers.html', context)

from django.http import JsonResponse
import json

@login_required(login_url='login')
def track_application(request, job_id):
    """
    Called via AJAX when user clicks 'Mark as Applied'.
    """
    if request.method == "POST":
        job = get_object_or_404(Job, id=job_id)
        
        # Create the record
        JobApplication.objects.get_or_create(user=request.user, job=job)
        
        return JsonResponse({'status': 'success', 'message': 'Application recorded'})
    
    return JsonResponse({'status': 'error'}, status=400)