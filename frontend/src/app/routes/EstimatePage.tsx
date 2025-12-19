import { useState, useRef, useEffect, useMemo, useCallback, memo } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { motion, AnimatePresence } from "framer-motion";
import { 
  Send, X, Paperclip, Check, ChevronDown, ChevronUp, Camera, SwitchCamera,
  Bot, User, Sparkles, CheckCircle2, Circle, Play, RotateCcw, Film, Mail, Copy, CheckCircle
} from "lucide-react";
import rehypeRaw from "rehype-raw";
import ImageLightbox from "../../components/shared/ImageLightBox";
import { api } from "../../lib/api";

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
  isVideo?: boolean;
  duration?: number;
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
const MAX_VIDEO_SIZE = 25 * 1024 * 1024; // 25MB

// ==================== UTILITIES ====================
function formatCurrency(amount: number): string {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(amount);
}

function formatTime(timestamp: string): string {
  return new Date(timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function formatDuration(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}

function isVideoFile(file: File): boolean {
  return file.type.startsWith('video/');
}

async function uploadFile(file: File): Promise<FileUploadResponse> {
  const formData = new FormData();
  formData.append("file", file);
  const response = await fetch(`${API_BASE}/upload`, { method: "POST", body: formData });
  if (!response.ok) throw new Error(await response.text() || "Upload failed");
  return response.json();
}

// // Generate thumbnail from video blob - extract first frame
// async function generateVideoThumbnail(videoBlob: Blob): Promise<string> {
//   return new Promise((resolve, reject) => {
//     const video = document.createElement('video');
//     const canvas = document.createElement('canvas');
//     const ctx = canvas.getContext('2d');
    
//     video.preload = 'metadata';
//     video.muted = true;
//     video.playsInline = true;
    
//     const url = URL.createObjectURL(videoBlob);
    
//     video.onloadeddata = () => {
//       // Seek to first frame
//       video.currentTime = 0.1;
//     };
    
//     video.onseeked = () => {
//       canvas.width = video.videoWidth;
//       canvas.height = video.videoHeight;
      
//       if (ctx) {
//         ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
//         const thumbnailUrl = canvas.toDataURL('image/jpeg', 0.8);
//         URL.revokeObjectURL(url);
//         resolve(thumbnailUrl);
//       } else {
//         URL.revokeObjectURL(url);
//         reject(new Error('Could not get canvas context'));
//       }
//     };
    
//     video.onerror = () => {
//       URL.revokeObjectURL(url);
//       reject(new Error('Failed to load video'));
//     };
    
//     video.src = url;
//   });
// }

// // Get video duration
// async function getVideoDuration(videoBlob: Blob): Promise<number> {
//   return new Promise((resolve) => {
//     const video = document.createElement('video');
//     video.preload = 'metadata';
//     const url = URL.createObjectURL(videoBlob);
    
//     video.onloadedmetadata = () => {
//       URL.revokeObjectURL(url);
//       resolve(video.duration);
//     };
    
//     video.onerror = () => {
//       URL.revokeObjectURL(url);
//       resolve(0);
//     };
    
//     video.src = url;
//   });
// }

// ==================== PROGRESS BAR ====================
const ProgressBar = memo(function ProgressBar({ currentStage }: { currentStage: string }) {
  const currentIndex = STAGES.findIndex((s) => s.key === currentStage);

  return (
    <div className="w-full">
      <div className="flex items-center justify-between relative">
        <div className="absolute left-0 right-0 top-4 sm:top-5 h-0.5 bg-navy-200 dark:bg-navy-700 -z-10" />
        <motion.div 
          className="absolute left-0 top-4 sm:top-5 h-0.5 bg-gradient-to-r from-amber-500 to-amber-400 -z-10"
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
                className={`w-8 h-8 sm:w-10 sm:h-10 rounded-full flex items-center justify-center text-sm shadow-sm ${
                  isCompleted || isCurrent ? "text-white" : "text-navy-400"
                }`}
              >
                {isCompleted ? (
                  <CheckCircle2 className="w-4 h-4 sm:w-5 sm:h-5" />
                ) : isCurrent ? (
                  <motion.div animate={{ rotate: 360 }} transition={{ duration: 2, repeat: Infinity, ease: "linear" }}>
                    <Sparkles className="w-4 h-4 sm:w-5 sm:h-5" />
                  </motion.div>
                ) : (
                  <Circle className="w-4 h-4 sm:w-5 sm:h-5" />
                )}
              </motion.div>
              
              <p className={`text-[10px] sm:text-xs font-medium mt-1 sm:mt-2 text-center ${
                isCurrent ? "text-amber-600 dark:text-amber-400" : "text-navy-500 dark:text-navy-400"
              }`}>
                {stage.label}
              </p>
            </div>
          );
        })}
      </div>
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

// ==================== IMAGE/VIDEO PREVIEW ====================
const ImagePreview = memo(function ImagePreview({ files, onRemove }: { files: UploadedFile[]; onRemove: (i: number) => void }) {
  if (files.length === 0) return null;
  
  return (
    <motion.div 
      initial={{ opacity: 0, height: 0 }}
      animate={{ opacity: 1, height: 'auto' }}
      exit={{ opacity: 0, height: 0 }}
      className="flex gap-2 p-2 bg-navy-50 dark:bg-navy-800/50 rounded-xl mb-2 overflow-x-auto max-h-24"
    >
      {files.map((file, idx) => (
        <motion.div 
          key={idx} 
          initial={{ opacity: 0, scale: 0.8 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: idx * 0.05 }}
          className="relative flex-shrink-0 group"
        >
          {/* Thumbnail */}
          <img 
            src={file.preview} 
            alt={`Preview ${idx + 1}`}
            className={`h-16 w-16 object-cover rounded-lg border-2 transition-all ${
              file.uploading ? "border-amber-400 opacity-70" : file.error ? "border-red-400" : file.uploaded ? "border-emerald-400" : "border-navy-200 dark:border-navy-600"
            }`} 
          />
          
          {/* Video indicator overlay */}
          {file.isVideo && (
            <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
              <div className="w-8 h-8 rounded-full bg-black/50 flex items-center justify-center">
                <Play size={14} className="text-white ml-0.5" fill="white" />
              </div>
              {file.duration !== undefined && (
                <div className="absolute bottom-1 right-1 bg-black/70 text-white text-[8px] px-1 rounded">
                  {formatDuration(file.duration)}
                </div>
              )}
            </div>
          )}
          
          {/* Uploading spinner */}
          {file.uploading && (
            <div className="absolute inset-0 flex items-center justify-center bg-black/30 rounded-lg">
              <motion.div animate={{ rotate: 360 }} transition={{ duration: 1, repeat: Infinity, ease: "linear" }} className="w-5 h-5 border-2 border-white border-t-transparent rounded-full" />
            </div>
          )}
          
          {/* Upload success indicator */}
          {file.uploaded && !file.isVideo && (
            <motion.div initial={{ scale: 0 }} animate={{ scale: 1 }} className="absolute bottom-0.5 right-0.5 bg-emerald-500 text-white rounded-full p-0.5">
              <Check size={8} />
            </motion.div>
          )}
          
          {/* Video upload success - show film icon instead */}
          {file.uploaded && file.isVideo && (
            <motion.div initial={{ scale: 0 }} animate={{ scale: 1 }} className="absolute bottom-0.5 left-0.5 bg-emerald-500 text-white rounded-full p-0.5">
              <Film size={8} />
            </motion.div>
          )}
          
          {/* Error indicator */}
          {file.error && <div className="absolute bottom-0.5 right-0.5 bg-red-500 text-white text-[8px] px-1 rounded">!</div>}
          
          {/* Remove button */}
          <button onClick={() => onRemove(idx)} className="absolute -top-1.5 -right-1.5 bg-red-500 hover:bg-red-600 text-white rounded-full p-0.5 opacity-0 group-hover:opacity-100 transition-all shadow-md">
            <X size={10} />
          </button>
        </motion.div>
      ))}
    </motion.div>
  );
});

// ==================== CAMERA MODAL WITH VIDEO RECORDING ====================

interface CameraModalProps {
  isOpen: boolean;
  onClose: () => void;
  onCapture: (file: File, thumbnail?: string, duration?: number) => void;
}

type ModalMode = 'camera' | 'photo-preview' | 'video-preview';

// Generate thumbnail from video blob - extract first frame
async function generateVideoThumbnail(videoBlob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const video = document.createElement('video');
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');
    
    video.preload = 'metadata';
    video.muted = true;
    video.playsInline = true;
    
    const url = URL.createObjectURL(videoBlob);
    
    video.onloadeddata = () => {
      video.currentTime = 0.1;
    };
    
    video.onseeked = () => {
      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;
      
      if (ctx) {
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
        const thumbnailUrl = canvas.toDataURL('image/jpeg', 0.8);
        URL.revokeObjectURL(url);
        resolve(thumbnailUrl);
      } else {
        URL.revokeObjectURL(url);
        reject(new Error('Could not get canvas context'));
      }
    };
    
    video.onerror = () => {
      URL.revokeObjectURL(url);
      reject(new Error('Failed to load video'));
    };
    
    video.src = url;
  });
}

// Get video duration
async function getVideoDuration(videoBlob: Blob): Promise<number> {
  return new Promise((resolve) => {
    const video = document.createElement('video');
    video.preload = 'metadata';
    const url = URL.createObjectURL(videoBlob);
    
    video.onloadedmetadata = () => {
      URL.revokeObjectURL(url);
      resolve(video.duration);
    };
    
    video.onerror = () => {
      URL.revokeObjectURL(url);
      resolve(0);
    };
    
    video.src = url;
  });
}

// Separate progress ring component to minimize re-renders
const ProgressRing = memo(function ProgressRing({ progress }: { progress: number }) {
  const circumference = 2 * Math.PI * 46;
  const strokeDashoffset = circumference * (1 - progress / 100);
  
  return (
    <svg 
      className="absolute inset-0 w-full h-full"
      viewBox="0 0 96 96"
      style={{ transform: 'rotate(-90deg)' }}
    >
      <circle
        cx="48"
        cy="48"
        r="46"
        stroke="rgba(239, 68, 68, 0.3)"
        strokeWidth="4"
        fill="none"
      />
      <circle
        cx="48"
        cy="48"
        r="46"
        stroke="rgb(239, 68, 68)"
        strokeWidth="4"
        fill="none"
        strokeDasharray={circumference}
        strokeDashoffset={strokeDashoffset}
        strokeLinecap="round"
        style={{ transition: 'stroke-dashoffset 0.1s linear' }}
      />
    </svg>
  );
});

function CameraModal({ isOpen, onClose, onCapture }: CameraModalProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const previewVideoRef = useRef<HTMLVideoElement>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const recordedChunksRef = useRef<Blob[]>([]);
  const longPressTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const progressRef = useRef<number>(0);
  const rafIdRef = useRef<number | null>(null);
  const recordingStartTimeRef = useRef<number>(0);
  const isLongPressRef = useRef<boolean>(false);
  const streamRef = useRef<MediaStream | null>(null);

  const [facingMode, setFacingMode] = useState<"user" | "environment">("environment");
  const [error, setError] = useState<string | null>(null);
  const [mode, setMode] = useState<ModalMode>('camera');
  const [cameraReady, setCameraReady] = useState(false);
  
  const [isRecording, setIsRecording] = useState(false);
  const [recordingProgress, setRecordingProgress] = useState(0);
  const [recordingTimeLeft, setRecordingTimeLeft] = useState(5);
  const [capturedBlob, setCapturedBlob] = useState<Blob | null>(null);
  const [capturedThumbnail, setCapturedThumbnail] = useState<string | null>(null);
  const [isVideoPlaying, setIsVideoPlaying] = useState(false);

  const MAX_RECORDING_TIME = 5000; // 5 seconds
  const LONG_PRESS_THRESHOLD = 500; // 500ms to trigger video mode (increased from 300)

  // Start camera - simplified and fixed
  const startCamera = useCallback(async (facing: "user" | "environment") => {
    try {
      // Stop existing stream first
      if (streamRef.current) {
        streamRef.current.getTracks().forEach(track => track.stop());
        streamRef.current = null;
      }
      
      setCameraReady(false);
      setError(null);
      
      // Request camera WITHOUT audio
      const constraints: MediaStreamConstraints = {
        video: { 
          facingMode: facing,
          width: { ideal: 1280 },
          height: { ideal: 720 }
        },
        audio: false // DISABLED audio
      };
      
      console.log('Requesting camera with constraints:', constraints);
      
      const mediaStream = await navigator.mediaDevices.getUserMedia(constraints);
      
      console.log('Got media stream:', mediaStream.getTracks().map(t => ({ kind: t.kind, label: t.label, enabled: t.enabled })));
      
      streamRef.current = mediaStream;
      
      // Attach to video element
      if (videoRef.current) {
        videoRef.current.srcObject = mediaStream;
        
        // Wait for video to be ready
        videoRef.current.onloadedmetadata = () => {
          console.log('Video metadata loaded');
          videoRef.current?.play()
            .then(() => {
              console.log('Video playing');
              setCameraReady(true);
            })
            .catch(err => {
              console.error('Video play error:', err);
              setError('Failed to start video preview');
            });
        };
      }
    } catch (err) {
      console.error("Camera error:", err);
      setError(`Camera error: ${err instanceof Error ? err.message : 'Unknown error'}`);
    }
  }, []);

  const stopCamera = useCallback(() => {
    console.log('Stopping camera');
    if (streamRef.current) { 
      streamRef.current.getTracks().forEach(track => {
        console.log('Stopping track:', track.kind, track.label);
        track.stop();
      });
      streamRef.current = null;
    }
    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
    setCameraReady(false);
  }, []);

  // Start camera when modal opens
  useEffect(() => {
    if (isOpen && mode === 'camera') {
      console.log('Modal opened, starting camera');
      startCamera(facingMode);
    }
    
    return () => {
      if (!isOpen) {
        stopCamera();
      }
    };
  }, [isOpen, mode, facingMode, startCamera, stopCamera]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      stopCamera();
      if (rafIdRef.current) {
        cancelAnimationFrame(rafIdRef.current);
      }
      if (longPressTimerRef.current) {
        clearTimeout(longPressTimerRef.current);
      }
    };
  }, [stopCamera]);

  // Reset state when modal closes
  useEffect(() => {
    if (!isOpen) {
      setMode('camera');
      setCapturedBlob(null);
      setCapturedThumbnail(null);
      setIsRecording(false);
      setRecordingProgress(0);
      setRecordingTimeLeft(5);
      isLongPressRef.current = false;
    }
  }, [isOpen]);

  const switchCamera = useCallback(() => {
    const newFacing = facingMode === "user" ? "environment" : "user";
    setFacingMode(newFacing);
    startCamera(newFacing);
  }, [facingMode, startCamera]);

  // Capture photo
  const capturePhoto = useCallback(() => {
    console.log('Capturing photo');
    if (!videoRef.current || !canvasRef.current) {
      console.error('Video or canvas ref not available');
      return;
    }
    
    const video = videoRef.current;
    const canvas = canvasRef.current;
    
    // Make sure video has dimensions
    if (video.videoWidth === 0 || video.videoHeight === 0) {
      console.error('Video has no dimensions');
      setError('Camera not ready. Please try again.');
      return;
    }
    
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    
    const ctx = canvas.getContext("2d");
    if (ctx) {
      ctx.drawImage(video, 0, 0);
      canvas.toBlob((blob) => {
        if (blob) {
          console.log('Photo captured, size:', blob.size);
          setCapturedBlob(blob);
          setCapturedThumbnail(canvas.toDataURL('image/jpeg', 0.8));
          setMode('photo-preview');
          stopCamera();
        }
      }, "image/jpeg", 0.9);
    }
  }, [stopCamera]);

  // Start video recording
  const startRecording = useCallback(() => {
    console.log('Starting recording');
    
    if (!streamRef.current) {
      console.error('No stream available for recording');
      setError('Camera not ready for recording');
      return;
    }

    recordedChunksRef.current = [];
    
    try {
      // Determine supported mime type
      let mimeType = 'video/webm';
      if (MediaRecorder.isTypeSupported('video/webm;codecs=vp9')) {
        mimeType = 'video/webm;codecs=vp9';
      } else if (MediaRecorder.isTypeSupported('video/webm;codecs=vp8')) {
        mimeType = 'video/webm;codecs=vp8';
      } else if (MediaRecorder.isTypeSupported('video/webm')) {
        mimeType = 'video/webm';
      } else if (MediaRecorder.isTypeSupported('video/mp4')) {
        mimeType = 'video/mp4';
      }
      
      console.log('Using mime type:', mimeType);
      
      const mediaRecorder = new MediaRecorder(streamRef.current, {
        mimeType,
        videoBitsPerSecond: 2500000
      });
      
      mediaRecorder.ondataavailable = (event) => {
        console.log('Data available:', event.data.size);
        if (event.data.size > 0) {
          recordedChunksRef.current.push(event.data);
        }
      };

      mediaRecorder.onstop = async () => {
        console.log('Recording stopped, chunks:', recordedChunksRef.current.length);
        
        if (rafIdRef.current) {
          cancelAnimationFrame(rafIdRef.current);
          rafIdRef.current = null;
        }
        
        if (recordedChunksRef.current.length === 0) {
          console.error('No recorded chunks');
          setError('Recording failed - no data captured');
          setIsRecording(false);
          return;
        }
        
        const blob = new Blob(recordedChunksRef.current, { type: mimeType });
        console.log('Created blob, size:', blob.size);
        
        // Generate thumbnail
        try {
          const thumbnail = await generateVideoThumbnail(blob);
          setCapturedThumbnail(thumbnail);
        } catch (err) {
          console.warn('Failed to generate thumbnail:', err);
          setCapturedThumbnail(null);
        }
        
        setCapturedBlob(blob);
        setMode('video-preview');
        setIsRecording(false);
        setRecordingProgress(0);
        setRecordingTimeLeft(5);
        progressRef.current = 0;
        stopCamera();
      };

      mediaRecorder.onerror = (event) => {
        console.error('MediaRecorder error:', event);
        setError('Recording error occurred');
        setIsRecording(false);
      };

      // Start recording with timeslice for periodic data
      mediaRecorder.start(100); // Get data every 100ms
      mediaRecorderRef.current = mediaRecorder;
      recordingStartTimeRef.current = performance.now();
      setIsRecording(true);

      // Progress updates using RAF but throttled state updates
      let lastStateUpdate = 0;
      
      const updateProgress = (timestamp: number) => {
        if (!mediaRecorderRef.current || mediaRecorderRef.current.state !== 'recording') {
          return;
        }
        
        const elapsed = timestamp - recordingStartTimeRef.current;
        const progress = Math.min((elapsed / MAX_RECORDING_TIME) * 100, 100);
        progressRef.current = progress;
        
        // Update React state every 100ms
        if (timestamp - lastStateUpdate > 100) {
          lastStateUpdate = timestamp;
          setRecordingProgress(progress);
          setRecordingTimeLeft(Math.max(0, Math.ceil((MAX_RECORDING_TIME - elapsed) / 1000)));
        }

        if (elapsed >= MAX_RECORDING_TIME) {
          console.log('Max recording time reached, stopping');
          if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
            mediaRecorderRef.current.stop();
          }
        } else {
          rafIdRef.current = requestAnimationFrame(updateProgress);
        }
      };

      rafIdRef.current = requestAnimationFrame(updateProgress);
      
    } catch (err) {
      console.error("Recording error:", err);
      setError(`Recording error: ${err instanceof Error ? err.message : 'Unknown'}`);
      setIsRecording(false);
    }
  }, [stopCamera]);

  // Stop video recording
  const stopRecording = useCallback(() => {
    console.log('stopRecording called, recorder state:', mediaRecorderRef.current?.state);
    
    if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
      mediaRecorderRef.current.stop();
    }
    if (rafIdRef.current) {
      cancelAnimationFrame(rafIdRef.current);
      rafIdRef.current = null;
    }
  }, []);

  // Handle press start
  const handlePressStart = useCallback((e: React.MouseEvent | React.TouchEvent) => {
    e.preventDefault();
    
    if (!cameraReady) {
      console.log('Camera not ready, ignoring press');
      return;
    }
    
    console.log('Press start');
    isLongPressRef.current = false;
    
    // Start long-press timer
    longPressTimerRef.current = setTimeout(() => {
      console.log('Long press threshold reached, starting recording');
      isLongPressRef.current = true;
      startRecording();
    }, LONG_PRESS_THRESHOLD);
  }, [cameraReady, startRecording]);

  // Handle press end
  const handlePressEnd = useCallback((e: React.MouseEvent | React.TouchEvent) => {
    e.preventDefault();
    
    console.log('Press end, isRecording:', isRecording, 'isLongPress:', isLongPressRef.current);
    
    // Clear the long press timer
    if (longPressTimerRef.current) {
      clearTimeout(longPressTimerRef.current);
      longPressTimerRef.current = null;
    }

    if (isRecording) {
      // Was recording, stop it
      console.log('Stopping recording');
      stopRecording();
    } else if (!isLongPressRef.current) {
      // Quick tap - take photo
      console.log('Quick tap, taking photo');
      capturePhoto();
    }
    
    isLongPressRef.current = false;
  }, [isRecording, stopRecording, capturePhoto]);

  // Handle press cancel (mouse leave, touch cancel)
  const handlePressCancel = useCallback(() => {
    console.log('Press cancel');
    
    if (longPressTimerRef.current) {
      clearTimeout(longPressTimerRef.current);
      longPressTimerRef.current = null;
    }
    
    if (isRecording) {
      stopRecording();
    }
    
    isLongPressRef.current = false;
  }, [isRecording, stopRecording]);

  // Retake
  const handleRetake = useCallback(() => {
    setCapturedBlob(null);
    setCapturedThumbnail(null);
    setMode('camera');
    startCamera(facingMode);
  }, [facingMode, startCamera]);

  // Confirm and send
  const handleConfirm = useCallback(async () => {
    if (!capturedBlob) return;

    const isVideo = mode === 'video-preview';
    const extension = isVideo ? 'webm' : 'jpg';
    const mimeType = isVideo ? (capturedBlob.type || 'video/webm') : 'image/jpeg';
    const file = new File([capturedBlob], `capture_${Date.now()}.${extension}`, { type: mimeType });
    
    let duration: number | undefined;
    if (isVideo) {
      duration = await getVideoDuration(capturedBlob);
    }
    
    onCapture(file, capturedThumbnail || undefined, duration);
    onClose();
  }, [capturedBlob, capturedThumbnail, mode, onCapture, onClose]);

  // Video preview playback
  const toggleVideoPlayback = useCallback(() => {
    if (!previewVideoRef.current) return;
    
    if (isVideoPlaying) {
      previewVideoRef.current.pause();
    } else {
      previewVideoRef.current.play();
    }
    setIsVideoPlaying(!isVideoPlaying);
  }, [isVideoPlaying]);

  // Load video preview
  useEffect(() => {
    if (mode === 'video-preview' && capturedBlob && previewVideoRef.current) {
      const url = URL.createObjectURL(capturedBlob);
      previewVideoRef.current.src = url;
      return () => URL.revokeObjectURL(url);
    }
  }, [mode, capturedBlob]);

  if (!isOpen) return null;

  return (
    <motion.div 
      initial={{ opacity: 0 }} 
      animate={{ opacity: 1 }} 
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-50 bg-black"
    >
      {/* Camera Mode */}
      {mode === 'camera' && (
        <>
          {/* Header */}
          <div className="absolute top-0 left-0 right-0 z-10 flex items-center justify-between p-4 bg-gradient-to-b from-black/70 to-transparent">
            <button 
              onClick={onClose} 
              className="text-white p-2 hover:bg-white/10 rounded-lg transition-colors"
            >
              <X size={24} />
            </button>
            
            <div className="flex items-center gap-3">
              {isRecording && (
                <motion.div 
                  initial={{ scale: 0 }}
                  animate={{ scale: 1 }}
                  className="flex items-center gap-2"
                >
                  <motion.div
                    animate={{ opacity: [1, 0.3, 1] }}
                    transition={{ duration: 1, repeat: Infinity }}
                    className="w-3 h-3 bg-red-500 rounded-full"
                  />
                  <span className="text-white font-bold text-lg">{recordingTimeLeft}s</span>
                </motion.div>
              )}
              
              {!cameraReady && !error && (
                <span className="text-white/70 text-sm">Loading camera...</span>
              )}
            </div>

            <button 
              onClick={switchCamera} 
              disabled={isRecording || !cameraReady}
              className="text-white p-2 hover:bg-white/10 rounded-lg transition-colors disabled:opacity-50"
            >
              <SwitchCamera size={24} />
            </button>
          </div>

          {/* Video Preview */}
          <div className="w-full h-full relative overflow-hidden bg-black">
            {error ? (
              <div className="absolute inset-0 flex items-center justify-center">
                <div className="text-white text-center p-4">
                  <p className="mb-4">{error}</p>
                  <button 
                    onClick={() => startCamera(facingMode)} 
                    className="px-4 py-2 bg-amber-500 rounded-lg font-medium hover:bg-amber-600 transition-colors"
                  >
                    Try Again
                  </button>
                </div>
              </div>
            ) : (
              <video 
                ref={videoRef}
                autoPlay
                playsInline
                muted
                className="w-full h-full object-cover"
              />
            )}
            <canvas ref={canvasRef} className="hidden" />
          </div>

          {/* Bottom Controls */}
          <div className="absolute bottom-0 left-0 right-0 z-10 pb-8 pt-6 bg-gradient-to-t from-black/70 to-transparent flex flex-col items-center gap-3">
            <p className="text-white text-sm font-medium opacity-70">
              {isRecording ? "Recording..." : "Tap for photo • Hold for video"}
            </p>
            
            {/* Capture Button */}
            <div className="relative w-24 h-24 flex items-center justify-center">
              {/* Progress ring */}
              {isRecording && (
                <div className="absolute inset-0">
                  <ProgressRing progress={recordingProgress} />
                </div>
              )}

              {/* Button */}
              <button
                onMouseDown={handlePressStart}
                onMouseUp={handlePressEnd}
                onMouseLeave={handlePressCancel}
                onTouchStart={handlePressStart}
                onTouchEnd={handlePressEnd}
                onTouchCancel={handlePressCancel}
                disabled={!!error || !cameraReady}
                className="relative w-20 h-20 rounded-full bg-white border-4 border-gray-300 flex items-center justify-center disabled:opacity-50 shadow-2xl active:scale-95 transition-transform touch-none"
              >
                <div 
                  className={`w-14 h-14 border-2 border-gray-400 transition-all duration-200 ${
                    isRecording 
                      ? 'bg-red-500 rounded-lg scale-50' 
                      : 'bg-white rounded-full'
                  }`}
                />
              </button>
            </div>
          </div>
        </>
      )}

      {/* Photo Preview Mode */}
      {mode === 'photo-preview' && capturedBlob && (
        <div className="w-full h-full flex flex-col">
          <div className="flex-shrink-0 flex items-center justify-between p-4 bg-black/50">
            <button onClick={onClose} className="text-white p-2 hover:bg-white/10 rounded-lg">
              <X size={24} />
            </button>
            <span className="text-white font-medium text-lg">Photo Preview</span>
            <div className="w-10" />
          </div>

          <div className="flex-1 flex items-center justify-center bg-black overflow-hidden">
            <img 
              src={capturedThumbnail || URL.createObjectURL(capturedBlob)} 
              alt="Captured" 
              className="max-w-full max-h-full object-contain"
            />
          </div>

          <div className="flex-shrink-0 flex gap-4 p-6 bg-black/50">
            <motion.button
              onClick={handleRetake}
              whileTap={{ scale: 0.95 }}
              className="flex-1 flex items-center justify-center gap-2 py-3 px-6 bg-white/10 text-white rounded-xl font-medium hover:bg-white/20 transition-colors"
            >
              <RotateCcw size={20} />
              Retake
            </motion.button>
            <motion.button
              onClick={handleConfirm}
              whileTap={{ scale: 0.95 }}
              className="flex-1 flex items-center justify-center gap-2 py-3 px-6 bg-amber-500 text-white rounded-xl font-medium hover:bg-amber-600 transition-colors shadow-lg"
            >
              <Check size={20} />
              Use This
            </motion.button>
          </div>
        </div>
      )}

      {/* Video Preview Mode */}
      {mode === 'video-preview' && capturedBlob && (
        <div className="w-full h-full flex flex-col">
          <div className="flex-shrink-0 flex items-center justify-between p-4 bg-black/50">
            <button onClick={onClose} className="text-white p-2 hover:bg-white/10 rounded-lg">
              <X size={24} />
            </button>
            <span className="text-white font-medium text-lg">Video Preview</span>
            <div className="w-10" />
          </div>

          <div className="flex-1 relative flex items-center justify-center bg-black overflow-hidden">
            <video 
              ref={previewVideoRef}
              loop
              playsInline
              className="max-w-full max-h-full object-contain"
              onPlay={() => setIsVideoPlaying(true)}
              onPause={() => setIsVideoPlaying(false)}
              onEnded={() => setIsVideoPlaying(false)}
            />
            
            <button
              onClick={toggleVideoPlayback}
              className="absolute inset-0 flex items-center justify-center"
            >
              {!isVideoPlaying && (
                <motion.div
                  initial={{ scale: 0 }}
                  animate={{ scale: 1 }}
                  className="w-20 h-20 rounded-full bg-white/20 backdrop-blur-sm flex items-center justify-center"
                >
                  <Play size={32} className="text-white ml-1" fill="white" />
                </motion.div>
              )}
            </button>
          </div>

          <div className="flex-shrink-0 flex gap-4 p-6 bg-black/50">
            <motion.button
              onClick={handleRetake}
              whileTap={{ scale: 0.95 }}
              className="flex-1 flex items-center justify-center gap-2 py-3 px-6 bg-white/10 text-white rounded-xl font-medium hover:bg-white/20 transition-colors"
            >
              <RotateCcw size={20} />
              Retake
            </motion.button>
            <motion.button
              onClick={handleConfirm}
              whileTap={{ scale: 0.95 }}
              className="flex-1 flex items-center justify-center gap-2 py-3 px-6 bg-amber-500 text-white rounded-xl font-medium hover:bg-amber-600 transition-colors shadow-lg"
            >
              <Check size={20} />
              Use This
            </motion.button>
          </div>
        </div>
      )}
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
  const [projectId, setProjectId] = useState<string>("new");
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [pendingFiles, setPendingFiles] = useState<UploadedFile[]>([]);
  const [projectState, setProjectState] = useState<ProjectState | null>(null);
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isCameraOpen, setIsCameraOpen] = useState(false);
  const [lightboxImage, setLightboxImage] = useState<string | null>(null);
  const [showSaveModal, setShowSaveModal] = useState(false);
  const [saveEmail, setSaveEmail] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [savedToken, setSavedToken] = useState<string | null>(null);
  const [tokenCopied, setTokenCopied] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => { setTimeout(() => messagesEndRef.current?.scrollIntoView({ behavior: "smooth" }), 100); }, [messages.length, isSending]);
  useEffect(() => { const t = textareaRef.current; if (t) { t.style.height = "auto"; t.style.height = `${Math.min(t.scrollHeight, 150)}px`; } }, [input]);
  useEffect(() => { if (!isSending && messages.length > 0) { const timer = setTimeout(() => textareaRef.current?.focus(), 50); return () => clearTimeout(timer); } }, [isSending, messages.length]);
  useEffect(() => { return () => { pendingFiles.forEach((f) => URL.revokeObjectURL(f.preview)); }; }, []);

  // Initialize chat only once on mount
  useEffect(() => {
    let isMounted = true;
    const start = async () => {
      setIsSending(true);
      try {
        const res = await fetch(`${API_BASE}/chat`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ project_id: projectId, message: "", state: null }) });
        if (!res.ok) throw new Error("Failed to start");
        const data: any = await res.json();
        if (!isMounted) return; // Prevent state updates if component unmounted
        // Use backend-provided project_id (PRJ-XXXXXX) for subsequent requests
        if (data.project_id && data.project_id !== projectId) {
          setProjectId(data.project_id);
        } else if (data.state?.project_id && data.state.project_id !== projectId) {
          setProjectId(data.state.project_id);
        }
        setProjectState(data.state);
        setMessages([{ role: "assistant", content: data.assistant, timestamp: new Date().toISOString() }]);
      } catch { 
        if (isMounted) {
          setError("Failed to connect. Please refresh.");
        }
      } finally { 
        if (isMounted) {
          setIsSending(false);
        }
      }
    };
    start();
    return () => {
      isMounted = false;
    };
  }, []); // Empty dependency array - only run once on mount

  // Add file to upload with video support
  const addFileToUpload = useCallback(async (file: File, thumbnail?: string, duration?: number) => {
    const isVideo = isVideoFile(file);
    
    // Validate video size
    if (isVideo && file.size > MAX_VIDEO_SIZE) {
      setError(`Video too large. Maximum size is 25MB. Your video is ${(file.size / (1024 * 1024)).toFixed(1)}MB`);
      return;
    }
    
    // Use provided thumbnail for videos, or create object URL for images
    let preview: string;
    if (thumbnail) {
      preview = thumbnail;
    } else if (isVideo) {
      // Generate thumbnail for video files uploaded via file picker
      try {
        preview = await generateVideoThumbnail(file);
      } catch {
        // Fallback to a placeholder
        preview = 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64"><rect fill="%23374151" width="64" height="64"/><polygon fill="%23fff" points="26,20 26,44 44,32"/></svg>';
      }
    } else {
      preview = URL.createObjectURL(file);
    }
    
    // Get duration for videos if not provided
    let videoDuration = duration;
    if (isVideo && videoDuration === undefined) {
      try {
        videoDuration = await getVideoDuration(file);
      } catch {
        videoDuration = undefined;
      }
    }
    
    const fileEntry: UploadedFile = { 
      file, 
      preview, 
      uploading: true,
      isVideo,
      duration: videoDuration
    };
    
    setPendingFiles((prev) => [...prev, fileEntry]);
    
    try {
      const result = await uploadFile(file);
      setPendingFiles((prev) => prev.map((f) => 
        f.file === file 
          ? { ...f, uploading: false, uploaded: { file_id: result.file_id, url: result.url } } 
          : f
      ));
    } catch (err) {
      setPendingFiles((prev) => prev.map((f) => 
        f.file === file 
          ? { ...f, uploading: false, error: err instanceof Error ? err.message : "Upload failed" } 
          : f
      ));
    }
  }, []);

  const handleFileSelect = useCallback(async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []);
    e.target.value = "";
    for (const file of files) await addFileToUpload(file);
  }, [addFileToUpload]);

  const handleCameraCapture = useCallback((file: File, thumbnail?: string, duration?: number) => { 
    addFileToUpload(file, thumbnail, duration); 
  }, [addFileToUpload]);
  
  const removeFile = useCallback((index: number) => { 
    setPendingFiles((prev) => { 
      const file = prev[index]; 
      if (file && !file.isVideo) {
        // Only revoke if it's an object URL (not a data URL from thumbnail)
        if (file.preview.startsWith('blob:')) {
          URL.revokeObjectURL(file.preview);
        }
      }
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
    
    // Clean up previews
    pendingFiles.forEach((f) => {
      if (f.preview.startsWith('blob:')) {
        URL.revokeObjectURL(f.preview);
      }
    });
    setPendingFiles([]);

    try {
      const res = await fetch(`${API_BASE}/chat`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ project_id: projectId, message: messageContent, state: projectState }) });
      if (!res.ok) throw new Error(await res.text());
      const data: any = await res.json();
      if (data.project_id) {
        setProjectId(data.project_id);
      } else if (data.state?.project_id) {
        setProjectId(data.state.project_id);
      }
      setProjectState(data.state);
      setMessages((prev) => [...prev, { role: "assistant", content: data.assistant || "(no response)", timestamp: new Date().toISOString() }]);
    } catch (err) { setError(err instanceof Error ? err.message : "Something went wrong"); } finally { setIsSending(false); }
  }, [isSending, input, pendingFiles, projectId, projectState]);

  const handleSelectTier = useCallback((tierId: string) => { sendMessage(`I select the ${tierId} tier`); }, [sendMessage]);
  const handleKeyDown = useCallback((e: React.KeyboardEvent) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(); } }, [sendMessage]);

  const isCompleted = projectState?.current_stage === "completed";
  const hasUploadingFiles = pendingFiles.some((f) => f.uploading);
  const hasUploadedFiles = pendingFiles.some((f) => f.uploaded);

  // Show save modal when completed
  useEffect(() => {
    if (isCompleted && !savedToken && !showSaveModal) {
      setShowSaveModal(true);
    }
  }, [isCompleted, savedToken, showSaveModal]);

  const handleSaveProject = useCallback(async () => {
    if (!saveEmail.trim()) {
      setError("Please enter your email address");
      return;
    }
    
    setIsSaving(true);
    setError(null);
    
    try {
      const response: any = await api.saveProject(saveEmail, projectId);
      setSavedToken(response.token);
      setShowSaveModal(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save project");
    } finally {
      setIsSaving(false);
    }
  }, [saveEmail]);

  const handleCopyToken = useCallback(() => {
    if (savedToken) {
      navigator.clipboard.writeText(savedToken);
      setTokenCopied(true);
      setTimeout(() => setTokenCopied(false), 2000);
    }
  }, [savedToken]);

  return (
    <div className="min-h-screen flex flex-col bg-gradient-to-b from-navy-50 to-white dark:from-navy-950 dark:to-navy-900">
      {/* Header */}
      <header className="flex-shrink-0 border-b border-navy-100 dark:border-navy-800 bg-white/80 dark:bg-navy-900/80 backdrop-blur-lg sticky top-16 md:top-20 z-30">
        <div className="max-w-4xl mx-auto px-3 sm:px-4 py-2 sm:py-3">
          <div className="flex items-center justify-between mb-2 sm:mb-3">
            <div className="min-w-0 flex-1">
              <h1 className="text-base sm:text-xl font-bold text-navy-900 dark:text-white truncate">Renovation Estimator</h1>
              {projectState?.project_title && (
                <p className="text-xs sm:text-sm text-navy-500 dark:text-navy-400 truncate">{projectState.project_title}</p>
              )}
            </div>
            {projectState?.project_type && (
              <span className="text-[10px] sm:text-xs font-medium text-navy-600 dark:text-navy-300 bg-navy-100 dark:bg-navy-800 px-2 py-0.5 sm:px-3 sm:py-1 rounded-full capitalize ml-2 flex-shrink-0">
                {projectState.project_type}
              </span>
            )}
          </div>
          <ProgressBar currentStage={projectState?.current_stage || "project_basics"} />
        </div>
      </header>

      {/* Messages */}
      <main className="flex-1 overflow-y-auto">
        <div className="max-w-4xl mx-auto px-3 sm:px-4 py-4 sm:py-6">
          <div className="space-y-4 sm:space-y-6 mt-14 sm:mt-16">
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
            <div className="max-w-4xl mx-auto flex items-center justify-between">
              <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
              <button onClick={() => setError(null)} className="text-red-500 hover:text-red-700">
                <X size={16} />
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Input */}
      {!isCompleted && (
        <footer className="flex-shrink-0 border-t border-navy-100 dark:border-navy-800 bg-white dark:bg-navy-900 sticky bottom-0">
          <div className="max-w-4xl mx-auto px-3 sm:px-4 py-2 sm:py-3">
            <AnimatePresence>
              {pendingFiles.length > 0 && <ImagePreview files={pendingFiles} onRemove={removeFile} />}
            </AnimatePresence>
            <div className="flex items-center gap-1.5 sm:gap-2">
              <motion.button onClick={() => fileInputRef.current?.click()} disabled={isSending} whileTap={{ scale: 0.95 }} className="flex-shrink-0 p-2 sm:p-3 text-navy-500 dark:text-navy-400 hover:text-navy-700 dark:hover:text-navy-200 hover:bg-navy-100 dark:hover:bg-navy-800 rounded-xl transition-colors disabled:opacity-50" title="Attach images">
                <Paperclip size={18} className="sm:w-5 sm:h-5" />
              </motion.button>
              <motion.button onClick={() => setIsCameraOpen(true)} disabled={isSending} whileTap={{ scale: 0.95 }} className="flex-shrink-0 p-2 sm:p-3 text-navy-500 dark:text-navy-400 hover:text-navy-700 dark:hover:text-navy-200 hover:bg-navy-100 dark:hover:bg-navy-800 rounded-xl transition-colors disabled:opacity-50" title="Take photo or video">
                <Camera size={18} className="sm:w-5 sm:h-5" />
              </motion.button>
              <input ref={fileInputRef} type="file" multiple accept="image/jpeg,image/png,image/webp,video/mp4,video/webm,video/quicktime" onChange={handleFileSelect} className="hidden" />
              <div className="flex-1">
                <textarea ref={textareaRef} value={input} onChange={(e) => setInput(e.target.value)} onKeyDown={handleKeyDown} placeholder="Type your message..." disabled={isSending} rows={1} className="w-full resize-none rounded-xl border border-navy-200 dark:border-navy-700 bg-white dark:bg-navy-800 px-3 py-2 sm:px-4 sm:py-3 text-sm text-navy-900 dark:text-white placeholder-navy-400 focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-transparent disabled:opacity-50 disabled:bg-navy-50 dark:disabled:bg-navy-900" />
              </div>
              <motion.button onClick={() => sendMessage()} disabled={isSending || hasUploadingFiles || (!input.trim() && !hasUploadedFiles)} whileTap={{ scale: 0.95 }} className="flex-shrink-0 p-2 sm:p-3 bg-gradient-to-r from-amber-500 to-amber-400 text-white rounded-xl shadow-lg shadow-amber-500/25 hover:shadow-xl hover:shadow-amber-500/30 transition-all disabled:opacity-50 disabled:cursor-not-allowed" title="Send message">
                <Send size={18} className="sm:w-5 sm:h-5" />
              </motion.button>
            </div>
            <p className="text-[10px] sm:text-xs text-navy-400 dark:text-navy-500 mt-1.5 text-center hidden sm:block">Press Enter to send • Shift+Enter for new line</p>
          </div>
        </footer>
      )}

      {/* Completed Footer */}
      {isCompleted && (
        <motion.footer initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="flex-shrink-0 border-t border-emerald-200 dark:border-emerald-800 bg-gradient-to-r from-emerald-50 to-emerald-100 dark:from-emerald-900/20 dark:to-emerald-800/20 py-6">
          <div className="max-w-4xl mx-auto px-4 text-center">
            {savedToken ? (
              <div className="space-y-4">
                <div className="flex items-center justify-center gap-2 text-emerald-700 dark:text-emerald-400 font-medium">
                  <CheckCircle2 className="w-5 h-5" />
                  <span>Project saved! Your token has been sent to your email.</span>
                </div>
                <div className="bg-white dark:bg-navy-800 rounded-xl p-4 border border-emerald-200 dark:border-emerald-700">
                  <p className="text-sm text-navy-600 dark:text-navy-400 mb-2">Your Project Token:</p>
                  <div className="flex items-center justify-center gap-2">
                    <code className="text-lg font-mono font-bold text-navy-900 dark:text-white bg-navy-50 dark:bg-navy-900 px-4 py-2 rounded-lg">
                      {savedToken}
                    </code>
                    <motion.button
                      onClick={handleCopyToken}
                      whileTap={{ scale: 0.95 }}
                      className="p-2 bg-navy-100 dark:bg-navy-700 hover:bg-navy-200 dark:hover:bg-navy-600 rounded-lg transition-colors"
                      title="Copy token"
                    >
                      {tokenCopied ? (
                        <CheckCircle className="w-5 h-5 text-emerald-600" />
                      ) : (
                        <Copy className="w-5 h-5 text-navy-600 dark:text-navy-300" />
                      )}
                    </motion.button>
                  </div>
                  <p className="text-xs text-navy-500 dark:text-navy-400 mt-2">Save this token to access your project later</p>
                </div>
              </div>
            ) : (
              <div className="flex items-center justify-center gap-2 text-emerald-700 dark:text-emerald-400 font-medium">
                <CheckCircle2 className="w-5 h-5" />
                <span>Your renovation estimate is complete!</span>
              </div>
            )}
          </div>
        </motion.footer>
      )}

      {/* Save Project Modal */}
      <AnimatePresence>
        {showSaveModal && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center p-4"
            onClick={() => !isSaving && setShowSaveModal(false)}
          >
            <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 20 }}
              onClick={(e) => e.stopPropagation()}
              className="relative bg-white dark:bg-navy-800 rounded-2xl shadow-2xl max-w-md w-full"
            >
              <div className="p-6">
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-xl font-bold text-navy-900 dark:text-white">Save Your Project</h2>
                  {!isSaving && (
                    <button
                      onClick={() => setShowSaveModal(false)}
                      className="p-2 hover:bg-navy-100 dark:hover:bg-navy-700 rounded-lg transition-colors"
                    >
                      <X className="w-5 h-5 text-navy-500" />
                    </button>
                  )}
                </div>
                
                <p className="text-sm text-navy-600 dark:text-navy-400 mb-4">
                  Enter your email to receive your project token. You'll need this token to access your project later.
                </p>
                
                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-navy-700 dark:text-navy-300 mb-2">
                      Email Address
                    </label>
                    <div className="relative">
                      <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-navy-400" />
                      <input
                        type="email"
                        value={saveEmail}
                        onChange={(e) => setSaveEmail(e.target.value)}
                        placeholder="your@email.com"
                        disabled={isSaving}
                        className="w-full pl-10 pr-4 py-3 bg-navy-50 dark:bg-navy-900 border border-navy-200 dark:border-navy-700 rounded-xl text-navy-900 dark:text-white placeholder-navy-400 focus:outline-none focus:ring-2 focus:ring-amber-500 disabled:opacity-50"
                        onKeyDown={(e) => {
                          if (e.key === "Enter" && !isSaving) {
                            handleSaveProject();
                          }
                        }}
                      />
                    </div>
                  </div>
                  
                  <div className="flex gap-3">
                    <button
                      onClick={() => setShowSaveModal(false)}
                      disabled={isSaving}
                      className="flex-1 py-3 px-4 bg-navy-100 dark:bg-navy-700 text-navy-700 dark:text-navy-200 font-medium rounded-xl hover:bg-navy-200 dark:hover:bg-navy-600 transition-colors disabled:opacity-50"
                    >
                      Cancel
                    </button>
                    <motion.button
                      onClick={handleSaveProject}
                      disabled={isSaving || !saveEmail.trim()}
                      whileTap={{ scale: 0.98 }}
                      className="flex-1 py-3 px-4 bg-gradient-to-r from-amber-500 to-amber-400 text-navy-900 font-semibold rounded-xl shadow-lg shadow-amber-500/25 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      {isSaving ? "Saving..." : "Save Project"}
                    </motion.button>
                  </div>
                </div>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Camera Modal */}
      <AnimatePresence>{isCameraOpen && <CameraModal isOpen={isCameraOpen} onClose={() => setIsCameraOpen(false)} onCapture={handleCameraCapture} />}</AnimatePresence>

      {/* Image Lightbox */}
      <ImageLightbox isOpen={!!lightboxImage} imageUrl={lightboxImage || ""} onClose={() => setLightboxImage(null)} />
    </div>
  );
}