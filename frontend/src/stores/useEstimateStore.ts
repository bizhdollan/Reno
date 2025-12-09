import { create } from 'zustand';
import type { 
  ConversationStep, 
  Message, 
  UploadedImage, 
  ThreeTierEstimate,
  TierName 
} from '../lib/types';

/**
 * Zustand Store for Estimate Flow State
 */
interface EstimateState {
  // Current step in the conversation flow
  currentStep: ConversationStep;
  
  // Chat messages
  messages: Message[];
  
  // Project basics
  projectTitle: string;
  projectType: string;
  zipCode: string;
  
  // Uploaded images
  images: UploadedImage[];
  
  // Generated estimate
  estimate: ThreeTierEstimate | null;
  selectedTier: TierName | null;
  
  // Project token after submission
  projectToken: string | null;
  
  // Loading states
  isLoading: boolean;
  
  // Actions
  setCurrentStep: (step: ConversationStep) => void;
  addMessage: (message: Message) => void;
  setProjectBasics: (title: string, type: string, zip: string) => void;
  addImage: (image: UploadedImage) => void;
  removeImage: (imageId: string) => void;
  setEstimate: (estimate: ThreeTierEstimate) => void;
  selectTier: (tier: TierName) => void;
  setProjectToken: (token: string) => void;
  setLoading: (loading: boolean) => void;
  reset: () => void;
}

const initialState = {
  currentStep: 'welcome' as ConversationStep,
  messages: [],
  projectTitle: '',
  projectType: '',
  zipCode: '',
  images: [],
  estimate: null,
  selectedTier: null,
  projectToken: null,
  isLoading: false,
};

export const useEstimateStore = create<EstimateState>((set) => ({
  ...initialState,
  
  setCurrentStep: (step) => set({ currentStep: step }),
  
  addMessage: (message) => 
    set((state) => ({ 
      messages: [...state.messages, message] 
    })),
  
  setProjectBasics: (title, type, zip) => 
    set({ 
      projectTitle: title, 
      projectType: type, 
      zipCode: zip 
    }),
  
  addImage: (image) => 
    set((state) => ({ 
      images: [...state.images, image] 
    })),
  
  removeImage: (imageId) => 
    set((state) => ({ 
      images: state.images.filter((img) => img.id !== imageId) 
    })),
  
  setEstimate: (estimate) => set({ estimate }),
  
  selectTier: (tier) => set({ selectedTier: tier }),
  
  setProjectToken: (token) => set({ projectToken: token }),
  
  setLoading: (loading) => set({ isLoading: loading }),
  
  reset: () => set(initialState),
}));

