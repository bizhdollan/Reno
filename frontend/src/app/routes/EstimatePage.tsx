import { useState, useRef, useEffect, useMemo } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Image, Send, X, Paperclip } from "lucide-react";

// Types
interface Message {
  role: "user" | "assistant";
  content: string | MessagePart[];
  timestamp: string;
}

interface MessagePart {
  type: "text" | "image_url";
  text?: string;
  image_url?: { url: string };
}

interface ProjectState {
  current_stage: string;
  project_title?: string;
  project_type?: string;
  zip_code?: string;
  images?: any[];
  materials?: any[];
  measurements?: any;
  estimate?: any;
  messages?: any[];
  [key: string]: any;
}

// Stage configuration
const STAGES = [
  { key: "project_basics", label: "Project Info" },
  { key: "visual_collection", label: "Images" },
  { key: "material_verification", label: "Materials" },
  { key: "measurement_verification", label: "Measurements" },
  { key: "final_review", label: "Review" },
  { key: "cost_estimation", label: "Estimate" },
  { key: "completed", label: "Done" },
];

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api/v1";

// Utility: Convert File to base64 data URL
async function fileToDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result as string);
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

// Progress indicator component
function ProgressBar({ currentStage }: { currentStage: string }) {
  const currentIndex = STAGES.findIndex((s) => s.key === currentStage);
  const progress = Math.max(0, ((currentIndex + 1) / STAGES.length) * 100);

  return (
    <div className="w-full">
      <div className="flex items-center justify-between mb-1.5">
        <span className="text-xs font-medium text-gray-600">
          {STAGES[currentIndex]?.label || "Getting Started"}
        </span>
        <span className="text-xs text-gray-400">
          {currentIndex + 1} of {STAGES.length}
        </span>
      </div>
      <div className="h-1.5 bg-gray-200 rounded-full overflow-hidden">
        <div
          className="h-full bg-gradient-to-r from-blue-500 to-blue-600 rounded-full transition-all duration-500 ease-out"
          style={{ width: `${progress}%` }}
        />
      </div>
    </div>
  );
}

// Typing indicator component
function TypingIndicator() {
  return (
    <div className="flex items-center gap-1 text-gray-500 text-sm py-3">
      <span>Thinking</span>
      <span className="flex gap-0.5">
        <span className="animate-bounce" style={{ animationDelay: "0ms" }}>.</span>
        <span className="animate-bounce" style={{ animationDelay: "150ms" }}>.</span>
        <span className="animate-bounce" style={{ animationDelay: "300ms" }}>.</span>
      </span>
    </div>
  );
}

// Image preview component
function ImagePreview({
  files,
  onRemove,
}: {
  files: File[];
  onRemove: (index: number) => void;
}) {
  const [previews, setPreviews] = useState<string[]>([]);

  useEffect(() => {
    const loadPreviews = async () => {
      const urls = await Promise.all(files.map((f) => fileToDataUrl(f)));
      setPreviews(urls);
    };
    loadPreviews();
  }, [files]);

  if (files.length === 0) return null;

  return (
    <div className="flex gap-2 p-2 overflow-x-auto">
      {previews.map((url, idx) => (
        <div key={idx} className="relative flex-shrink-0 group">
          <img
            src={url}
            alt={`Preview ${idx + 1}`}
            className="h-16 w-16 object-cover rounded-lg border border-gray-200"
          />
          <button
            onClick={() => onRemove(idx)}
            className="absolute -top-1.5 -right-1.5 bg-gray-800 text-white rounded-full p-0.5 opacity-0 group-hover:opacity-100 transition-opacity"
          >
            <X size={12} />
          </button>
        </div>
      ))}
    </div>
  );
}

// Message bubble component
function MessageBubble({ message }: { message: Message }) {
  const isUser = message.role === "user";

  // Extract text content
  const textContent = useMemo(() => {
    if (typeof message.content === "string") {
      return message.content;
    }
    const textPart = message.content.find((p) => p.type === "text");
    return textPart?.text || "";
  }, [message.content]);

  // Extract images
  const images = useMemo(() => {
    if (typeof message.content === "string") return [];
    return message.content
      .filter((p) => p.type === "image_url")
      .map((p) => p.image_url?.url)
      .filter(Boolean) as string[];
  }, [message.content]);

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[85%] md:max-w-[75%] rounded-2xl px-4 py-3 ${
          isUser
            ? "bg-blue-600 text-white"
            : "bg-gray-100 text-gray-900"
        }`}
      >
        {/* Images */}
        {images.length > 0 && (
          <div className="flex flex-wrap gap-2 mb-2">
            {images.map((url, idx) => (
              <img
                key={idx}
                src={url}
                alt={`Uploaded ${idx + 1}`}
                className="max-h-40 rounded-lg object-cover"
              />
            ))}
          </div>
        )}

        {/* Text content */}
        {textContent && (
          <div
            className={`prose prose-sm max-w-none ${
              isUser
                ? "prose-invert"
                : "prose-gray"
            }`}
          >
            {isUser ? (
              <p className="m-0 whitespace-pre-wrap">{textContent}</p>
            ) : (
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                  // Custom table styling
                  table: ({ children }) => (
                    <div className="overflow-x-auto my-2">
                      <table className="min-w-full text-sm border-collapse">
                        {children}
                      </table>
                    </div>
                  ),
                  th: ({ children }) => (
                    <th className="border border-gray-300 bg-gray-50 px-3 py-1.5 text-left font-semibold">
                      {children}
                    </th>
                  ),
                  td: ({ children }) => (
                    <td className="border border-gray-300 px-3 py-1.5">
                      {children}
                    </td>
                  ),
                  // Headings
                  h1: ({ children }) => (
                    <h1 className="text-lg font-bold mt-3 mb-2">{children}</h1>
                  ),
                  h2: ({ children }) => (
                    <h2 className="text-base font-bold mt-3 mb-1.5">{children}</h2>
                  ),
                  h3: ({ children }) => (
                    <h3 className="text-sm font-semibold mt-2 mb-1">{children}</h3>
                  ),
                  // Lists
                  ul: ({ children }) => (
                    <ul className="list-disc list-inside my-1 space-y-0.5">{children}</ul>
                  ),
                  ol: ({ children }) => (
                    <ol className="list-decimal list-inside my-1 space-y-0.5">{children}</ol>
                  ),
                  // Paragraphs
                  p: ({ children }) => <p className="my-1.5">{children}</p>,
                  // Strong
                  strong: ({ children }) => (
                    <strong className="font-semibold">{children}</strong>
                  ),
                  // Code
                  code: ({ children }) => (
                    <code className="bg-gray-200 px-1 py-0.5 rounded text-xs font-mono">
                      {children}
                    </code>
                  ),
                }}
              >
                {textContent}
              </ReactMarkdown>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// Main chat page
export default function EstimatePage() {
  const projectId = useMemo(() => crypto.randomUUID(), []);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [pendingFiles, setPendingFiles] = useState<File[]>([]);
  const [projectState, setProjectState] = useState<ProjectState | null>(null);
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isSending]);

  // Auto-resize textarea
  useEffect(() => {
    const textarea = textareaRef.current;
    if (textarea) {
      textarea.style.height = "auto";
      textarea.style.height = `${Math.min(textarea.scrollHeight, 200)}px`;
    }
  }, [input]);

  // Auto-focus textarea after message is sent
  useEffect(() => {
    if (!isSending && messages.length > 0) {
      // Small delay to ensure DOM has updated and textarea is no longer disabled
      const timer = setTimeout(() => {
        textareaRef.current?.focus();
      }, 50);
      return () => clearTimeout(timer);
    }
  }, [isSending, messages.length]);

  // Send initial message to start conversation
  useEffect(() => {
    const startConversation = async () => {
      setIsSending(true);
      try {
        const res = await fetch(`${API_BASE}/chat`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            project_id: projectId,
            message: "Hi, I want to start a renovation project",
            state: null,
          }),
        });

        if (!res.ok) throw new Error("Failed to start conversation");

        const data = await res.json();
        setProjectState(data.state);
        setMessages([
          {
            role: "assistant",
            content: data.assistant,
            timestamp: new Date().toISOString(),
          },
        ]);
      } catch (err) {
        setError("Failed to connect. Please refresh and try again.");
      } finally {
        setIsSending(false);
      }
    };

    startConversation();
  }, [projectId]);

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []);
    setPendingFiles((prev) => [...prev, ...files]);
    // Reset input so same file can be selected again
    e.target.value = "";
  };

  const removeFile = (index: number) => {
    setPendingFiles((prev) => prev.filter((_, i) => i !== index));
  };

  const sendMessage = async () => {
    if (isSending) return;
    if (!input.trim() && pendingFiles.length === 0) return;

    const userText = input.trim();
    setIsSending(true);
    setError(null);
    setInput("");

    // Build message content
    let messageContent: string | MessagePart[] = userText;
    
    if (pendingFiles.length > 0) {
      const imageParts = await Promise.all(
        pendingFiles.map(async (file) => ({
          type: "image_url" as const,
          image_url: { url: await fileToDataUrl(file) },
        }))
      );

      const parts: MessagePart[] = [];
      if (userText) {
        parts.push({ type: "text", text: userText });
      }
      parts.push(...imageParts);
      messageContent = parts;
    }

    // Add user message to UI
    const userMessage: Message = {
      role: "user",
      content: messageContent,
      timestamp: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, userMessage]);
    setPendingFiles([]);

    try {
      const res = await fetch(`${API_BASE}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          project_id: projectId,
          message: messageContent,
          state: projectState,
        }),
      });

      if (!res.ok) {
        const detail = await res.text();
        throw new Error(detail || "Failed to send message");
      }

      const data = await res.json();
      setProjectState(data.state);

      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: data.assistant || "(no response)",
          timestamp: new Date().toISOString(),
        },
      ]);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Something went wrong";
      setError(message);
    } finally {
      setIsSending(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <div className="h-screen flex flex-col bg-white">
      {/* Header */}
      <header className="flex-shrink-0 border-b border-gray-200 bg-white">
        <div className="max-w-3xl mx-auto px-4 py-3">
          <div className="flex items-center justify-between mb-2">
            <h1 className="text-lg font-semibold text-gray-900">
              Renovation Estimate
            </h1>
            {projectState?.project_title && (
              <span className="text-sm text-gray-500">
                {projectState.project_title}
              </span>
            )}
          </div>
          <ProgressBar currentStage={projectState?.current_stage || "project_basics"} />
        </div>
      </header>

      {/* Messages area */}
      <main className="flex-1 overflow-y-auto">
        <div className="max-w-3xl mx-auto px-4 py-6">
          <div className="space-y-4">
            {messages.map((msg, idx) => (
              <MessageBubble key={idx} message={msg} />
            ))}
            
            {isSending && (
              <div className="flex justify-start">
                <div className="bg-gray-100 rounded-2xl px-4">
                  <TypingIndicator />
                </div>
              </div>
            )}
            
            <div ref={messagesEndRef} />
          </div>
        </div>
      </main>

      {/* Error display */}
      {error && (
        <div className="flex-shrink-0 border-t border-red-200 bg-red-50 px-4 py-2">
          <div className="max-w-3xl mx-auto">
            <p className="text-sm text-red-600">{error}</p>
          </div>
        </div>
      )}

      {/* Input area */}
      <footer className="flex-shrink-0 border-t border-gray-200 bg-white">
        <div className="max-w-3xl mx-auto px-4 py-3">
          {/* Image previews */}
          <ImagePreview files={pendingFiles} onRemove={removeFile} />

          {/* Input row */}
          <div className="flex items-end gap-2">
            {/* File input button */}
            <button
              onClick={() => fileInputRef.current?.click()}
              disabled={isSending}
              className="flex-shrink-0 p-2.5 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-full transition-colors disabled:opacity-50"
              title="Attach images"
            >
              <Paperclip size={20} />
            </button>
            <input
              ref={fileInputRef}
              type="file"
              multiple
              accept="image/jpeg,image/png,image/webp"
              onChange={handleFileSelect}
              className="hidden"
            />

            {/* Text input */}
            <div className="flex-1 relative">
              <textarea
                ref={textareaRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Type your message..."
                disabled={isSending}
                rows={1}
                className="w-full resize-none rounded-2xl border border-gray-300 bg-gray-50 px-4 py-2.5 pr-12 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:opacity-50 disabled:bg-gray-100"
              />
            </div>

            {/* Send button */}
            <button
              onClick={sendMessage}
              disabled={isSending || (!input.trim() && pendingFiles.length === 0)}
              className="flex-shrink-0 p-2.5 bg-blue-600 text-white rounded-full hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              title="Send message"
            >
              <Send size={20} />
            </button>
          </div>

          {/* Hint text */}
          <p className="text-xs text-gray-400 mt-2 text-center">
            Press Enter to send, Shift+Enter for new line
          </p>
        </div>
      </footer>
    </div>
  );
}
