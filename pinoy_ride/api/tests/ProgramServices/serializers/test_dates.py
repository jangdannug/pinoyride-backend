from django.test import TestCase
from api.serializers import ProgramSerializer

class ProgramSerializerDatesTestCase(TestCase):
    
    def setUp(self):
        """Set up valid and invalid test data before each test."""
        self.valid_program = {
            "name": "Valid Training Program",
            "start_date": "2025-02-15",
            "end_date": "2025-06-30",
            "batches": [
                {
                    "name": "Batch 1",
                    "start_date": "2025-03-01",  
                    "end_date": "2025-05-30",  
                    "venue": "Main Hall",
                    "category": "Technology",
                    "start_time": "09:00:00", 
                    "end_time": "12:00:00"
                }
            ]
        }

        self.invalid_program_end_before_start = {
            "name": "Invalid Training",
            "start_date": "2025-07-01",
            "end_date": "2025-06-01",
        }

        self.invalid_batch_date = {
            "name": "Batch 2",
            "start_date": "2025-04-10",
            "end_date": "2025-04-05",
            "start_time": "09:00:00", 
            "end_time": "12:00:00",
            "venue": "Main Hall",
            "category": "Technology"
        }

        self.outside_program_batch = {
            "name": "Batch 3",
            "start_date": "2025-01-10",  
            "end_date": "2025-07-10",  
            "venue": "Main Hall",
            "category": "Technology"
        }

        self.invalid_program_with_batch_dates = {
            "name": "Invalid Program with Batch Errors",
            "start_date": "2025-02-15",
            "end_date": "2025-06-30",
            "batches": [self.invalid_batch_date]  
        }

        self.invalid_program_with_outside_batch_dates = {
            "name": "Invalid Program with Outside Batch Dates",
            "start_date": "2025-02-15",
            "end_date": "2025-06-30",
            "batches": [self.outside_program_batch]  
        }

    def test_valid_program(self):
        """✅ Test that a valid program passes serializer validation."""
        serializer = ProgramSerializer(data=self.valid_program)
        is_valid = serializer.is_valid()
        
        self.assertTrue(is_valid, "Valid program should pass validation.")

    def test_invalid_program_end_date_before_start(self):
        """✅ Test that a program with an invalid end date fails validation."""
        serializer = ProgramSerializer(data=self.invalid_program_end_before_start)
        is_valid = serializer.is_valid()
        self.assertFalse(is_valid, "Invalid program should fail validation.")
        self.assertIn("program", serializer.errors)

    def test_invalid_batch_end_date_before_start(self):
        """✅ Test that a batch with end_date before start_date fails validation."""
        serializer = ProgramSerializer(data=self.invalid_program_with_batch_dates)
        is_valid = serializer.is_valid()
        self.assertFalse(is_valid, "Invalid batch should fail validation.")
        self.assertIn("batches", serializer.errors)

    def test_invalid_batch_outside_program_dates(self):
        """✅ Test that a batch with dates outside the program range fails validation."""
        serializer = ProgramSerializer(data=self.invalid_program_with_outside_batch_dates)
        is_valid = serializer.is_valid()
        self.assertFalse(is_valid, "Batch with dates outside the program should fail validation.")
        self.assertIn("batches", serializer.errors)
