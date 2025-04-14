import os
import streamlit as st
import tempfile
import io
from dotenv import load_dotenv

# Set page configuration as the very first Streamlit command.
st.set_page_config(page_title="Document Chat Assistant", layout="wide")

# Load environment variables (e.g., MISTRAL_API_KEY) from .env.
load_dotenv()

# ------------------------------------------------------------
# Import necessary libraries.
from mistralai import Mistral, DocumentURLChunk
from mistralai.models import OCRResponse
import arxiv
from langchain.embeddings.huggingface import HuggingFaceEmbeddings
from langchain.vectorstores import FAISS
from langchain.text_splitter import RecursiveCharacterTextSplitter
from PIL import Image

# ------------------------------------------------------------
# Custom CSS for a dark, ChatGPT-like UI.
custom_css = """
<style>
/* Overall dark theme */
body {
    background-color: #121212;
    color: #e0e0e0;
}
[data-testid="stSidebar"] {
    background: #1f1f1f;
    color: #e0e0e0;
}
/* Chat container similar to ChatGPT */
.chat-container {
    background-color: #343541;
    border-radius: 8px;
    padding: 1rem 2rem;
    margin-bottom: 80px;
    max-height: 70vh;
    overflow-y: auto;
    margin-top: 1rem;
}
/* Message container */
.message-container {
    display: block;
    margin-bottom: 1rem;
}
/* Chat bubble styling */
.message-bubble {
    margin: 0.5rem 0;
    padding: 12px 16px;
    border-radius: 6px;
    max-width: 80%;
    white-space: pre-wrap;
    word-wrap: break-word;
}
.message-user {
    background: #057553;
    color: #ffffff;
    float: right;
    text-align: right;
}
.message-assistant {
    background: #444654;
    color: #ffffff;
    float: left;
    text-align: left;
}
/* Clear floats */
.message-container::after {
    content: "";
    clear: both;
    display: table;
}
/* Fixed chat input area at bottom */
.chat-input-container {
    position: fixed;
    bottom: 0;
    left: 320px;
    width: calc(100% - 320px);
    background: #1f1f1f;
    padding: 10px 20px;
    border-top: 1px solid #444;
    box-shadow: 0 -2px 5px rgba(0,0,0,0.5);
    display: flex;
    gap: 10px;
}
.chat-input-container input[type="text"] {
    flex: 1;
    padding: 10px;
    border: 1px solid #444;
    border-radius: 5px;
    font-size: 16px;
    background: #121212;
    color: #e0e0e0;
}
@media(max-width: 800px) {
    .chat-input-container {
         left: 0;
         width: 100%;
    }
}
</style>
"""
st.markdown(custom_css, unsafe_allow_html=True)

# ------------------------------------------------------------
# Session State Initialization.
if "staged_pdfs" not in st.session_state:
    st.session_state.staged_pdfs = []   # Temporarily hold uploaded PDFs.
if "staged_arxiv" not in st.session_state:
    st.session_state.staged_arxiv = []    # Temporarily hold selected arXiv papers.
if "uploaded_docs" not in st.session_state:
    st.session_state.uploaded_docs = []   # Final processed PDFs.
if "arxiv_docs" not in st.session_state:
    st.session_state.arxiv_docs = []        # Final processed arXiv papers.
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []      # Global conversation history.
if "chat_counter" not in st.session_state:
    st.session_state.chat_counter = 0
if "arxiv_results" not in st.session_state:
    st.session_state.arxiv_results = []     # Temporary storage for arXiv search results.

# ------------------------------------------------------------
# Function Definitions.
def initialize_mistral_client(api_key):
    if not api_key:
        st.error("Missing API Key.")
        return None
    return Mistral(api_key=api_key)

def process_ocr(client, document_source):
    if client is None:
        raise ValueError("Mistral client not available.")
    return client.ocr.process(
        document=DocumentURLChunk(document_url=document_source["document_url"]),
        model="mistral-ocr-latest",
        include_image_base64=True
    )

def do_arxiv_search(query: str, author: str, sort_by: str):
    if len(query.split()) > 3:
        query = f"ti:{query}"
    else:
        query = f"({query})"
    if author:
        query += f" AND au:{author}"
    from arxiv import SortCriterion
    sort_criterion = SortCriterion.SubmittedDate if sort_by == "SubmittedDate" else SortCriterion.Relevance
    search = arxiv.Search(query=query, max_results=10, sort_by=sort_criterion)
    client_arxiv = arxiv.Client()
    return list(client_arxiv.results(search))

def get_combined_markdown(ocr_response: OCRResponse) -> str:
    texts = [page.markdown for page in ocr_response.pages]
    return "\n\n".join(texts)

def process_ocr_for_staged(client):
    if not client:
        st.error("Mistral client not available.")
        return

    # Process staged PDFs.
    for staged in st.session_state.staged_pdfs:
        filename = staged["filename"]
        file_bytes = staged["file_bytes"]
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(file_bytes)
            tmp_path = tmp.name
        try:
            with open(tmp_path, "rb") as f:
                file_upload = client.files.upload(
                    file={"file_name": filename, "content": f},
                    purpose="ocr"
                )
            signed_url = client.files.get_signed_url(file_id=file_upload.id)
            ocr_response = process_ocr(client, {"document_url": signed_url.url})
            if ocr_response and ocr_response.pages:
                text = "\n\n".join([page.markdown for page in ocr_response.pages])
                st.session_state.uploaded_docs.append({
                    "source": "upload",
                    "filename": filename,
                    "document_url": signed_url.url,
                    "content": text
                })
                st.success(f"Processed PDF '{filename}'!")
            else:
                st.warning(f"No text found in '{filename}'.")
        except Exception as e:
            st.error(f"Error processing '{filename}': {str(e)}")
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
    st.session_state.staged_pdfs.clear()

    # Process staged arXiv papers.
    for staged in st.session_state.staged_arxiv:
        pdf_url = staged["pdf_url"]
        title = staged.get("title", "Paper")
        try:
            ocr_response = process_ocr(client, {"document_url": pdf_url})
            if ocr_response and ocr_response.pages:
                text = "\n\n".join([page.markdown for page in ocr_response.pages])
                st.session_state.arxiv_docs.append({
                    "source": "arxiv",
                    "title": title,
                    "document_url": pdf_url,
                    "content": text
                })
                st.success(f"Processed paper '{title}'!")
            else:
                st.warning(f"No text found in '{title}'.")
        except Exception as e:
            st.error(f"Error processing paper '{title}': {str(e)}")
    st.session_state.staged_arxiv.clear()

def generate_response_from_documents(client, query, context_text):
    try:
        prompt = f"""I have parts of several documents:

{context_text}

Answer this question based on the documents:
{query}"""
        messages = [{"role": "user", "content": [{"type": "text", "text": prompt}]}]
        model = "mistral-small-latest"
        response = client.chat.complete(model=model, messages=messages)
        return response.choices[0].message.content
    except Exception as e:
        st.error(f"Error generating response: {str(e)}")
        return f"Error generating response: {str(e)}"

def render_chat_message(role, message):
    msg = message.strip().strip('"')
    container_start = '<div class="message-container">'
    container_end = '</div>'
    if role.lower() == "assistant" and ((msg.startswith('[') and msg.endswith(']')) or ("\\operatorname" in msg or "\\frac" in msg)):
        if msg.startswith('[') and msg.endswith(']'):
            msg = msg[1:-1].strip()
        st.markdown(f"""{container_start}
<div class="message-bubble message-assistant">{msg}</div>
{container_end}""", unsafe_allow_html=True)
        st.latex(msg)
    else:
        bubble_class = "message-bubble message-user" if role.lower() == "user" else "message-bubble message-assistant"
        st.markdown(f"""{container_start}
<div class="{bubble_class}">{msg}</div>
{container_end}""", unsafe_allow_html=True)

def get_global_context():
    texts = []
    for doc in st.session_state.uploaded_docs:
        if doc.get("content"):
            texts.append(doc["content"])
    for doc in st.session_state.arxiv_docs:
        if doc.get("content"):
            texts.append(doc["content"])
    return "\n\n".join(texts)

def chat_ui(client):
    global_context = get_global_context()
    st.markdown('<div class="chat-container">', unsafe_allow_html=True)
    if st.session_state.chat_history:
        for msg in st.session_state.chat_history:
            render_chat_message(msg["role"], msg["content"])
    else:
        st.info("No conversation yet. Once your documents are processed, type a question below.")
    st.markdown('</div>', unsafe_allow_html=True)

    chat_container = st.empty()
    with chat_container.container():
        cols = st.columns([4, 1])
        user_message = cols[0].text_input("Type your question here...", key=f"chat_input_{st.session_state.chat_counter}")
        send_pressed = cols[1].button("Send", key=f"send_btn_{st.session_state.chat_counter}")
        if send_pressed and user_message:
            st.session_state.chat_history.append({"role": "user", "content": user_message})
            if global_context.strip():
                response = generate_response_from_documents(client, user_message, global_context)
            else:
                response = "Error: No document data available. Please process your documents first."
            st.session_state.chat_history.append({"role": "assistant", "content": response})
            st.session_state.chat_counter += 1
            if hasattr(st, "experimental_rerun"):
                st.experimental_rerun()

# ------------------------------------------------------------
# Main Application Function.
def main():
    st.title("Document Chat Assistant")
    mistral_key = os.getenv("MISTRAL_API_KEY")
    if not mistral_key:
        st.error("MISTRAL_API_KEY not found in .env")
        st.stop()

    client = initialize_mistral_client(mistral_key)
    if not client:
        st.error("Failed to initialize Mistral client.")
        st.stop()

    # Store client in session_state.
    st.session_state.client = client

    # ------------------------------------------------------------
    # Sidebar: Document Loader Panel with friendly instructions.
    st.sidebar.header("Upload & Find Documents")

    st.sidebar.markdown("#### Upload Your PDFs")
    staged_files = st.sidebar.file_uploader("Choose PDF files", type=["pdf"], accept_multiple_files=True, key="upload_staging")
    if staged_files:
        # Prevent duplicate staging by checking file names.
        current_files = [pdf['filename'] for pdf in st.session_state.staged_pdfs]
        for file in staged_files:
            if file.name not in current_files:
                st.session_state.staged_pdfs.append({
                    "filename": file.name,
                    "file_bytes": file.read()
                })
        st.sidebar.success(f"Added {len(staged_files)} PDF(s) to your upload list.")
    if st.session_state.staged_pdfs:
        st.sidebar.markdown("**Files waiting to be processed:**")
        for pdf in st.session_state.staged_pdfs:
            st.sidebar.markdown(f"- {pdf['filename']}")

    st.sidebar.markdown("#### Find Research Papers Online")
    search_type = st.sidebar.radio("Search by", ["Keyword", "Arxiv ID"], horizontal=True, key="arxiv_search_type")
    if search_type == "Keyword":
        keyword_query = st.sidebar.text_input("Enter keywords", key="arxiv_kw")
        author_filter = st.sidebar.text_input("Author name (optional)", key="arxiv_author")
        sort_by_option = st.sidebar.selectbox("Sort by", ["SubmittedDate", "Relevance"], index=0, key="arxiv_sort_by")
        if len((keyword_query or "").split()) > 3:
            final_query = f"ti:{keyword_query}"
        else:
            final_query = f"({keyword_query or ''})"
        if author_filter:
            final_query += f" AND au:{author_filter}"
    else:
        final_query = st.sidebar.text_input("Enter Arxiv ID(s) (comma-separated)", key="arxiv_ids")
    if st.sidebar.button("Search Online Papers"):
        if final_query:
            with st.spinner("Searching online papers..."):
                try:
                    if search_type == "Keyword":
                        from arxiv import SortCriterion
                        sort_by = SortCriterion.SubmittedDate if sort_by_option == "SubmittedDate" else SortCriterion.Relevance
                        search = arxiv.Search(query=final_query, max_results=10, sort_by=sort_by)
                    else:
                        id_list = [x.strip() for x in final_query.split(",") if x.strip()]
                        search = arxiv.Search(id_list=id_list)
                    client_arxiv = arxiv.Client()
                    results = list(client_arxiv.results(search))
                    st.session_state.arxiv_results = results
                except Exception as e:
                    st.sidebar.error(f"Error during search: {str(e)}")
        else:
            st.sidebar.error("Please enter a search query.")
    if st.session_state.arxiv_results:
        docs = st.session_state.arxiv_results
        options = {f"{i+1}. {doc.title}": i for i, doc in enumerate(docs)}
        selected_arxiv = st.sidebar.multiselect("Select papers to add", list(options.keys()), key="arxiv_multiselect_2")
        if selected_arxiv and st.sidebar.button("Add Selected Papers"):
            with st.spinner("Adding selected papers..."):
                staged_urls = [arv["pdf_url"] for arv in st.session_state.staged_arxiv]
                for option in selected_arxiv:
                    idx = options[option]
                    paper = docs[idx]
                    try:
                        arxiv_id = paper.get_short_id()
                    except Exception:
                        arxiv_id = None
                    pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf" if arxiv_id else paper.pdf_url
                    if pdf_url not in staged_urls:
                        st.session_state.staged_arxiv.append({
                            "title": paper.title,
                            "pdf_url": pdf_url
                        })
                st.sidebar.success(f"Added {len(selected_arxiv)} paper(s) to your list.")
        if st.session_state.staged_arxiv:
            st.sidebar.markdown("**Papers waiting to be processed:**")
            for entry in st.session_state.staged_arxiv:
                st.sidebar.markdown(f"- {entry['title']}")

    st.sidebar.markdown("#### Documents Ready to Process")
    if st.session_state.staged_pdfs or st.session_state.staged_arxiv:
        st.sidebar.markdown("These items are waiting to be processed:")
        for pdf in st.session_state.staged_pdfs:
            st.sidebar.markdown(f"- PDF: {pdf['filename']}")
        for paper in st.session_state.staged_arxiv:
            st.sidebar.markdown(f"- Online Paper: {paper['title']}")
        if st.sidebar.button("Process All Documents"):
            with st.spinner("Processing documents..."):
                process_ocr_for_staged(st.session_state.client)
            st.sidebar.success("Documents have been processed!")
    else:
        st.sidebar.info("No documents staged yet.")

    # ------------------------------------------------------------
    # Main Area: Chat UI
    st.title("Chat with Your Documents")
    chat_ui(st.session_state.client)

if __name__ == "__main__":
    main()
