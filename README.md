# 📄 Document Chat Assistant

## Overview

**Document Chat Assistant** is an AI-powered web app that lets you interact with uploaded research papers and PDFs using natural language queries. Whether it's extracting summaries, understanding formulas, or comparing multiple documents — this assistant uses the power of **Mistral OCR** and **LLMs** to help you make sense of academic documents.

## Features

- 💬 **Real-time Chat Interface**: Ask questions like you're chatting with ChatGPT.
- 📂 **Upload Your PDFs**: Load multiple PDFs from your local system.
- 🔍 **Search & Load from arXiv**: Fetch academic papers directly via keyword or arXiv ID.
- 🧠 **AI-Powered Reasoning**: Uses Mistral’s OCR and LLMs to extract and analyze document content.
- 🧮 **Math Formula Rendering**: Detects and renders LaTeX math equations clearly.
- 🖼️ **Image Extraction**: Automatically detects and preserves image content from documents.
- 🌙 **Dark-Themed UI**: Clean, responsive layout optimized for focus and readability.

## Technologies Used

- **Frontend**: Streamlit, HTML/CSS
- **Backend & Logic**: Python, LangChain
- **LLMs**: Mistral (OCR & chat models)
- **PDF Handling**: Mistral OCR API
- **Search API**: arXiv Python library
- **Environment Management**: python-dotenv

---

## Setup Instructions

### Prerequisites

- Python 3.8+
- pip or conda
- Mistral API Key (Sign up on [mistral.ai](https://mistral.ai))

### Installation

1. **Clone the Repository**
   ```sh
   git clone https://github.com/your-username/document-chat-assistant.git
   cd document-chat-assistant
