"use client";
import { useState, useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkBreaks from 'remark-breaks';
import remarkGfm from 'remark-gfm';
import rehypeRaw from 'rehype-raw';
import rehypeSanitize from 'rehype-sanitize';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { materialDark } from 'react-syntax-highlighter/dist/esm/styles/prism';
import ConversationHistory from '../components/conversationHistory';

interface Message {
  content: string;
  isUser: boolean;
  isStreaming?: boolean;
}

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([
    { 
      content: "Hello! How can I help you today?", 
      isUser: false,
      isStreaming: false
    }
  ]);
  const [inputMessage, setInputMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [conversations, setConversations] = useState<any[]>([]);
  const [selectedConversation, setSelectedConversation] = useState<number | null>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    const fetchConversations = async () => {
      try {
        const response = await fetch('http://localhost:8000/conversations');
        const data = await response.json();
        setConversations(Array.isArray(data) ? data : []);
      } catch (error) {
        console.error('Error fetching conversations:', error);
        setConversations([]);
      }
    };
    
    fetchConversations();
  }, []);

  const loadConversation = (conversationId: number) => {
    fetch(`http://localhost:8000/conversations/${conversationId}/messages`)
      .then(res => res.json())
      .then(messages => {
        setMessages(messages.map((msg: any) => ({
          content: msg.text
            .replace(/^(\n|\r)+/, '') // Remove leading newlines
            .trimStart(), // Trim leading whitespace
          isUser: msg.is_user,
          isStreaming: msg.is_ai ? false : undefined
        })));
        setSelectedConversation(conversationId);
      });
  };

  const handleSubmit = async (e?: React.FormEvent) => {
    e?.preventDefault();
    if (!inputMessage.trim() || isLoading) return;

    // Add user message FIRST
    setMessages(prev => [...prev, { content: inputMessage, isUser: true }]);
    
    // Then add AI response placeholder
    setMessages(prev => [...prev, { content: '', isUser: false, isStreaming: true }]);
    
    setInputMessage('');
    setIsLoading(true);

    try {
      const response = await fetch('http://localhost:8000/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          query: inputMessage,
          conversation_id: selectedConversation 
        }),
      });

      if (!response.body) throw new Error('No response body');
      
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let aiResponse = '';
      let buffer = '';
      let thinking = true;
      let newConversationId: number | null = null;

      // Add initial AI message with streaming state
      setMessages(prev => [...prev, { content: '', isUser: false, isStreaming: true }]);

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });
        
        // Check for conversation ID in initial chunk
        if (!selectedConversation && chunk.includes('id: ')) {
          const idPart = chunk.split('\n\n')[0];
          const convoId = parseInt(idPart.split(': ')[1], 10);
          setSelectedConversation(convoId);
          
          // Add the new conversation to the list immediately
          setConversations(prev => [
            { id: convoId, topic: inputMessage.substring(0, 50) },
            ...prev
          ]);

          // Process remaining chunk after ID
          const remainingChunk = chunk.split('\n\n').slice(1).join('\n\n');
          buffer += remainingChunk;
          continue;
        }

        // Decode and process the chunk
        if (chunk.includes("</think>") && thinking) {
          thinking = false;
          aiResponse = "";
          buffer = "";
        }
        
        if (thinking) {
          aiResponse = "Thinking...";
          
          // Update the last message with properly formatted markdown
          setMessages(prev => {
            const newMessages = [...prev];
            const lastMessage = newMessages[newMessages.length - 1];
            lastMessage.content = "*" + aiResponse + "*";
            return newMessages;
          });

          continue;
        } else {
          buffer += chunk;
        }

        // Remove </think>
        const cleanChunk = buffer.replace(/<\/think>/, '');

        if (cleanChunk) {
          aiResponse += cleanChunk;
          
          // Update the last message with properly formatted markdown
          setMessages(prev => {
            const newMessages = [...prev];
            const lastMessage = newMessages[newMessages.length - 1];
            
            // Trim leading newlines and whitespace
            const cleanedContent = aiResponse
              .replace(/^(\n|\r)+/, '') // Remove leading newlines
              .replace(/(\\n)/g, '\n')
              .trimStart();

            lastMessage.content = cleanedContent;
            return newMessages;
          });
        }
        buffer = '';
      }

      // Flush any remaining data and mark streaming complete
      const finalChunk = decoder.decode();
      if (finalChunk) {
        aiResponse += finalChunk;
      }

      // Final cleanup and streaming state update
      setMessages(prev => {
        const newMessages = [...prev];
        const lastMessage = newMessages[newMessages.length - 1];
        if (!lastMessage.isUser) {
          lastMessage.content = aiResponse
            .replace(/(\\n)/g, '\n')
            .replace(/^(\n|\r)+/, '')
            .trimStart();
          lastMessage.isStreaming = false;
        }
        return newMessages;
      });

      // After streaming, update conversations list
      if (newConversationId) {
        fetch('http://localhost:8000/conversations')
          .then(res => res.json())
          .then(data => setConversations(data || []));
      }

    } catch (error) {
      console.error('Error:', error);
      setMessages(prev => [...prev, { 
        content: 'Error: Could not get response', 
        isUser: false 
      }]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleNewConversation = () => {
    setMessages([{ 
      content: "Hello! How can I help you today?", 
      isUser: false,
      isStreaming: false 
    }]);
    setSelectedConversation(null);
    // Force refresh conversations list
    fetch('http://localhost:8000/conversations')
      .then(res => res.json())
      .then(data => setConversations(data || []));
  };

  // Add delete handler
  const handleDeleteConversation = async (conversationId: number) => {
    try {
      await fetch(`http://localhost:8000/conversations/${conversationId}`, {
        method: 'DELETE',
      });
      setConversations(prev => prev.filter(c => c.id !== conversationId));
      if (selectedConversation === conversationId) {
        setMessages([{ content: "Hello! How can I help you today?", isUser: false }]);
        setSelectedConversation(null);
      }
    } catch (error) {
      console.error('Error deleting conversation:', error);
    }
  };

  return (
    <div className="flex flex-row h-screen bg-neutral-950 text-neutral-200">
      {/* History panel */}
      <ConversationHistory 
        conversations={conversations}
        selectedConversation={selectedConversation}
        onConversationLoad={loadConversation}
        onNewConversation={handleNewConversation}
        onConversationDelete={handleDeleteConversation}
      />

      {/* Main chat container */}
      <div className="flex-1 flex flex-col p-4">
        <div className="flex-1 overflow-y-auto pr-2">
          <div className="space-y-4 max-w-6xl mx-auto" id="chat-container">
            {messages.map((message, index) => {
              if (message.content === '' && message.isStreaming) return null;
              
              return (
                <div 
                  key={`${index}-${message.content.substring(0,10)}`}
                  className={`flex justify-${message.isUser ? 'end' : 'start'}`}
                >
                  <div style={{ whiteSpace: 'pre-line' }} className={`text-neutral-200 rounded-lg p-3 max-w-[60%] ${
                    message.isUser ? 'bg-neutral-800 ml-auto' : 'bg-neutral-900'
                  } ${message.isStreaming ? 'animate-pulse' : ''}`}>
                    <ReactMarkdown
                      children={message.content}
                      remarkPlugins={[remarkGfm]}
                      rehypePlugins={[rehypeRaw, rehypeSanitize]}
                      components={{
                        code({ node, inline, className, children, ...props }) {
                          const match = /language-(\w+)/.exec(className || '');
                          return !inline && match ? (
                            <SyntaxHighlighter
                              style={materialDark}
                              language={match[1]}
                              PreTag="div"
                              {...props}
                            >
                              {String(children).replace(/\n$/, '')}
                            </SyntaxHighlighter>
                          ) : (
                            <code className={className} {...props}>
                              {children}
                            </code>
                          );
                        },
                      }}>
                    </ReactMarkdown>
                  </div>
                </div>
              )
            })}
            <div ref={messagesEndRef} />
          </div>
        </div>

        {/* Input area */}
        <div className="border-neutral-700 pt-4">
          <div className="max-w-6xl mx-auto">
            <form onSubmit={handleSubmit} className="flex gap-2">
              <input
                type="text"
                value={inputMessage}
                onChange={(e) => setInputMessage(e.target.value)}
                placeholder="Type your message..."
                className="flex-1 border border-neutral-700 rounded-lg p-2 bg-neutral-900 focus:outline-none focus:ring-2 focus:ring-neutral-600 placeholder-neutral-500"
                disabled={isLoading}
              />
              <button
                type="submit"
                disabled={isLoading}
                className={`px-4 py-2 rounded-lg transition-colors ${
                  isLoading 
                    ? 'bg-neutral-600 cursor-not-allowed' 
                    : 'bg-neutral-700 hover:bg-neutral-600'
                }`}
              >
                {isLoading ? 'Sending...' : 'Send'}
              </button>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
}
