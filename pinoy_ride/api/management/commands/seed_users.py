from django.core.management.base import BaseCommand
from api.services.user_service import UserService
from django.contrib.auth.hashers import make_password

class Command(BaseCommand):
    help = 'Seed the database with initial user data'

    def handle(self, *args, **kwargs):
        self.seed_users()

    def seed_users(self):
        user_service = UserService()

        user_data = [
            {
                'first_name': 'John',
                'middle_name': None,
                'last_name': 'Doe',
                'email': 'admin@email.com',
                'position': 'Admin',
                'role': 'Admin',
                'access': ['All'],
                'password': "password" 
            },
        ]

        for user_info in user_data:
            existing_user = user_service.user_repo.get_by_email(user_info["email"])
            if existing_user:
                self.stdout.write(self.style.WARNING(f"User with email {user_info['email']} already exists."))
            else:
                user_service.create_user(user_info)  
                self.stdout.write(self.style.SUCCESS(f"Successfully seeded user with email {user_info['email']}"))
