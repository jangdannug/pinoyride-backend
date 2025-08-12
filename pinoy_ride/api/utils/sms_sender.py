from twilio.rest import Client
from django.conf import settings

class SMSSender:
    """
    A reusable SMS sender class for sending various types of SMS notifications.
    """

    def __init__(self):
        self.client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        self.from_number = settings.TWILIO_PHONE_NUMBER

    def send_sms(self, recipient_number, message):
        """
        Sends an SMS via Twilio.

        :param recipient_number: Recipient's phone number
        :param message: The SMS content
        :return: Boolean (True if sent successfully, False if failed)
        """
        try:
            if not recipient_number:
                raise ValueError("Recipient number is required.")

            message = self.client.messages.create(
                body=message,
                from_=self.from_number,
                to=recipient_number
            )

            return True
        except Exception as e:
            return False

    def send_batch_assignment_sms(self, batch, beneficiary):
        """
        Sends an SMS notification to a beneficiary about their batch assignment.
        """
        first_rep = beneficiary.authorized_representatives.first()
        latest_contact = beneficiary.contact_numbers.order_by("-id").first()

        message = f"Hello {beneficiary.first_name}, you have been assigned to batch {batch.name} at {batch.venue}."


        if first_rep and first_rep.email:
            self.send_sms(first_rep.contact_number, message)


        if latest_contact:
            return self.send_sms(latest_contact.contact_number, message)

        return False
