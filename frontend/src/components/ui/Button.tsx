/**
 * PG Index Agents - Componente Button
 * https://github.com/686f6c61/pg-index-agents
 *
 * Componente de boton reutilizable con multiples variantes visuales,
 * tamanos, y soporte para estados de carga. Implementado con forwardRef
 * para compatibilidad con refs de React.
 *
 * Variantes:
 *   - primary/default: Accion principal, fondo azul
 *   - secondary: Accion secundaria, fondo gris
 *   - outline: Solo borde, fondo transparente
 *   - danger/destructive: Acciones peligrosas, fondo rojo
 *   - ghost: Sin fondo, hover sutil
 *
 * Tamanos:
 *   - sm: Compacto, para acciones inline
 *   - md: Estandar (por defecto)
 *   - lg: Grande, para acciones principales
 *
 * El estado loading muestra un spinner animado y deshabilita el boton.
 *
 * @author 686f6c61
 * @license MIT
 */

'use client';

import { ButtonHTMLAttributes, forwardRef } from 'react';
import { classNames } from '@/lib/utils';

/** Props del componente Button */
interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'danger' | 'ghost' | 'default' | 'outline' | 'destructive';
  size?: 'sm' | 'md' | 'lg';
  loading?: boolean;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = 'primary', size = 'md', loading, children, disabled, ...props }, ref) => {
    const variants = {
      primary:
        'bg-[var(--primary)] text-[var(--primary-foreground)] hover:bg-blue-600 focus:ring-[var(--ring)]',
      default:
        'bg-[var(--primary)] text-[var(--primary-foreground)] hover:bg-blue-600 focus:ring-[var(--ring)]',
      secondary:
        'bg-[var(--secondary)] text-[var(--secondary-foreground)] hover:bg-slate-200 dark:hover:bg-slate-600 focus:ring-slate-400',
      outline:
        'border border-[var(--border)] bg-transparent text-[var(--foreground)] hover:bg-[var(--secondary)] focus:ring-slate-400',
      danger:
        'bg-[var(--destructive)] text-[var(--destructive-foreground)] hover:bg-red-600 focus:ring-red-400',
      destructive:
        'bg-[var(--destructive)] text-[var(--destructive-foreground)] hover:bg-red-600 focus:ring-red-400',
      ghost:
        'bg-transparent text-[var(--foreground)] hover:bg-[var(--secondary)] focus:ring-slate-400',
    };

    const sizes = {
      sm: 'px-3 py-1.5 text-sm',
      md: 'px-4 py-2 text-sm',
      lg: 'px-6 py-3 text-base',
    };

    return (
      <button
        ref={ref}
        className={classNames(
          'inline-flex items-center justify-center font-medium rounded-md transition-colors',
          'focus:outline-none focus:ring-2 focus:ring-offset-2',
          'disabled:opacity-50 disabled:cursor-not-allowed',
          variants[variant],
          sizes[size],
          className
        )}
        disabled={disabled || loading}
        aria-busy={loading}
        aria-disabled={disabled || loading}
        {...props}
      >
        {loading && (
          <svg
            className="animate-spin -ml-1 mr-2 h-4 w-4"
            fill="none"
            viewBox="0 0 24 24"
            aria-hidden="true"
            role="status"
          >
            <circle
              className="opacity-25"
              cx="12"
              cy="12"
              r="10"
              stroke="currentColor"
              strokeWidth="4"
            />
            <path
              className="opacity-75"
              fill="currentColor"
              d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
            />
          </svg>
        )}
        {loading && <span className="sr-only">Cargando...</span>}
        {children}
      </button>
    );
  }
);

Button.displayName = 'Button';
