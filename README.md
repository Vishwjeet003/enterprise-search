# Enterprise Search Application

A production-quality enterprise search application that uses Google Drive as the data source, Gemini APIs for embeddings and question answering, and provides context-aware agentic search with inline citations.

## Architecture

- **Backend**: FastAPI (Python) with modular components
- **Frontend**: React with modern UI
- **Data Source**: Google Drive (real OAuth integration)
- **AI**: Google Gemini for embeddings and answer generation
- **Vector Store**: In-memory vector store (MVP-ready, can be upgraded to Pinecone/Weaviate)

## Features

1. **Google Drive Integration**
   - OAuth2 authentication
   - Fetches PDF files (MVP: limited to 5 files to keep token usage low)
   - Extracts text content

2. **Intelligent Indexing**
   - Document chunking with overlap
   - Embedding generation using Gemini
   - Vector similarity search
   - **MVP Mode**: Limits content to 50,000 chars per file to reduce token usage

3. **Agentic Search**
   - Query understanding
   - Context retrieval
   - Answer generation
   - Citation mapping with inline references

4. **Clean UI**
   - Modern, responsive design
   - Search interface
   - Answer display with citations
   - Source document listing

## MVP Limitations & Free Tier Models

This MVP version is optimized for free tier usage:
- **File Types**: Only PDFs (no Google Docs)
- **Content Limit**: First 50,000 characters per file
- **Purpose**: Keep token usage minimal while demonstrating full functionality

### Free Tier Models Used

The application uses **100% free models** with zero API costs:

1. **Text Generation**: `gemini-1.5-flash`
   - Free tier model (no cost)
   - Fast response times
   - Good quality for search and Q&A
   - Can be changed to `gemini-pro` in config if needed

2. **Embeddings**: Local `sentence-transformers` (Primary) + Gemini API (Fallback)
   - **Primary**: `all-MiniLM-L6-v2` (sentence-transformers) - **Completely free, no API calls, no rate limits**
   - **Fallback**: `models/embedding-001` (Gemini) - Only used if local model unavailable
   - Automatic fallback with rate limiting and retry logic
   - **No rate limiting issues** - local embeddings run entirely on your machine

You can adjust these limits in `.env` by changing `MAX_FILES_TO_INDEX`, `FILE_TYPES`, and `LLM_MODEL`.

## Setup Instructions

### Prerequisites

- Python 3.9+
- Node.js 16+
- Google Cloud Project with Drive API and Gemini API enabled
- Google OAuth2 credentials

### Step 1: Google Cloud Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing one
3. Enable **Google Drive API**:
   - Navigate to "APIs & Services" > "Library"
   - Search for "Google Drive API" and enable it
4. Enable **Generative AI API**:
   - Search for "Generative Language API" and enable it
5. Create OAuth2 credentials:
   - Go to "APIs & Services" > "Credentials"
   - Click "Create Credentials" > "OAuth client ID"
   - Choose "Web application"
   - Add authorized redirect URI: `http://localhost:8000/auth/callback`
   - Save Client ID and Client Secret
6. Get Gemini API Key:
   - Go to [Google AI Studio](https://makersuite.google.com/app/apikey)
   - Create a new API key

### Step 2: Backend Setup

1. Navigate to project root:
   ```bash
   cd enterprise-search
   ```

2. Create virtual environment:
   ```bash
   python -m venv venv
   ```

3. Activate virtual environment:
   - Windows:
     ```bash
     venv\Scripts\activate
     ```
   - macOS/Linux:
     ```bash
     source venv/bin/activate
     ```

4. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

5. Create `.env` file:
   ```bash
   cp .env.example .env
   ```

6. Edit `.env` and add your credentials:
   ```
   GOOGLE_CLIENT_ID=your_client_id_here
   GOOGLE_CLIENT_SECRET=your_client_secret_here
   GOOGLE_REDIRECT_URI=http://localhost:8000/auth/callback
   
   # Gemini API Key (optional - only needed for text generation, not embeddings)
   GEMINI_API_KEY=your_gemini_api_key_here
   
   # Optional: Model configuration (defaults to free tier models)
   LLM_MODEL=gemini-1.5-flash  # Free tier model (or gemini-pro for paid)
   EMBEDDING_MODEL=models/embedding-001  # Only used as fallback if local model fails
   ```
   
   **Important**: Embeddings use local `sentence-transformers` by default (no API key needed, no rate limits). Gemini API key is only required for text generation (search answers).

7. Start backend server (from project root):
   ```bash
   uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
   ```

   Or using Python module syntax:
   ```bash
   python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
   ```

### Step 3: Frontend Setup

1. Navigate to frontend directory:
   ```bash
   cd frontend
   ```

2. Install dependencies:
   ```bash
   npm install
   ```

3. Start development server:
   ```bash
   npm start
   ```

   The frontend will open at `http://localhost:3000`

### Step 4: Using the Application

1. **Authenticate**: Click "Connect Google Drive" and authorize the application
2. **Index Documents**: Click "Index Documents" to fetch and index your Google Drive documents
3. **Search**: Enter a question and click "Search" to get AI-generated answers with citations

## Project Structure

```
enterprise-search/
├── backend/
│   ├── main.py              # FastAPI application
│   ├── config.py            # Configuration management
│   ├── drive_connector.py   # Google Drive OAuth & document fetching
│   ├── indexer.py           # Document chunking & embedding
│   ├── store.py             # Vector store implementation
│   ├── search_agent.py      # Agentic search orchestration
│   └── citation_agent.py    # Citation mapping
├── frontend/
│   ├── src/
│   │   ├── App.jsx          # Main React component
│   │   ├── App.css          # Styles
│   │   ├── api.js           # API client
│   │   ├── index.js         # React entry point
│   │   └── index.css        # Global styles
│   └── package.json
├── requirements.txt         # Python dependencies
├── .env.example            # Environment variables template
└── README.md               # This file
```

## API Endpoints

- `GET /` - Health check
- `GET /auth/authorize` - Get OAuth authorization URL
- `GET /auth/callback` - OAuth callback handler
- `GET /drive/documents` - List Google Drive documents
- `POST /index/documents` - Index all documents
- `POST /search` - Perform search query
- `GET /stats` - Get vector store statistics

## How It Works

1. **Authentication**: User authenticates via Google OAuth2
2. **Document Fetching**: Application fetches Google Docs and PDFs from Drive
3. **Indexing**: Documents are chunked, embedded using Gemini, and stored in vector store
4. **Search Process**:
   - Query understanding: Analyzes user query
   - Context retrieval: Finds relevant chunks using vector similarity
   - Answer generation: Uses Gemini to generate answer from context
   - Citation mapping: Maps answer text to source documents and inserts citations
5. **Response**: Returns answer with inline citations and source list

## Production Considerations

For production deployment, consider:

1. **Vector Store**: Replace in-memory store with Pinecone, Weaviate, or Qdrant
2. **Session Management**: Use Redis or database for user sessions
3. **Caching**: Add caching for frequently accessed documents
4. **Error Handling**: Enhanced error handling and logging
5. **Security**: Add rate limiting, authentication middleware
6. **Scalability**: Use async processing for large document sets
7. **Monitoring**: Add logging and monitoring (e.g., Sentry, DataDog)

## Troubleshooting

### Backend won't start
- Check that all environment variables are set in `.env`
- Verify Python version is 3.9+
- Ensure all dependencies are installed

### OAuth errors
- Verify redirect URI matches exactly in Google Cloud Console
- Check that Google Drive API is enabled
- Ensure credentials are correct

### Embedding errors
- Verify Gemini API key is valid
- Check that Generative Language API is enabled
- Ensure API key has proper permissions

### Frontend connection issues
- Verify backend is running on port 8000
- Check CORS settings in `backend/main.py`
- Ensure `FRONTEND_URL` in `.env` matches frontend URL

## License

This project is provided as-is for demonstration purposes.

