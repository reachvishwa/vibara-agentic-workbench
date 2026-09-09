import React, { useState, useRef, useEffect } from 'react';
import 'katex/dist/katex.min.css';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import rehypeHighlight from 'rehype-highlight';

import 'highlight.js/styles/github-dark.css';

import {
  Plus, Menu, X, Settings, Trash2, Edit2, Send, Copy, Check,
  Search, Download, Moon, Sun, Paperclip, Zap, AlertCircle, Loader, FileText,
  ChevronDown, ChevronRight, SlidersHorizontal
} from 'lucide-react';

//const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000/api';
const API_BASE_URL = (import.meta as ImportMeta & { env?: { REACT_APP_API_URL?: string } }).env?.REACT_APP_API_URL || 'http://localhost:8000/api';
// ============================================================================
// TYPES
// ============================================================================

interface Message {
  id: number;
  conversation_id: number;
  role: 'user' | 'assistant';
  content: string;
  created_at: string;
}

interface Conversation {
  id: number;
  name: string;
  created_at: string;
  updated_at: string;
  messages?: Message[];
}

interface Settings {
  api_key?: string;
  default_model: string;
  temperature: string;
  max_tokens: number;
  system_prompt: string;
  theme: string;
}

interface Model {
  id: string;
  name: string;
  provider: string;
  description?: string;
  multimodal?: boolean;
}

// ============================================================================
// API CLIENT
// ============================================================================

const apiClient = {
  async getConversations(): Promise<Conversation[]> {
    const res = await fetch(`${API_BASE_URL}/conversations`);
    if (!res.ok) throw new Error('Failed to fetch conversations');
    return res.json();
  },

  async createConversation(name: string): Promise<Conversation> {
    const res = await fetch(`${API_BASE_URL}/conversations`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name })
    });
    if (!res.ok) throw new Error('Failed to create conversation');
    return res.json();
  },

  async getConversation(id: number): Promise<Conversation> {
    const res = await fetch(`${API_BASE_URL}/conversations/${id}`);
    if (!res.ok) throw new Error('Failed to fetch conversation');
    return res.json();
  },

  async updateConversation(id: number, name: string): Promise<Conversation> {
    const res = await fetch(`${API_BASE_URL}/conversations/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name })
    });
    if (!res.ok) throw new Error('Failed to update conversation');
    return res.json();
  },

  async deleteConversation(id: number): Promise<void> {
    const res = await fetch(`${API_BASE_URL}/conversations/${id}`, { method: 'DELETE' });
    if (!res.ok) throw new Error('Failed to delete conversation');
  },

  async clearConversationMessages(id: number): Promise<void> {
    const res = await fetch(`${API_BASE_URL}/conversations/${id}/messages`, { method: 'DELETE' });
    if (!res.ok) throw new Error('Failed to clear conversation');
  },

  async connectPowerBIMCP(): Promise<{ connected: boolean; tool_count: number; tools: string[] }> {
    const res = await fetch(`${API_BASE_URL}/mcp/powerbi/connect`, { method: 'POST' });
    if (!res.ok) throw new Error('Failed to connect to Power BI MCP server');
    return res.json();
  },

  async disconnectPowerBIMCP(): Promise<void> {
    await fetch(`${API_BASE_URL}/mcp/powerbi/disconnect`, { method: 'POST' });
  },

  async getPowerBIMCPStatus(): Promise<{ connected: boolean; tool_count: number; tools: string[] }> {
    const res = await fetch(`${API_BASE_URL}/mcp/powerbi/status`);
    if (!res.ok) throw new Error('Failed to get MCP status');
    return res.json();
  },

  async connectFilesystemMCP(): Promise<{ connected: boolean; tool_count: number; tools: string[] }> {
    const res = await fetch(`${API_BASE_URL}/mcp/filesystem/connect`, { method: 'POST' });
    if (!res.ok) throw new Error('Failed to connect to Filesystem MCP server');
    return res.json();
  },

  async disconnectFilesystemMCP(): Promise<void> {
    await fetch(`${API_BASE_URL}/mcp/filesystem/disconnect`, { method: 'POST' });
  },

  async getFilesystemMCPStatus(): Promise<{ connected: boolean; tool_count: number; tools: string[] }> {
    const res = await fetch(`${API_BASE_URL}/mcp/filesystem/status`);
    if (!res.ok) throw new Error('Failed to get Filesystem MCP status');
    return res.json();
  },

  async connectDuckDBMCP(): Promise<{ connected: boolean; tool_count: number; tools: string[] }> {
    const res = await fetch(`${API_BASE_URL}/mcp/duckdb/connect`, { method: 'POST' });
    if (!res.ok) throw new Error('Failed to connect to DuckDB MCP server');
    return res.json();
  },

  async disconnectDuckDBMCP(): Promise<void> {
    await fetch(`${API_BASE_URL}/mcp/duckdb/disconnect`, { method: 'POST' });
  },

  async getDuckDBMCPStatus(): Promise<{ connected: boolean; tool_count: number; tools: string[] }> {
    const res = await fetch(`${API_BASE_URL}/mcp/duckdb/status`);
    if (!res.ok) throw new Error('Failed to get DuckDB MCP status');
    return res.json();
  },

  async connectAccessMCP(): Promise<{ connected: boolean; tool_count: number; tools: string[] }> {
    const res = await fetch(`${API_BASE_URL}/mcp/access/connect`, { method: 'POST' });
    if (!res.ok) throw new Error('Failed to connect to Access MCP server');
    return res.json();
  },

  async disconnectAccessMCP(): Promise<void> {
    await fetch(`${API_BASE_URL}/mcp/access/disconnect`, { method: 'POST' });
  },

  async getAccessMCPStatus(): Promise<{ connected: boolean; tool_count: number; tools: string[] }> {
    const res = await fetch(`${API_BASE_URL}/mcp/access/status`);
    if (!res.ok) throw new Error('Failed to get Access MCP status');
    return res.json();
  },

  async connectNativeTools(): Promise<{ connected: boolean; tool_count: number; tools: string[] }> {
    const res = await fetch(`${API_BASE_URL}/tools/native/connect`, { method: 'POST' });
    if (!res.ok) throw new Error('Failed to enable native tools');
    return res.json();
  },

  async disconnectNativeTools(): Promise<void> {
    await fetch(`${API_BASE_URL}/tools/native/disconnect`, { method: 'POST' });
  },

  async getNativeToolsStatus(): Promise<{ connected: boolean; tool_count: number; tools: string[] }> {
    const res = await fetch(`${API_BASE_URL}/tools/native/status`);
    if (!res.ok) throw new Error('Failed to get native tools status');
    return res.json();
  },

  async sendMessage(conversationId: number, message: string, model: string, temperature: number, maxTokens: number, image?: { data: string; media_type: string } | null, document?: { data: string; filename: string; media_type: string } | null, useMcp?: boolean): Promise<ReadableStream<Uint8Array> | null> {
    const res = await fetch(`${API_BASE_URL}/chat/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        conversation_id: conversationId,
        message,
        model,
        temperature,
        max_tokens: maxTokens,
        ...(image ? { image } : {}),
        ...(document ? { document } : {}),
        ...(useMcp ? { use_mcp: true } : {})
      })
    });
    if (!res.ok) throw new Error('Failed to send message');
    return res.body;
  },

  async getSettings(): Promise<Settings> {
    const res = await fetch(`${API_BASE_URL}/settings`);
    if (!res.ok) throw new Error('Failed to fetch settings');
    return res.json();
  },

  async updateSettings(settings: Partial<Settings>): Promise<Settings> {
    const res = await fetch(`${API_BASE_URL}/settings`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(settings)
    });
    if (!res.ok) throw new Error('Failed to update settings');
    return res.json();
  },

  async getModels(): Promise<Model[]> {
    const res = await fetch(`${API_BASE_URL}/models`);
    if (!res.ok) throw new Error('Failed to fetch models');
    return res.json();
  }
};

// ============================================================================
// COMPONENTS
// ============================================================================

export default function NvidiaLLMChat() {
  const [isDarkMode, setIsDarkMode] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [chatOptionsOpen, setChatOptionsOpen] = useState(false);
  const [currentChat, setCurrentChat] = useState<number | null>(null);
  const [showSettings, setShowSettings] = useState(false);
  const [settingsTab, setSettingsTab] = useState('api');
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [chatMessages, setChatMessages] = useState<{ [key: number]: Message[] }>({});
  const [copiedCode, setCopiedCode] = useState<number | null>(null);
  const [editingConvId, setEditingConvId] = useState<number | null>(null);
  const [editingName, setEditingName] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [apiKey, setApiKey] = useState('');
  const [selectedModel, setSelectedModel] = useState('nvidia/nemotron-3-ultra-550b-a55b');
  const [temperature, setTemperature] = useState(0.3);
  const [maxTokens, setMaxTokens] = useState(32000);
  const [mcpEnabled, setMcpEnabled] = useState(false);
  const [powerbiConnected, setPowerbiConnected] = useState(false);
  const [powerbiConnecting, setPowerbiConnecting] = useState(false);
  const [powerbiToolCount, setPowerbiToolCount] = useState(0);
  const [fsConnected, setFsConnected] = useState(false);
  const [fsConnecting, setFsConnecting] = useState(false);
  const [fsToolCount, setFsToolCount] = useState(0);
  const [duckdbConnected, setDuckdbConnected] = useState(false);
  const [duckdbConnecting, setDuckdbConnecting] = useState(false);
  const [duckdbToolCount, setDuckdbToolCount] = useState(0);
  const [accessConnected, setAccessConnected] = useState(false);
  const [accessConnecting, setAccessConnecting] = useState(false);
  const [accessToolCount, setAccessToolCount] = useState(0);
  const [bashConnected, setBashConnected] = useState(false);
  const [bashConnecting, setBashConnecting] = useState(false);
  const [bashToolCount, setBashToolCount] = useState(0);
  const [systemPrompt, setSystemPrompt] = useState('You are a helpful AI assistant.');
  const [message, setMessage] = useState('');
  const [models, setModels] = useState<Model[]>([]);
  const [isStreamingMessage, setIsStreamingMessage] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Load initial data
  useEffect(() => {
    loadConversations();
    loadSettings();
    loadModels();
  }, []);

  const loadConversations = async () => {
    try {
      const data = await apiClient.getConversations();
      setConversations(data);
      if (data.length > 0 && !currentChat) {
        setCurrentChat(data[0].id);
        await loadConversation(data[0].id);
      }
    } catch (err) {
      setError('Failed to load conversations');
      console.error(err);
    }
  };

  const loadConversation = async (id: number) => {
    try {
      const data = await apiClient.getConversation(id);
      setChatMessages(prev => ({
        ...prev,
        [id]: data.messages || []
      }));
    } catch (err) {
      setError('Failed to load conversation');
      console.error(err);
    }
  };

  const loadSettings = async () => {
    try {
      const data = await apiClient.getSettings();
      setApiKey(data.api_key || '');
      setSelectedModel(data.default_model);
      setTemperature(parseFloat(data.temperature));
      setMaxTokens(data.max_tokens);
      setSystemPrompt(data.system_prompt);
    } catch (err) {
      console.error('Failed to load settings:', err);
    }
  };

  const loadModels = async () => {
    try {
      const data = await apiClient.getModels();
      setModels(data);
      const hasCurrentModel = data.some(model => model.id === selectedModel);
      if (!hasCurrentModel && data.length > 0) {
        setSelectedModel(data[0].id);
      }
    } catch (err) {
      console.error('Failed to load models:', err);
    }
  };

  const handleNewChat = async () => {
    try {
      const newConv = await apiClient.createConversation(`New Chat ${Date.now()}`);
      setConversations([...conversations, newConv]);
      setCurrentChat(newConv.id);
      setChatMessages(prev => ({ ...prev, [newConv.id]: [] }));
    } catch (err) {
      setError('Failed to create conversation');
      console.error(err);
    }
  };

  const handleSelectChat = async (id: number) => {
    setCurrentChat(id);
    if (!chatMessages[id]) {
      await loadConversation(id);
    }
  };

  const handleDeleteChat = async (id: number) => {
    try {
      await apiClient.deleteConversation(id);
      setConversations(conversations.filter(c => c.id !== id));
      const newMessages = { ...chatMessages };
      delete newMessages[id];
      setChatMessages(newMessages);
      if (currentChat === id) {
        setCurrentChat(conversations.length > 1 ? conversations[0].id : null);
      }
    } catch (err) {
      setError('Failed to delete conversation');
      console.error(err);
    }
  };

  const handleRenameChat = async (id: number, newName: string) => {
    if (!newName.trim()) return;
    try {
      const updated = await apiClient.updateConversation(id, newName);
      setConversations(conversations.map(c => c.id === id ? updated : c));
      setEditingConvId(null);
    } catch (err) {
      setError('Failed to rename conversation');
      console.error(err);
    }
  };

const handleSendMessage = async () => {
    const activeChatId = currentChat;
    if (activeChatId === null) return;
    if (!message.trim() && !selectedFile) return;

    setIsStreamingMessage(true);
    setError(null);

    try {
      // Add user message to UI
      const userMsg: Message = {
        id: Date.now(),
        conversation_id: activeChatId,
        role: 'user',
        content: message,
        created_at: new Date().toISOString()
      };

      setChatMessages(prev => ({
        ...prev,
        [activeChatId]: [...(prev[activeChatId] || []), userMsg]
      }));
      
      setMessage('');

      const IMAGE_EXTENSIONS = ['.png', '.jpg', '.jpeg', '.gif', '.webp'];
      const isImageFile = selectedFile && (
        selectedFile.type.startsWith('image/') ||
        IMAGE_EXTENSIONS.some(ext => selectedFile.name.toLowerCase().endsWith(ext))
      );

      if (selectedFile && isImageFile) {
        // Image upload: read to base64 and send as vision content (multimodal models only)
        const dataUrl: string = await new Promise((resolve, reject) => {
          const reader = new FileReader();
          reader.onload = (e) => resolve(e.target?.result as string);
          reader.onerror = reject;
          reader.readAsDataURL(selectedFile);
        });
        const [prefix, base64Data] = dataUrl.split(',');
        const mediaTypeMatch = prefix.match(/data:(.*);base64/);
        const mediaType = mediaTypeMatch ? mediaTypeMatch[1] : (selectedFile.type || 'image/png');

        setSelectedFile(null);
        await sendToAPI(message, { data: base64Data, media_type: mediaType }, null);
        return;
      }

      if (selectedFile && !isImageFile) {
        // Document upload (PDF, CSV, XLSX, TXT): send as base64, backend extracts text
        const dataUrl: string = await new Promise((resolve, reject) => {
          const reader = new FileReader();
          reader.onload = (e) => resolve(e.target?.result as string);
          reader.onerror = reject;
          reader.readAsDataURL(selectedFile);
        });
        const [prefix, base64Data] = dataUrl.split(',');
        const mediaTypeMatch = prefix.match(/data:(.*);base64/);
        const mediaType = mediaTypeMatch ? mediaTypeMatch[1] : (selectedFile.type || 'application/octet-stream');

        const fileName = selectedFile.name;
        setSelectedFile(null);
        await sendToAPI(message, null, { data: base64Data, filename: fileName, media_type: mediaType });
        return;
      }

      // Send without any attachment
      await sendToAPI(message, null, null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to send message');
      console.error(err);
    } finally {
      setIsStreamingMessage(false);
    }
  };

  const sendToAPI = async (
    finalMessage: string,
    image: { data: string; media_type: string } | null,
    document: { data: string; filename: string; media_type: string } | null
  ) => {
    const activeChatId = currentChat;
    if (activeChatId === null) return;

    try {
      const stream = await apiClient.sendMessage(
        activeChatId,
        finalMessage,
        selectedModel,
        temperature,
        maxTokens,
        image,
        document,
        mcpEnabled
      );

      if (!stream) throw new Error('No stream received');

      const reader = stream.getReader();
      const decoder = new TextDecoder();
      let fullResponse = '';
      let assistantMsgId = Date.now();
      let eventBuffer = '';

      const normalizeChunkText = (chunk: unknown): string => {
        if (typeof chunk === 'string') return chunk;
        if (typeof chunk === 'number' || typeof chunk === 'boolean' || chunk === null) return String(chunk);
        if (Array.isArray(chunk)) return chunk.map(normalizeChunkText).join('');
        if (chunk && typeof chunk === 'object') {
          const record = chunk as Record<string, unknown>;
          if (typeof record.content === 'string') return record.content;
          if (typeof record.text === 'string') return record.text;
          if (record.delta && typeof (record.delta as Record<string, unknown>).content === 'string') {
            return (record.delta as Record<string, unknown>).content as string;
          }
          if (record.message && typeof (record.message as Record<string, unknown>).content === 'string') {
            return (record.message as Record<string, unknown>).content as string;
          }
        }
        return '';
      };

      const processPayload = (payload: string) => {
        const trimmed = payload.trim();
        if (!trimmed || trimmed === '[DONE]') return;

        try {
          const data = JSON.parse(trimmed);
          const chunkText = normalizeChunkText(data.chunk ?? data);
          if (chunkText) {
            fullResponse += chunkText;
            setChatMessages(prev => ({
              ...prev,
              [activeChatId]: prev[activeChatId].map((msg: Message) =>
                msg.id === assistantMsgId
                  ? { ...msg, content: fullResponse }
                  : msg
              )
            }));
          } else if (data.error) {
            throw new Error(data.error);
          }
        } catch (e) {
          if (e instanceof SyntaxError) {
            if (trimmed) {
              fullResponse += trimmed;
              setChatMessages(prev => ({
                ...prev,
                [activeChatId]: prev[activeChatId].map((msg: Message) =>
                  msg.id === assistantMsgId
                    ? { ...msg, content: fullResponse }
                    : msg
                )
              }));
            }
            return;
          }
          throw e;
        }
      };

      const processEventBuffer = (buffer: string) => {
        const parts = buffer.split(/\r?\n\r?\n/);
        const remainder = parts.pop() ?? '';

        for (const eventBlock of parts) {
          const lines = eventBlock.split(/\r?\n/);
          let payload = '';

          for (const line of lines) {
            if (line.startsWith('data:')) {
              payload += line.slice(5).trimStart();
            }
          }

          if (payload) {
            processPayload(payload);
          }
        }

        return remainder;
      };

      setChatMessages(prev => ({
        ...prev,
        [activeChatId]: [...(prev[activeChatId] || []), {
          id: assistantMsgId,
          conversation_id: activeChatId,
          role: 'assistant',
          content: '',
          created_at: new Date().toISOString()
        }]
      }));

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        eventBuffer += decoder.decode(value, { stream: true });
        eventBuffer = processEventBuffer(eventBuffer);
      }

      if (eventBuffer.trim()) {
        processPayload(eventBuffer.trim());
      }

      setConversations(prev =>
        prev.map(c =>
          c.id === activeChatId
            ? { ...c, updated_at: new Date().toISOString() }
            : c
        )
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to send message');
      console.error(err);
    }
  };
  
  const handleCopyCode = (text: string, id: number) => {
    navigator.clipboard.writeText(text);
    setCopiedCode(id);
    setTimeout(() => setCopiedCode(null), 2000);
  };

  const handleExportConversation = () => {
    if (!currentChat) return;
    const conv = conversations.find(c => c.id === currentChat);
    const messages = chatMessages[currentChat] || [];
    const data = { conversation: conv, messages };
    const json = JSON.stringify(data, null, 2);
    const blob = new Blob([json], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${conv?.name.replace(/\s+/g, '_')}_${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleClearConversation = async () => {
    if (!currentChat) return;
    if (!window.confirm('Clear all messages in this chat? This cannot be undone.')) return;
    try {
      await apiClient.clearConversationMessages(currentChat);
      setChatMessages(prev => ({ ...prev, [currentChat]: [] }));
    } catch (err) {
      setError('Failed to clear conversation');
      console.error(err);
    }
  };

  const handleTogglePowerbiConnection = async () => {
    if (powerbiConnected) {
      await apiClient.disconnectPowerBIMCP();
      setPowerbiConnected(false);
      setPowerbiToolCount(0);
      return;
    }
    setPowerbiConnecting(true);
    try {
      const result = await apiClient.connectPowerBIMCP();
      setPowerbiConnected(result.connected);
      setPowerbiToolCount(result.tool_count);
    } catch (err) {
      setError('Failed to connect to Power BI MCP server. Make sure the path is correct and Power BI Desktop or a PBIP is open.');
      console.error(err);
    } finally {
      setPowerbiConnecting(false);
    }
  };

  const handleToggleFilesystemConnection = async () => {
    if (fsConnected) {
      await apiClient.disconnectFilesystemMCP();
      setFsConnected(false);
      setFsToolCount(0);
      return;
    }
    setFsConnecting(true);
    try {
      const result = await apiClient.connectFilesystemMCP();
      setFsConnected(result.connected);
      setFsToolCount(result.tool_count);
    } catch (err) {
      setError('Failed to connect to Filesystem MCP server. Make sure Node.js/npx is installed.');
      console.error(err);
    } finally {
      setFsConnecting(false);
    }
  };

  const handleToggleDuckDBConnection = async () => {
    if (duckdbConnected) {
      await apiClient.disconnectDuckDBMCP();
      setDuckdbConnected(false);
      setDuckdbToolCount(0);
      return;
    }
    setDuckdbConnecting(true);
    try {
      const result = await apiClient.connectDuckDBMCP();
      setDuckdbConnected(result.connected);
      setDuckdbToolCount(result.tool_count);
    } catch (err) {
      setError('Failed to connect to DuckDB MCP server. Make sure uv/uvx is installed.');
      console.error(err);
    } finally {
      setDuckdbConnecting(false);
    }
  };

  const handleToggleAccessConnection = async () => {
    if (accessConnected) {
      await apiClient.disconnectAccessMCP();
      setAccessConnected(false);
      setAccessToolCount(0);
      return;
    }
    setAccessConnecting(true);
    try {
      const result = await apiClient.connectAccessMCP();
      setAccessConnected(result.connected);
      setAccessToolCount(result.tool_count);
    } catch (err) {
      setError('Failed to connect to Access MCP server. Make sure pyodbc is installed and the Access driver is available.');
      console.error(err);
    } finally {
      setAccessConnecting(false);
    }
  };

  const handleToggleBashTools = async () => {
    if (bashConnected) {
      await apiClient.disconnectNativeTools();
      setBashConnected(false);
      setBashToolCount(0);
      return;
    }
    setBashConnecting(true);
    try {
      const result = await apiClient.connectNativeTools();
      setBashConnected(result.connected);
      setBashToolCount(result.tool_count);
    } catch (err) {
      setError('Failed to enable native tools (bash).');
      console.error(err);
    } finally {
      setBashConnecting(false);
    }
  };

  const handleSaveSettings = async () => {
    try {
      await apiClient.updateSettings({
        api_key: apiKey,
        default_model: selectedModel,
        temperature: temperature.toString(),
        max_tokens: maxTokens,
        system_prompt: systemPrompt,
        theme: isDarkMode ? 'dark' : 'light'
      });
      setShowSettings(false);
      setError(null);
    } catch (err) {
      setError('Failed to save settings');
      console.error(err);
    }
  };

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [chatMessages, currentChat]);

  const filteredConversations = conversations.filter(c =>
    c.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const bgClass = isDarkMode ? 'bg-slate-900 text-slate-100' : 'bg-white text-slate-900';
  const sideBgClass = isDarkMode ? 'bg-slate-950 border-slate-800' : 'bg-slate-50 border-slate-200';
  const inputBgClass = isDarkMode ? 'bg-slate-800 border-slate-700' : 'bg-slate-100 border-slate-300';
  const hoverClass = isDarkMode ? 'hover:bg-slate-800' : 'hover:bg-slate-100';
  const buttonHoverClass = isDarkMode ? 'hover:bg-slate-700' : 'hover:bg-slate-200';
  const accentClass = isDarkMode ? 'text-blue-400' : 'text-blue-600';
  const messageBgClass = isDarkMode ? 'bg-slate-800' : 'bg-slate-100';

  return (
    <div className={`flex h-screen ${bgClass} font-sans`}>
      {/* Sidebar */}
      <div className={`${sidebarOpen ? 'w-64' : 'w-0'} transition-all duration-300 ${sideBgClass} border-r flex flex-col overflow-hidden`}>
        {/* New Chat Button */}
        <div className={`p-4 border-b ${isDarkMode ? 'border-slate-800' : 'border-slate-200'}`}>
          <button
            onClick={handleNewChat}
            className={`w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg ${isDarkMode ? 'bg-blue-600 hover:bg-blue-700' : 'bg-blue-500 hover:bg-blue-600'} text-white font-medium transition-colors`}
          >
            <Plus size={18} />
            New Chat
          </button>
        </div>

        {/* Search */}
        <div className={`px-4 pt-4 pb-2`}>
          <div className={`flex items-center gap-2 px-3 py-2 rounded-lg ${inputBgClass} border`}>
            <Search size={16} className={`${isDarkMode ? 'text-slate-400' : 'text-slate-500'}`} />
            <input
              type="text"
              placeholder="Search..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className={`flex-1 bg-transparent outline-none text-sm ${isDarkMode ? 'placeholder-slate-500' : 'placeholder-slate-400'}`}
            />
          </div>
        </div>

        {/* Conversations List */}
        <div className="flex-1 overflow-y-auto">
          <div className="space-y-1 px-3 py-2">
            {filteredConversations.length === 0 ? (
              <div className={`px-3 py-8 text-center ${isDarkMode ? 'text-slate-400' : 'text-slate-500'} text-sm`}>
                No conversations
              </div>
            ) : (
              filteredConversations.map(conv => (
                <div key={conv.id} className="group">
                  {editingConvId === conv.id ? (
                    <input
                      type="text"
                      value={editingName}
                      onChange={(e) => setEditingName(e.target.value)}
                      onBlur={() => handleRenameChat(conv.id, editingName)}
                      onKeyPress={(e) => e.key === 'Enter' && handleRenameChat(conv.id, editingName)}
                      autoFocus
                      className={`w-full px-3 py-2 rounded-lg ${inputBgClass} border outline-none text-sm`}
                    />
                  ) : (
                    <div
                      onClick={() => handleSelectChat(conv.id)}
                      className={`flex items-center justify-between px-3 py-2.5 rounded-lg cursor-pointer transition-colors ${currentChat === conv.id ? (isDarkMode ? 'bg-slate-700' : 'bg-slate-200') : hoverClass}`}
                    >
                      <span className="flex-1 text-sm truncate">{conv.name}</span>
                      <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setEditingConvId(conv.id);
                            setEditingName(conv.name);
                          }}
                          className={`p-1.5 rounded ${buttonHoverClass} transition-colors`}
                        >
                          <Edit2 size={14} />
                        </button>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleDeleteChat(conv.id);
                          }}
                          className={`p-1.5 rounded ${buttonHoverClass} transition-colors text-red-400`}
                        >
                          <Trash2 size={14} />
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              ))
            )}
          </div>
        </div>

        {/* Chat Options (collapsible): Model, Temperature, Max Tokens, Power BI MCP */}
        <div className={`border-t ${isDarkMode ? 'border-slate-800' : 'border-slate-200'}`}>
          <button
            onClick={() => setChatOptionsOpen(!chatOptionsOpen)}
            className={`w-full flex items-center justify-between px-4 py-3 text-sm font-medium ${hoverClass} transition-colors`}
          >
            <span className="flex items-center gap-2">
              <SlidersHorizontal size={16} />
              Chat Options
            </span>
            {chatOptionsOpen ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
          </button>
          {chatOptionsOpen && (
            <div className="px-4 pb-4 space-y-3 text-xs max-h-96 overflow-y-auto">
              <div>
                <label className={`block mb-1 font-medium ${accentClass}`}>Model</label>
                <select
                  value={selectedModel}
                  onChange={(e) => setSelectedModel(e.target.value)}
                  className={`w-full px-2 py-1.5 rounded ${inputBgClass} border outline-none text-sm`}
                >
                  {models.map(m => (
                    <option key={m.id} value={m.id} className={isDarkMode ? 'bg-slate-800' : 'bg-white'}>
                      {m.provider}: {m.name}{m.multimodal ? ' 👁' : ''}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className={`block mb-1 font-medium ${accentClass}`}>
                  Temperature: {temperature.toFixed(2)}
                </label>
                <input
                  type="range"
                  min="0"
                  max="2"
                  step="0.1"
                  value={temperature}
                  onChange={(e) => setTemperature(parseFloat(e.target.value))}
                  className="w-full"
                />
              </div>
              <div>
                <label className={`block mb-1 font-medium ${accentClass}`}>Max Tokens</label>
                <input
                  type="number"
                  min="1"
                  max="1000000"
                  value={maxTokens}
                  onChange={(e) => setMaxTokens(parseInt(e.target.value))}
                  className={`w-full px-2 py-1.5 rounded ${inputBgClass} border outline-none text-sm`}
                />
              </div>

              {/* Power BI MCP Controls */}
              <div className={`rounded-lg p-3 border ${isDarkMode ? 'border-slate-700' : 'border-slate-300'}`}>
                <div className="flex items-center justify-between">
                  <span className={`font-medium ${accentClass}`}>Power BI (MCP)</span>
                  <button
                    onClick={handleTogglePowerbiConnection}
                    disabled={powerbiConnecting}
                    className={`px-2 py-1 rounded text-xs ${powerbiConnected ? 'bg-red-600 hover:bg-red-700' : 'bg-blue-600 hover:bg-blue-700'} text-white disabled:opacity-50`}
                  >
                    {powerbiConnecting ? 'Connecting...' : powerbiConnected ? 'Disconnect' : 'Connect'}
                  </button>
                </div>
                <div className="text-xs opacity-70 mt-1">
                  {powerbiConnected ? `Connected \u2014 ${powerbiToolCount} tools` : 'Not connected'}
                </div>
              </div>

              {/* Filesystem MCP Controls */}
              <div className={`rounded-lg p-3 border ${isDarkMode ? 'border-slate-700' : 'border-slate-300'}`}>
                <div className="flex items-center justify-between">
                  <span className={`font-medium ${accentClass}`}>Filesystem (MCP)</span>
                  <button
                    onClick={handleToggleFilesystemConnection}
                    disabled={fsConnecting}
                    className={`px-2 py-1 rounded text-xs ${fsConnected ? 'bg-red-600 hover:bg-red-700' : 'bg-blue-600 hover:bg-blue-700'} text-white disabled:opacity-50`}
                  >
                    {fsConnecting ? 'Connecting...' : fsConnected ? 'Disconnect' : 'Connect'}
                  </button>
                </div>
                <div className="text-xs opacity-70 mt-1">
                  {fsConnected ? `Connected \u2014 ${fsToolCount} tools` : 'Not connected'}
                </div>
              </div>

              {/* DuckDB MCP Controls */}
              <div className={`rounded-lg p-3 border ${isDarkMode ? 'border-slate-700' : 'border-slate-300'}`}>
                <div className="flex items-center justify-between">
                  <span className={`font-medium ${accentClass}`}>DuckDB (MCP)</span>
                  <button
                    onClick={handleToggleDuckDBConnection}
                    disabled={duckdbConnecting}
                    className={`px-2 py-1 rounded text-xs ${duckdbConnected ? 'bg-red-600 hover:bg-red-700' : 'bg-blue-600 hover:bg-blue-700'} text-white disabled:opacity-50`}
                  >
                    {duckdbConnecting ? 'Connecting...' : duckdbConnected ? 'Disconnect' : 'Connect'}
                  </button>
                </div>
                <div className="text-xs opacity-70 mt-1">
                  {duckdbConnected ? `Connected \u2014 ${duckdbToolCount} tools` : 'Not connected'}
                </div>
              </div>

              {/* MS Access MCP Controls */}
              <div className={`rounded-lg p-3 border ${isDarkMode ? 'border-slate-700' : 'border-slate-300'}`}>
                <div className="flex items-center justify-between">
                  <span className={`font-medium ${accentClass}`}>MS Access (MCP)</span>
                  <button
                    onClick={handleToggleAccessConnection}
                    disabled={accessConnecting}
                    className={`px-2 py-1 rounded text-xs ${accessConnected ? 'bg-red-600 hover:bg-red-700' : 'bg-blue-600 hover:bg-blue-700'} text-white disabled:opacity-50`}
                  >
                    {accessConnecting ? 'Connecting...' : accessConnected ? 'Disconnect' : 'Connect'}
                  </button>
                </div>
                <div className="text-xs opacity-70 mt-1">
                  {accessConnected ? `Connected \u2014 ${accessToolCount} tools` : 'Not connected'}
                </div>
              </div>

              {/* Native Tools (Bash + Web Search) Controls */}
              <div className={`rounded-lg p-3 border ${isDarkMode ? 'border-orange-700' : 'border-orange-300'}`}>
                <div className="flex items-center justify-between">
                  <span className={`font-medium ${accentClass}`}>Bash + Web Search (native)</span>
                  <button
                    onClick={handleToggleBashTools}
                    disabled={bashConnecting}
                    className={`px-2 py-1 rounded text-xs ${bashConnected ? 'bg-red-600 hover:bg-red-700' : 'bg-blue-600 hover:bg-blue-700'} text-white disabled:opacity-50`}
                  >
                    {bashConnecting ? 'Enabling...' : bashConnected ? 'Disable' : 'Enable'}
                  </button>
                </div>
                <div className="text-xs opacity-70 mt-1">
                  {bashConnected ? `Enabled \u2014 ${bashToolCount} tool(s)` : 'Disabled'}
                </div>
                <div className="text-xs opacity-60 mt-1">
                  Bash is sandboxed to one folder, allow-listed commands only. Web search via Tavily.
                </div>
              </div>

              {(powerbiConnected || fsConnected || duckdbConnected || accessConnected || bashConnected) && (
                <label className="flex items-center gap-2 text-xs cursor-pointer">
                  <input
                    type="checkbox"
                    checked={mcpEnabled}
                    onChange={(e) => setMcpEnabled(e.target.checked)}
                  />
                  Use connected MCP tools in this chat
                </label>
              )}
            </div>

          )}
        </div>

        {/* Bottom Actions */}
        <div className={`border-t ${isDarkMode ? 'border-slate-800' : 'border-slate-200'} p-4 space-y-2`}>
          <button
            onClick={() => setShowSettings(true)}
            className={`w-full flex items-center gap-3 px-4 py-2.5 rounded-lg ${hoverClass} transition-colors text-sm`}
          >
            <Settings size={18} />
            Settings
          </button>
          <button
            onClick={() => setIsDarkMode(!isDarkMode)}
            className={`w-full flex items-center gap-3 px-4 py-2.5 rounded-lg ${hoverClass} transition-colors text-sm`}
          >
            {isDarkMode ? <Sun size={18} /> : <Moon size={18} />}
            {isDarkMode ? 'Light' : 'Dark'}
          </button>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex flex-col">
        {/* Header */}
        <div className={`border-b ${isDarkMode ? 'border-slate-800' : 'border-slate-200'} px-4 py-4 flex items-center justify-between`}>
          <div className="flex items-center gap-4">
            <button
              onClick={() => setSidebarOpen(!sidebarOpen)}
              className={`p-2 rounded-lg ${buttonHoverClass} transition-colors`}
            >
              {sidebarOpen ? <X size={20} /> : <Menu size={20} />}
            </button>
            <div>
              <h1 className="font-semibold">
                {currentChat ? conversations.find(c => c.id === currentChat)?.name : 'Select a chat'}
              </h1>
              <p className={`text-xs ${isDarkMode ? 'text-slate-400' : 'text-slate-500'}`}>
                Model: {models.find(m => m.id === selectedModel)?.provider ? `${models.find(m => m.id === selectedModel)?.provider}: ${models.find(m => m.id === selectedModel)?.name}` : selectedModel}
              </p>
            </div>
          </div>
          {currentChat && (
            <div className="flex gap-1">
              <button
                onClick={handleClearConversation}
                className={`p-2 rounded-lg ${buttonHoverClass} transition-colors`}
                title="Clear conversation"
              >
                <Trash2 size={18} />
              </button>
              <button
                onClick={handleExportConversation}
                className={`p-2 rounded-lg ${buttonHoverClass} transition-colors`}
                title="Export conversation"
              >
                <Download size={18} />
              </button>
            </div>
          )}
        </div>

        {/* Error Alert */}
        {error && (
          <div className={`mx-4 mt-4 p-3 rounded-lg ${isDarkMode ? 'bg-red-900/20 border border-red-700' : 'bg-red-50 border border-red-200'} flex items-start gap-2`}>
            <AlertCircle size={18} className="text-red-500 mt-0.5" />
            <div className="flex-1">
              <p className={`text-sm ${isDarkMode ? 'text-red-200' : 'text-red-700'}`}>{error}</p>
            </div>
            <button
              onClick={() => setError(null)}
              className="text-red-500 hover:text-red-700"
            >
              <X size={16} />
            </button>
          </div>
        )}

        {/* Messages Area */}
        {currentChat ? (
          <div className="flex-1 overflow-y-auto px-4 py-6 space-y-4">
            {(chatMessages[currentChat] || []).map((msg) => (
              <MessageBubble
                key={msg.id}
                message={msg}
                isDarkMode={isDarkMode}
                onCopyCode={handleCopyCode}
                copiedCode={copiedCode}
              />
            ))}
            {isStreamingMessage && <TypingIndicator isDarkMode={isDarkMode} />}
            <div ref={messagesEndRef} />
          </div>
        ) : (
          <div className="flex-1 flex flex-col items-center justify-center text-center">
            <div className={`text-5xl mb-4 ${accentClass}`}>
              <Zap size={48} />
            </div>
            <h2 className="text-2xl font-semibold mb-2">No Chat Selected</h2>
            <p className={`${isDarkMode ? 'text-slate-400' : 'text-slate-500'} mb-6 max-w-sm`}>
              Create a new chat or select an existing conversation to start chatting with NVIDIA LLMs
            </p>
            <button
              onClick={handleNewChat}
              className={`px-6 py-2.5 rounded-lg ${isDarkMode ? 'bg-blue-600 hover:bg-blue-700' : 'bg-blue-500 hover:bg-blue-600'} text-white font-medium transition-colors`}
            >
              Create New Chat
            </button>
          </div>
        )}

        {/* Message Input */}
        {currentChat && (
          <div className={`border-t ${isDarkMode ? 'border-slate-800' : 'border-slate-200'} p-6`}>
            <div className="max-w-4xl mx-auto space-y-3">
              {/* Selected file preview */}
              {selectedFile && (
                <div className="flex items-center gap-2 mb-2">
                  {selectedFile.type.startsWith('image/') ? (
                    <img
                      src={URL.createObjectURL(selectedFile)}
                      alt="Selected attachment"
                      className="h-14 w-14 object-cover rounded border"
                    />
                  ) : (
                    <div className={`h-14 w-14 flex items-center justify-center rounded border ${inputBgClass}`}>
                      <FileText size={22} />
                    </div>
                  )}
                  <span className="text-xs opacity-70">{selectedFile.name}</span>
                  <button
                    onClick={() => setSelectedFile(null)}
                    className={`text-xs px-2 py-1 rounded ${buttonHoverClass}`}
                  >
                    Remove
                  </button>
                </div>
              )}

              {/* Message Input Box */}
              <div className={`flex gap-3`}>
                <div className={`flex-1 flex items-end gap-2 px-4 py-3 rounded-lg border ${inputBgClass}`}>
                  <input
                    type="file"
                    accept="image/*,.pdf,.csv,.xlsx,.xlsm,.txt,.md"
                    ref={fileInputRef}
                    className="hidden"
                    onChange={(e) => {
                      const file = e.target.files?.[0];
                      if (file) setSelectedFile(file);
                      e.target.value = '';
                    }}
                  />
                  <button
                    onClick={() => fileInputRef.current?.click()}
                    className={`p-2 rounded ${buttonHoverClass} transition-colors`}
                    title="Attach an image, PDF, CSV, or Excel file"
                  >
                    <Paperclip size={18} />
                  </button>
                  <textarea
                    value={message}
                    onChange={(e) => setMessage(e.target.value)}
                    onKeyPress={(e) => {
                      if (e.key === 'Enter' && !e.shiftKey) {
                        e.preventDefault();
                        handleSendMessage();
                      }
                    }}
                    placeholder="Type your message... (Shift+Enter for new line)"
                    className={`flex-1 bg-transparent outline-none resize-none max-h-32 text-sm`}
                    rows={1}
                    disabled={isStreamingMessage}
                  />
                </div>
                <button
                  onClick={handleSendMessage}
                  disabled={(!message.trim() && !selectedFile) || isStreamingMessage}
                  className={`p-3 rounded-lg ${isDarkMode ? 'bg-blue-600 hover:bg-blue-700 disabled:bg-slate-700' : 'bg-blue-500 hover:bg-blue-600 disabled:bg-slate-300'} text-white transition-colors disabled:cursor-not-allowed`}
                >
                  {isStreamingMessage ? <Loader size={18} className="animate-spin" /> : <Send size={18} />}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Settings Panel */}
      {showSettings && (
        <SettingsPanel
          isDarkMode={isDarkMode}
          settingsTab={settingsTab}
          setSettingsTab={setSettingsTab}
          apiKey={apiKey}
          setApiKey={setApiKey}
          selectedModel={selectedModel}
          setSelectedModel={setSelectedModel}
          models={models}
          systemPrompt={systemPrompt}
          setSystemPrompt={setSystemPrompt}
          onClose={() => setShowSettings(false)}
          onSave={handleSaveSettings}
          sideBgClass={sideBgClass}
          inputBgClass={inputBgClass}
          buttonHoverClass={buttonHoverClass}
          accentClass={accentClass}
        />
      )}
    </div>
  );
}

// ============================================================================
// MESSAGE BUBBLE COMPONENT
// ============================================================================

function MessageBubble({ message, isDarkMode, onCopyCode, copiedCode }: any) {
  const isAssistant = message.role === 'assistant';

  const extractText = (value: React.ReactNode): string => {
    if (typeof value === 'string' || typeof value === 'number') return String(value);
    if (Array.isArray(value)) return value.map(extractText).join('');
    if (value && typeof value === 'object' && 'props' in value) {
      const props = (value as { props?: { children?: React.ReactNode } }).props;
      return props?.children ? extractText(props.children) : '';
    }
    return '';
  };

  const bgClass = isAssistant
    ? (isDarkMode ? 'bg-slate-800' : 'bg-slate-100')
    : (isDarkMode ? 'bg-blue-900' : 'bg-blue-100');

  const textClass = isAssistant
    ? (isDarkMode ? 'text-slate-100' : 'text-slate-900')
    : (isDarkMode ? 'text-blue-100' : 'text-blue-900');

  const MarkdownRenderer = ReactMarkdown as React.ComponentType<any>;

  return (
    <div className={`flex ${isAssistant ? 'justify-start' : 'justify-end'}`}>
      <div className={`max-w-4xl rounded-lg px-4 py-3 ${bgClass} ${textClass}`}>
        <MarkdownRenderer
          remarkPlugins={[remarkGfm, remarkMath]}
          rehypePlugins={[rehypeKatex, rehypeHighlight]}
          components={{
            code({ inline, className, children, ...props }: any) {
              const match = /language-(\w+)/.exec(className || '');

              if (!inline) {
                const code = extractText(children).replace(/\n$/, '');

                return (
                  <CodeBlock
                    code={code}
                    language={match ? match[1] : 'text'}
                    isDarkMode={isDarkMode}
                    onCopy={() => onCopyCode(code, message.id)}
                    isCopied={copiedCode === message.id}
                  />
                );
              }

              return (
                <code
                  className="bg-slate-700 px-1 py-0.5 rounded text-sm"
                  {...props}
                >
                  {extractText(children)}
                </code>
              );
            },

            table({ children }: any) {
              return (
                <div className="overflow-x-auto my-4">
                  <table className="table-auto border-collapse border border-slate-600 w-full">
                    {children}
                  </table>
                </div>
              );
            },

            th({ children }: any) {
              return (
                <th className="border border-slate-600 px-3 py-2 text-left font-semibold">
                  {children}
                </th>
              );
            },

            td({ children }: any) {
              return (
                <td className="border border-slate-600 px-3 py-2">
                  {children}
                </td>
              );
            }
          }}
        >
          {message.content}
        </MarkdownRenderer>
      </div>
    </div>
  );
}
// ============================================================================
// CODE BLOCK COMPONENT
// ============================================================================

function CodeBlock({ code, language, isDarkMode, onCopy, isCopied }: any) {
  return (
    <div className={`my-2 rounded-lg overflow-hidden border ${isDarkMode ? 'border-slate-700 bg-slate-900' : 'border-slate-300 bg-slate-50'}`}>
      <div className={`flex items-center justify-between px-4 py-2 ${isDarkMode ? 'bg-slate-800' : 'bg-slate-200'}`}>
        <span className={`text-xs font-mono ${isDarkMode ? 'text-slate-400' : 'text-slate-600'}`}>{language}</span>
        <button
          onClick={onCopy}
          className={`flex items-center gap-1 text-xs px-2 py-1 rounded ${isDarkMode ? 'hover:bg-slate-700' : 'hover:bg-slate-300'} transition-colors`}
        >
          {isCopied ? (
            <>
              <Check size={14} /> Copied
            </>
          ) : (
            <>
              <Copy size={14} /> Copy
            </>
          )}
        </button>
      </div>
      <pre className={`p-4 overflow-x-auto text-sm font-mono`}>
        <code>{code}</code>
      </pre>
    </div>
  );
}

// ============================================================================
// TYPING INDICATOR COMPONENT
// ============================================================================

function TypingIndicator({ isDarkMode }: any) {
  return (
    <div className="flex gap-2 p-4">
      <div className={`w-2 h-2 rounded-full ${isDarkMode ? 'bg-slate-400' : 'bg-slate-500'} animate-bounce`} style={{ animationDelay: '0ms' }} />
      <div className={`w-2 h-2 rounded-full ${isDarkMode ? 'bg-slate-400' : 'bg-slate-500'} animate-bounce`} style={{ animationDelay: '150ms' }} />
      <div className={`w-2 h-2 rounded-full ${isDarkMode ? 'bg-slate-400' : 'bg-slate-500'} animate-bounce`} style={{ animationDelay: '300ms' }} />
    </div>
  );
}

// ============================================================================
// SETTINGS PANEL COMPONENT
// ============================================================================

function SettingsPanel({
  isDarkMode,
  settingsTab,
  setSettingsTab,
  apiKey,
  setApiKey,
  selectedModel,
  setSelectedModel,
  models,
  systemPrompt,
  setSystemPrompt,
  onClose,
  onSave,
  sideBgClass,
  inputBgClass,
  buttonHoverClass,
  accentClass
}: any) {
  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className={`${sideBgClass} rounded-lg shadow-2xl w-full max-w-2xl max-h-96 overflow-hidden flex flex-col border ${isDarkMode ? 'border-slate-700' : 'border-slate-300'}`}>
        {/* Header */}
        <div className={`flex items-center justify-between px-6 py-4 border-b ${isDarkMode ? 'border-slate-700' : 'border-slate-200'}`}>
          <h2 className="text-lg font-semibold">Settings</h2>
          <button onClick={onClose} className={`p-2 rounded-lg ${buttonHoverClass} transition-colors`}>
            <X size={20} />
          </button>
        </div>

        {/* Tabs */}
        <div className={`flex border-b ${isDarkMode ? 'border-slate-700' : 'border-slate-200'} px-6`}>
          {['api', 'model', 'prompt'].map(tab => (
            <button
              key={tab}
              onClick={() => setSettingsTab(tab)}
              className={`px-4 py-3 font-medium text-sm transition-colors ${settingsTab === tab ? (isDarkMode ? 'border-b-2 border-blue-500 text-blue-400' : 'border-b-2 border-blue-500 text-blue-600') : isDarkMode ? 'text-slate-400 hover:text-slate-300' : 'text-slate-600 hover:text-slate-700'}`}
            >
              {tab.charAt(0).toUpperCase() + tab.slice(1)}
            </button>
          ))}
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
          {settingsTab === 'api' && (
            <div>
              <label className={`block text-sm font-medium mb-2 ${accentClass}`}>
                NVIDIA API Key
              </label>
              <input
                type="password"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder="nvapi_..."
                className={`w-full px-3 py-2 rounded-lg ${inputBgClass} border outline-none text-sm`}
              />
              <p className={`text-xs mt-2 ${isDarkMode ? 'text-slate-400' : 'text-slate-600'}`}>
                Get your API key from the NVIDIA API console
              </p>
            </div>
          )}

          {settingsTab === 'model' && (
            <div>
              <label className={`block text-sm font-medium mb-2 ${accentClass}`}>
                Default Model
              </label>
              <select
                value={selectedModel}
                onChange={(e) => setSelectedModel(e.target.value)}
                className={`w-full px-3 py-2 rounded-lg ${inputBgClass} border outline-none text-sm`}
              >
                {models.map(m => (
                  <option key={m.id} value={m.id} className={isDarkMode ? 'bg-slate-800' : 'bg-white'}>
                    {m.provider}: {m.name}{m.multimodal ? ' 👁' : ''}
                  </option>
                ))}
              </select>
            </div>
          )}

          {settingsTab === 'prompt' && (
            <div>
              <label className={`block text-sm font-medium mb-2 ${accentClass}`}>
                System Prompt
              </label>
              <textarea
                value={systemPrompt}
                onChange={(e) => setSystemPrompt(e.target.value)}
                className={`w-full px-3 py-2 rounded-lg ${inputBgClass} border outline-none text-sm resize-none h-24`}
              />
            </div>
          )}
        </div>

        {/* Footer */}
        <div className={`border-t ${isDarkMode ? 'border-slate-700' : 'border-slate-200'} px-6 py-4 flex justify-end gap-3`}>
          <button
            onClick={onClose}
            className={`px-4 py-2 rounded-lg ${buttonHoverClass} transition-colors text-sm font-medium`}
          >
            Close
          </button>
          <button
            onClick={onSave}
            className={`px-4 py-2 rounded-lg ${isDarkMode ? 'bg-blue-600 hover:bg-blue-700' : 'bg-blue-500 hover:bg-blue-600'} text-white text-sm font-medium transition-colors`}
          >
            Save Settings
          </button>
        </div>
      </div>
    </div>
  );
}
