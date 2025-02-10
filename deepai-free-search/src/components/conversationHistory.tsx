"use client";
import { useState, useEffect } from 'react';

interface Conversation {
  id: number;
  topic: string;
}

interface ConversationHistoryProps {
  conversations: Conversation[];
  selectedConversation: number | null;
  onConversationLoad: (id: number) => void;
  onNewConversation: () => void;
  onConversationDelete: (id: number) => void;
}

export default function ConversationHistory({
  conversations,
  selectedConversation,
  onConversationLoad,
  onNewConversation,
  onConversationDelete
}: ConversationHistoryProps) {
  // Local state for animation control
  const [isFirstLoad, setIsFirstLoad] = useState(true);
  
  // Animation effect for initial load
  useEffect(() => {
    if (conversations.length > 0 && isFirstLoad) {
      setIsFirstLoad(false);
      const timer = setTimeout(() => {
        // Trigger animation logic here if needed
      }, 500);
      return () => clearTimeout(timer);
    }
  }, [conversations, isFirstLoad]);

  // Memoized conversation items with virtualization would go here
  // For now we'll use basic mapping for simplicity
  
  return (
    <div className="w-128 bg-neutral-900 border-neutral-800 flex flex-col h-full">
      <div className="p-10 pb-0 flex justify-between items-center border-b border-neutral-800">
        <h2 className="text-lg font-semibold text-neutral-200">Conversation History</h2>
        <button
          onClick={onNewConversation}
          className="p-2 rounded hover:bg-neutral-900 text-neutral-400 hover:text-neutral-200 transition-colors duration-200"
          aria-label="Start new conversation"
        >
          <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 24 24" fill="currentColor">
            <path d="M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z"/>
          </svg>
        </button>
      </div>
      
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        <div>
          <h3 className="text-xs text-neutral-500 uppercase mb-2">Recent Chats</h3>
          <div className="space-y-2">
            {conversations.map(convo => (
              <div 
                key={convo.id}
                className={`group relative flex justify-between items-center p-2 rounded-lg hover:bg-neutral-900 cursor-pointer transition-all duration-200 ${
                  selectedConversation === convo.id 
                    ? 'bg-neutral-900 shadow-inner border border-neutral-800' 
                    : 'text-neutral-400 hover:text-neutral-200'
                }`}
              >
                <div 
                  onClick={() => onConversationLoad(convo.id)}
                  className="flex-1 truncate pr-4"
                >
                  {convo.topic}
                </div>
                
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    onConversationDelete(convo.id);
                  }}
                  className="absolute right-2 top-1/2 -translate-y-1/2 p-1 rounded hover:bg-neutral-700 text-red-400 hover:text-red-300 opacity-0 group-hover:opacity-100 transition-opacity duration-200"
                  aria-label={`Delete conversation ${convo.topic}`}
                >
                  <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z"/>
                  </svg>
                </button>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
