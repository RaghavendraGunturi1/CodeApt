from django.contrib import admin
from django.urls import path
from django.shortcuts import render, redirect
from django.contrib import messages
from django import forms
import pandas as pd
from datetime import date, timedelta
from .models import DailyQuestion, TestCase, UserStreak, DailySubmission

class ExcelUploadForm(forms.Form):
    file = forms.FileField()

@admin.register(DailyQuestion)
class DailyQuestionAdmin(admin.ModelAdmin):
    list_display = ('title', 'question_type', 'release_date')
    change_list_template = "admin/challenges_changelist.html"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('upload-excel/', self.upload_excel, name='upload_challenges_excel'),
        ]
        return custom_urls + urls

    def upload_excel(self, request):
        if request.method == "POST":
            excel_file = request.FILES["file"]
            try:
                # 1. Read Excel and handle empty cells (NaN)
                df = pd.read_excel(excel_file)
                df = df.fillna('')  # Replaces NaN with empty strings
                
                # 2. Determine Start Date (Tomorrow or after the last existing question)
                last_question = DailyQuestion.objects.order_by('-release_date').first()
                if last_question:
                    start_date = last_question.release_date + timedelta(days=1)
                else:
                    start_date = date.today()

                count = 0
                for index, row in df.iterrows():
                    # --- DATA CLEANING SECTION (CRITICAL FIXES) ---
                    
                    # Get the type and strip whitespace
                    q_type = str(row['type']).strip().upper() 
                    
                    # Handle Correct Option safely
                    raw_correct = str(row.get('correct_option', ''))
                    clean_correct = raw_correct.strip() # Removes " " around "A"
                    
                    # Logic: If CODE, option MUST be None. If MCQ, truncate to max 10 chars.
                    if q_type == 'CODE':
                        clean_correct = None
                    else:
                        if len(clean_correct) > 10:
                            clean_correct = clean_correct[:10]
                        if clean_correct == '':
                            clean_correct = None

                    # Calculate Date
                    release_date = start_date + timedelta(days=count)

                    # --- CREATE QUESTION ---
                    q = DailyQuestion.objects.create(
                        question_type=q_type,
                        title=str(row['title']).strip(),
                        description=str(row['description']).strip(),
                        release_date=release_date,
                        
                        # MCQ Fields (Safe string conversion)
                        option_a=str(row.get('option_a', '')).strip(),
                        option_b=str(row.get('option_b', '')).strip(),
                        option_c=str(row.get('option_c', '')).strip(),
                        option_d=str(row.get('option_d', '')).strip(),
                        
                        correct_option=clean_correct  # Uses the cleaned variable
                    )

                    # --- CREATE TEST CASES (Only for CODE) ---
                    if q_type == 'CODE':
                        for i in range(1, 6): # Loop input1/output1 to input5/output5
                            inp_key = f'input{i}'
                            out_key = f'output{i}'
                            
                            # Check if columns exist in Excel and have data
                            if inp_key in row and out_key in row:
                                val_in = str(row[inp_key]).strip()
                                val_out = str(row[out_key]).strip()
                                
                                if val_in and val_out: # Only add if data is present
                                    TestCase.objects.create(
                                        question=q,
                                        input_data=val_in,
                                        expected_output=val_out
                                    )
                    
                    count += 1
                
                messages.success(request, f"Successfully scheduled {count} questions starting from {start_date}.")
                return redirect("..")

            except Exception as e:
                # Print error to console for debugging if needed
                print(f"Excel Upload Error: {e}")
                messages.error(request, f"Error processing file: {e}")

        form = ExcelUploadForm()
        return render(request, "admin/excel_upload.html", {"form": form})

admin.site.register(UserStreak)
admin.site.register(DailySubmission)
admin.site.register(TestCase)