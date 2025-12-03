/**
 * PG Index Agents - Componente Header
 * https://github.com/686f6c61/pg-index-agents
 *
 * Barra de navegacion principal de la aplicacion. Se mantiene fija
 * en la parte superior de la pantalla y proporciona acceso a todas
 * las secciones principales.
 *
 * Enlaces de navegacion:
 *   - Databases: Listado y gestion de bases de datos
 *   - Activity: Historial de actividad y jobs
 *   - PoC: Documentacion de la prueba de concepto
 *   - Setup: Instrucciones de instalacion y configuracion
 *
 * El header incluye deteccion de ruta activa para resaltar
 * la seccion actual en la navegacion.
 *
 * @author 686f6c61
 * @license MIT
 */

'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Database, Activity, Settings, FileText, BookOpen } from 'lucide-react';

/** Componente de cabecera con navegacion principal */
export function Header() {
  const pathname = usePathname();

  const isActive = (path: string) => {
    if (path === '/') {
      return pathname === '/' || pathname.startsWith('/database');
    }
    return pathname.startsWith(path);
  };

  const linkClasses = (path: string) =>
    `text-sm font-medium transition-colors flex items-center gap-1.5 px-3 py-1.5 rounded-md ${
      isActive(path)
        ? 'bg-[var(--primary)]/10 text-[var(--primary)]'
        : 'text-[var(--muted-foreground)] hover:text-[var(--foreground)] hover:bg-[var(--muted)]'
    }`;

  return (
    <header className="bg-[var(--card)] border-b border-[var(--border)] sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          <div className="flex items-center gap-8">
            <Link href="/" className="flex items-center gap-2">
              <Database className="h-8 w-8 text-[var(--primary)]" />
              <span className="text-xl font-bold text-[var(--foreground)]">
                PG Index Agents
              </span>
            </Link>

            <nav className="hidden md:flex items-center gap-2">
              <Link href="/" className={linkClasses('/')}>
                <Database className="h-4 w-4" />
                Databases
              </Link>
              <Link href="/activity" className={linkClasses('/activity')}>
                <Activity className="h-4 w-4" />
                Activity
              </Link>
              <Link href="/poc" className={linkClasses('/poc')}>
                <FileText className="h-4 w-4" />
                PoC
              </Link>
              <Link href="/setup" className={linkClasses('/setup')}>
                <BookOpen className="h-4 w-4" />
                Setup
              </Link>
            </nav>
          </div>

          <div className="flex items-center gap-4">
            <button className="p-2 text-[var(--muted-foreground)] hover:text-[var(--foreground)] transition-colors rounded-md hover:bg-[var(--muted)]">
              <Settings className="h-5 w-5" />
            </button>
          </div>
        </div>
      </div>
    </header>
  );
}
