# apps/core/management/commands/create_tenant.py
from django.core.management.base import BaseCommand
from core.models import Tenant, Domain

class Command(BaseCommand):
    help = 'Creates a new tenant with domain'

    def add_arguments(self, parser):
        parser.add_argument('name', type=str)
        parser.add_argument('schema_name', type=str)
        parser.add_argument('domain', type=str)

    def handle(self, *args, **options):
        name = options['name']
        schema_name = options['schema_name']
        domain = options['domain']
        tenant = Tenant.objects.create(name=name, schema_name=schema_name)
        Domain.objects.create(tenant=tenant, domain=domain)
        self.stdout.write(self.style.SUCCESS(f'Tenant {name} created with schema {schema_name}'))