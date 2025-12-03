/**
 * PG Index Agents - Componente AIExplanation
 * https://github.com/686f6c61/pg-index-agents
 *
 * Este modulo proporciona componentes para mostrar explicaciones generadas
 * por IA sobre anomalias, senales, propuestas y tareas de mantenimiento.
 * Utiliza el servicio ai_explainer del backend para generar contenido.
 *
 * Componentes exportados:
 *
 *   AIExplanation:
 *     Componente inline o expandible que muestra explicaciones bajo demanda.
 *     Incluye cache en memoria para evitar llamadas API repetidas.
 *
 *   AIExplanationModal:
 *     Version modal para explicaciones detalladas en pantalla completa.
 *
 * Tipos de contenido soportados:
 *   - anomaly: Anomalias detectadas por Explorer
 *   - signal: Senales de monitoreo del Observer
 *   - maintenance: Tareas del Gardener
 *   - proposal: Propuestas del Architect
 *
 * Las explicaciones se renderizan con ReactMarkdown para formateo enriquecido.
 *
 * @author 686f6c61
 * @license MIT
 */

'use client';

import { useState } from 'react';
import { Sparkles, X, RefreshCw, ChevronDown, ChevronUp } from 'lucide-react';
import { Button } from './Button';
import { api } from '@/lib/api';
import ReactMarkdown from 'react-markdown';

/** Props para el componente AIExplanation inline */
interface AIExplanationProps {
  type: 'anomaly' | 'signal' | 'maintenance' | 'proposal';
  data: any;
  databaseId: number;
  compact?: boolean;
}

// Cache for explanations to avoid repeated API calls
const explanationCache = new Map<string, string>();

function getCacheKey(type: string, data: any): string {
  return `${type}-${JSON.stringify(data)}`;
}

export function AIExplanation({ type, data, databaseId, compact = false }: AIExplanationProps) {
  const [explanation, setExplanation] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState(false);

  const cacheKey = getCacheKey(type, data);

  const fetchExplanation = async () => {
    // Check cache first
    if (explanationCache.has(cacheKey)) {
      setExplanation(explanationCache.get(cacheKey)!);
      setExpanded(true);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const result = await api.explainItem(type, data, databaseId);
      const exp = result.explanation;
      setExplanation(exp);
      explanationCache.set(cacheKey, exp);
      setExpanded(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al generar explicacion');
    } finally {
      setLoading(false);
    }
  };

  const handleClick = () => {
    if (explanation) {
      setExpanded(!expanded);
    } else {
      fetchExplanation();
    }
  };

  if (compact) {
    return (
      <button
        onClick={handleClick}
        disabled={loading}
        className="inline-flex items-center gap-1 text-xs text-[var(--primary)] hover:underline disabled:opacity-50"
        title="Explicar con IA"
      >
        {loading ? (
          <RefreshCw className="h-3 w-3 animate-spin" />
        ) : (
          <Sparkles className="h-3 w-3" />
        )}
        {explanation ? (expanded ? 'Ocultar' : 'Ver explicacion') : 'Explicar con IA'}
      </button>
    );
  }

  return (
    <div className="mt-3">
      {/* Button to trigger or toggle explanation */}
      <button
        onClick={handleClick}
        disabled={loading}
        className={`
          flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium
          transition-all duration-200
          ${explanation
            ? 'bg-purple-50 dark:bg-purple-900/20 text-purple-700 dark:text-purple-300 hover:bg-purple-100 dark:hover:bg-purple-900/30'
            : 'bg-[var(--secondary)] text-[var(--foreground)] hover:bg-[var(--muted)]'
          }
          disabled:opacity-50
        `}
      >
        {loading ? (
          <RefreshCw className="h-4 w-4 animate-spin" />
        ) : (
          <Sparkles className="h-4 w-4" />
        )}
        <span>
          {explanation
            ? (expanded ? 'Ocultar explicacion IA' : 'Ver explicacion IA')
            : 'Explicar con IA'
          }
        </span>
        {explanation && (
          expanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />
        )}
      </button>

      {/* Error message */}
      {error && (
        <div className="mt-2 p-2 bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 rounded text-sm">
          {error}
        </div>
      )}

      {/* Explanation content */}
      {explanation && expanded && (
        <div className="mt-3 p-4 bg-gradient-to-br from-purple-50 to-blue-50 dark:from-purple-900/20 dark:to-blue-900/20 rounded-lg border border-purple-200 dark:border-purple-800">
          <div className="flex items-center gap-2 mb-3 text-sm font-medium text-purple-700 dark:text-purple-300">
            <Sparkles className="h-4 w-4" />
            Explicacion generada por IA
          </div>
          <div className="prose prose-sm dark:prose-invert max-w-none text-[var(--card-foreground)]">
            <ReactMarkdown
              components={{
                h1: ({children}) => <h1 className="text-lg font-bold text-[var(--primary)] mt-4 mb-2">{children}</h1>,
                h2: ({children}) => <h2 className="text-base font-bold text-[var(--primary)] mt-4 mb-2">{children}</h2>,
                h3: ({children}) => <h3 className="text-sm font-bold text-[var(--primary)] mt-3 mb-1">{children}</h3>,
                p: ({children}) => <p className="mb-2 text-sm leading-relaxed">{children}</p>,
                ul: ({children}) => <ul className="list-disc pl-5 mb-2 space-y-1">{children}</ul>,
                ol: ({children}) => <ol className="list-decimal pl-5 mb-2 space-y-1">{children}</ol>,
                li: ({children}) => <li className="text-sm">{children}</li>,
                code: ({children, className}) => {
                  const isBlock = className?.includes('language-');
                  return isBlock
                    ? <code className="block bg-[var(--secondary)] p-2 rounded text-xs font-mono my-2 overflow-x-auto">{children}</code>
                    : <code className="bg-[var(--secondary)] px-1 py-0.5 rounded text-xs font-mono">{children}</code>;
                },
                pre: ({children}) => <pre className="bg-[var(--secondary)] p-3 rounded-lg my-2 overflow-x-auto">{children}</pre>,
                strong: ({children}) => <strong className="font-semibold text-[var(--primary)]">{children}</strong>,
                blockquote: ({children}) => <blockquote className="border-l-4 border-purple-400 pl-3 italic my-2">{children}</blockquote>,
              }}
            >
              {explanation}
            </ReactMarkdown>
          </div>
        </div>
      )}
    </div>
  );
}

// Standalone modal version for more detailed explanations
interface AIExplanationModalProps {
  isOpen: boolean;
  onClose: () => void;
  type: 'anomaly' | 'signal' | 'maintenance' | 'proposal';
  data: any;
  databaseId: number;
  title?: string;
}

export function AIExplanationModal({ isOpen, onClose, type, data, databaseId, title }: AIExplanationModalProps) {
  const [explanation, setExplanation] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const cacheKey = getCacheKey(type, data);

  const fetchExplanation = async () => {
    if (explanationCache.has(cacheKey)) {
      setExplanation(explanationCache.get(cacheKey)!);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const result = await api.explainItem(type, data, databaseId);
      const exp = result.explanation;
      setExplanation(exp);
      explanationCache.set(cacheKey, exp);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al generar explicacion');
    } finally {
      setLoading(false);
    }
  };

  // Fetch on open if not already cached
  useState(() => {
    if (isOpen && !explanation && !explanationCache.has(cacheKey)) {
      fetchExplanation();
    } else if (isOpen && explanationCache.has(cacheKey)) {
      setExplanation(explanationCache.get(cacheKey)!);
    }
  });

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4"
      onClick={onClose}
    >
      <div
        className="bg-[var(--card)] rounded-xl shadow-2xl max-w-2xl w-full max-h-[85vh] overflow-hidden"
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div className="bg-gradient-to-r from-purple-500 to-blue-500 p-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-white">
              <Sparkles className="h-5 w-5" />
              <h2 className="text-lg font-bold">
                {title || `Explicacion de ${type}`}
              </h2>
            </div>
            <button
              onClick={onClose}
              className="p-1 hover:bg-white/20 rounded-full transition-colors"
            >
              <X className="h-5 w-5 text-white" />
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="p-5 overflow-y-auto max-h-[calc(85vh-80px)]">
          {loading && (
            <div className="flex items-center justify-center py-12">
              <RefreshCw className="h-8 w-8 animate-spin text-purple-500" />
              <span className="ml-3 text-[var(--muted-foreground)]">
                Generando explicacion con IA...
              </span>
            </div>
          )}

          {error && (
            <div className="p-4 bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 rounded-lg">
              {error}
              <Button
                size="sm"
                variant="secondary"
                onClick={fetchExplanation}
                className="mt-2"
              >
                Reintentar
              </Button>
            </div>
          )}

          {explanation && (
            <div className="prose prose-sm dark:prose-invert max-w-none text-[var(--card-foreground)]">
              <ReactMarkdown
                components={{
                  h1: ({children}) => <h1 className="text-lg font-bold text-[var(--primary)] mt-4 mb-2">{children}</h1>,
                  h2: ({children}) => <h2 className="text-base font-bold text-[var(--primary)] mt-4 mb-2">{children}</h2>,
                  h3: ({children}) => <h3 className="text-sm font-bold text-[var(--primary)] mt-3 mb-1">{children}</h3>,
                  p: ({children}) => <p className="mb-2 text-sm leading-relaxed">{children}</p>,
                  ul: ({children}) => <ul className="list-disc pl-5 mb-2 space-y-1">{children}</ul>,
                  ol: ({children}) => <ol className="list-decimal pl-5 mb-2 space-y-1">{children}</ol>,
                  li: ({children}) => <li className="text-sm">{children}</li>,
                  code: ({children, className}) => {
                    const isBlock = className?.includes('language-');
                    return isBlock
                      ? <code className="block bg-[var(--secondary)] p-2 rounded text-xs font-mono my-2 overflow-x-auto">{children}</code>
                      : <code className="bg-[var(--secondary)] px-1 py-0.5 rounded text-xs font-mono">{children}</code>;
                  },
                  pre: ({children}) => <pre className="bg-[var(--secondary)] p-3 rounded-lg my-2 overflow-x-auto">{children}</pre>,
                  strong: ({children}) => <strong className="font-semibold text-[var(--primary)]">{children}</strong>,
                }}
              >
                {explanation}
              </ReactMarkdown>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
