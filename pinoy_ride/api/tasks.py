
from api.models import Beneficiary, Batch
from celery import shared_task

from django.conf import settings
from api.utils.mailer import EmailSender
from api.utils.sms_sender import SMSSender

from django.forms.models import model_to_dict




# @shared_task
# def count_programs():
#     count = Program.objects.count()
#     return f"Number of Programs: {count}"


@shared_task
def count_beneficiaries():
    count = Beneficiary.objects.count()
    
    return f"Number of Beneficiaries: {count}"

from celery import shared_task

@shared_task
def send_notifications(batch_id, beneficiary_ids, notification_type=None):
    """
    Sends notifications asynchronously to beneficiaries via email.
    """

    if notification_type is None:
        pass
    
    mailer = EmailSender()
    sms_sender = SMSSender()
    batch = Batch.objects.select_related("program").get(id=batch_id)
    beneficiaries = Beneficiary.objects.filter(id__in=beneficiary_ids).prefetch_related(
        "authorized_representatives",  
        "contact_numbers" 
    )
    
    print(f"Sending notifications for batch {batch.name} under program {batch.program.name} to {len(beneficiaries)} beneficiaries.")

    for beneficiary in beneficiaries:
        
        if notification_type in ["email", "both"]:
            print(f"Attempting to send email to {beneficiary.email}")
            mailer.send_batch_assignment_email(batch=batch, beneficiary=beneficiary)
            print(f"Email function executed for {beneficiary.email}")
            print(f"Email sent to {beneficiary.first_name} ({beneficiary.email})")

            
        if notification_type in ["sms", "both"]:
            sms_sender.send_batch_assignment_sms(batch=batch, beneficiary=beneficiary)
        
       

    return f"Notifications sent for batch {batch}"





@shared_task
def remind_advance():
    """Every minute: remind assigned riders ADVANCE_REMINDER_MINUTES before an advance pickup (sent once)."""
    from api.services.advance_booking_service import AdvanceBookingService
    return f"Advance reminders sent: {AdvanceBookingService.send_due_reminders()}"
