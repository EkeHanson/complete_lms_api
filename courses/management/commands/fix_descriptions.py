#RUN THIS COMMAND WITH : python manage.py fix_descriptions --schema SCHEMA_NAME
from django.core.management.base import BaseCommand
from django_tenants.utils import schema_context, get_tenant_model
import json
from courses.models import Course

class Command(BaseCommand):
    help = 'Fix invalid Draft.js descriptions in Course model for all tenants'

    def add_arguments(self, parser):
        parser.add_argument('--schema', type=str, help='Run for a specific tenant schema (optional)')

    def handle(self, *args, **options):
        TenantModel = get_tenant_model()
        empty_description = json.dumps({
            "blocks": [{"key": "empty", "text": "", "type": "unstyled", "depth": 0, "inlineStyleRanges": [], "entityRanges": [], "data": {}}],
            "entityMap": {}
        })

        # Get specific tenant or all tenants
        schema_name = options.get('schema')
        if schema_name:
            tenants = TenantModel.objects.filter(schema_name=schema_name)
        else:
            tenants = TenantModel.objects.all()

        for tenant in tenants:
            with schema_context(tenant.schema_name):
                self.stdout.write(self.style.NOTICE(f'Processing tenant: {tenant.schema_name}'))
                courses = Course.objects.all()
                for course in courses:
                    try:
                        if not course.description or course.description.strip() == '':
                            course.description = empty_description
                            course.save()
                            self.stdout.write(self.style.SUCCESS(f'Fixed course {course.id} in {tenant.schema_name}: Set empty description'))
                            continue

                        # Attempt to parse JSON
                        try:
                            parsed = json.loads(course.description)
                        except json.JSONDecodeError:
                            self.stdout.write(self.style.WARNING(f'Course {course.id} in {tenant.schema_name}: Invalid JSON in description'))
                            course.description = empty_description
                            course.save()
                            self.stdout.write(self.style.SUCCESS(f'Fixed course {course.id} in {tenant.schema_name}: Replaced invalid JSON with empty description'))
                            continue

                        # Check if parsed is a dictionary and has valid Draft.js structure
                        if not isinstance(parsed, dict):
                            self.stdout.write(self.style.WARNING(f'Course {course.id} in {tenant.schema_name}: Description is not a dictionary'))
                            course.description = empty_description
                            course.save()
                            self.stdout.write(self.style.SUCCESS(f'Fixed course {course.id} in {tenant.schema_name}: Set valid empty description'))
                            continue

                        if not parsed.get('blocks') or not isinstance(parsed.get('blocks'), list) or not parsed.get('entityMap'):
                            self.stdout.write(self.style.WARNING(f'Course {course.id} in {tenant.schema_name}: Invalid Draft.js structure'))
                            course.description = empty_description
                            course.save()
                            self.stdout.write(self.style.SUCCESS(f'Fixed course {course.id} in {tenant.schema_name}: Set valid empty description'))
                            continue

                        # Valid Draft.js JSON, no action needed
                        self.stdout.write(self.style.SUCCESS(f'Course {course.id} in {tenant.schema_name}: Description is valid'))
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f'Error processing course {course.id} in {tenant.schema_name}: {str(e)}'))