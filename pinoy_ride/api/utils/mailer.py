from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings

class EmailSender:
    """
    A reusable email sender class for sending various types of emails.
    """

    def send_email(self, recipient_email, subject, template_name=None, context=None, plain_text=None):
        """
        Sends an email using Django's EmailMultiAlternatives.
        
        :param recipient_email: Recipient's email address
        :param subject: Email subject
        :param template_name: The name of the HTML template (inside `templates/emails/`)
        :param context: Data to be passed into the template
        :param plain_text: Optional plaintext content (if no HTML template is provided)
        :return: Boolean (True if sent successfully, False if failed)
        """
        try:
            if not (template_name or plain_text):
                raise ValueError("Either an HTML template or plain text content must be provided.")

            html_content = render_to_string(f"emails/{template_name}.html", context) if template_name else None
            text_content = strip_tags(html_content) if html_content else plain_text  

            email = EmailMultiAlternatives(
                subject=subject,
                body=text_content,  
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[recipient_email],
            )
            
            if html_content:
                email.attach_alternative(html_content, "text/html")  
            if(email.send()):
                print("email is working")
            return True
        except Exception as e:
            return False

    def send_batch_assignment_email(self, batch, beneficiary):
        """
        Sends an email notifying a beneficiary about their batch assignment.
        """
        
        subject = f"Assignment to {batch.name}"
        
        first_rep = beneficiary.authorized_representatives.first() 
        
        context = {
            "beneficiary": beneficiary,
            "batch": batch,
            "rep": {
                "first_name": first_rep.first_name if first_rep else None,
                "last_name": first_rep.last_name if first_rep else None,
                "email": first_rep.email if first_rep else None,
            } if first_rep else None, 
        }
        
        if first_rep:
            self.send_email(
                recipient_email=first_rep.email,
                subject=subject,
                template_name="batch_notification",
                context=context
            )
        
        
        return self.send_email(
            recipient_email=beneficiary.email,
            subject=subject,
            template_name="batch_notification",
            context=context
        )

    