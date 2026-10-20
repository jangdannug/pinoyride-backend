
from celery import shared_task

# Legacy models from the project template. They no longer exist in api.models, and the hard import
# made this whole module (and so the remind-advance-bookings Celery task) fail to load.
try:
    from api.models import Beneficiary, Batch
except ImportError:  # pragma: no cover
    Beneficiary = Batch = None

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


@shared_task
def flag_at_risk_advance():
    """Every minute: flag advance bookings the rider will be late for and return them to the pool
    AT_RISK_REASSIGN_MINUTES before pickup (overlap plan section 5). No pushes."""
    from api.services.booking_window_service import flag_at_risk_and_reassign
    flagged, returned = flag_at_risk_and_reassign()
    return f"At-risk flagged: {flagged}, returned to pool: {returned}"
