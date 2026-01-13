import React, { useState, useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import './App.css';
import api from './api';

function App() {
  const [messages, setMessages] = useState([]);
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [currentAnswer, setCurrentAnswer] = useState('');
  const [statusMessage, setStatusMessage] = useState('');
  const [authenticated, setAuthenticated] = useState(false);
  const [indexing, setIndexing] = useState(false);
  const [indexingStatus, setIndexingStatus] = useState('');
  const [indexed, setIndexed] = useState(false);
  const [stats, setStats] = useState(null);
  const [error, setError] = useState('');
  const [conversationId] = useState('default');
  const messagesEndRef = useRef(null);
  const chatContainerRef = useRef(null);

  useEffect(() => {
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('authenticated') === 'true') {
      setAuthenticated(true);
      window.history.replaceState({}, document.title, '/');
    }
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, currentAnswer]);

  const scrollToBottom = () => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  };

  const handleAuthenticate = async () => {
    try {
      setError('');
      const response = await api.getAuthorizationUrl();
      window.location.href = response.authorization_url;
    } catch (err) {
      setError(`Authentication error: ${err.message}`);
    }
  };

  const handleIndexDocuments = async () => {
    setIndexing(true);
    setError('');
    setIndexingStatus('Starting indexing...');
    
    try {
      await api.indexDocumentsStream(
        (message) => {
          setIndexingStatus(message);
        },
        (data) => {
          setIndexed(true);
          setStats(data.stats);
          setIndexingStatus(`Successfully indexed ${data.indexed} document(s)`);
          setTimeout(() => setIndexingStatus(''), 3000);
        },
        (err) => {
          setError(`Indexing error: ${err.message}`);
          setIndexingStatus('');
        }
      );
    } catch (err) {
      setError(`Indexing error: ${err.message}`);
      setIndexingStatus('');
    } finally {
      setIndexing(false);
    }
  };

  const handleClearChat = async () => {
    try {
      await api.clearChatHistory(conversationId);
      setMessages([]);
      setCurrentAnswer('');
    } catch (err) {
      // Ignore errors
    }
  };

  const handleSearch = async (e) => {
    e.preventDefault();
    if (!query.trim()) {
      setError('Please enter a search query');
      return;
    }

    const userMessage = query.trim();
    setQuery('');
    setLoading(true);
    setError('');
    setStatusMessage('');
    setCurrentAnswer('');
    
    // Add user message to chat
    const newUserMessage = {
      role: 'user',
      content: userMessage,
      timestamp: new Date()
    };
    setMessages(prev => [...prev, newUserMessage]);

    try {
      let assistantMessage = {
        role: 'assistant',
        content: '',
        citations: [],
        sources: [],
        timestamp: new Date()
      };

      await api.searchStream(
        userMessage,
        conversationId,
        (text, type) => {
          if (type === 'status') {
            setStatusMessage(text);
          } else if (type === 'answer') {
            setCurrentAnswer(prev => prev + text);
            assistantMessage.content = assistantMessage.content + text;
          }
        },
        (data) => {
          assistantMessage.content = data.text;
          assistantMessage.citations = data.citations || [];
          assistantMessage.sources = data.sources || [];
          
          // Add complete assistant message to chat
          setMessages(prev => [...prev, assistantMessage]);
          setCurrentAnswer('');
          setStatusMessage('');
          setLoading(false);
        },
        (err) => {
          setError(`Search error: ${err.message}`);
          setLoading(false);
          setCurrentAnswer('');
          setStatusMessage('');
        }
      );
    } catch (err) {
      setError(`Search error: ${err.message}`);
      setLoading(false);
      setCurrentAnswer('');
      setStatusMessage('');
    }
  };

  const renderMessage = (message, index) => {
    if (message.role === 'user') {
      return (
        <div key={index} className="message user-message">
          <div className="message-content">
            <div className="message-text">{message.content}</div>
          </div>
        </div>
      );
    } else {
      return (
        <div key={index} className="message assistant-message">
          <div className="message-content">
            <div className="message-text markdown-content">
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                  // Handle text nodes to convert [1] patterns to citations
                  text: ({ node, children, ...props }) => {
                    const text = String(children);
                    // Match [1], [2], etc. patterns
                    const citationPattern = /\[(\d+)\]/g;
                    const parts = [];
                    let lastIndex = 0;
                    let match;
                    
                    while ((match = citationPattern.exec(text)) !== null) {
                      // Add text before citation
                      if (match.index > lastIndex) {
                        parts.push(text.substring(lastIndex, match.index));
                      }
                      
                      // Add citation badge
                      const citationNum = match[1];
                      const citation = message.citations?.find(c => c.number === parseInt(citationNum));
                      const webUrl = citation?.web_url || `https://drive.google.com/file/d/${citation?.document_id || ''}/view`;
                      
                      parts.push(
                        <sup key={`citation-${match.index}`} className="citation-marker">
                          <a
                            href={webUrl}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="citation-link"
                            title={citation?.document_name || `Source ${citationNum}`}
                          >
                            {citationNum}
                          </a>
                        </sup>
                      );
                      
                      lastIndex = match.index + match[0].length;
                    }
                    
                    // Add remaining text
                    if (lastIndex < text.length) {
                      parts.push(text.substring(lastIndex));
                    }
                    
                    return parts.length > 0 ? <>{parts}</> : <>{children}</>;
                  },
                  // Handle markdown links (for [[1]](url) format)
                  a: ({ node, href, children, ...props }) => {
                    const linkText = children?.[0]?.toString() || '';
                    // Match both [[1]] and [1] patterns in links
                    const citationMatch = linkText.match(/\[\[?(\d+)\]\]?/);
                    if (citationMatch) {
                      const citationNum = citationMatch[1];
                      const citation = message.citations?.find(c => c.number === parseInt(citationNum));
                      return (
                        <sup className="citation-marker">
                          <a
                            href={href}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="citation-link"
                            title={citation?.document_name || `Source ${citationNum}`}
                            {...props}
                          >
                            {citationNum}
                          </a>
                        </sup>
                      );
                    }
                    return (
                      <a href={href} target="_blank" rel="noopener noreferrer" {...props}>
                        {children}
                      </a>
                    );
                  },
                }}
              >
                {message.content}
              </ReactMarkdown>
            </div>
            {(message.sources?.length > 0 || message.citations?.length > 0) && (
              <div className="message-sources">
                {message.sources?.length > 0 && (
                  <div className="sources-list">
                    <div className="sources-header">Sources:</div>
                    <div className="sources-items">
                      {message.sources.map((source, idx) => (
                        <a
                          key={idx}
                          href={source.web_url || `https://drive.google.com/file/d/${source.document_id}/view`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="source-item"
                        >
                          <span className="source-name">{source.document_name}</span>
                          <span className="source-icon">↗</span>
                        </a>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      );
    }
  };

  return (
    <div className="App">
      <div className="app-container">
        {!authenticated ? (
          <div className="auth-screen">
            <div className="auth-card">
              <h1>Enterprise Search</h1>
              <p>AI-powered search across your documents</p>
              <button className="btn btn-primary" onClick={handleAuthenticate}>
                Connect Google Drive
              </button>
              {error && <div className="error-message">{error}</div>}
            </div>
          </div>
        ) : (
          <div className="chat-container">
            <header className="chat-header">
              <div className="header-content">
                <h1>Enterprise Search</h1>
                {stats && (
                  <div className="header-stats">
                    <span>{stats.total_documents} docs</span>
                    <span className="divider">•</span>
                    <span>{stats.total_chunks} chunks</span>
                  </div>
                )}
              </div>
              {messages.length > 0 && (
                <button className="btn-clear" onClick={handleClearChat} title="Clear chat">
                  Clear
                </button>
              )}
            </header>

            {!indexed && (
              <div className="setup-banner">
                <div className="setup-content">
                  <div>
                    <h3>Index Documents</h3>
                    <p>Index your Google Drive PDF documents to enable search</p>
                    {indexingStatus && (
                      <div className="indexing-status">
                        <div className="spinner-small"></div>
                        <span>{indexingStatus}</span>
                      </div>
                    )}
                  </div>
                  <button
                    className="btn btn-secondary"
                    onClick={handleIndexDocuments}
                    disabled={indexing}
                  >
                    {indexing ? 'Indexing...' : 'Index Documents'}
                  </button>
                </div>
              </div>
            )}

            <div className="chat-messages" ref={chatContainerRef}>
              {messages.length === 0 && indexed && (
                <div className="welcome-message">
                  <h2>Ask anything about your documents</h2>
                  <p>Start a conversation to search through your indexed documents</p>
                </div>
              )}
              
              {messages.map((message, index) => renderMessage(message, index))}
              
              {loading && (
                <div className="message assistant-message">
                  <div className="message-content">
                    {statusMessage && (
                      <div className="status-message">{statusMessage}</div>
                    )}
                    {currentAnswer && (
                      <div className="message-text markdown-content">
                        <ReactMarkdown
                          remarkPlugins={[remarkGfm]}
                          components={{
                            // Handle text nodes to convert [1] patterns to citations
                            text: ({ node, children, ...props }) => {
                              const text = String(children);
                              // Match [1], [2], etc. patterns
                              const citationPattern = /\[(\d+)\]/g;
                              const parts = [];
                              let lastIndex = 0;
                              let match;
                              
                              while ((match = citationPattern.exec(text)) !== null) {
                                // Add text before citation
                                if (match.index > lastIndex) {
                                  parts.push(text.substring(lastIndex, match.index));
                                }
                                
                                // Add citation badge (without link for streaming)
                                const citationNum = match[1];
                                parts.push(
                                  <sup key={`citation-${match.index}`} className="citation-marker">
                                    <span className="citation-link citation-placeholder">
                                      {citationNum}
                                    </span>
                                  </sup>
                                );
                                
                                lastIndex = match.index + match[0].length;
                              }
                              
                              // Add remaining text
                              if (lastIndex < text.length) {
                                parts.push(text.substring(lastIndex));
                              }
                              
                              return parts.length > 0 ? <>{parts}</> : <>{children}</>;
                            },
                            // Handle markdown links
                            a: ({ node, href, children, ...props }) => {
                              const linkText = children?.[0]?.toString() || '';
                              const citationMatch = linkText.match(/\[\[?(\d+)\]\]?/);
                              if (citationMatch) {
                                const citationNum = citationMatch[1];
                                return (
                                  <sup className="citation-marker">
                                    <span className="citation-link citation-placeholder">
                                      {citationNum}
                                    </span>
                                  </sup>
                                );
                              }
                              return (
                                <a href={href} target="_blank" rel="noopener noreferrer" {...props}>
                                  {children}
                                </a>
                              );
                            },
                          }}
                        >
                          {currentAnswer}
                        </ReactMarkdown>
                      </div>
                    )}
                    {!currentAnswer && !statusMessage && (
                      <div className="message-text">
                        <span className="typing-indicator">
                          <span></span><span></span><span></span>
                        </span>
                      </div>
                    )}
                  </div>
                </div>
              )}
              
              <div ref={messagesEndRef} />
            </div>

            {error && (
              <div className="error-banner">
                {error}
              </div>
            )}

            <div className="chat-input-container">
              <form onSubmit={handleSearch} className="chat-input-form">
                <input
                  type="text"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Ask a question about your documents..."
                  className="chat-input"
                  disabled={loading || !indexed}
                />
                <button
                  type="submit"
                  className="btn-send"
                  disabled={loading || !indexed || !query.trim()}
                >
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <line x1="22" y1="2" x2="11" y2="13"></line>
                    <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
                  </svg>
                </button>
              </form>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default App;
