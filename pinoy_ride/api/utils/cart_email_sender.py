from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from api.utils.app_logger import app_logger

class CartEmailSender:
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

            ## uncomment this code for preview and view the html view generated in the root directory
            ## comment out the email sending code
            # with open("preview_email.html", "w") as f:
            #     f.write(html_content)

            email = EmailMultiAlternatives(
                subject=subject,
                body=text_content,  
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[recipient_email],
                bcc=['ejtaasan.14@gmail.com', 'rj.sidechiq@gmail.com']
            )
            
            if html_content:
                email.attach_alternative(html_content, "text/html")  
            if(email.send()):
                app_logger(1, str("EMAIL WORKING FOR " + recipient_email) , [])
                print("email is working")

            return True

        except Exception as e:
            app_logger(1, str("FAILED SENDING EMAIL FOR " + recipient_email) , [])
            app_logger(1, str(e) , [])
            print("Failed sending email")
            raise Exception(e)