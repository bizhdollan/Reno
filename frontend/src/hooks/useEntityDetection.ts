import { useState, useCallback, useEffect } from "react";

export interface DetectedEntity {
  type: string;
  label: string;
  confidence: number;
  category?: string;
  location?: string;
  removable?: boolean;
}

interface UseEntityDetectionResult {
  entities: DetectedEntity[];
  isLoading: boolean;
  error: string | null;
  setEntitiesFromState: (entities: DetectedEntity[]) => void;
  clearEntities: () => void;
}

/**
 * Hook for managing detected entities from image analysis.
 *
 * UPDATED: Entities are now extracted from comprehensive image analysis
 * during the chat flow, NOT from a separate API call.
 *
 * Usage:
 *   const { entities, setEntitiesFromState, clearEntities } = useEntityDetection();
 *
 *   // When projectState updates with image_analyses:
 *   useEffect(() => {
 *     const analysisEntities = projectState?.image_analyses?.[0]?.unified_data?.entities;
 *     if (analysisEntities) {
 *       setEntitiesFromState(analysisEntities);
 *     }
 *   }, [projectState?.image_analyses]);
 */
export function useEntityDetection(): UseEntityDetectionResult {
  const [entities, setEntities] = useState<DetectedEntity[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  /**
   * Set entities from project state (from comprehensive analysis).
   * This replaces the old API-based detection.
   */
  const setEntitiesFromState = useCallback((stateEntities: DetectedEntity[]) => {
    if (stateEntities && Array.isArray(stateEntities)) {
      setEntities(stateEntities);
      setError(null);
    }
  }, []);

  const clearEntities = useCallback(() => {
    setEntities([]);
    setError(null);
  }, []);

  return {
    entities,
    isLoading,
    error,
    setEntitiesFromState,
    clearEntities,
  };
}

/**
 * Helper to extract entities from project state.
 * Call this when projectState.image_analyses updates.
 */
export function extractEntitiesFromState(projectState: any): DetectedEntity[] {
  if (!projectState?.image_analyses?.length) {
    return getDefaultEntities();
  }

  // Get entities from the first (primary) image analysis
  const primaryAnalysis = projectState.image_analyses[0];
  const unifiedData = primaryAnalysis?.unified_data;

  if (unifiedData?.entities && Array.isArray(unifiedData.entities)) {
    return unifiedData.entities.map((e: any) => ({
      type: e.type || "unknown",
      label: e.label || e.type || "Unknown",
      confidence: e.confidence || 0.8,
      category: e.category,
      location: e.location,
      removable: e.removable,
    }));
  }

  // Fallback: generate basic entities from what's visible
  return generateEntitiesFromUnifiedData(unifiedData);
}

/**
 * Generate entities from unified_data when explicit entities aren't available.
 */
function generateEntitiesFromUnifiedData(unifiedData: any): DetectedEntity[] {
  if (!unifiedData) {
    return getDefaultEntities();
  }

  const entities: DetectedEntity[] = [];

  // Floor
  if (unifiedData.floor?.material && unifiedData.floor.material !== "unknown") {
    entities.push({
      type: "floor",
      label: `Floor (${unifiedData.floor.material})`,
      confidence: 0.9,
      category: "surface",
      removable: false,
    });
  }

  // Walls
  if (unifiedData.walls?.material && unifiedData.walls.material !== "unknown") {
    entities.push({
      type: "walls",
      label: `Walls (${unifiedData.walls.paint_color || unifiedData.walls.material})`,
      confidence: 0.9,
      category: "surface",
      removable: false,
    });
  }

  // Ceiling
  if (unifiedData.ceiling?.material && unifiedData.ceiling.material !== "unknown") {
    entities.push({
      type: "ceiling",
      label: "Ceiling",
      confidence: 0.85,
      category: "surface",
      removable: false,
    });
  }

  // Windows
  const windows = unifiedData.structural_elements?.windows;
  if (windows && windows.length > 0) {
    entities.push({
      type: "window",
      label: `Windows (${windows.length})`,
      confidence: 0.9,
      category: "structural",
      removable: false,
    });
  }

  // Doors
  const doors = unifiedData.structural_elements?.doors;
  if (doors && doors.length > 0) {
    entities.push({
      type: "door",
      label: `Doors (${doors.length})`,
      confidence: 0.9,
      category: "structural",
      removable: false,
    });
  }

  // Fixtures
  if (unifiedData.fixtures?.length > 0) {
    for (const fixture of unifiedData.fixtures.slice(0, 3)) {
      entities.push({
        type: fixture.type || "fixture",
        label: fixture.type || "Fixture",
        confidence: 0.8,
        category: "fixture",
        removable: true,
      });
    }
  }

  // If we didn't find anything, return defaults
  if (entities.length === 0) {
    return getDefaultEntities();
  }

  return entities;
}

/**
 * Default entities when nothing can be extracted.
 */
function getDefaultEntities(): DetectedEntity[] {
  return [
    { type: "floor", label: "Floor", confidence: 0.8, category: "surface", removable: false },
    { type: "walls", label: "Walls", confidence: 0.8, category: "surface", removable: false },
    { type: "ceiling", label: "Ceiling", confidence: 0.7, category: "surface", removable: false },
  ];
}

export default useEntityDetection;
