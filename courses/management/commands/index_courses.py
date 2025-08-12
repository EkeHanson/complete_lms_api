from django.core.management.base import BaseCommand
from django_tenants.utils import get_tenant_model, schema_context
from courses.models import Course, Module, Lesson
import json
import logging
from sentence_transformers import SentenceTransformer
from pinecone import Pinecone, ServerlessSpec


# Set up logging
logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Index courses for AI chat'

    def handle(self, *args, **options):
        Tenant = get_tenant_model()
        tenants = Tenant.objects.all()
        if not tenants:
            logger.error("No tenants found. Please create at least one tenant.")
            self.stdout.write(self.style.ERROR("No tenants found."))
            return

        for tenant in tenants:
            self.stdout.write(f"Processing tenant: {tenant.schema_name}")
            try:
                with schema_context(tenant.schema_name):
                    if tenant.schema_name != 'public':  # Skip public schema for tenant apps
                        documents = []
                        try:
                            for course in Course.objects.filter(status='Published'):
                                doc = {
                                    'id': str(course.id),
                                    'title': course.title,
                                    'description': f"{course.description} {course.short_description}",
                                    'learning_outcomes': ' '.join(course.learning_outcomes),
                                    'prerequisites': ' '.join(course.prerequisites),
                                    'modules': []
                                }
                                for module in course.modules.all():
                                    module_doc = {
                                        'title': module.title,
                                        'description': module.description,
                                        'lessons': []
                                    }
                                    for lesson in module.lessons.all():
                                        lesson_content = lesson.content_text or lesson.description
                                        if lesson.content_url:
                                            lesson_content += f" URL: {lesson.content_url}"
                                        module_doc['lessons'].append({
                                            'title': lesson.title,
                                            'content': lesson_content
                                        })
                                    doc['modules'].append(module_doc)
                                documents.append(json.dumps(doc))
                            self.index_documents(documents, tenant.schema_name)
                        except Exception as e:
                            logger.error(f"Error processing courses for tenant {tenant.schema_name}: {str(e)}")
                            self.stdout.write(self.style.ERROR(f"Error in tenant {tenant.schema_name}: {str(e)}"))
                    else:
                        self.stdout.write(f"Skipping public schema for tenant-specific apps.")
            except Exception as e:
                logger.error(f"Failed to switch to schema {tenant.schema_name}: {str(e)}")
                self.stdout.write(self.style.ERROR(f"Failed to process tenant {tenant.schema_name}: {str(e)}"))


def index_documents(self, documents, tenant_schema):
    pc = Pinecone(api_key=os.environ.get('PINECONE_API_KEY'))
    index_name = os.environ.get('PINECONE_INDEX_NAME', 'lms-courses')
    if index_name not in pc.list_indexes().names():
        pc.create_index(
            name=index_name,
            dimension=384,
            metric='cosine',
            spec=ServerlessSpec(cloud='aws', region='us-west-2')
        )
    index = pc.Index(index_name)
    model = SentenceTransformer('all-MiniLM-L6-v2')
    vectors = []
    for i, doc in enumerate(documents):
        embedding = model.encode(doc).tolist()
        vectors.append({
            'id': f"{tenant_schema}_{i}",
            'values': embedding,
            'metadata': {'text': doc, 'tenant': tenant_schema}
        })
    index.upsert(vectors=vectors, namespace=tenant_schema)
    self.stdout.write(self.style.SUCCESS(f"Indexed {len(documents)} documents for {tenant_schema}"))