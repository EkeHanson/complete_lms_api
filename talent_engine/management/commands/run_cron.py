# talent_engine/management/commands/run_cron.py
from django.core.management.base import BaseCommand
from talent_engine.cron import close_expired_requisitions

class Command(BaseCommand):
    help = 'Manually run the close_expired_requisitions job'

    def handle(self, *args, **kwargs):
        self.stdout.write("Running close_expired_requisitions...")
        try:
            close_expired_requisitions()
            self.stdout.write(self.style.SUCCESS("Cron job completed successfully."))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error: {str(e)}"))