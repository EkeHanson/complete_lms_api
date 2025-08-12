from sentence_transformers import SentenceTransformer
from pinecone import Pinecone
import os
from openai import OpenAI  # Or import grok from grok-api
from channels.db import database_sync_to_async

@database_sync_to_async
def generate_ai_response(query, documents):
    client = OpenAI(api_key=os.environ.get('OPENAI_API_KEY'))
    context = "\n\n".join(documents)
    prompt = f"Answer the user's question based ONLY on the following course content. Be helpful and educational:\n\n{context}\n\nQuestion: {query}"
    response = client.chat.completions.create(
        model="gpt-4o-mini",  # Or "grok-beta" if using xAI
        messages=[{"role": "system", "content": prompt}],
        max_tokens=500
    )
    return response.choices[0].message.content

@database_sync_to_async
def retrieve_documents(query, tenant_schema, top_k=5):
    pc = Pinecone(api_key=os.environ.get('PINECONE_API_KEY'))
    index = pc.Index(os.environ.get('PINECONE_INDEX_NAME'))
    model = SentenceTransformer('all-MiniLM-L6-v2')
    query_embedding = model.encode(query).tolist()
    results = index.query(
        namespace=tenant_schema,
        vector=query_embedding,
        top_k=top_k,
        include_metadata=True
    )
    return [match['metadata']['text'] for match in results['matches']]