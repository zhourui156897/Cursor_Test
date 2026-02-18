import { useState, useRef, useEffect } from 'react';
import { Send, MessageSquare, Plus, Trash2, FileText, Bot, BookOpen, Wrench } from 'lucide-react';
import { chatApi, type ChatResponse, type Conversation } from '../api/client';

type ChatMode = 'rag' | 'agent';

interface ToolCall {
  tool: string;
  arguments: Record<string, unknown>;
  result_preview?: string;
}

interface DisplayMessage {
  role: string;
  content: string;
  sources?: { index: number; entity_id: string; title: string; source: string }[];
  toolCalls?: ToolCall[];
}

export default function Chat() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeConvId, setActiveConvId] = useState<string | null>(null);
  const [messages, setMessages] = useState<DisplayMessage[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [mode, setMode] = useState<ChatMode>('rag');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => { loadConversations(); }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const loadConversations = async () => {
    try {
      const list = await chatApi.listConversations();
      setConversations(list);
    } catch { /* ignore */ }
  };

  const selectConversation = async (id: string) => {
    setActiveConvId(id);
    try {
      const msgs = await chatApi.getMessages(id);
      setMessages(msgs.map(m => ({
        role: m.role,
        content: m.content,
        sources: m.sources || undefined,
      })));
    } catch { /* ignore */ }
  };

  const startNew = () => {
    setActiveConvId(null);
    setMessages([]);
  };

  const deleteConv = async (id: string) => {
    try {
      await chatApi.deleteConversation(id);
      if (activeConvId === id) startNew();
      loadConversations();
    } catch { /* ignore */ }
  };

  const sendMessage = async () => {
    if (!input.trim() || loading) return;
    const userMsg = input.trim();
    setInput('');
    setMessages(prev => [...prev, { role: 'user', content: userMsg }]);
    setLoading(true);

    try {
      const resp: ChatResponse = await chatApi.send(userMsg, activeConvId || undefined, mode);
      if (!activeConvId) setActiveConvId(resp.conversation_id);
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: resp.answer,
        sources: resp.sources,
        toolCalls: resp.tool_calls as ToolCall[],
      }]);
      loadConversations();
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : '发送失败';
      setMessages(prev => [...prev, { role: 'assistant', content: `错误: ${msg}` }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex h-[calc(100vh-64px)] -m-6">
      {/* Sidebar */}
      <div className="w-64 bg-gray-50 border-r flex flex-col">
        <div className="p-3">
          <button onClick={startNew} className="w-full flex items-center gap-2 px-3 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-sm">
            <Plus className="w-4 h-4" /> 新对话
          </button>
        </div>
        <div className="flex-1 overflow-y-auto">
          {conversations.map(c => (
            <div
              key={c.id}
              onClick={() => selectConversation(c.id)}
              className={`flex items-center justify-between px-3 py-2 cursor-pointer text-sm hover:bg-gray-100 group ${activeConvId === c.id ? 'bg-blue-50 text-blue-700' : 'text-gray-700'}`}
            >
              <div className="flex items-center gap-2 flex-1 min-w-0">
                <MessageSquare className="w-3.5 h-3.5 flex-shrink-0" />
                <span className="truncate">{c.title}</span>
              </div>
              <button
                onClick={e => { e.stopPropagation(); deleteConv(c.id); }}
                className="opacity-0 group-hover:opacity-100 p-1 hover:text-red-500"
              >
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* Chat Area */}
      <div className="flex-1 flex flex-col">
        {/* Mode Selector */}
        <div className="border-b px-6 py-2 flex items-center gap-4">
          <span className="text-xs text-gray-500">模式:</span>
          <button
            onClick={() => setMode('rag')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
              mode === 'rag' ? 'bg-blue-100 text-blue-700' : 'text-gray-500 hover:bg-gray-100'
            }`}
          >
            <BookOpen className="w-3.5 h-3.5" /> RAG 问答
          </button>
          <button
            onClick={() => setMode('agent')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
              mode === 'agent' ? 'bg-purple-100 text-purple-700' : 'text-gray-500 hover:bg-gray-100'
            }`}
          >
            <Bot className="w-3.5 h-3.5" /> Agent 智能体
          </button>
          <span className="text-xs text-gray-400 ml-2">
            {mode === 'rag' ? '基于知识库检索回答' : '自主调用工具完成复杂任务'}
          </span>
        </div>

        <div className="flex-1 overflow-y-auto p-6 space-y-4">
          {messages.length === 0 && (
            <div className="flex flex-col items-center justify-center h-full text-gray-400">
              {mode === 'rag' ? (
                <>
                  <BookOpen className="w-16 h-16 mb-4" />
                  <h2 className="text-xl font-semibold mb-2">RAG 知识问答</h2>
                  <p className="text-sm">基于你的知识库进行语义检索和智能回答</p>
                </>
              ) : (
                <>
                  <Bot className="w-16 h-16 mb-4" />
                  <h2 className="text-xl font-semibold mb-2">Agent 智能体</h2>
                  <p className="text-sm mb-4">可以搜索、创建笔记、打标签、查图谱、生成摘要</p>
                  <div className="grid grid-cols-2 gap-2 text-xs">
                    {[
                      '帮我搜索关于投资的笔记',
                      '知识库有多少条数据？',
                      '总结一下我最近的待办事项',
                      '创建一条关于会议纪要的笔记',
                    ].map((hint, i) => (
                      <button
                        key={i}
                        onClick={() => setInput(hint)}
                        className="px-3 py-2 bg-gray-100 hover:bg-gray-200 rounded-lg text-gray-600 text-left"
                      >
                        {hint}
                      </button>
                    ))}
                  </div>
                </>
              )}
            </div>
          )}
          {messages.map((m, i) => (
            <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              <div className={`max-w-[75%] rounded-2xl px-4 py-3 ${m.role === 'user' ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-900'}`}>
                {/* Tool calls */}
                {m.toolCalls && m.toolCalls.length > 0 && (
                  <div className="mb-3 space-y-1.5">
                    {m.toolCalls.map((tc, j) => (
                      <div key={j} className="flex items-center gap-1.5 text-xs bg-purple-50 text-purple-700 px-2.5 py-1.5 rounded-lg">
                        <Wrench className="w-3 h-3" />
                        <span className="font-medium">{tc.tool}</span>
                        <span className="text-purple-400">({Object.values(tc.arguments).join(', ')})</span>
                      </div>
                    ))}
                  </div>
                )}
                <div className="whitespace-pre-wrap text-sm">{m.content}</div>
                {m.sources && m.sources.length > 0 && (
                  <div className="mt-3 pt-2 border-t border-gray-200 space-y-1">
                    <div className="text-xs text-gray-500 font-medium">引用来源:</div>
                    {m.sources.map(s => (
                      <div key={s.index} className="flex items-center gap-1.5 text-xs text-gray-600">
                        <FileText className="w-3 h-3" />
                        <span>[{s.index}] {s.title}</span>
                        <span className="text-gray-400">({s.source})</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ))}
          {loading && (
            <div className="flex justify-start">
              <div className="bg-gray-100 rounded-2xl px-4 py-3">
                <div className="flex items-center gap-2">
                  <div className="flex gap-1">
                    <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                    <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                    <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                  </div>
                  <span className="text-xs text-gray-400">
                    {mode === 'agent' ? 'Agent 正在思考和调用工具...' : '正在检索和生成回答...'}
                  </span>
                </div>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        <div className="border-t p-4">
          <div className="flex gap-3 max-w-4xl mx-auto">
            <input
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && !e.shiftKey && sendMessage()}
              placeholder={mode === 'agent' ? '让 Agent 帮你完成任务...' : '向第二大脑提问...'}
              className="flex-1 px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              disabled={loading}
            />
            <button
              onClick={sendMessage}
              disabled={loading || !input.trim()}
              className={`px-5 py-3 text-white rounded-xl disabled:opacity-50 ${
                mode === 'agent' ? 'bg-purple-600 hover:bg-purple-700' : 'bg-blue-600 hover:bg-blue-700'
              }`}
            >
              <Send className="w-5 h-5" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
