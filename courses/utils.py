from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.http.models import PointStruct, Distance, VectorParams, Filter, FieldCondition, MatchValue
import os
import json
import logging
from channels.db import database_sync_to_async
from django_tenants.utils import schema_context
from courses.models import Course
import requests
import openai
from transformers import pipeline
import uuid
# Load the QA pipeline once at module level
qa_pipeline = pipeline("question-answering", model="distilbert-base-uncased-distilled-squad")


# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('debug.log')
    ]
)
logger = logging.getLogger(__name__)

QDRANT_URL = os.environ.get("QDRANT_URL", "http://localhost:6333")
QDRANT_COLLECTION = os.environ.get("QDRANT_COLLECTION", "lms-course-ai-chat")

def get_qdrant_client():
    return QdrantClient(url=QDRANT_URL)

def ensure_collection(client, collection_name, vector_size):
    if collection_name not in [c.name for c in client.get_collections().collections]:
        client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE)
        )

@database_sync_to_async
def retrieve_documents(query, tenant_schema, top_k=10):
    try:
        model = SentenceTransformer('all-MiniLM-L6-v2')
        query_embedding = model.encode(query).tolist()
        client = get_qdrant_client()
        ensure_collection(client, QDRANT_COLLECTION, 384)
        search_filter = Filter(
            must=[
                FieldCondition(key="tenant", match=MatchValue(value=tenant_schema))
            ]
        )
        results = client.search(
            collection_name=QDRANT_COLLECTION,
            query_vector=query_embedding,
            limit=top_k,
            query_filter=search_filter,  # <-- use query_filter here
            with_payload=True
        )
        documents = [
            point.payload['text']
            for point in results
            if 'text' in point.payload and point.payload['text']
        ]
        logger.debug(f"Query: {query}, Retrieved documents: {documents}")
        # print("documents")
        # print(documents)
        # print("documents")
        return documents
    except Exception as e:
        logger.error(f"Error in retrieve_documents: {str(e)}", exc_info=True)
        raise

def index_courses_for_tenant(tenant_schema):
    if tenant_schema == "public":
        logger.info("Skipping indexing for public schema.")
        return
    try:
        with schema_context(tenant_schema):
            # print("tenant_schema")
            # print(tenant_schema)
            # print("tenant_schema")
            documents = []
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
                #print("Indexing document:", doc)  # <-- Added print statement here

            model = SentenceTransformer('all-MiniLM-L6-v2')
            client = get_qdrant_client()
            ensure_collection(client, QDRANT_COLLECTION, 384)
            points = []
            for i, doc in enumerate(documents):
                embedding = model.encode(doc).tolist()
                points.append(PointStruct(
                    id=i,  # <-- Use integer ID
                    vector=embedding,
                    payload={"text": doc, "tenant": tenant_schema}
                ))
            client.upsert(collection_name=QDRANT_COLLECTION, points=points)
            logger.info(f"Indexed {len(documents)} documents for {tenant_schema}")
    except Exception as e:
        logger.error(f"Error indexing courses for tenant {tenant_schema}: {str(e)}", exc_info=True)


@database_sync_to_async
def generate_ai_response(query, documents, tenant_schema):
    try:
        if not documents:
            return {
                "courses": [],
                "message": "No relevant course content found."
            }

        courses = []
        for doc in documents:
            try:
                course = json.loads(doc)
                # Trim description to first 10 words
                description = course.get("description", "")
                desc_words = description.split()
                trimmed_description = " ".join(desc_words[:10]) + ("..." if len(desc_words) > 10 else "")
                # Parse learning outcomes
                learning_outcomes = course.get("learning_outcomes", "")
                if isinstance(learning_outcomes, str):
                    try:
                        learning_outcomes = json.loads(learning_outcomes)
                    except Exception:
                        learning_outcomes = [learning_outcomes]
                # Add discount_price and price if available
                discount_price = course.get("discount_price", None)
                price = course.get("price", None)
                courses.append({
                    "title": course.get("title", "Untitled Course"),
                    "description": trimmed_description,
                    "learning_outcomes": learning_outcomes,
                    "discount_price": discount_price,
                    "price": price
                })
            except Exception as e:
                logger.error(f"Error parsing course document: {str(e)}")
                continue

        return {
            "courses": courses,
            "message": "Recommended courses found." if courses else "No relevant course content found."
        }
    except Exception as e:
        logger.error(f"Error in generate_ai_response: {str(e)}", exc_info=True)
        return {
            "courses": [],
            "message": "Sorry, the AI service is currently unavailable."
        }