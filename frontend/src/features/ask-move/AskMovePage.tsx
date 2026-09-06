import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { api } from '../../services/api';
import { Send, Bot, User } from 'lucide-react';

const markdownComponents = {
  p: ({ children }: any) => <p className="mb-2 last:mb-0">{children}</p>,
  strong: ({ children }: any) => <strong className="font-semibold text-gray-900">{children}</strong>,
  h1: ({ children }: any) => <h3 className="text-sm font-bold text-gray-900 mt-3 mb-1.5 first:mt-0">{children}</h3>,
  h2: ({ children }: any) => <h3 className="text-sm font-bold text-gray-900 mt-3 mb-1.5 first:mt-0">{children}</h3>,
  h3: ({ children }: any) => <h4 className="text-sm font-bold text-gray-900 mt-2 mb-1 first:mt-0">{children}</h4>,
  ul: ({ children }: any) => <ul className="list-disc pl-5 space-y-1 mb-2">{children}</ul>,
  ol: ({ children }: any) => <ol className="list-decimal pl-5 space-y-1 mb-2">{children}</ol>,
  li: ({ children }: any) => <li>{children}</li>,
  code: ({ children }: any) => <code className="bg-gray-200 rounded px-1 py-0.5 text-xs font-mono">{children}</code>,
  table: ({ children }: any) => (
    <div className="overflow-x-auto mb-2">
      <table className="min-w-full text-xs border border-gray-200">{children}</table>
    </div>
  ),
  thead: ({ children }: any) => <thead className="bg-gray-100">{children}</thead>,
  th: ({ children }: any) => <th className="px-2 py-1 text-left font-semibold border-b border-gray-200">{children}</th>,
  td: ({ children }: any) => <td className="px-2 py-1 border-b border-gray-100">{children}</td>,
};

export default function AskMovePage() {
  const [query, setQuery] = useState('');
  const [messages, setMessages] = useState<Array<{role: 'user'|'ai', text: string}>>([
    { role: 'ai', text: 'Hello! I am MoveIQ Assistant. How can I help you analyze today\'s operational readiness?' }
  ]);
  const [loading, setLoading] = useState(false);

  const handleSend = async () => {
    if (!query.trim()) return;
    const q = query;
    setMessages(prev => [...prev, { role: 'user', text: q }]);
    setQuery('');
    setLoading(true);
    
    try {
      const res = await api.askMove(q);
      setMessages(prev => [...prev, { role: 'ai', text: res.answer }]);
    } catch (e) {
      setMessages(prev => [...prev, { role: 'ai', text: 'Sorry, I encountered an error answering your question.' }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto h-[calc(100vh-6rem)] flex flex-col bg-white rounded-xl border border-gray-200 shadow-sm">
      <div className="p-4 border-b border-gray-200 bg-gray-50 rounded-t-xl">
        <h2 className="text-lg font-bold text-gray-900">Ask MoveIQ</h2>
        <p className="text-sm text-gray-500">Natural language operational analysis</p>
      </div>
      
      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        {messages.map((msg, i) => (
          <div key={i} className={`flex gap-4 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            {msg.role === 'ai' && (
              <div className="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center flex-shrink-0">
                <Bot className="w-5 h-5 text-blue-600" />
              </div>
            )}
            <div className={`px-4 py-3 rounded-lg max-w-[80%] text-sm ${
              msg.role === 'user' ? 'bg-blue-600 text-white rounded-br-none' : 'bg-gray-100 text-gray-900 rounded-bl-none'
            }`}>
              {msg.role === 'ai' ? (
                <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
                  {msg.text}
                </ReactMarkdown>
              ) : (
                msg.text
              )}
            </div>
            {msg.role === 'user' && (
              <div className="w-8 h-8 rounded-full bg-gray-200 flex items-center justify-center flex-shrink-0">
                <User className="w-5 h-5 text-gray-600" />
              </div>
            )}
          </div>
        ))}
        {loading && (
          <div className="flex gap-4">
            <div className="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center">
              <Bot className="w-5 h-5 text-blue-600" />
            </div>
            <div className="px-4 py-3 rounded-lg bg-gray-100 text-gray-500 flex items-center gap-2">
              <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"></div>
              <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{animationDelay: '150ms'}}></div>
              <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{animationDelay: '300ms'}}></div>
            </div>
          </div>
        )}
      </div>

      <div className="p-4 border-t border-gray-200 bg-white rounded-b-xl">
        <div className="flex gap-2">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSend()}
            placeholder="Ask about shifts, risks, or decisions..."
            className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <button
            onClick={handleSend}
            disabled={loading || !query.trim()}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
          >
            <Send className="w-4 h-4" /> Send
          </button>
        </div>
      </div>
    </div>
  );
}
