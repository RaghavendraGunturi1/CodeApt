from curriculum.models import Topic
from assessments.models import Exam, StudentExamAttempt
from assessments.views import calculate_final_score

def recalculate_tcs():
    print("Recalculating TCS Test 1 Scores...")
    # Find the topic named exactly 'TCS Test 1' (case insensitive match if needed)
    topics = Topic.objects.filter(name__icontains='TCS Test 1')
    if not topics.exists():
        print("Could not find a topic matching 'TCS Test 1'.")
        # List topics just to be sure
        all_topics = Topic.objects.values_list('name', flat=True)
        print("Available topics: ", list(all_topics)[:20])
        return

    topic = topics.first()
    print(f"Found Topic: {topic.name}")
    
    try:
        exam = topic.exam
    except Exam.DoesNotExist:
        print("This topic does not have an associated Exam.")
        return
        
    attempts = StudentExamAttempt.objects.filter(exam=exam, completed_at__isnull=False)
    count = attempts.count()
    print(f"Found {count} completed attempts for Exam: {exam.topic.name}")
    
    updated = 0
    for att in attempts:
        old_score = att.score
        
        # Recalculate using the function from views
        calculate_final_score(att)
        
        # Refresh from db
        att.refresh_from_db()
        new_score = att.score
        
        if old_score != new_score:
            print(f"Attempt ID {att.id} ({att.user.username if att.user else att.roll_number}): Score changed from {old_score} -> {new_score}")
            updated += 1
            
    print(f"Finished. Recalculated {count} attempts. {updated} scores were updated.")

recalculate_tcs()
