/**
 * PG Index Agents - Componente Card
 * https://github.com/686f6c61/pg-index-agents
 *
 * Sistema de componentes Card para agrupar contenido relacionado con
 * bordes, sombras y padding consistentes. Sigue el patron de composicion
 * de React para flexibilidad maxima.
 *
 * Componentes exportados:
 *
 *   Card:
 *     Contenedor principal con borde y sombra. Soporta diferentes
 *     niveles de padding (none, sm, md, lg) y atributos ARIA.
 *
 *   CardHeader:
 *     Seccion de cabecera con espaciado apropiado.
 *
 *   CardTitle:
 *     Titulo estilizado para usar dentro de CardHeader.
 *
 *   CardContent:
 *     Area de contenido principal de la tarjeta.
 *
 * @author 686f6c61
 * @license MIT
 */

'use client';

import { ReactNode } from 'react';
import { classNames } from '@/lib/utils';

/** Props del componente Card principal */
interface CardProps {
  children: ReactNode;
  className?: string;
  padding?: 'none' | 'sm' | 'md' | 'lg';
  role?: 'region' | 'article' | 'section';
  'aria-label'?: string;
  'aria-labelledby'?: string;
}

export function Card({
  children,
  className,
  padding = 'md',
  role,
  'aria-label': ariaLabel,
  'aria-labelledby': ariaLabelledBy
}: CardProps) {
  const paddingClasses = {
    none: '',
    sm: 'p-3',
    md: 'p-4',
    lg: 'p-6',
  };

  return (
    <div
      className={classNames(
        'bg-[var(--card)] border border-[var(--border)] rounded-lg shadow-sm',
        paddingClasses[padding],
        className
      )}
      role={role}
      aria-label={ariaLabel}
      aria-labelledby={ariaLabelledBy}
    >
      {children}
    </div>
  );
}

interface CardHeaderProps {
  children: ReactNode;
  className?: string;
}

export function CardHeader({ children, className }: CardHeaderProps) {
  return (
    <div className={classNames('flex flex-col space-y-1.5 p-6 pb-4', className)}>
      {children}
    </div>
  );
}

interface CardTitleProps {
  children: ReactNode;
  className?: string;
}

export function CardTitle({ children, className }: CardTitleProps) {
  return (
    <h3 className={classNames('text-lg font-semibold text-[var(--card-foreground)]', className)}>
      {children}
    </h3>
  );
}

interface CardContentProps {
  children: ReactNode;
  className?: string;
}

export function CardContent({ children, className }: CardContentProps) {
  return (
    <div className={classNames('p-6 pt-0', className)}>
      {children}
    </div>
  );
}
