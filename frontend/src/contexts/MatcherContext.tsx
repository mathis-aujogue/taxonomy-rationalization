import { createContext, useContext, useState, ReactNode } from 'react';
import type { MatchResult } from '../api/client';

type SortField = 'target_l1' | 'target_l2' | 'target_l3' | 'matched_l1' | 'matched_l2' | 'matched_l3' | 'confidence' | 'status';
type SortDirection = 'asc' | 'desc' | null;

interface MatcherState {
  ourTargetId: string;
  clientTargetId: string;
  threshold: number;
  results: MatchResult[];
  expandedRow: number | null;
  sortField: SortField;
  sortDirection: SortDirection;
  statusFilter: string;
  confidenceMin: number;
  confidenceMax: number;
  validationStates: Record<string, 'pending' | 'validated' | 'rejected'>;
}

interface MatcherContextType {
  state: MatcherState;
  setState: (state: Partial<MatcherState>) => void;
  updateValidation: (targetL3: string, status: 'pending' | 'validated' | 'rejected') => void;
  reset: () => void;
}

const initialState: MatcherState = {
  ourTargetId: 'shq_hybrid',
  clientTargetId: '',
  threshold: 0.7,
  results: [],
  expandedRow: null,
  sortField: 'confidence',
  sortDirection: 'desc',
  statusFilter: 'all',
  confidenceMin: 0,
  confidenceMax: 1,
  validationStates: {},
};

const MatcherContext = createContext<MatcherContextType | undefined>(undefined);

export function MatcherProvider({ children }: { children: ReactNode }) {
  const [state, setStateInternal] = useState<MatcherState>(() => {
    // Try to load from localStorage
    const saved = localStorage.getItem('matcher-state');
    if (saved) {
      try {
        const parsed = JSON.parse(saved);
        return { ...initialState, ...parsed };
      } catch {
        return initialState;
      }
    }
    return initialState;
  });

  const setState = (updates: Partial<MatcherState>) => {
    setStateInternal((prev) => {
      const newState = { ...prev, ...updates };
      // Save to localStorage
      localStorage.setItem('matcher-state', JSON.stringify(newState));
      return newState;
    });
  };

  const updateValidation = (targetL3: string, status: 'pending' | 'validated' | 'rejected') => {
    setStateInternal((prev) => {
      const newValidationStates = { ...prev.validationStates, [targetL3]: status };
      const newState = { ...prev, validationStates: newValidationStates };
      localStorage.setItem('matcher-state', JSON.stringify(newState));
      return newState;
    });
  };

  const reset = () => {
    setStateInternal(initialState);
    localStorage.removeItem('matcher-state');
  };

  return (
    <MatcherContext.Provider value={{ state, setState, updateValidation, reset }}>
      {children}
    </MatcherContext.Provider>
  );
}

export function useMatcherContext() {
  const context = useContext(MatcherContext);
  if (!context) {
    throw new Error('useMatcherContext must be used within MatcherProvider');
  }
  return context;
}
