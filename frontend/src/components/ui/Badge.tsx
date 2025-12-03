/**
 * PG Index Agents - Componente Badge
 * https://github.com/686f6c61/pg-index-agents
 *
 * Componente para mostrar etiquetas o badges con diferentes variantes
 * visuales. Se utiliza para indicar estados, severidades, tipos de tablas,
 * y otras categorizaciones a lo largo de la interfaz.
 *
 * Variantes disponibles:
 *   - default: Estilo neutro
 *   - secondary: Enfasis reducido
 *   - success: Exito, estados positivos
 *   - warning: Advertencias, atencion requerida
 *   - danger/destructive: Errores, alta severidad
 *   - info: Informacion general
 *
 * @author 686f6c61
 * @license MIT
 */

'use client';

import { classNames } from '@/lib/utils';

/** Props del componente Badge */
interface BadgeProps {
  children: React.ReactNode;
  variant?: 'default' | 'success' | 'warning' | 'danger' | 'info' | 'destructive' | 'secondary';
  size?: 'sm' | 'md';
  className?: string;
}

export function Badge({ children, variant = 'default', size = 'sm', className }: BadgeProps) {
  const variants = {
    default: 'bg-[var(--secondary)] text-[var(--secondary-foreground)]',
    secondary: 'bg-[var(--muted)] text-[var(--muted-foreground)]',
    success: 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300',
    warning: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300',
    danger: 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300',
    destructive: 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300',
    info: 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300',
  };

  const sizes = {
    sm: 'px-2 py-0.5 text-xs',
    md: 'px-2.5 py-1 text-sm',
  };

  return (
    <span
      className={classNames(
        'inline-flex items-center font-medium rounded-full',
        variants[variant],
        sizes[size],
        className
      )}
    >
      {children}
    </span>
  );
}
