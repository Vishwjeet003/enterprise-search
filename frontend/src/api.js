/** API client for backend communication */
const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

class ApiClient {
  constructor(baseUrl) {
    this.baseUrl = baseUrl;
  }

  async request(endpoint, options = {}) {
    const url = `${this.baseUrl}${endpoint}`;
    const config = {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
    };

    try {
      const response = await fetch(url, config);
      if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: response.statusText }));
        throw new Error(error.detail || `HTTP error! status: ${response.status}`);
      }
      return await response.json();
    } catch (error) {
      throw error;
    }
  }

  async getAuthorizationUrl() {
    return this.request('/auth/authorize');
  }

  async listDocuments() {
    return this.request('/drive/documents');
  }

  async indexDocuments() {
    return this.request('/drive/documents').then(() => {
      return this.request('/index/documents', { method: 'POST' });
    });
  }

  async indexDocumentsStream(onProgress, onComplete, onError) {
    const response = await fetch(`${this.baseUrl}/index/documents/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value);
        const lines = chunk.split('\n');

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));
              
              if (data.type === 'status') {
                onProgress?.(data.message);
              } else if (data.type === 'progress') {
                onProgress?.(`${data.document}: ${data.chunks} chunks (${data.current}/${data.total})`);
              } else if (data.type === 'complete') {
                onComplete?.(data);
              } else if (data.type === 'error') {
                onError?.(new Error(data.message));
              }
            } catch (e) {
              // Ignore parsing errors
            }
          }
        }
      }
    } finally {
      reader.releaseLock();
    }
  }

  async search(query) {
    return this.request('/search', {
      method: 'POST',
      body: JSON.stringify({ query }),
    });
  }

  async searchStream(query, conversationId = 'default', onToken, onComplete, onError) {
    const response = await fetch(`${this.baseUrl}/search/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query, conversation_id: conversationId }),
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));
              
              if (data.type === 'status') {
                onToken?.(data.message, 'status');
              } else if (data.type === 'answer_start') {
                // Answer generation started
              } else if (data.type === 'answer') {
                onToken?.(data.text, 'answer');
              } else if (data.type === 'answer_complete') {
                onComplete?.(data);
              } else if (data.type === 'done') {
                // Stream complete
              } else if (data.type === 'error') {
                onError?.(new Error(data.message));
              }
            } catch (e) {
              // Ignore parsing errors
            }
          }
        }
      }
    } finally {
      reader.releaseLock();
    }
  }

  async getStats() {
    return this.request('/stats');
  }

  async getChatHistory(conversationId = 'default') {
    return this.request(`/chat/history/${conversationId}`);
  }

  async clearChatHistory(conversationId = 'default') {
    return this.request(`/chat/history/${conversationId}`, { method: 'DELETE' });
  }
}

export default new ApiClient(API_BASE_URL);

