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

class TestCaseInline(admin.TabularInline):
    model = TestCase
    extra = 1           # Shows 1 empty slot for a new test case
    min_num = 0         # Allows saving without test cases (important for MCQs)
    can_delete = True   # Allows deleting test cases directly here
    fields = ('input_data', 'expected_output') # Only show relevant fields

@admin.register(DailyQuestion)
class DailyQuestionAdmin(admin.ModelAdmin):
    list_display = ('title', 'question_type', 'release_date')
    change_list_template = "admin/challenges_changelist.html"
    inlines = [TestCaseInline]

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
                # 1. Read Excel
                df = pd.read_excel(excel_file)
                df = df.fillna('')
                
                # 2. Determine Start Date
                last_question = DailyQuestion.objects.order_by('-release_date').first()
                if last_question:
                    start_date = last_question.release_date + timedelta(days=1)
                else:
                    start_date = date.today()

                count = 0
                for index, row in df.iterrows():
                    # --- DATA CLEANING SECTION ---
                    
                    q_type = str(row['type']).strip().upper() 
                    
                    # CLEAN TITLES & DESCRIPTIONS (Remove _x000D_)
                    title_clean = str(row['title']).replace('_x000D_', '').strip()
                    desc_clean = str(row['description']).replace('_x000D_', '').strip()

                    # Handle Correct Option
                    raw_correct = str(row.get('correct_option', ''))
                    clean_correct = raw_correct.strip()
                    
                    if q_type == 'CODE':
                        clean_correct = None
                    else:
                        if len(clean_correct) > 10:
                            clean_correct = clean_correct[:10]
                        if clean_correct == '':
                            clean_correct = None

                    # --- CLEAN STARTER CODE (The Fix) ---
                    s_code = str(row.get('starter_code', ''))
                    # Remove the Excel artifact and extra spaces
                    s_code = s_code.replace('_x000D_', '').strip()
                    
                    if s_code.lower() == 'nan' or not s_code:
                        s_code = None

                    # Calculate Date
                    release_date = start_date + timedelta(days=count)

                    # --- CREATE QUESTION ---
                    q = DailyQuestion.objects.create(
                        question_type=q_type,
                        title=title_clean,       # Use cleaned title
                        description=desc_clean,  # Use cleaned description
                        release_date=release_date,
                        
                        option_a=str(row.get('option_a', '')).strip(),
                        option_b=str(row.get('option_b', '')).strip(),
                        option_c=str(row.get('option_c', '')).strip(),
                        option_d=str(row.get('option_d', '')).strip(),
                        correct_option=clean_correct,
                        
                        starter_code=s_code      # Use cleaned starter code
                    )

                    # --- CREATE TEST CASES ---
                    if q_type == 'CODE':
                        for i in range(1, 6): 
                            inp_key = f'input{i}'
                            out_key = f'output{i}'
                            
                            if inp_key in row and out_key in row:
                                val_in = str(row[inp_key]).replace('_x000D_', '').strip()  # Clean inputs too
                                val_out = str(row[out_key]).replace('_x000D_', '').strip() # Clean outputs too
                                
                                if val_in and val_out:
                                    TestCase.objects.create(
                                        question=q,
                                        input_data=val_in,
                                        expected_output=val_out
                                    )
                    
                    count += 1
                
                messages.success(request, f"Successfully scheduled {count} questions.")
                return redirect("..")

            except Exception as e:
                print(f"Excel Upload Error: {e}")
                messages.error(request, f"Error processing file: {e}")

        form = ExcelUploadForm()
        return render(request, "admin/excel_upload.html", {"form": form})

admin.site.register(UserStreak)
admin.site.register(DailySubmission)
admin.site.register(TestCase)