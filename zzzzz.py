# python manage.py makemigrations token_blacklist users courses forum groups messaging subscriptions

# python manage.py makemigrations token_blacklist users, courses, courses, forum, groups, messaging, subscriptions
# python manage.py migrate_schemas --shared
# python manage.py migrate_schemas


# python manage.py makemigrations token_blacklist users, courses, forum, messaging
# python manage.py migrate_schemas --shared
# python manage.py migrate_schemas



#python manage.py shell
from core.models import Tenant, Domain
if not Tenant.objects.filter(schema_name='public').exists():
    tenant = Tenant.objects.create(
        name='public',
        schema_name='public'
    )
    tenant.auto_create_schema = False
    tenant.save()
    Domain.objects.create(tenant=tenant, domain='127.0.0.1', is_primary=True)
    Domain.objects.create(tenant=tenant, domain='localhost', is_primary=False)


from core.models import Tenant, Domain
if not Tenant.objects.filter(schema_name='proliance').exists():
    tenant = Tenant.objects.create(
        name='proliance',
        schema_name='proliance'
    )
    tenant.auto_create_schema = False
    tenant.save()
    Domain.objects.create(tenant=tenant, domain='prolianceltd.com', is_primary=True)


    Domain.objects.create(tenant=tenant, domain='localhost', is_primary=False)

from core.models import Tenant, Domain
if not Tenant.objects.filter(schema_name='render').exists():
    tenant = Tenant.objects.create(
        name='render',
        schema_name='render'
    )
    tenant.auto_create_schema = False
    tenant.save()
    Domain.objects.create(tenant=tenant, domain='complete-lms-api-jnwb.onrender.com', is_primary=True)
   



#CREATE TENANT ADMIN USER 
# python manage.py shell
from core.models import Tenant
from users.models import CustomUser
from django_tenants.utils import tenant_context
tenant = Tenant.objects.get(schema_name='proliance')
with tenant_context(tenant):
    CustomUser.objects.create_superuser(
        email='support@prolianceltd.com',
        password='qwertyqwerty',
        role='admin',
        first_name='Monday',
        last_name='Davidson',
        tenant=tenant
    )
    
    
from core.models import Tenant
from users.models import CustomUser
from django_tenants.utils import tenant_context
tenant = Tenant.objects.get(schema_name='appbrew')
with tenant_context(tenant):
    CustomUser.objects.create_superuser(
        email='support@appbrew.com',
        password='qwertyqwerty',
        role='admin',
        first_name='Belejit',
        last_name='Hanson',
        tenant=tenant
    )

from core.models import Tenant
from users.models import CustomUser
from django_tenants.utils import tenant_context
tenant = Tenant.objects.get(schema_name='appbrew')
with tenant_context(tenant):
    CustomUser.objects.create_superuser(
        email='info@appbrew.com',
        password='qwertyqwerty',
        role='admin',
        first_name='Awaji-mimam',
        last_name='Abraham',
        tenant=tenant
    )






from core.models import Tenant
from subscriptions.models import Subscription
tenant = Tenant.objects.get(schema_name='appbrew')
Subscription.objects.create(tenant=tenant, module='talent_engine', is_active=True)

from django.db import connection
from django_tenants.utils import schema_context

schema_name = 'abraham_ekene_onwon'
with schema_context(schema_name):
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = %s
            AND table_name = 'talent_engine_job_requisition';
        """, [schema_name])
        tables = cursor.fetchall()
        print(tables)  