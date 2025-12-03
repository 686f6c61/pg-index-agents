/**
 * PG Index Agents - Componente ErrorBoundary
 * https://github.com/686f6c61/pg-index-agents
 *
 * Componente de React para capturar errores en el arbol de componentes
 * y mostrar una UI de fallback en lugar de que la aplicacion falle.
 *
 * Exportaciones:
 *
 *   ErrorBoundary:
 *     Clase componente que implementa getDerivedStateFromError y
 *     componentDidCatch para captura de errores. Muestra UI de error
 *     con opcion de reintentar.
 *
 *   withErrorBoundary:
 *     HOC (Higher Order Component) para envolver componentes funcionales
 *     con ErrorBoundary de forma declarativa.
 *
 * @author 686f6c61
 * @license MIT
 */

'use client';

import React, { Component, ErrorInfo, ReactNode } from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';
import { Button } from './Button';
import { Card } from './Card';

/** Props del componente ErrorBoundary */
interface Props {
  children: ReactNode;
  fallback?: ReactNode;
  onError?: (error: Error, errorInfo: ErrorInfo) => void;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null,
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('ErrorBoundary caught an error:', error, errorInfo);
    this.props.onError?.(error, errorInfo);
  }

  private handleRetry = () => {
    this.setState({ hasError: false, error: null });
  };

  public render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <Card className="p-6 text-center">
          <AlertTriangle className="h-12 w-12 mx-auto text-red-500 mb-4" />
          <h2 className="text-lg font-semibold text-[var(--card-foreground)] mb-2">
            Algo salio mal
          </h2>
          <p className="text-sm text-[var(--muted-foreground)] mb-4">
            {this.state.error?.message || 'Error inesperado en el componente'}
          </p>
          <Button onClick={this.handleRetry} size="sm">
            <RefreshCw className="h-4 w-4 mr-2" />
            Reintentar
          </Button>
        </Card>
      );
    }

    return this.props.children;
  }
}

// HOC for functional components
export function withErrorBoundary<P extends object>(
  WrappedComponent: React.ComponentType<P>,
  fallback?: ReactNode
) {
  return function WithErrorBoundary(props: P) {
    return (
      <ErrorBoundary fallback={fallback}>
        <WrappedComponent {...props} />
      </ErrorBoundary>
    );
  };
}
