/**
 * PG Index Agents - Componente Dialog
 * https://github.com/686f6c61/pg-index-agents
 *
 * Componente modal accesible para confirmaciones y acciones del usuario.
 * Incluye soporte para cierre con Escape, click fuera del modal, y
 * bloqueo de scroll del body mientras esta abierto.
 *
 * Caracteristicas:
 *   - Variante default y danger para acciones destructivas
 *   - Estados de carga durante operaciones asincronas
 *   - Botones de confirmacion y cancelacion personalizables
 *   - Backdrop con desenfoque para enfocar atencion
 *
 * @author 686f6c61
 * @license MIT
 */

'use client';

import { useEffect, useRef } from 'react';
import { X } from 'lucide-react';
import { Button } from './Button';

/** Props del componente Dialog */
interface DialogProps {
  open: boolean;
  onClose: () => void;
  title: string;
  description?: string;
  children?: React.ReactNode;
  confirmText?: string;
  cancelText?: string;
  onConfirm?: () => void;
  variant?: 'default' | 'danger';
  loading?: boolean;
}

export function Dialog({
  open,
  onClose,
  title,
  description,
  children,
  confirmText = 'Confirm',
  cancelText = 'Cancel',
  onConfirm,
  variant = 'default',
  loading = false,
}: DialogProps) {
  const dialogRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && open) {
        onClose();
      }
    };

    if (open) {
      document.addEventListener('keydown', handleEscape);
      document.body.style.overflow = 'hidden';
    }

    return () => {
      document.removeEventListener('keydown', handleEscape);
      document.body.style.overflow = 'unset';
    };
  }, [open, onClose]);

  if (!open) return null;

  const handleBackdropClick = (e: React.MouseEvent) => {
    if (e.target === e.currentTarget) {
      onClose();
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      onClick={handleBackdropClick}
    >
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" />

      {/* Dialog */}
      <div
        ref={dialogRef}
        className="relative z-10 w-full max-w-md mx-4 bg-[var(--card)] border border-[var(--border)] rounded-xl shadow-2xl animate-in fade-in zoom-in-95 duration-200"
      >
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-[var(--border)]">
          <h2 className="text-lg font-semibold text-[var(--card-foreground)]">
            {title}
          </h2>
          <button
            onClick={onClose}
            className="p-1 rounded-lg hover:bg-[var(--muted)] transition-colors"
          >
            <X className="h-5 w-5 text-[var(--muted-foreground)]" />
          </button>
        </div>

        {/* Content */}
        <div className="p-4">
          {description && (
            <p className="text-sm text-[var(--muted-foreground)] mb-4">
              {description}
            </p>
          )}
          {children}
        </div>

        {/* Footer */}
        {onConfirm && (
          <div className="flex items-center justify-end gap-2 p-4 border-t border-[var(--border)] bg-[var(--secondary)]/50 rounded-b-xl">
            <Button variant="secondary" onClick={onClose} disabled={loading}>
              {cancelText}
            </Button>
            <Button
              onClick={onConfirm}
              loading={loading}
              className={
                variant === 'danger'
                  ? 'bg-red-600 hover:bg-red-700 text-white'
                  : ''
              }
            >
              {confirmText}
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}
