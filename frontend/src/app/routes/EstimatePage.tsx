import { useState, useRef, useEffect, useMemo, useCallback, memo } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Send, X, Paperclip, Check, ChevronDown, ChevronUp, Camera, SwitchCamera } from "lucide-react";
import rehypeRaw from "rehype-raw";

// ==================== TYPES ====================

interface Message {
  role: "user" | "assistant";
  content: string | MessageContent[];
  timestamp: string;
}

interface MessageContent {
  type: "text" | "image_url" | "tier_cards";
  text?: string;
  image_url?: { url: string };
  tiers?: CostTier[];
}

interface CategoryBreakdown {
  category: string;
  description: string;
  materials_cost: number;
  labor_cost: number;
  total: number;
}

interface CostTier {
  id: string;
  name: string;
  badge: string;
  description: string;
  total_cost: number;
  cogs: number;
  markup_percentage: number;
  markup_amount: number;
  included_items: string[];
  detailed_breakdown: CategoryBreakdown[];
}

interface ProjectState {
  current_stage: string;
  image_sub_state?: string;
  project_title?: string;
  project_type?: string;
  zip_code?: string;
  cost_tiers?: CostTier[];
  selected_tier?: string;
  [key: string]: any;
}

interface UploadedFile {
  file: File;
  preview: string;
  uploaded?: { file_id: string; url: string };
  uploading?: boolean;
  error?: string;
}

interface FileUploadResponse {
  file_id: string;
  filename: string;
  url: string;
  size: number;
  content_type: string;
}

// ==================== CONSTANTS ====================

const STAGES = [
  { key: "project_basics", label: "Project Info", icon: "📋" },
  { key: "image_analysis_generation", label: "Analysis", icon: "🔍" },
  { key: "final_review", label: "Review", icon: "✅" },
  { key: "cost_estimation", label: "Estimate", icon: "💰" },
  { key: "completed", label: "Done", icon: "🎉" },
];

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api/v1";

// ==================== UTILITIES ====================

function formatCurrency(amount: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(amount);
}

async function uploadFile(file: File): Promise<FileUploadResponse> {
  const formData = new FormData();
  formData.append("file", file);
  const response = await fetch(`${API_BASE}/upload`, { method: "POST", body: formData });
  if (!response.ok) throw new Error(await response.text() || "Upload failed");
  return response.json();
}

// ==================== COMPONENTS ====================

const ProgressBar = memo(function ProgressBar({ currentStage }: { currentStage: string }) {
  const currentIndex = STAGES.findIndex((s) => s.key === currentStage);
  const progress = Math.max(0, ((currentIndex + 1) / STAGES.length) * 100);
  const current = STAGES[currentIndex] || STAGES[0];

  return (
    <div className="w-full">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className="text-lg">{current.icon}</span>
          <span className="text-sm font-medium text-gray-700">{current.label}</span>
        </div>
        <span className="text-xs text-gray-400">Step {currentIndex + 1} of {STAGES.length}</span>
      </div>
      <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
        <div className="h-full bg-gradient-to-r from-blue-500 to-blue-600 rounded-full transition-all duration-500 ease-out" style={{ width: `${progress}%` }} />
      </div>
    </div>
  );
});

function TypingIndicator() {
  return (
    <div className="flex items-center gap-1.5 text-gray-500 text-sm py-3 px-1">
      <span>Thinking</span>
      <span className="flex gap-0.5">
        {[0, 1, 2].map((i) => (
          <span key={i} className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: `${i * 150}ms` }} />
        ))}
      </span>
    </div>
  );
}

const ImagePreview = memo(function ImagePreview({ files, onRemove }: { files: UploadedFile[]; onRemove: (i: number) => void }) {
  if (files.length === 0) return null;
  return (
    <div className="flex gap-2 p-3 bg-gray-50 rounded-xl mb-2 overflow-x-auto">
      {files.map((file, idx) => (
        <div key={idx} className="relative flex-shrink-0 group">
          <img src={file.preview} alt={`Preview ${idx + 1}`}
            className={`h-20 w-20 object-cover rounded-lg border-2 ${file.uploading ? "border-blue-400 opacity-70" : file.error ? "border-red-400" : file.uploaded ? "border-green-400" : "border-gray-200"}`} />
          {file.uploading && <div className="absolute inset-0 flex items-center justify-center bg-black/20 rounded-lg"><div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" /></div>}
          {file.uploaded && <div className="absolute bottom-1 right-1 bg-green-500 text-white rounded-full p-0.5"><Check size={10} /></div>}
          {file.error && <div className="absolute bottom-1 right-1 bg-red-500 text-white text-xs px-1 rounded">!</div>}
          <button onClick={() => onRemove(idx)} className="absolute -top-2 -right-2 bg-red-500 text-white rounded-full p-1 opacity-0 group-hover:opacity-100 transition-opacity shadow-md"><X size={12} /></button>
        </div>
      ))}
    </div>
  );
});

// ==================== CAMERA MODAL ====================

interface CameraModalProps {
  isOpen: boolean;
  onClose: () => void;
  onCapture: (file: File) => void;
}

function CameraModal({ isOpen, onClose, onCapture }: CameraModalProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [stream, setStream] = useState<MediaStream | null>(null);
  const [facingMode, setFacingMode] = useState<"user" | "environment">("environment");
  const [error, setError] = useState<string | null>(null);
  const [isCapturing, setIsCapturing] = useState(false);

  const startCamera = useCallback(async (facing: "user" | "environment") => {
    try {
      // Stop existing stream
      if (stream) {
        stream.getTracks().forEach(track => track.stop());
      }
      
      setError(null);
      const mediaStream = await navigator.mediaDevices.getUserMedia({
        video: {
          facingMode: facing,
          width: { ideal: 1920 },
          height: { ideal: 1080 }
        },
        audio: false
      });
      
      setStream(mediaStream);
      if (videoRef.current) {
        videoRef.current.srcObject = mediaStream;
      }
    } catch (err) {
      console.error("Camera error:", err);
      setError("Unable to access camera. Please check permissions.");
    }
  }, [stream]);

  const stopCamera = useCallback(() => {
    if (stream) {
      stream.getTracks().forEach(track => track.stop());
      setStream(null);
    }
  }, [stream]);

  useEffect(() => {
    if (isOpen) {
      startCamera(facingMode);
    } else {
      stopCamera();
    }
    return () => stopCamera();
  }, [isOpen]);

  const switchCamera = useCallback(() => {
    const newFacing = facingMode === "user" ? "environment" : "user";
    setFacingMode(newFacing);
    startCamera(newFacing);
  }, [facingMode, startCamera]);

  const capturePhoto = useCallback(() => {
    if (!videoRef.current || !canvasRef.current) return;
    
    setIsCapturing(true);
    const video = videoRef.current;
    const canvas = canvasRef.current;
    
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    
    const ctx = canvas.getContext("2d");
    if (ctx) {
      ctx.drawImage(video, 0, 0);
      
      canvas.toBlob((blob) => {
        if (blob) {
          const file = new File([blob], `camera_${Date.now()}.jpg`, { type: "image/jpeg" });
          onCapture(file);
          onClose();
        }
        setIsCapturing(false);
      }, "image/jpeg", 0.9);
    }
  }, [onCapture, onClose]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 bg-black flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between p-4 bg-black/50">
        <button onClick={onClose} className="text-white p-2">
          <X size={24} />
        </button>
        <span className="text-white font-medium">Take Photo</span>
        <button onClick={switchCamera} className="text-white p-2">
          <SwitchCamera size={24} />
        </button>
      </div>

      {/* Camera View */}
      <div className="flex-1 relative flex items-center justify-center bg-black">
        {error ? (
          <div className="text-white text-center p-4">
            <p className="mb-4">{error}</p>
            <button
              onClick={() => startCamera(facingMode)}
              className="px-4 py-2 bg-blue-600 rounded-lg"
            >
              Try Again
            </button>
          </div>
        ) : (
          <video
            ref={videoRef}
            autoPlay
            playsInline
            muted
            className="max-h-full max-w-full object-contain"
          />
        )}
        <canvas ref={canvasRef} className="hidden" />
      </div>

      {/* Capture Button */}
      <div className="p-6 bg-black/50 flex justify-center">
        <button
          onClick={capturePhoto}
          disabled={!!error || isCapturing}
          className="w-16 h-16 rounded-full bg-white border-4 border-gray-300 flex items-center justify-center disabled:opacity-50 active:scale-95 transition-transform"
        >
          {isCapturing ? (
            <div className="w-6 h-6 border-2 border-gray-600 border-t-transparent rounded-full animate-spin" />
          ) : (
            <div className="w-12 h-12 rounded-full bg-white border-2 border-gray-400" />
          )}
        </button>
      </div>
    </div>
  );
}

// ==================== TIER COMPONENTS ====================

const TierCard = memo(function TierCard({ tier, isSelected, isExpanded, onSelect, onToggleExpand }: { tier: CostTier; isSelected: boolean; isExpanded: boolean; onSelect: () => void; onToggleExpand: () => void }) {
  const badgeColors: Record<string, string> = { "Budget-Friendly": "bg-green-100 text-green-800", Recommended: "bg-blue-100 text-blue-800", Premium: "bg-purple-100 text-purple-800" };
  return (
    <div className={`border rounded-xl transition-all duration-200 ${isSelected ? "border-blue-500 ring-2 ring-blue-200 bg-blue-50/50" : "border-gray-200 hover:border-gray-300 bg-white"}`}>
      <div className="p-4">
        <div className="flex items-start justify-between mb-2">
          <div>
            <h3 className="font-semibold text-gray-900">{tier.name}</h3>
            <span className={`inline-block px-2 py-0.5 text-xs font-medium rounded-full mt-1 ${badgeColors[tier.badge] || "bg-gray-100 text-gray-800"}`}>{tier.badge}</span>
          </div>
          <div className="text-right">
            <div className="text-2xl font-bold text-gray-900">{formatCurrency(tier.total_cost)}</div>
            <div className="text-xs text-gray-500">Total estimate</div>
          </div>
        </div>
        <p className="text-sm text-gray-600 mb-3">{tier.description}</p>
        <div className="flex gap-4 text-xs text-gray-500 mb-3"><span>COGS: {formatCurrency(tier.cogs)}</span><span>Markup: {tier.markup_percentage}%</span></div>
        <div className="flex flex-wrap gap-1.5 mb-3">
          {tier.included_items.slice(0, 5).map((item, idx) => (<span key={idx} className="inline-flex items-center gap-1 px-2 py-0.5 bg-gray-100 text-gray-700 text-xs rounded"><Check size={10} className="text-green-500" />{item}</span>))}
          {tier.included_items.length > 5 && <span className="text-xs text-gray-400">+{tier.included_items.length - 5} more</span>}
        </div>
        <div className="flex gap-2">
          <button onClick={onSelect} className={`flex-1 py-2 px-4 rounded-lg font-medium text-sm transition-colors ${isSelected ? "bg-blue-600 text-white" : "bg-gray-100 text-gray-700 hover:bg-gray-200"}`}>{isSelected ? "Selected ✓" : "Select This Tier"}</button>
          <button onClick={onToggleExpand} className="px-3 py-2 rounded-lg bg-gray-100 text-gray-600 hover:bg-gray-200 transition-colors">{isExpanded ? <ChevronUp size={18} /> : <ChevronDown size={18} />}</button>
        </div>
      </div>
      {isExpanded && (
        <div className="border-t border-gray-200 p-4 bg-gray-50/50">
          <h4 className="font-medium text-sm text-gray-700 mb-3">Detailed Breakdown</h4>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead><tr className="border-b border-gray-200"><th className="text-left py-2 font-medium text-gray-600">Category</th><th className="text-right py-2 font-medium text-gray-600">Materials</th><th className="text-right py-2 font-medium text-gray-600">Labor</th><th className="text-right py-2 font-medium text-gray-600">Total</th></tr></thead>
              <tbody>{tier.detailed_breakdown.map((item, idx) => (<tr key={idx} className="border-b border-gray-100"><td className="py-2"><div className="font-medium text-gray-900">{item.category}</div><div className="text-xs text-gray-500">{item.description}</div></td><td className="text-right py-2 text-gray-700">{formatCurrency(item.materials_cost)}</td><td className="text-right py-2 text-gray-700">{formatCurrency(item.labor_cost)}</td><td className="text-right py-2 font-medium text-gray-900">{formatCurrency(item.total)}</td></tr>))}</tbody>
              <tfoot><tr className="border-t-2 border-gray-300"><td className="py-2 font-medium">Subtotal (COGS)</td><td colSpan={3} className="text-right py-2 font-medium">{formatCurrency(tier.cogs)}</td></tr><tr><td className="py-2 text-gray-600">Markup ({tier.markup_percentage}%)</td><td colSpan={3} className="text-right py-2 text-gray-600">{formatCurrency(tier.markup_amount)}</td></tr><tr className="bg-blue-50"><td className="py-2 font-bold text-blue-900">Total Estimate</td><td colSpan={3} className="text-right py-2 font-bold text-blue-900 text-lg">{formatCurrency(tier.total_cost)}</td></tr></tfoot>
            </table>
          </div>
        </div>
      )}
    </div>
  );
});

function TierCards({ tiers, onSelectTier }: { tiers: CostTier[]; onSelectTier: (tierId: string) => void }) {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const handleConfirm = useCallback(() => { if (selectedId) onSelectTier(selectedId); }, [selectedId, onSelectTier]);
  return (
    <div className="space-y-4">
      <div className="grid gap-4 md:grid-cols-1 lg:grid-cols-3">{tiers.map((tier) => (<TierCard key={tier.id} tier={tier} isSelected={selectedId === tier.id} isExpanded={expandedId === tier.id} onSelect={() => setSelectedId(tier.id)} onToggleExpand={() => setExpandedId(expandedId === tier.id ? null : tier.id)} />))}</div>
      {selectedId && (<div className="flex justify-center pt-2"><button onClick={handleConfirm} className="px-6 py-3 bg-blue-600 text-white font-semibold rounded-xl hover:bg-blue-700 transition-colors shadow-lg shadow-blue-200">Accept {tiers.find((t) => t.id === selectedId)?.name || "Selected Tier"} & Submit</button></div>)}
    </div>
  );
}

const MessageBubble = memo(function MessageBubble({ message, onSelectTier }: { message: Message; onSelectTier?: (tierId: string) => void }) {
  const isUser = message.role === "user";
  const { textContent, images, tierCards } = useMemo(() => {
    if (typeof message.content === "string") return { textContent: message.content, images: [], tierCards: null };
    const text = message.content.filter((p) => p.type === "text").map((p) => p.text).join("\n");
    const imgs = message.content.filter((p) => p.type === "image_url").map((p) => p.image_url?.url).filter(Boolean) as string[];
    const tiers = message.content.find((p) => p.type === "tier_cards");
    return { textContent: text, images: imgs, tierCards: tiers };
  }, [message.content]);

  const getImageSrc = (url: string) => url.startsWith("/") ? `${API_BASE.replace("/api/v1", "")}${url}` : url;

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div className={`max-w-[90%] md:max-w-[80%] ${isUser ? "" : "w-full"}`}>
        {images.length > 0 && (<div className="flex flex-wrap gap-2 mb-2 justify-end">{images.map((url, idx) => <img key={idx} src={getImageSrc(url)} alt={`Uploaded ${idx + 1}`} className="max-h-48 rounded-xl object-cover shadow-sm" loading="lazy" />)}</div>)}
        {textContent && (
          <div className={`rounded-2xl px-4 py-3 ${isUser ? "bg-blue-600 text-white ml-auto" : "bg-gray-100 text-gray-900"}`} style={{ maxWidth: isUser ? "fit-content" : "100%" }}>
            <div className={`prose prose-sm max-w-none ${isUser ? "prose-invert" : "prose-gray"}`}>
              {isUser ? <p className="m-0 whitespace-pre-wrap">{textContent}</p> : (
                <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeRaw]} components={{
                  h1: ({ children }) => <h1 className="text-xl font-bold mt-4 mb-2">{children}</h1>,
                  h2: ({ children }) => <h2 className="text-lg font-bold mt-3 mb-2">{children}</h2>,
                  h3: ({ children }) => <h3 className="text-base font-semibold mt-2 mb-1">{children}</h3>,
                  p: ({ children }) => <p className="my-2">{children}</p>,
                  ul: ({ children }) => <ul className="list-disc list-inside my-2 space-y-1">{children}</ul>,
                  ol: ({ children }) => <ol className="list-decimal list-inside my-2 space-y-1">{children}</ol>,
                  img: ({ src, alt }) => <img src={getImageSrc(src || "")} alt={alt} className="rounded-xl my-3 shadow-sm w-36 h-24 object-cover" loading="lazy" />,
                  strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
                  hr: () => <hr className="my-4 border-gray-300" />,
                }}>{textContent}</ReactMarkdown>
              )}
            </div>
          </div>
        )}
        {tierCards?.tiers && onSelectTier && <div className="mt-3"><TierCards tiers={tierCards.tiers} onSelectTier={onSelectTier} /></div>}
      </div>
    </div>
  );
});

// ==================== MAIN COMPONENT ====================

export default function EstimatePage() {
  const projectId = useMemo(() => crypto.randomUUID(), []);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [pendingFiles, setPendingFiles] = useState<UploadedFile[]>([]);
  const [projectState, setProjectState] = useState<ProjectState | null>(null);
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isCameraOpen, setIsCameraOpen] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => { setTimeout(() => messagesEndRef.current?.scrollIntoView({ behavior: "smooth" }), 100); }, [messages.length, isSending]);
  useEffect(() => { const t = textareaRef.current; if (t) { t.style.height = "auto"; t.style.height = `${Math.min(t.scrollHeight, 150)}px`; } }, [input]);
  // Auto-focus textarea after message is sent
  useEffect(() => {
    if (!isSending && messages.length > 0) {
      const timer = setTimeout(() => {
        textareaRef.current?.focus();
      }, 50);
      return () => clearTimeout(timer);
    }
  }, [isSending, messages.length]);
  useEffect(() => { return () => { pendingFiles.forEach((f) => URL.revokeObjectURL(f.preview)); }; }, []);

  useEffect(() => {
    const start = async () => {
      setIsSending(true);
      try {
        const res = await fetch(`${API_BASE}/chat`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ project_id: projectId, message: "", state: null }) });
        if (!res.ok) throw new Error("Failed to start");
        const data = await res.json();
        setProjectState(data.state);
        setMessages([{ role: "assistant", content: data.assistant, timestamp: new Date().toISOString() }]);
      } catch { setError("Failed to connect. Please refresh."); } finally { setIsSending(false); }
    };
    start();
  }, [projectId]);

  const addFileToUpload = useCallback(async (file: File) => {
    const preview = URL.createObjectURL(file);
    const fileEntry: UploadedFile = { file, preview, uploading: true };
    
    setPendingFiles((prev) => [...prev, fileEntry]);
    
    try {
      const result = await uploadFile(file);
      setPendingFiles((prev) =>
        prev.map((f) =>
          f.preview === preview
            ? { ...f, uploading: false, uploaded: { file_id: result.file_id, url: result.url } }
            : f
        )
      );
    } catch (err) {
      setPendingFiles((prev) =>
        prev.map((f) =>
          f.preview === preview
            ? { ...f, uploading: false, error: err instanceof Error ? err.message : "Upload failed" }
            : f
        )
      );
    }
  }, []);

  const handleFileSelect = useCallback(async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []);
    e.target.value = "";
    for (const file of files) {
      await addFileToUpload(file);
    }
  }, [addFileToUpload]);

  const handleCameraCapture = useCallback((file: File) => {
    addFileToUpload(file);
  }, [addFileToUpload]);

  const removeFile = useCallback((index: number) => {
    setPendingFiles((prev) => {
      const file = prev[index];
      if (file) URL.revokeObjectURL(file.preview);
      return prev.filter((_, i) => i !== index);
    });
  }, []);

  const sendMessage = useCallback(async (overrideMessage?: string) => {
    if (isSending) return;
    const messageText = overrideMessage ?? input.trim();
    const uploadedFiles = pendingFiles.filter((f) => f.uploaded && !f.error);
    if (!messageText && uploadedFiles.length === 0) return;
    if (pendingFiles.some((f) => f.uploading)) { setError("Please wait for uploads to complete"); return; }

    setIsSending(true); setError(null); setInput("");
    let messageContent: string | MessageContent[] = messageText;
    let displayContent: string | MessageContent[] = messageText;

    if (uploadedFiles.length > 0) {
      const parts: MessageContent[] = [], displayParts: MessageContent[] = [];
      if (messageText) { parts.push({ type: "text", text: messageText }); displayParts.push({ type: "text", text: messageText }); }
      for (const file of uploadedFiles) {
        parts.push({ type: "image_url", image_url: { url: file.uploaded!.url } });
        displayParts.push({ type: "image_url", image_url: { url: file.uploaded!.url } });
      }
      messageContent = parts; displayContent = displayParts;
    }

    setMessages((prev) => [...prev, { role: "user", content: displayContent, timestamp: new Date().toISOString() }]);
    pendingFiles.forEach((f) => URL.revokeObjectURL(f.preview));
    setPendingFiles([]);

    try {
      const res = await fetch(`${API_BASE}/chat`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ project_id: projectId, message: messageContent, state: projectState }) });
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      setProjectState(data.state);
      setMessages((prev) => [...prev, { role: "assistant", content: data.assistant || "(no response)", timestamp: new Date().toISOString() }]);
    } catch (err) { setError(err instanceof Error ? err.message : "Something went wrong"); } finally { setIsSending(false); }
  }, [isSending, input, pendingFiles, projectId, projectState]);

  const handleSelectTier = useCallback((tierId: string) => { sendMessage(`I select the ${tierId} tier`); }, [sendMessage]);
  const handleKeyDown = useCallback((e: React.KeyboardEvent) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(); } }, [sendMessage]);

  const isCompleted = projectState?.current_stage === "completed";
  const hasUploadingFiles = pendingFiles.some((f) => f.uploading);
  const hasUploadedFiles = pendingFiles.some((f) => f.uploaded);

  return (
    <div className="h-screen flex flex-col bg-gray-50">
      <header className="flex-shrink-0 border-b border-gray-200 bg-white shadow-sm">
        <div className="max-w-4xl mx-auto px-4 py-4">
          <div className="flex items-center justify-between mb-3">
            <h1 className="text-xl font-bold text-gray-900">Renovation Estimator</h1>
            {projectState?.project_title && <span className="text-sm text-gray-500 bg-gray-100 px-3 py-1 rounded-full">{projectState.project_title}</span>}
          </div>
          <ProgressBar currentStage={projectState?.current_stage || "project_basics"} />
        </div>
      </header>

      <main className="flex-1 overflow-y-auto">
        <div className="max-w-4xl mx-auto px-4 py-6">
          <div className="space-y-4">
            {messages.map((msg, idx) => <MessageBubble key={idx} message={msg} onSelectTier={handleSelectTier} />)}
            {isSending && <div className="flex justify-start"><div className="bg-gray-100 rounded-2xl px-4"><TypingIndicator /></div></div>}
            <div ref={messagesEndRef} />
          </div>
        </div>
      </main>

      {error && <div className="flex-shrink-0 border-t border-red-200 bg-red-50 px-4 py-3"><div className="max-w-4xl mx-auto"><p className="text-sm text-red-600">{error}</p></div></div>}

      {!isCompleted && (
        <footer className="flex-shrink-0 border-t border-gray-200 bg-white">
          <div className="max-w-4xl mx-auto px-4 py-4">
            <ImagePreview files={pendingFiles} onRemove={removeFile} />
            <div className="flex items-end gap-2 sm:gap-3">
              {/* Attach Images Button */}
              <button
                onClick={() => fileInputRef.current?.click()}
                disabled={isSending}
                className="flex-shrink-0 p-2.5 sm:p-3 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-xl transition-colors disabled:opacity-50"
                title="Attach images"
              >
                <Paperclip size={20} className="sm:w-[22px] sm:h-[22px]" />
              </button>
              
              {/* Camera Button */}
              <button
                onClick={() => setIsCameraOpen(true)}
                disabled={isSending}
                className="flex-shrink-0 p-2.5 sm:p-3 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-xl transition-colors disabled:opacity-50"
                title="Take photo"
              >
                <Camera size={20} className="sm:w-[22px] sm:h-[22px]" />
              </button>
              
              <input ref={fileInputRef} type="file" multiple accept="image/jpeg,image/png,image/webp" onChange={handleFileSelect} className="hidden" />
              
              {/* Text Input */}
              <div className="flex-1">
                <textarea
                  ref={textareaRef}
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder="Type your message..."
                  disabled={isSending}
                  rows={1}
                  className="w-full resize-none rounded-xl border border-gray-300 bg-white px-3 sm:px-4 py-2.5 sm:py-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:opacity-50 disabled:bg-gray-50"
                />
              </div>
              
              {/* Send Button */}
              <button
                onClick={() => sendMessage()}
                disabled={isSending || hasUploadingFiles || (!input.trim() && !hasUploadedFiles)}
                className="flex-shrink-0 p-2.5 sm:p-3 bg-blue-600 text-white rounded-xl hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed shadow-sm"
                title="Send message"
              >
                <Send size={20} className="sm:w-[22px] sm:h-[22px]" />
              </button>
            </div>
            <p className="text-xs text-gray-400 mt-2 text-center hidden sm:block">Press Enter to send • Shift+Enter for new line</p>
          </div>
        </footer>
      )}

      {isCompleted && (
        <footer className="flex-shrink-0 border-t border-gray-200 bg-green-50 py-4">
          <div className="max-w-4xl mx-auto px-4 text-center">
            <p className="text-green-700 font-medium">✅ Your renovation estimate is complete!</p>
          </div>
        </footer>
      )}

      {/* Camera Modal */}
      <CameraModal
        isOpen={isCameraOpen}
        onClose={() => setIsCameraOpen(false)}
        onCapture={handleCameraCapture}
      />
    </div>
  );
}