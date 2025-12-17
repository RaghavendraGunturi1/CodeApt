import pandas as pd
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from .models import Subject, Topic, Module # <--- Import Module
from .forms import BulkUploadForm

@login_required
@user_passes_test(lambda u: u.is_staff)
def bulk_upload_topics(request, slug):
    subject = get_object_or_404(Subject, slug=slug)
    
    if request.method == 'POST':
        form = BulkUploadForm(request.POST, request.FILES)
        if form.is_valid():
            file = request.FILES['excel_file']
            
            try:
                df = pd.read_excel(file)
                
                # Standardize column names to lowercase just in case
                df.columns = df.columns.str.lower()
                
                count = 0
                for index, row in df.iterrows():
                    # 1. Handle Module (Sub-topic)
                    module_name = row.get('module')
                    topic_module = None
                    
                    if pd.notna(module_name) and str(module_name).strip():
                        # Get or Create the Module automatically
                        topic_module, created = Module.objects.get_or_create(
                            subject=subject,
                            name=str(module_name).strip()
                        )

                    # 2. Create Topic
                    Topic.objects.create(
                        subject=subject,
                        module=topic_module, # Assign to the module
                        order=row.get('order', count + 1),
                        name=row.get('name', f"Topic {count + 1}"),
                        topic_type=row.get('type', 'text'),
                        content=row.get('content', ''),
                        video_id=row.get('video_id', ''),
                        duration=row.get('duration', '')
                    )
                    count += 1
                
                messages.success(request, f"Successfully uploaded {count} topics with modules!")
                return redirect('course_detail', slug=subject.slug)
                
            except Exception as e:
                messages.error(request, f"Error processing file: {str(e)}")
                return redirect('bulk_upload_topics', slug=subject.slug)
    else:
        form = BulkUploadForm()

    return render(request, 'curriculum/bulk_upload.html', {'form': form, 'subject': subject})