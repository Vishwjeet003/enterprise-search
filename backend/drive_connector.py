"""Google Drive connector for fetching documents."""
import io
from typing import List, Dict, Optional
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import PyPDF2


class DriveConnector:
    """Handles Google Drive OAuth and document fetching."""
    
    SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
    
    def __init__(self, client_id: str, client_secret: str, redirect_uri: str):
        """Initialize Drive connector with OAuth credentials."""
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.credentials: Optional[Credentials] = None
        self.service = None
    
    def _create_flow(self) -> Flow:
        """Create OAuth flow with client config."""
        return Flow.from_client_config(
            {
                "web": {
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [self.redirect_uri]
                }
            },
            scopes=self.SCOPES
        )
    
    def get_authorization_url(self) -> str:
        """Get OAuth authorization URL."""
        flow = self._create_flow()
        flow.redirect_uri = self.redirect_uri
        authorization_url, _ = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            prompt='consent'
        )
        return authorization_url
    
    def authenticate(self, authorization_code: str) -> None:
        """Authenticate using authorization code."""
        flow = self._create_flow()
        flow.redirect_uri = self.redirect_uri
        flow.fetch_token(code=authorization_code)
        self.credentials = flow.credentials
        self.service = build('drive', 'v3', credentials=self.credentials)
    
    def set_credentials(self, credentials: Credentials) -> None:
        """Set credentials directly (for session management)."""
        self.credentials = credentials
        if self.credentials and self.credentials.valid:
            self.service = build('drive', 'v3', credentials=self.credentials)
        elif self.credentials and self.credentials.expired and self.credentials.refresh_token:
            self.credentials.refresh(Request())
            self.service = build('drive', 'v3', credentials=self.credentials)
    
    def list_documents(self, mime_types: List[str] = None, max_files: int = None) -> List[Dict]:
        """List documents matching specified MIME types."""
        if not self.service:
            raise ValueError("Not authenticated. Call authenticate() first.")
        
        if mime_types is None:
            mime_types = ['application/pdf']
        
        query_parts = [f"mimeType='{mime_type}'" for mime_type in mime_types]
        query = " or ".join(query_parts) + " and trashed=false"
        
        results = []
        page_token = None
        
        while True:
            remaining = max_files - len(results) if max_files else None
            page_size = min(remaining, 100) if remaining else 100
            
            if max_files and len(results) >= max_files:
                break
            
            response = self.service.files().list(
                q=query,
                fields="nextPageToken, files(id, name, mimeType, modifiedTime, webViewLink)",
                pageToken=page_token,
                pageSize=page_size,
                orderBy="modifiedTime desc"
            ).execute()
            
            new_files = response.get('files', [])
            results.extend(new_files)
            
            if max_files and len(results) >= max_files:
                results = results[:max_files]
                break
            
            page_token = response.get('nextPageToken')
            if not page_token:
                break
        
        return results
    
    def extract_text_from_doc(self, file_id: str) -> str:
        """Extract text from a Google Doc."""
        if not self.service:
            raise ValueError("Not authenticated.")
        
        try:
            request = self.service.files().export_media(fileId=file_id, mimeType='text/plain')
            file_content = io.BytesIO()
            downloader = MediaIoBaseDownload(file_content, request)
            done = False
            while not done:
                status, done = downloader.next_chunk()
            return file_content.getvalue().decode('utf-8')
        except Exception as e:
            raise Exception(f"Error extracting text from Google Doc: {str(e)}")
    
    def extract_text_from_pdf(self, file_id: str) -> str:
        """Extract text from a PDF file."""
        if not self.service:
            raise ValueError("Not authenticated.")
        
        try:
            request = self.service.files().get_media(fileId=file_id)
            file_content = io.BytesIO()
            downloader = MediaIoBaseDownload(file_content, request)
            done = False
            while not done:
                status, done = downloader.next_chunk()
            
            file_content.seek(0)
            pdf_reader = PyPDF2.PdfReader(file_content)
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
            return text
        except Exception as e:
            raise Exception(f"Error extracting text from PDF: {str(e)}")
    
    def get_document_content(self, file_id: str, mime_type: str) -> str:
        """Get text content from a document based on its MIME type."""
        if mime_type == 'application/vnd.google-apps.document':
            return self.extract_text_from_doc(file_id)
        elif mime_type == 'application/pdf':
            return self.extract_text_from_pdf(file_id)
        else:
            raise ValueError(f"Unsupported MIME type: {mime_type}")
