import { useState, useRef, useEffect, useMemo, useCallback, memo } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { motion, AnimatePresence } from "framer-motion";
import { 
  Send, X, Paperclip, Check, ChevronDown, ChevronUp, Camera, SwitchCamera,
  Bot, User, Sparkles, CheckCircle2, Circle
} from "lucide-react";
import rehypeRaw from "rehype-raw";
import ImageLightbox from "../../components/shared/ImageLightbox";

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
  { key: "project_basics", label: "Project Info", icon: "📋", description: "Tell us about your project" },
  { key: "image_analysis_generation", label: "Analysis", icon: "🔍", description: "AI analyzes your space" },
  { key: "final_review", label: "Review", icon: "✅", description: "Confirm your details" },
  { key: "cost_estimation", label: "Estimate", icon: "💰", description: "Get your pricing" },
  { key: "completed", label: "Done", icon: "🎉", description: "Estimate complete!" },
];

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api/v1";

// ==================== UTILITIES ====================
function formatCurrency(amount: number): string {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(amount);
}

function formatTime(timestamp: string): string {
  return new Date(timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

async function uploadFile(file: File): Promise<FileUploadResponse> {
  const formData = new FormData();
  formData.append("file", file);
  const response = await fetch(`${API_BASE}/upload`, { method: "POST", body: formData });
  if (!response.ok) throw new Error(await response.text() || "Upload failed");
  return response.json();
}

// ==================== PROGRESS BAR ====================
const ProgressBar = memo(function ProgressBar({ currentStage }: { currentStage: string }) {
  const currentIndex = STAGES.findIndex((s) => s.key === currentStage);

  return (
    <div className="w-full">
      <div className="flex items-center justify-between relative">
        <div className="absolute left-0 right-0 top-5 h-0.5 bg-navy-200 dark:bg-navy-700 -z-10" />
        <motion.div 
          className="absolute left-0 top-5 h-0.5 bg-gradient-to-r from-amber-500 to-amber-400 -z-10"
          initial={{ width: 0 }}
          animate={{ width: `${(currentIndex / (STAGES.length - 1)) * 100}%` }}
          transition={{ duration: 0.5, ease: "easeOut" }}
        />
        
        {STAGES.map((stage, index) => {
          const isCompleted = index < currentIndex;
          const isCurrent = index === currentIndex;
          
          return (
            <div key={stage.key} className="flex flex-col items-center relative">
              <motion.div
                initial={false}
                animate={{
                  scale: isCurrent ? 1.1 : 1,
                  backgroundColor: isCompleted || isCurrent ? "rgb(245, 158, 11)" : "rgb(226, 232, 240)"
                }}
                className={`w-10 h-10 rounded-full flex items-center justify-center text-lg shadow-sm ${
                  isCompleted || isCurrent ? "text-white" : "text-navy-400"
                }`}
              >
                {isCompleted ? (
                  <CheckCircle2 className="w-5 h-5" />
                ) : isCurrent ? (
                  <motion.div animate={{ rotate: 360 }} transition={{ duration: 2, repeat: Infinity, ease: "linear" }}>
                    <Sparkles className="w-5 h-5" />
                  </motion.div>
                ) : (
                  <Circle className="w-5 h-5" />
                )}
              </motion.div>
              
              <div className="hidden sm:block mt-2 text-center">
                <p className={`text-xs font-medium ${isCurrent ? "text-amber-600 dark:text-amber-400" : "text-navy-500 dark:text-navy-400"}`}>
                  {stage.label}
                </p>
              </div>
            </div>
          );
        })}
      </div>
      
      <motion.div 
        key={currentStage}
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        className="mt-6 text-center sm:hidden"
      >
        <span className="text-2xl mb-1 block">{STAGES[currentIndex]?.icon}</span>
        <p className="text-sm font-medium text-navy-900 dark:text-white">{STAGES[currentIndex]?.label}</p>
        <p className="text-xs text-navy-500 dark:text-navy-400">{STAGES[currentIndex]?.description}</p>
      </motion.div>
    </div>
  );
});

// ==================== TYPING INDICATOR ====================
function TypingIndicator() {
  return (
    <div className="flex items-center gap-2">
      <div className="w-8 h-8 rounded-full bg-gradient-to-br from-navy-600 to-navy-700 flex items-center justify-center">
        <Bot className="w-4 h-4 text-white" />
      </div>
      <div className="flex items-center gap-1.5 bg-white dark:bg-navy-800 rounded-2xl px-4 py-3 shadow-sm border border-navy-100 dark:border-navy-700">
        <span className="text-navy-500 dark:text-navy-400 text-sm">Thinking</span>
        <span className="flex gap-1">
          {[0, 1, 2].map((i) => (
            <motion.span
              key={i}
              animate={{ y: [0, -4, 0] }}
              transition={{ duration: 0.6, repeat: Infinity, delay: i * 0.15 }}
              className="w-1.5 h-1.5 bg-amber-500 rounded-full"
            />
          ))}
        </span>
      </div>
    </div>
  );
}

// ==================== IMAGE PREVIEW ====================
const ImagePreview = memo(function ImagePreview({ files, onRemove }: { files: UploadedFile[]; onRemove: (i: number) => void }) {
  if (files.length === 0) return null;
  
  return (
    <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="flex gap-2 p-3 bg-navy-50 dark:bg-navy-800/50 rounded-xl mb-2 overflow-x-auto">
      {files.map((file, idx) => (
        <motion.div 
          key={idx} 
          initial={{ opacity: 0, scale: 0.8 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: idx * 0.05 }}
          className="relative flex-shrink-0 group"
        >
          <img 
            src={file.preview} 
            alt={`Preview ${idx + 1}`}
            className={`h-20 w-20 object-cover rounded-lg border-2 transition-all ${
              file.uploading ? "border-amber-400 opacity-70" : file.error ? "border-red-400" : file.uploaded ? "border-emerald-400" : "border-navy-200 dark:border-navy-600"
            }`} 
          />
          {file.uploading && (
            <div className="absolute inset-0 flex items-center justify-center bg-black/30 rounded-lg">
              <motion.div animate={{ rotate: 360 }} transition={{ duration: 1, repeat: Infinity, ease: "linear" }} className="w-6 h-6 border-2 border-white border-t-transparent rounded-full" />
            </div>
          )}
          {file.uploaded && (
            <motion.div initial={{ scale: 0 }} animate={{ scale: 1 }} className="absolute bottom-1 right-1 bg-emerald-500 text-white rounded-full p-0.5">
              <Check size={10} />
            </motion.div>
          )}
          {file.error && <div className="absolute bottom-1 right-1 bg-red-500 text-white text-xs px-1 rounded">!</div>}
          <button onClick={() => onRemove(idx)} className="absolute -top-2 -right-2 bg-red-500 hover:bg-red-600 text-white rounded-full p-1 opacity-0 group-hover:opacity-100 transition-all shadow-md">
            <X size={12} />
          </button>
        </motion.div>
      ))}
    </motion.div>
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
      if (stream) stream.getTracks().forEach(track => track.stop());
      setError(null);
      const mediaStream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: facing, width: { ideal: 1920 }, height: { ideal: 1080 } },
        audio: false
      });
      setStream(mediaStream);
      if (videoRef.current) videoRef.current.srcObject = mediaStream;
    } catch (err) {
      console.error("Camera error:", err);
      setError("Unable to access camera. Please check permissions.");
    }
  }, [stream]);

  const stopCamera = useCallback(() => {
    if (stream) { stream.getTracks().forEach(track => track.stop()); setStream(null); }
  }, [stream]);

  useEffect(() => {
    if (isOpen) startCamera(facingMode);
    else stopCamera();
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
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="fixed inset-0 z-50 bg-black flex flex-col">
      <div className="flex items-center justify-between p-4 bg-black/50">
        <button onClick={onClose} className="text-white p-2 hover:bg-white/10 rounded-lg transition-colors"><X size={24} /></button>
        <span className="text-white font-medium">Take Photo</span>
        <button onClick={switchCamera} className="text-white p-2 hover:bg-white/10 rounded-lg transition-colors"><SwitchCamera size={24} /></button>
      </div>
      <div className="flex-1 relative flex items-center justify-center bg-black">
        {error ? (
          <div className="text-white text-center p-4">
            <p className="mb-4">{error}</p>
            <button onClick={() => startCamera(facingMode)} className="px-4 py-2 bg-amber-500 rounded-lg font-medium">Try Again</button>
          </div>
        ) : (
          <video ref={videoRef} autoPlay playsInline muted className="max-h-full max-w-full object-contain" />
        )}
        <canvas ref={canvasRef} className="hidden" />
      </div>
      <div className="p-6 bg-black/50 flex justify-center">
        <motion.button onClick={capturePhoto} disabled={!!error || isCapturing} whileTap={{ scale: 0.95 }} className="w-16 h-16 rounded-full bg-white border-4 border-gray-300 flex items-center justify-center disabled:opacity-50">
          {isCapturing ? (
            <motion.div animate={{ rotate: 360 }} transition={{ duration: 1, repeat: Infinity, ease: "linear" }} className="w-6 h-6 border-2 border-gray-600 border-t-transparent rounded-full" />
          ) : (
            <div className="w-12 h-12 rounded-full bg-white border-2 border-gray-400" />
          )}
        </motion.button>
      </div>
    </motion.div>
  );
}

// ==================== TIER CARD ====================
const TierCard = memo(function TierCard({ tier, isSelected, isExpanded, onSelect, onToggleExpand }: { tier: CostTier; isSelected: boolean; isExpanded: boolean; onSelect: () => void; onToggleExpand: () => void }) {
  const badgeColors: Record<string, string> = { 
    "Budget-Friendly": "bg-emerald-100 text-emerald-700 dark:bg-emerald-500/20 dark:text-emerald-400", 
    "Recommended": "bg-amber-100 text-amber-700 dark:bg-amber-500/20 dark:text-amber-400", 
    "Premium": "bg-purple-100 text-purple-700 dark:bg-purple-500/20 dark:text-purple-400" 
  };
  
  return (
    <motion.div 
      layout
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      whileHover={{ y: -2 }}
      className={`border rounded-2xl transition-all duration-300 overflow-hidden ${
        isSelected ? "border-amber-500 ring-2 ring-amber-200 dark:ring-amber-500/30 bg-amber-50/50 dark:bg-amber-500/10" : "border-navy-200 dark:border-navy-700 hover:border-navy-300 dark:hover:border-navy-600 bg-white dark:bg-navy-800"
      }`}
    >
      <div className="p-5">
        <div className="flex items-start justify-between mb-3">
          <div>
            <h3 className="font-semibold text-navy-900 dark:text-white text-lg">{tier.name}</h3>
            <span className={`inline-block px-2.5 py-0.5 text-xs font-medium rounded-full mt-1 ${badgeColors[tier.badge] || "bg-gray-100 text-gray-800"}`}>{tier.badge}</span>
          </div>
          <div className="text-right">
            <div className="text-2xl font-bold text-navy-900 dark:text-white">{formatCurrency(tier.total_cost)}</div>
            <div className="text-xs text-navy-500 dark:text-navy-400">Total estimate</div>
          </div>
        </div>
        <p className="text-sm text-navy-600 dark:text-navy-300 mb-4">{tier.description}</p>
        <div className="flex gap-4 text-xs text-navy-500 dark:text-navy-400 mb-4">
          <span>COGS: {formatCurrency(tier.cogs)}</span>
          <span>Markup: {tier.markup_percentage}%</span>
        </div>
        <div className="flex flex-wrap gap-1.5 mb-4">
          {tier.included_items.slice(0, 5).map((item, idx) => (
            <span key={idx} className="inline-flex items-center gap-1 px-2 py-0.5 bg-navy-100 dark:bg-navy-700 text-navy-700 dark:text-navy-300 text-xs rounded-md">
              <Check size={10} className="text-emerald-500" />{item}
            </span>
          ))}
          {tier.included_items.length > 5 && <span className="text-xs text-navy-400">+{tier.included_items.length - 5} more</span>}
        </div>
        <div className="flex gap-2">
          <motion.button onClick={onSelect} whileTap={{ scale: 0.98 }} className={`flex-1 py-2.5 px-4 rounded-xl font-medium text-sm transition-all ${isSelected ? "bg-amber-500 text-white shadow-lg shadow-amber-500/25" : "bg-navy-100 dark:bg-navy-700 text-navy-700 dark:text-navy-200 hover:bg-navy-200 dark:hover:bg-navy-600"}`}>
            {isSelected ? "Selected ✓" : "Select This Tier"}
          </motion.button>
          <button onClick={onToggleExpand} className="px-3 py-2 rounded-xl bg-navy-100 dark:bg-navy-700 text-navy-600 dark:text-navy-300 hover:bg-navy-200 dark:hover:bg-navy-600 transition-colors">
            {isExpanded ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
          </button>
        </div>
      </div>
      
      <AnimatePresence>
        {isExpanded && (
          <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }} transition={{ duration: 0.2 }} className="border-t border-navy-100 dark:border-navy-700 bg-navy-50/50 dark:bg-navy-900/50 overflow-hidden">
            <div className="p-5">
              <h4 className="font-medium text-sm text-navy-700 dark:text-navy-300 mb-3">Detailed Breakdown</h4>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-navy-200 dark:border-navy-700">
                      <th className="text-left py-2 font-medium text-navy-600 dark:text-navy-400">Category</th>
                      <th className="text-right py-2 font-medium text-navy-600 dark:text-navy-400">Materials</th>
                      <th className="text-right py-2 font-medium text-navy-600 dark:text-navy-400">Labor</th>
                      <th className="text-right py-2 font-medium text-navy-600 dark:text-navy-400">Total</th>
                    </tr>
                  </thead>
                  <tbody>
                    {tier.detailed_breakdown.map((item, idx) => (
                      <tr key={idx} className="border-b border-navy-100 dark:border-navy-800">
                        <td className="py-2"><div className="font-medium text-navy-900 dark:text-white">{item.category}</div><div className="text-xs text-navy-500 dark:text-navy-400">{item.description}</div></td>
                        <td className="text-right py-2 text-navy-700 dark:text-navy-300">{formatCurrency(item.materials_cost)}</td>
                        <td className="text-right py-2 text-navy-700 dark:text-navy-300">{formatCurrency(item.labor_cost)}</td>
                        <td className="text-right py-2 font-medium text-navy-900 dark:text-white">{formatCurrency(item.total)}</td>
                      </tr>
                    ))}
                  </tbody>
                  <tfoot>
                    <tr className="border-t-2 border-navy-300 dark:border-navy-600">
                      <td className="py-2 font-medium text-navy-900 dark:text-white">Subtotal (COGS)</td>
                      <td colSpan={3} className="text-right py-2 font-medium text-navy-900 dark:text-white">{formatCurrency(tier.cogs)}</td>
                    </tr>
                    <tr>
                      <td className="py-2 text-navy-600 dark:text-navy-400">Markup ({tier.markup_percentage}%)</td>
                      <td colSpan={3} className="text-right py-2 text-navy-600 dark:text-navy-400">{formatCurrency(tier.markup_amount)}</td>
                    </tr>
                    <tr className="bg-amber-100 dark:bg-amber-500/20">
                      <td className="py-3 font-bold text-amber-800 dark:text-amber-300 rounded-l-lg">Total Estimate</td>
                      <td colSpan={3} className="text-right py-3 font-bold text-amber-800 dark:text-amber-300 text-lg rounded-r-lg">{formatCurrency(tier.total_cost)}</td>
                    </tr>
                  </tfoot>
                </table>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
});

function TierCards({ tiers, onSelectTier }: { tiers: CostTier[]; onSelectTier: (tierId: string) => void }) {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const handleConfirm = useCallback(() => { if (selectedId) onSelectTier(selectedId); }, [selectedId, onSelectTier]);
  
  return (
    <div className="space-y-4">
      <div className="grid gap-4 lg:grid-cols-3">
        {tiers.map((tier, idx) => (
          <motion.div key={tier.id} initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: idx * 0.1 }}>
            <TierCard tier={tier} isSelected={selectedId === tier.id} isExpanded={expandedId === tier.id} onSelect={() => setSelectedId(tier.id)} onToggleExpand={() => setExpandedId(expandedId === tier.id ? null : tier.id)} />
          </motion.div>
        ))}
      </div>
      <AnimatePresence>
        {selectedId && (
          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 10 }} className="flex justify-center pt-2">
            <motion.button onClick={handleConfirm} whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }} className="px-8 py-3 bg-gradient-to-r from-amber-500 to-amber-400 text-navy-900 font-semibold rounded-xl shadow-lg shadow-amber-500/25 hover:shadow-xl hover:shadow-amber-500/30 transition-all">
              Accept {tiers.find((t) => t.id === selectedId)?.name} & Submit
            </motion.button>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

// ==================== MESSAGE BUBBLE ====================
const MessageBubble = memo(function MessageBubble({ message, onSelectTier, onImageClick }: { message: Message; onSelectTier?: (tierId: string) => void; onImageClick?: (url: string) => void }) {
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
    <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className={`flex gap-3 ${isUser ? "flex-row-reverse" : ""}`}>
      <div className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center ${isUser ? "bg-gradient-to-br from-amber-400 to-amber-500" : "bg-gradient-to-br from-navy-600 to-navy-700"}`}>
        {isUser ? <User className="w-4 h-4 text-white" /> : <Bot className="w-4 h-4 text-white" />}
      </div>
      
      <div className={`flex flex-col ${isUser ? "items-end" : "items-start"} max-w-[85%] md:max-w-[75%]`}>
        {images.length > 0 && (
          <div className="flex flex-wrap gap-2 mb-2">
            {images.map((url, idx) => (
              <motion.img 
                key={idx} 
                src={getImageSrc(url)} 
                alt={`Uploaded ${idx + 1}`} 
                onClick={() => onImageClick?.(getImageSrc(url))}
                whileHover={{ scale: 1.02 }}
                className="max-h-40 rounded-xl object-cover shadow-sm cursor-pointer hover:shadow-md transition-shadow" 
                loading="lazy" 
              />
            ))}
          </div>
        )}
        
        {textContent && (
          <div className={`rounded-2xl px-4 py-3 ${isUser ? "bg-gradient-to-br from-amber-500 to-amber-400 text-white" : "bg-white dark:bg-navy-800 text-navy-900 dark:text-white border border-navy-100 dark:border-navy-700 shadow-sm"}`}>
            <div className={`prose prose-sm max-w-none ${isUser ? "prose-invert" : "prose-navy dark:prose-invert"}`}>
              {isUser ? (
                <p className="m-0 whitespace-pre-wrap">{textContent}</p>
              ) : (
                <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeRaw]} components={{
                  h1: ({ children }) => <h1 className="text-xl font-bold mt-4 mb-2">{children}</h1>,
                  h2: ({ children }) => <h2 className="text-lg font-bold mt-3 mb-2">{children}</h2>,
                  h3: ({ children }) => <h3 className="text-base font-semibold mt-2 mb-1">{children}</h3>,
                  p: ({ children }) => <p className="my-2">{children}</p>,
                  ul: ({ children }) => <ul className="list-disc list-inside my-2 space-y-1">{children}</ul>,
                  ol: ({ children }) => <ol className="list-decimal list-inside my-2 space-y-1">{children}</ol>,
                  img: ({ src, alt }) => (
                    <img src={getImageSrc(src || "")} alt={alt} onClick={() => onImageClick?.(getImageSrc(src || ""))} className="rounded-xl my-3 shadow-sm w-36 h-24 object-cover cursor-pointer hover:opacity-90 transition-opacity" loading="lazy" />
                  ),
                  strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
                  hr: () => <hr className="my-4 border-navy-200 dark:border-navy-700" />,
                }}>{textContent}</ReactMarkdown>
              )}
            </div>
          </div>
        )}
        
        <span className="text-xs text-navy-400 dark:text-navy-500 mt-1 px-1">{formatTime(message.timestamp)}</span>
        
        {tierCards?.tiers && onSelectTier && (
          <div className="mt-3 w-full"><TierCards tiers={tierCards.tiers} onSelectTier={onSelectTier} /></div>
        )}
      </div>
    </motion.div>
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
  const [lightboxImage, setLightboxImage] = useState<string | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => { setTimeout(() => messagesEndRef.current?.scrollIntoView({ behavior: "smooth" }), 100); }, [messages.length, isSending]);
  useEffect(() => { const t = textareaRef.current; if (t) { t.style.height = "auto"; t.style.height = `${Math.min(t.scrollHeight, 150)}px`; } }, [input]);
  useEffect(() => { if (!isSending && messages.length > 0) { const timer = setTimeout(() => textareaRef.current?.focus(), 50); return () => clearTimeout(timer); } }, [isSending, messages.length]);
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
      setPendingFiles((prev) => prev.map((f) => f.preview === preview ? { ...f, uploading: false, uploaded: { file_id: result.file_id, url: result.url } } : f));
    } catch (err) {
      setPendingFiles((prev) => prev.map((f) => f.preview === preview ? { ...f, uploading: false, error: err instanceof Error ? err.message : "Upload failed" } : f));
    }
  }, []);

  const handleFileSelect = useCallback(async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []);
    e.target.value = "";
    for (const file of files) await addFileToUpload(file);
  }, [addFileToUpload]);

  const handleCameraCapture = useCallback((file: File) => { addFileToUpload(file); }, [addFileToUpload]);
  const removeFile = useCallback((index: number) => { setPendingFiles((prev) => { const file = prev[index]; if (file) URL.revokeObjectURL(file.preview); return prev.filter((_, i) => i !== index); }); }, []);

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
      const parts: MessageContent[] = [];
      const displayParts: MessageContent[] = [];
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
    <div className="min-h-screen flex flex-col bg-gradient-to-b from-navy-50 to-white dark:from-navy-950 dark:to-navy-900">
      {/* Header */}
      <header className="flex-shrink-0 border-b border-navy-100 dark:border-navy-800 bg-white/80 dark:bg-navy-900/80 backdrop-blur-lg sticky top-16 md:top-20 z-30">
        <div className="max-w-4xl mx-auto px-4 py-4">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h1 className="text-xl font-bold text-navy-900 dark:text-white">Renovation Estimator</h1>
              {projectState?.project_title && <p className="text-sm text-navy-500 dark:text-navy-400">{projectState.project_title}</p>}
            </div>
            {projectState?.project_type && (
              <span className="text-xs font-medium text-navy-600 dark:text-navy-300 bg-navy-100 dark:bg-navy-800 px-3 py-1 rounded-full capitalize">{projectState.project_type}</span>
            )}
          </div>
          <ProgressBar currentStage={projectState?.current_stage || "project_basics"} />
        </div>
      </header>

      {/* Messages */}
      <main className="flex-1 overflow-y-auto">
        <div className="max-w-4xl mx-auto px-4 py-6">
          <div className="space-y-6">
            <AnimatePresence>
              {messages.map((msg, idx) => <MessageBubble key={idx} message={msg} onSelectTier={handleSelectTier} onImageClick={setLightboxImage} />)}
            </AnimatePresence>
            {isSending && <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}><TypingIndicator /></motion.div>}
            <div ref={messagesEndRef} />
          </div>
        </div>
      </main>

      {/* Error */}
      <AnimatePresence>
        {error && (
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 20 }} className="flex-shrink-0 border-t border-red-200 dark:border-red-900 bg-red-50 dark:bg-red-900/20 px-4 py-3">
            <div className="max-w-4xl mx-auto"><p className="text-sm text-red-600 dark:text-red-400">{error}</p></div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Input */}
      {!isCompleted && (
        <footer className="flex-shrink-0 border-t border-navy-100 dark:border-navy-800 bg-white dark:bg-navy-900">
          <div className="max-w-4xl mx-auto px-4 py-4">
            <ImagePreview files={pendingFiles} onRemove={removeFile} />
            <div className="flex items-end gap-2">
              <motion.button onClick={() => fileInputRef.current?.click()} disabled={isSending} whileTap={{ scale: 0.95 }} className="flex-shrink-0 p-3 text-navy-500 dark:text-navy-400 hover:text-navy-700 dark:hover:text-navy-200 hover:bg-navy-100 dark:hover:bg-navy-800 rounded-xl transition-colors disabled:opacity-50" title="Attach images">
                <Paperclip size={20} />
              </motion.button>
              <motion.button onClick={() => setIsCameraOpen(true)} disabled={isSending} whileTap={{ scale: 0.95 }} className="flex-shrink-0 p-3 text-navy-500 dark:text-navy-400 hover:text-navy-700 dark:hover:text-navy-200 hover:bg-navy-100 dark:hover:bg-navy-800 rounded-xl transition-colors disabled:opacity-50" title="Take photo">
                <Camera size={20} />
              </motion.button>
              <input ref={fileInputRef} type="file" multiple accept="image/jpeg,image/png,image/webp" onChange={handleFileSelect} className="hidden" />
              <div className="flex-1">
                <textarea ref={textareaRef} value={input} onChange={(e) => setInput(e.target.value)} onKeyDown={handleKeyDown} placeholder="Type your message..." disabled={isSending} rows={1} className="w-full resize-none rounded-xl border border-navy-200 dark:border-navy-700 bg-white dark:bg-navy-800 px-4 py-3 text-sm text-navy-900 dark:text-white placeholder-navy-400 focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-transparent disabled:opacity-50 disabled:bg-navy-50 dark:disabled:bg-navy-900" />
              </div>
              <motion.button onClick={() => sendMessage()} disabled={isSending || hasUploadingFiles || (!input.trim() && !hasUploadedFiles)} whileTap={{ scale: 0.95 }} className="flex-shrink-0 p-3 bg-gradient-to-r from-amber-500 to-amber-400 text-white rounded-xl shadow-lg shadow-amber-500/25 hover:shadow-xl hover:shadow-amber-500/30 transition-all disabled:opacity-50 disabled:cursor-not-allowed" title="Send message">
                <Send size={20} />
              </motion.button>
            </div>
            <p className="text-xs text-navy-400 dark:text-navy-500 mt-2 text-center hidden sm:block">Press Enter to send • Shift+Enter for new line</p>
          </div>
        </footer>
      )}

      {/* Completed Footer */}
      {isCompleted && (
        <motion.footer initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="flex-shrink-0 border-t border-emerald-200 dark:border-emerald-800 bg-gradient-to-r from-emerald-50 to-emerald-100 dark:from-emerald-900/20 dark:to-emerald-800/20 py-6">
          <div className="max-w-4xl mx-auto px-4 text-center">
            <div className="flex items-center justify-center gap-2 text-emerald-700 dark:text-emerald-400 font-medium">
              <CheckCircle2 className="w-5 h-5" />
              <span>Your renovation estimate is complete!</span>
            </div>
          </div>
        </motion.footer>
      )}

      {/* Camera Modal */}
      <AnimatePresence>{isCameraOpen && <CameraModal isOpen={isCameraOpen} onClose={() => setIsCameraOpen(false)} onCapture={handleCameraCapture} />}</AnimatePresence>

      {/* Image Lightbox */}
      <ImageLightbox isOpen={!!lightboxImage} imageUrl={lightboxImage || ""} onClose={() => setLightboxImage(null)} />
    </div>
  );
}