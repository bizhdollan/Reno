import { useState, useEffect, useCallback, useMemo } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeRaw from 'rehype-raw';
import {
  ArrowLeft,
  Image as ImageIcon,
  MessageSquare,
  DollarSign,
  User,
  Download,
  CheckCircle2,
  Clock,
  MapPin,
  Home,
  Mail,
  Phone,
  Building,
  Loader2,
  AlertCircle,
  FileText,
  Calendar,
  Bot,
  User as UserIcon,
  X
} from 'lucide-react';
import { api } from '../../lib/api';
import ImageLightbox from '../../components/shared/ImageLightBox';
import { generateProjectPDF } from '../../utils/pdfGenerator';

// ==================== TYPES ====================
interface Message {
  role: 'user' | 'assistant';
  content: string | MessageContent[];
  timestamp: string;
}

interface MessageContent {
  type: 'text' | 'image_url' | 'tier_cards';
  text?: string;
  image_url?: { url: string };
  tiers?: any[];
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

interface ProjectDetails {
  // Basic info
  id: string;
  token: string;
  projectType: string | null;
  projectTitle: string | null;
  status: string;
  createdAt: string;
  updatedAt: string;
  zipCode: string | null;

  // Pricing
  selectedTier: CostTier | null;
  allTiers: CostTier[];

  // Images
  images: string[];

  // Conversation
  messages: Message[];

  // Homeowner details (for contractor view)
  homeownerName: string | null;
  homeownerEmail: string | null;
  homeownerPhone: string | null;

  // Contractor details (for unlocked projects)
  contractorName: string | null;
  contractorEmail: string | null;
  contractorPhone: string | null;
  contractorCompany: string | null;

  // Completion status
  homeownerCompleted: boolean;
  contractorCompleted: boolean;

  // View type
  isUnlockView: boolean; // True if viewing via unlock token (contractor)
}

type TabType = 'overview' | 'images' | 'conversation' | 'pricing' | 'homeowner';

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api/v1";

// ==================== UTILITIES ====================
function formatCurrency(amount: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0
  }).format(amount);
}

function formatTime(timestamp: string): string {
  return new Date(timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function formatDate(dateString: string): string {
  return new Date(dateString).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  });
}

function getImageSrc(url: string): string {
  return url.startsWith('/') ? `${API_BASE.replace('/api/v1', '')}${url}` : url;
}

// ==================== MESSAGE BUBBLE ====================
function MessageBubble({ message }: { message: Message }) {
  const isUser = message.role === 'user';

  const { textContent, images } = useMemo(() => {
    if (typeof message.content === 'string') {
      return { textContent: message.content, images: [] };
    }
    const text = message.content
      .filter(p => p.type === 'text')
      .map(p => p.text)
      .join('\n');
    const imgs = message.content
      .filter(p => p.type === 'image_url')
      .map(p => p.image_url?.url)
      .filter(Boolean) as string[];
    return { textContent: text, images: imgs };
  }, [message.content]);

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className={`flex gap-3 ${isUser ? 'flex-row-reverse' : ''}`}
    >
      <div className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center ${
        isUser ? 'bg-gradient-to-br from-amber-400 to-amber-500' : 'bg-gradient-to-br from-navy-600 to-navy-700'
      }`}>
        {isUser ? <UserIcon className="w-4 h-4 text-white" /> : <Bot className="w-4 h-4 text-white" />}
      </div>

      <div className={`flex flex-col ${isUser ? 'items-end' : 'items-start'} max-w-[85%]`}>
        {images.length > 0 && (
          <div className="flex flex-wrap gap-2 mb-2">
            {images.map((url, idx) => (
              <img
                key={idx}
                src={getImageSrc(url)}
                alt={`Uploaded ${idx + 1}`}
                className="max-h-40 rounded-xl object-cover shadow-sm"
                loading="lazy"
              />
            ))}
          </div>
        )}

        {textContent && (
          <div className={`rounded-2xl px-4 py-3 ${
            isUser
              ? 'bg-gradient-to-br from-amber-500 to-amber-400 text-white'
              : 'bg-white dark:bg-navy-800 text-navy-900 dark:text-white border border-navy-100 dark:border-navy-700'
          }`}>
            {isUser ? (
              <p className="whitespace-pre-wrap text-sm">{textContent}</p>
            ) : (
              <div className="prose prose-sm max-w-none dark:prose-invert">
                <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeRaw]}>
                  {textContent}
                </ReactMarkdown>
              </div>
            )}
          </div>
        )}

        {message.timestamp && (
          <span className="text-xs text-navy-400 dark:text-navy-500 mt-1 px-1">
            {formatTime(message.timestamp)}
          </span>
        )}
      </div>
    </motion.div>
  );
}

// ==================== TAB BUTTON ====================
interface TabButtonProps {
  active: boolean;
  onClick: () => void;
  icon: React.ReactNode;
  label: string;
  badge?: number | string;
}

function TabButton({ active, onClick, icon, label, badge }: TabButtonProps) {
  return (
    <motion.button
      onClick={onClick}
      whileTap={{ scale: 0.98 }}
      className={`relative flex items-center gap-2 px-4 py-3 rounded-xl font-medium text-sm transition-all ${
        active
          ? 'bg-amber-500 text-white shadow-lg shadow-amber-500/25'
          : 'bg-white dark:bg-navy-800 text-navy-600 dark:text-navy-300 hover:bg-navy-50 dark:hover:bg-navy-700'
      }`}
    >
      {icon}
      <span className="hidden sm:inline">{label}</span>
      {badge !== undefined && (
        <span className={`px-1.5 py-0.5 rounded-full text-xs font-medium ${
          active ? 'bg-white/20 text-white' : 'bg-navy-100 dark:bg-navy-700 text-navy-600 dark:text-navy-300'
        }`}>
          {badge}
        </span>
      )}
    </motion.button>
  );
}

// ==================== MAIN COMPONENT ====================
export default function ProjectDetailPage() {
  const { token } = useParams<{ token: string }>();
  const navigate = useNavigate();

  const [project, setProject] = useState<ProjectDetails | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<TabType>('overview');
  const [lightboxImage, setLightboxImage] = useState<string | null>(null);
  const [isMarkingComplete, setIsMarkingComplete] = useState(false);

  // Load project details
  useEffect(() => {
    if (!token) {
      setError('No token provided');
      setLoading(false);
      return;
    }

    const loadProjectDetails = async () => {
      setLoading(true);
      setError(null);

      try {
        const tokenType = token.startsWith('PRJ-') ? 'project' : token.startsWith('UNL-') ? 'unlock' : 'invalid';

        if (tokenType === 'invalid') {
          throw new Error('Invalid token format');
        }

        let projectData: any;
        let conversationData: any;
        let isUnlock = false;

        if (tokenType === 'project') {
          // Homeowner view
          projectData = await api.getProjectByToken(token);
          conversationData = await api.getConversationState(token);
        } else {
          // Contractor view (unlock)
          const unlockData = await api.getUnlockDetails(token);
          projectData = unlockData.project;
          conversationData = await api.getConversationState(projectData.token || projectData.id);
          isUnlock = true;

          // Add contractor info from unlock
          projectData.contractorName = unlockData.contractor_name;
          projectData.contractorEmail = unlockData.contractor_email;
          projectData.contractorPhone = unlockData.contractor_phone;
          projectData.contractorCompany = unlockData.contractor_company;
          projectData.contractorCompleted = unlockData.contractor_completed || false;
        }

        // Extract images from conversation
        const images: string[] = [];
        const messages = conversationData.state?.messages || [];

        messages.forEach((msg: any) => {
          if (Array.isArray(msg.content)) {
            msg.content.forEach((part: any) => {
              if (part.type === 'image_url' && part.image_url?.url) {
                images.push(part.image_url.url);
              }
            });
          }
        });

        // Parse selected tier
        let selectedTier: CostTier | null = null;
        const state = conversationData.state;

        if (state?.cost_tiers && state?.selected_tier) {
          const tier = state.cost_tiers.find((t: any) => t.id === state.selected_tier);
          if (tier) {
            selectedTier = tier;
          }
        }

        // Map to ProjectDetails
        const details: ProjectDetails = {
          id: projectData.id,
          token: isUnlock ? token : projectData.token,
          projectType: state?.project_type || projectData.project_type || null,
          projectTitle: state?.project_title || projectData.project_title || null,
          status: projectData.status,
          createdAt: projectData.created_at,
          updatedAt: projectData.updated_at || projectData.created_at,
          zipCode: state?.zip_code || projectData.zip_code || null,
          selectedTier,
          allTiers: state?.cost_tiers || [],
          images,
          messages: messages.filter((msg: any) => {
            if (msg.role === 'user') {
              if (typeof msg.content === 'string') return msg.content.trim().length > 0;
              if (Array.isArray(msg.content)) return msg.content.length > 0;
            }
            return true;
          }),
          homeownerName: projectData.homeowner_name || null,
          homeownerEmail: projectData.homeowner_email || null,
          homeownerPhone: projectData.homeowner_phone || null,
          contractorName: projectData.contractorName || null,
          contractorEmail: projectData.contractorEmail || null,
          contractorPhone: projectData.contractorPhone || null,
          contractorCompany: projectData.contractorCompany || null,
          homeownerCompleted: projectData.homeowner_completed || false,
          contractorCompleted: projectData.contractorCompleted || false,
          isUnlockView: isUnlock,
        };

        setProject(details);
      } catch (err) {
        console.error('Failed to load project:', err);
        setError(err instanceof Error ? err.message : 'Failed to load project details');
      } finally {
        setLoading(false);
      }
    };

    loadProjectDetails();
  }, [token]);

  const handleMarkComplete = useCallback(async () => {
    if (!project) return;

    setIsMarkingComplete(true);
    setError(null);

    try {
      if (project.isUnlockView) {
        await api.markProjectCompleteContractor(token!);
        setProject(prev => prev ? { ...prev, contractorCompleted: true } : null);
      } else {
        await api.markProjectCompleteHomeowner(token!);
        setProject(prev => prev ? { ...prev, homeownerCompleted: true } : null);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to mark project as complete');
    } finally {
      setIsMarkingComplete(false);
    }
  }, [project, token]);

  const handleDownloadPDF = useCallback(async () => {
    if (!project) return;

    try {
      setError(null);
      await generateProjectPDF({
        projectTitle: project.projectTitle,
        projectType: project.projectType,
        status: project.status,
        createdAt: project.createdAt,
        zipCode: project.zipCode,
        selectedTier: project.selectedTier,
        images: project.images,
        messages: project.messages,
        homeownerName: project.homeownerName,
        homeownerEmail: project.homeownerEmail,
        homeownerPhone: project.homeownerPhone,
        contractorName: project.contractorName,
        contractorEmail: project.contractorEmail,
        contractorPhone: project.contractorPhone,
        isUnlockView: project.isUnlockView,
        token: project.token,
      });
    } catch (err) {
      console.error('PDF generation failed:', err);
      setError('Failed to generate PDF. Please try again.');
    }
  }, [project]);

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-b from-navy-50 to-white dark:from-navy-950 dark:to-navy-900 flex items-center justify-center pt-20">
        <div className="text-center">
          <Loader2 className="w-12 h-12 text-amber-500 animate-spin mx-auto mb-4" />
          <p className="text-navy-600 dark:text-navy-400">Loading project details...</p>
        </div>
      </div>
    );
  }

  if (error || !project) {
    return (
      <div className="min-h-screen bg-gradient-to-b from-navy-50 to-white dark:from-navy-950 dark:to-navy-900 pt-20">
        <div className="max-w-4xl mx-auto px-4 py-16">
          <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-2xl p-8 text-center">
            <AlertCircle className="w-16 h-16 text-red-500 mx-auto mb-4" />
            <h2 className="text-2xl font-bold text-navy-900 dark:text-white mb-2">Failed to Load Project</h2>
            <p className="text-navy-600 dark:text-navy-400 mb-6">{error || 'Project not found'}</p>
            <Link to="/projects">
              <motion.button
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                className="px-6 py-3 bg-gradient-to-r from-amber-500 to-amber-400 text-navy-900 font-semibold rounded-xl shadow-lg"
              >
                Back to My Projects
              </motion.button>
            </Link>
          </div>
        </div>
      </div>
    );
  }

  const isProjectCompleted = project.homeownerCompleted && project.contractorCompleted;
  const canMarkComplete = project.isUnlockView ? !project.contractorCompleted : !project.homeownerCompleted;

  return (
    <div className="min-h-screen bg-gradient-to-b from-navy-50 to-white dark:from-navy-950 dark:to-navy-900 pt-20">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Header */}
        <div className="mb-6">
          <button
            onClick={() => navigate('/projects')}
            className="flex items-center gap-2 text-navy-600 dark:text-navy-400 hover:text-navy-900 dark:hover:text-white mb-4 transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
            <span className="text-sm font-medium">Back to My Projects</span>
          </button>

          <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
            <div>
              <h1 className="text-3xl font-bold text-navy-900 dark:text-white mb-2">
                {project.projectTitle || project.projectType || 'Project Details'}
              </h1>
              <div className="flex items-center gap-2 flex-wrap">
                <span className={`px-3 py-1 rounded-full text-xs font-medium ${
                  project.status === 'completed'
                    ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/20 dark:text-emerald-400'
                    : 'bg-blue-100 text-blue-700 dark:bg-blue-500/20 dark:text-blue-400'
                }`}>
                  {project.status}
                </span>
                <span className={`px-3 py-1 rounded-full text-xs font-medium ${
                  project.isUnlockView
                    ? 'bg-purple-100 text-purple-700 dark:bg-purple-500/20 dark:text-purple-400'
                    : 'bg-amber-100 text-amber-700 dark:bg-amber-500/20 dark:text-amber-400'
                }`}>
                  {project.isUnlockView ? 'Contractor View' : 'Homeowner View'}
                </span>
                {isProjectCompleted && (
                  <span className="px-3 py-1 rounded-full text-xs font-medium bg-emerald-100 text-emerald-700 dark:bg-emerald-500/20 dark:text-emerald-400 flex items-center gap-1">
                    <CheckCircle2 className="w-3 h-3" />
                    Project Completed
                  </span>
                )}
              </div>
            </div>

            <div className="flex gap-2">
              <motion.button
                onClick={handleDownloadPDF}
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                className="flex items-center gap-2 px-4 py-2 bg-white dark:bg-navy-800 text-navy-700 dark:text-navy-200 border border-navy-200 dark:border-navy-700 rounded-xl hover:bg-navy-50 dark:hover:bg-navy-700 transition-colors"
              >
                <Download className="w-4 h-4" />
                <span className="hidden sm:inline">PDF</span>
              </motion.button>

              {canMarkComplete && (
                <motion.button
                  onClick={handleMarkComplete}
                  disabled={isMarkingComplete}
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                  className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-emerald-500 to-emerald-400 text-white font-medium rounded-xl shadow-lg shadow-emerald-500/25 disabled:opacity-50"
                >
                  {isMarkingComplete ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <CheckCircle2 className="w-4 h-4" />
                  )}
                  <span className="hidden sm:inline">Mark Complete</span>
                </motion.button>
              )}
            </div>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex gap-2 mb-6 overflow-x-auto pb-2">
          <TabButton
            active={activeTab === 'overview'}
            onClick={() => setActiveTab('overview')}
            icon={<FileText className="w-4 h-4" />}
            label="Overview"
          />
          <TabButton
            active={activeTab === 'images'}
            onClick={() => setActiveTab('images')}
            icon={<ImageIcon className="w-4 h-4" />}
            label="Images"
            badge={project.images.length}
          />
          <TabButton
            active={activeTab === 'conversation'}
            onClick={() => setActiveTab('conversation')}
            icon={<MessageSquare className="w-4 h-4" />}
            label="Conversation"
            badge={project.messages.length}
          />
          <TabButton
            active={activeTab === 'pricing'}
            onClick={() => setActiveTab('pricing')}
            icon={<DollarSign className="w-4 h-4" />}
            label="Pricing"
          />
          {project.isUnlockView && (project.homeownerName || project.homeownerEmail || project.homeownerPhone) && (
            <TabButton
              active={activeTab === 'homeowner'}
              onClick={() => setActiveTab('homeowner')}
              icon={<User className="w-4 h-4" />}
              label="Homeowner"
            />
          )}
        </div>

        {/* Tab Content */}
        <AnimatePresence mode="wait">
          <motion.div
            key={activeTab}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            transition={{ duration: 0.2 }}
          >
            {/* OVERVIEW TAB */}
            {activeTab === 'overview' && (
              <div className="space-y-6">
                <div className="bg-white dark:bg-navy-800 rounded-2xl border border-navy-100 dark:border-navy-700 p-6">
                  <h3 className="text-lg font-semibold text-navy-900 dark:text-white mb-4">Project Information</h3>
                  <div className="grid sm:grid-cols-2 gap-4">
                    <div className="flex items-start gap-3">
                      <div className="w-10 h-10 rounded-xl bg-amber-100 dark:bg-amber-500/20 flex items-center justify-center flex-shrink-0">
                        <Home className="w-5 h-5 text-amber-600 dark:text-amber-400" />
                      </div>
                      <div>
                        <p className="text-sm text-navy-500 dark:text-navy-400">Project Type</p>
                        <p className="font-medium text-navy-900 dark:text-white capitalize">
                          {project.projectType || 'N/A'}
                        </p>
                      </div>
                    </div>

                    <div className="flex items-start gap-3">
                      <div className="w-10 h-10 rounded-xl bg-blue-100 dark:bg-blue-500/20 flex items-center justify-center flex-shrink-0">
                        <MapPin className="w-5 h-5 text-blue-600 dark:text-blue-400" />
                      </div>
                      <div>
                        <p className="text-sm text-navy-500 dark:text-navy-400">Location</p>
                        <p className="font-medium text-navy-900 dark:text-white">
                          {project.zipCode || 'N/A'}
                        </p>
                      </div>
                    </div>

                    <div className="flex items-start gap-3">
                      <div className="w-10 h-10 rounded-xl bg-emerald-100 dark:bg-emerald-500/20 flex items-center justify-center flex-shrink-0">
                        <Calendar className="w-5 h-5 text-emerald-600 dark:text-emerald-400" />
                      </div>
                      <div>
                        <p className="text-sm text-navy-500 dark:text-navy-400">Created</p>
                        <p className="font-medium text-navy-900 dark:text-white">
                          {formatDate(project.createdAt)}
                        </p>
                      </div>
                    </div>

                    <div className="flex items-start gap-3">
                      <div className="w-10 h-10 rounded-xl bg-purple-100 dark:bg-purple-500/20 flex items-center justify-center flex-shrink-0">
                        <DollarSign className="w-5 h-5 text-purple-600 dark:text-purple-400" />
                      </div>
                      <div>
                        <p className="text-sm text-navy-500 dark:text-navy-400">Estimated Cost</p>
                        <p className="font-medium text-navy-900 dark:text-white">
                          {project.selectedTier ? formatCurrency(project.selectedTier.total_cost) : 'N/A'}
                        </p>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Completion Status */}
                {project.status === 'completed' && (
                  <div className="bg-white dark:bg-navy-800 rounded-2xl border border-navy-100 dark:border-navy-700 p-6">
                    <h3 className="text-lg font-semibold text-navy-900 dark:text-white mb-4">Completion Status</h3>
                    <div className="space-y-3">
                      <div className="flex items-center gap-3">
                        <CheckCircle2 className={`w-5 h-5 ${
                          project.homeownerCompleted
                            ? 'text-emerald-500'
                            : 'text-navy-300 dark:text-navy-600'
                        }`} />
                        <span className="text-navy-700 dark:text-navy-300">
                          Homeowner marked as complete
                        </span>
                      </div>
                      <div className="flex items-center gap-3">
                        <CheckCircle2 className={`w-5 h-5 ${
                          project.contractorCompleted
                            ? 'text-emerald-500'
                            : 'text-navy-300 dark:text-navy-600'
                        }`} />
                        <span className="text-navy-700 dark:text-navy-300">
                          Contractor marked as complete
                        </span>
                      </div>

                      {isProjectCompleted && (
                        <div className="mt-4 p-4 bg-emerald-50 dark:bg-emerald-500/10 rounded-xl border border-emerald-200 dark:border-emerald-500/20">
                          <p className="text-sm text-emerald-700 dark:text-emerald-400 flex items-center gap-2">
                            <CheckCircle2 className="w-4 h-4" />
                            Project successfully completed by both parties!
                          </p>
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* IMAGES TAB */}
            {activeTab === 'images' && (
              <div className="bg-white dark:bg-navy-800 rounded-2xl border border-navy-100 dark:border-navy-700 p-6">
                <h3 className="text-lg font-semibold text-navy-900 dark:text-white mb-4">
                  Project Images ({project.images.length})
                </h3>
                {project.images.length > 0 ? (
                  <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
                    {project.images.map((url, idx) => (
                      <motion.div
                        key={idx}
                        initial={{ opacity: 0, scale: 0.9 }}
                        animate={{ opacity: 1, scale: 1 }}
                        transition={{ delay: idx * 0.05 }}
                        className="aspect-square rounded-xl overflow-hidden cursor-pointer group relative"
                        onClick={() => setLightboxImage(getImageSrc(url))}
                      >
                        <img
                          src={getImageSrc(url)}
                          alt={`Project image ${idx + 1}`}
                          className="w-full h-full object-cover transition-transform group-hover:scale-110"
                          loading="lazy"
                        />
                        <div className="absolute inset-0 bg-black/0 group-hover:bg-black/30 transition-colors flex items-center justify-center">
                          <ImageIcon className="w-8 h-8 text-white opacity-0 group-hover:opacity-100 transition-opacity" />
                        </div>
                      </motion.div>
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-12">
                    <ImageIcon className="w-16 h-16 text-navy-300 dark:text-navy-600 mx-auto mb-4" />
                    <p className="text-navy-600 dark:text-navy-400">No images uploaded for this project</p>
                  </div>
                )}
              </div>
            )}

            {/* CONVERSATION TAB */}
            {activeTab === 'conversation' && (
              <div className="bg-white dark:bg-navy-800 rounded-2xl border border-navy-100 dark:border-navy-700 p-6">
                <h3 className="text-lg font-semibold text-navy-900 dark:text-white mb-4">
                  Full Conversation ({project.messages.length} messages)
                </h3>
                <div className="space-y-4 max-h-[600px] overflow-y-auto pr-2">
                  {project.messages.map((msg, idx) => (
                    <MessageBubble key={idx} message={msg} />
                  ))}
                </div>
              </div>
            )}

            {/* PRICING TAB */}
            {activeTab === 'pricing' && (
              <div className="bg-white dark:bg-navy-800 rounded-2xl border border-navy-100 dark:border-navy-700 p-6">
                <h3 className="text-lg font-semibold text-navy-900 dark:text-white mb-4">
                  Selected Tier: {project.selectedTier?.name || 'None'}
                </h3>

                {project.selectedTier ? (
                  <div className="space-y-6">
                    {/* Tier Overview */}
                    <div className="grid sm:grid-cols-3 gap-4">
                      <div className="bg-navy-50 dark:bg-navy-900/50 rounded-xl p-4">
                        <p className="text-sm text-navy-500 dark:text-navy-400 mb-1">Total Cost</p>
                        <p className="text-2xl font-bold text-navy-900 dark:text-white">
                          {formatCurrency(project.selectedTier.total_cost)}
                        </p>
                      </div>
                      <div className="bg-navy-50 dark:bg-navy-900/50 rounded-xl p-4">
                        <p className="text-sm text-navy-500 dark:text-navy-400 mb-1">COGS</p>
                        <p className="text-2xl font-bold text-navy-900 dark:text-white">
                          {formatCurrency(project.selectedTier.cogs)}
                        </p>
                      </div>
                      <div className="bg-navy-50 dark:bg-navy-900/50 rounded-xl p-4">
                        <p className="text-sm text-navy-500 dark:text-navy-400 mb-1">Markup</p>
                        <p className="text-2xl font-bold text-navy-900 dark:text-white">
                          {project.selectedTier.markup_percentage}%
                        </p>
                      </div>
                    </div>

                    {/* Detailed Breakdown */}
                    <div>
                      <h4 className="font-medium text-navy-900 dark:text-white mb-3">Detailed Breakdown</h4>
                      <div className="overflow-x-auto">
                        <table className="w-full text-sm">
                          <thead>
                            <tr className="border-b border-navy-200 dark:border-navy-700">
                              <th className="text-left py-3 font-medium text-navy-600 dark:text-navy-400">Category</th>
                              <th className="text-right py-3 font-medium text-navy-600 dark:text-navy-400">Materials</th>
                              <th className="text-right py-3 font-medium text-navy-600 dark:text-navy-400">Labor</th>
                              <th className="text-right py-3 font-medium text-navy-600 dark:text-navy-400">Total</th>
                            </tr>
                          </thead>
                          <tbody>
                            {project.selectedTier.detailed_breakdown.map((item, idx) => (
                              <tr key={idx} className="border-b border-navy-100 dark:border-navy-800">
                                <td className="py-3">
                                  <div className="font-medium text-navy-900 dark:text-white">{item.category}</div>
                                  <div className="text-xs text-navy-500 dark:text-navy-400">{item.description}</div>
                                </td>
                                <td className="text-right py-3 text-navy-700 dark:text-navy-300">
                                  {formatCurrency(item.materials_cost)}
                                </td>
                                <td className="text-right py-3 text-navy-700 dark:text-navy-300">
                                  {formatCurrency(item.labor_cost)}
                                </td>
                                <td className="text-right py-3 font-medium text-navy-900 dark:text-white">
                                  {formatCurrency(item.total)}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                          <tfoot>
                            <tr className="border-t-2 border-navy-300 dark:border-navy-600">
                              <td className="py-3 font-medium text-navy-900 dark:text-white">Subtotal (COGS)</td>
                              <td colSpan={3} className="text-right py-3 font-medium text-navy-900 dark:text-white">
                                {formatCurrency(project.selectedTier.cogs)}
                              </td>
                            </tr>
                            <tr>
                              <td className="py-3 text-navy-600 dark:text-navy-400">
                                Markup ({project.selectedTier.markup_percentage}%)
                              </td>
                              <td colSpan={3} className="text-right py-3 text-navy-600 dark:text-navy-400">
                                {formatCurrency(project.selectedTier.markup_amount)}
                              </td>
                            </tr>
                            <tr className="bg-amber-100 dark:bg-amber-500/20">
                              <td className="py-3 font-bold text-amber-800 dark:text-amber-300 rounded-l-lg">
                                Total Estimate
                              </td>
                              <td colSpan={3} className="text-right py-3 font-bold text-amber-800 dark:text-amber-300 text-lg rounded-r-lg">
                                {formatCurrency(project.selectedTier.total_cost)}
                              </td>
                            </tr>
                          </tfoot>
                        </table>
                      </div>
                    </div>

                    {/* Included Items */}
                    <div>
                      <h4 className="font-medium text-navy-900 dark:text-white mb-3">Included Items</h4>
                      <div className="flex flex-wrap gap-2">
                        {project.selectedTier.included_items.map((item, idx) => (
                          <span
                            key={idx}
                            className="px-3 py-1.5 bg-emerald-50 dark:bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 text-sm rounded-lg border border-emerald-200 dark:border-emerald-500/20"
                          >
                            {item}
                          </span>
                        ))}
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="text-center py-12">
                    <DollarSign className="w-16 h-16 text-navy-300 dark:text-navy-600 mx-auto mb-4" />
                    <p className="text-navy-600 dark:text-navy-400">No pricing tier selected</p>
                  </div>
                )}
              </div>
            )}

            {/* HOMEOWNER TAB (Contractor view only) */}
            {activeTab === 'homeowner' && project.isUnlockView && (
              <div className="bg-white dark:bg-navy-800 rounded-2xl border border-navy-100 dark:border-navy-700 p-6">
                <h3 className="text-lg font-semibold text-navy-900 dark:text-white mb-4">Homeowner Contact</h3>
                <div className="space-y-4">
                  {project.homeownerName && (
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-xl bg-blue-100 dark:bg-blue-500/20 flex items-center justify-center">
                        <User className="w-5 h-5 text-blue-600 dark:text-blue-400" />
                      </div>
                      <div>
                        <p className="text-sm text-navy-500 dark:text-navy-400">Name</p>
                        <p className="font-medium text-navy-900 dark:text-white">{project.homeownerName}</p>
                      </div>
                    </div>
                  )}

                  {project.homeownerEmail && (
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-xl bg-emerald-100 dark:bg-emerald-500/20 flex items-center justify-center">
                        <Mail className="w-5 h-5 text-emerald-600 dark:text-emerald-400" />
                      </div>
                      <div>
                        <p className="text-sm text-navy-500 dark:text-navy-400">Email</p>
                        <a
                          href={`mailto:${project.homeownerEmail}`}
                          className="font-medium text-amber-600 dark:text-amber-400 hover:underline"
                        >
                          {project.homeownerEmail}
                        </a>
                      </div>
                    </div>
                  )}

                  {project.homeownerPhone && (
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-xl bg-purple-100 dark:bg-purple-500/20 flex items-center justify-center">
                        <Phone className="w-5 h-5 text-purple-600 dark:text-purple-400" />
                      </div>
                      <div>
                        <p className="text-sm text-navy-500 dark:text-navy-400">Phone</p>
                        <a
                          href={`tel:${project.homeownerPhone}`}
                          className="font-medium text-amber-600 dark:text-amber-400 hover:underline"
                        >
                          {project.homeownerPhone}
                        </a>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}
          </motion.div>
        </AnimatePresence>

        {/* Error Display */}
        {error && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="mt-4 p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-xl"
          >
            <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
          </motion.div>
        )}
      </div>

      {/* Image Lightbox */}
      <ImageLightbox
        isOpen={!!lightboxImage}
        imageUrl={lightboxImage || ''}
        onClose={() => setLightboxImage(null)}
      />
    </div>
  );
}
