import os
import json
import shutil
from pypdf import PdfWriter, PdfReader
from io import BytesIO

from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import FakeEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain.schema import Document
from langchain.chains import RetrievalQA
from langchain_community.llms import FakeListLLM

# --- Configuration ---
PDF_DIR = "./sample_pdfs"
JSONL_FILE = "ingestion_data.jsonl"
CHROMA_PATH = "./chroma_db_from_jsonl"

# --- 1. Data Simulation and Preprocessing ---

# In a real app, this mapping would come from a database or config file.
SOURCE_TO_CHANNEL_MAP = {
    "q1_finance_report.pdf": "channel_1",
    "marketing_campaign_summary.pdf": "channel_2",
    "hr_policy_update.pdf": "channel_4",
}

# Content for our dummy PDFs
PDF_CONTENTS = {
    "q1_finance_report.pdf": "The Q1 financial report for Project Alpha shows a 15% increase in revenue. This data is critical for strategic planning in the finance department.",
    "marketing_campaign_summary.pdf": "Our marketing team launched the 'Summer Splash' campaign last week. Initial metrics show a 25% engagement increase on social media. The campaign targets the 18-25 age demographic.",
    "hr_policy_update.pdf": "The new HR policy on remote work will be effective starting next month. All employees are required to complete the mandatory training module. This policy aims to improve work-life balance.",
}

def setup_dummy_pdfs():
    """Creates a directory with simple, one-page PDF files for demonstration."""
    print("--- Step 1: Setting up dummy PDF files ---")
    os.makedirs(PDF_DIR, exist_ok=True)
    for filename, content in PDF_CONTENTS.items():
        filepath = os.path.join(PDF_DIR, filename)
        
        # Create a simple PDF in memory
        packet = BytesIO()
        writer = PdfWriter()
        writer.add_blank_page(width=612, height=792) # Standard letter size
        
        # This is a simplified way to add text; real PDFs are more complex.
        # For this example, we'll store text in metadata and read it back.
        writer.add_metadata({"/Body": content})
        writer.write(packet)
        packet.seek(0)
        
        with open(filepath, "wb") as f:
            f.write(packet.read())
    print(f"Created {len(PDF_CONTENTS)} PDFs in '{PDF_DIR}' directory.\n")

def preprocess_pdfs_to_jsonl():
    """
    Reads PDFs, extracts text, adds channel metadata, and saves to a JSONL file.
    """
    print(f"--- Step 2: Preprocessing PDFs into '{JSONL_FILE}' ---")
    with open(JSONL_FILE, "w") as outfile:
        for filename in os.listdir(PDF_DIR):
            if filename.endswith(".pdf"):
                filepath = os.path.join(PDF_DIR, filename)
                
                # Extract text from our dummy PDF's metadata
                reader = PdfReader(filepath)
                # In a real scenario with complex PDFs, you'd iterate pages and extract text.
                # E.g., text = "".join(page.extract_text() for page in reader.pages)
                content = reader.metadata.get("/Body", "")

                channel = SOURCE_TO_CHANNEL_MAP.get(filename)
                
                if content and channel:
                    # Create the JSON object for this document
                    doc_data = {
                        "content": content,
                        "metadata": {
                            "source": filename,
                            "channel": channel
                        }
                    }
                    # Write the JSON object as a single line in the output file
                    outfile.write(json.dumps(doc_data) + "\n")
    print(f"Successfully created '{JSONL_FILE}'.\n")


def ingest_from_jsonl():
    """
    Reads the JSONL file and ingests its content into the Chroma vector store.
    """
    print(f"--- Step 3: Ingesting data from '{JSONL_FILE}' into Vector Store ---")
    documents_to_ingest = []
    with open(JSONL_FILE, "r") as infile:
        for line in infile:
            data = json.loads(line)
            doc = Document(
                page_content=data["content"],
                metadata=data["metadata"]
            )
            documents_to_ingest.append(doc)

    text_splitter = RecursiveCharacterTextSplitter(chunk_size=200, chunk_overlap=20)
    all_chunks = text_splitter.split_documents(documents_to_ingest)
    
    for chunk in all_chunks:
         print(f"  - Preparing chunk from '{chunk.metadata['source']}' for channel '{chunk.metadata['channel']}'")

    embedding_function = FakeEmbeddings(size=768)
    vectorstore = Chroma.from_documents(
        documents=all_chunks,
        embedding=embedding_function,
        persist_directory=CHROMA_PATH
    )
    print(f"\nSuccessfully created and persisted vector store at: {CHROMA_PATH}\n")
    return vectorstore

# --- 4. Querying (This function is unchanged!) ---

def answer_query_as_user(vectorstore: Chroma, user_channels: list, query: str):
    """
    Simulates a user query with channel-based access control.
    """
    print(f"👤 Querying as a user with access to: {user_channels}")
    print(f"   Query: '{query}'")

    retriever = vectorstore.as_retriever(
        search_kwargs={"filter": {"channel": {"$in": user_channels}}}
    )
    
    fake_llm = FakeListLLM(responses=["Based on the retrieved documents, here is the answer..."])
    qa_chain = RetrievalQA.from_chain_type(
        llm=fake_llm,
        chain_type="stuff",
        retriever=retriever,
        return_source_documents=True
    )

    result = qa_chain.invoke({"query": query})
    
    print("\n   ✅ Retrieval Result:")
    if result["source_documents"]:
        for doc in result["source_documents"]:
            print(f"      - Source: {doc.metadata['source']}, Channel: {doc.metadata['channel']}")
    else:
        print("      - No documents found for this user's channels.")
    print("-" * 50)


def cleanup():
    """Removes generated files and directories."""
    print("\n--- Cleaning up generated files and directories ---")
    if os.path.exists(PDF_DIR):
        shutil.rmtree(PDF_DIR)
    if os.path.exists(CHROMA_PATH):
        shutil.rmtree(CHROMA_PATH)
    if os.path.exists(JSONL_FILE):
        os.remove(JSONL_FILE)
    print("Cleanup complete.")

# --- Main Execution ---
if __name__ == "__main__":
    setup_dummy_pdfs()
    preprocess_pdfs_to_jsonl()
    vectorstore = ingest_from_jsonl()

    print("--- Step 4: Querying Data as Different Users ---")
    
    # Use Case 1: Finance user asks about revenue
    answer_query_as_user(vectorstore, user_channels=["channel_1", "channel_4"], query="What was the revenue increase?")
    
    # Use Case 2: Marketing user asks about revenue (should fail)
    answer_query_as_user(vectorstore, user_channels=["channel_2"], query="What was the revenue increase?")

    # Use Case 3: HR user asks about policy
    answer_query_as_user(vectorstore, user_channels=["channel_1", "channel_4"], query="What is the new remote work policy?")
    
    cleanup()