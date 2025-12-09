import { create } from 'zustand';
import type { MarketplaceFilters, ProjectType, TierName } from '../lib/types';

/**
 * Zustand Store for Marketplace State
 */
interface MarketplaceState {
  // Filters
  filters: MarketplaceFilters;
  
  // Actions
  setFilter: <K extends keyof MarketplaceFilters>(
    key: K, 
    value: MarketplaceFilters[K]
  ) => void;
  setFilters: (filters: MarketplaceFilters) => void;
  clearFilters: () => void;
}

const defaultFilters: MarketplaceFilters = {
  zipCode: undefined,
  projectType: undefined,
  minPrice: undefined,
  maxPrice: undefined,
  tier: undefined,
};

export const useMarketplaceStore = create<MarketplaceState>((set) => ({
  filters: defaultFilters,
  
  setFilter: (key, value) => 
    set((state) => ({
      filters: {
        ...state.filters,
        [key]: value,
      },
    })),
  
  setFilters: (filters) => set({ filters }),
  
  clearFilters: () => set({ filters: defaultFilters }),
}));

