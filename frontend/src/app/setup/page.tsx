/**
 * PG Index Agents - Pagina de configuracion
 * https://github.com/686f6c61/pg-index-agents
 *
 * Guia de instalacion con instrucciones paso a paso para configurar
 * las bases de datos de ejemplo y levantar el entorno de desarrollo.
 *
 * Bases de datos documentadas:
 *   - Stack Exchange (rapido): Descarga automatica de sitios SE
 *   - Stack Overflow (completo): Dataset full de archive.org
 *   - Airbnb: Datos de Inside Airbnb para particionamiento
 *
 * Incluye instrucciones para:
 *   - Requisitos previos del sistema
 *   - Creacion e importacion de cada base de datos
 *   - Configuracion y ejecucion del backend
 *   - Configuracion y ejecucion del frontend
 *   - Quick start todo-en-uno
 *
 * @author 686f6c61
 * @license MIT
 */

'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import {
  Database,
  Terminal,
  Download,
  Server,
  CheckCircle,
  Copy,
  Coffee,
  HardDrive,
  Home,
  Settings,
  AlertTriangle,
  Layers
} from 'lucide-react';
import { useState } from 'react';

/** Componente para bloques de codigo copiables */
function CodeBlock({ code, title }: { code: string; title?: string }) {
  const [copied, setCopied] = useState(false);

  const copyToClipboard = () => {
    navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="relative">
      {title && (
        <div className="text-xs text-[var(--muted-foreground)] mb-1">{title}</div>
      )}
      <pre className="bg-[var(--secondary)] p-4 rounded-lg overflow-x-auto text-sm font-mono">
        {code}
      </pre>
      <button
        onClick={copyToClipboard}
        className="absolute top-2 right-2 p-1.5 bg-[var(--background)] rounded hover:bg-[var(--muted)] transition-colors"
        title="Copiar"
      >
        {copied ? (
          <CheckCircle className="h-4 w-4 text-green-500" />
        ) : (
          <Copy className="h-4 w-4 text-[var(--muted-foreground)]" />
        )}
      </button>
    </div>
  );
}

export default function SetupPage() {
  return (
    <div className="space-y-8 max-w-4xl mx-auto">
      {/* Hero Section */}
      <div className="text-center space-y-4 py-8">
        <h1 className="text-4xl font-bold text-[var(--foreground)]">
          Guia de Instalacion
        </h1>
        <p className="text-xl text-[var(--muted-foreground)] max-w-2xl mx-auto">
          Como levantar las bases de datos de ejemplo para PG Index Agents
        </p>
      </div>

      {/* Overview of Available Databases */}
      <Card className="border-[var(--primary)]/20 bg-[var(--primary)]/5">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Layers className="h-6 w-6 text-[var(--primary)]" />
            Bases de Datos Disponibles
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-[var(--muted-foreground)] mb-4">
            El proyecto incluye 3 bases de datos de ejemplo para probar los agentes:
          </p>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="p-4 rounded-lg bg-blue-500/10 border border-blue-500/20">
              <Database className="h-6 w-6 text-blue-500 mb-2" />
              <div className="font-bold text-blue-500">Stack Exchange (Rapido)</div>
              <div className="text-sm text-[var(--muted-foreground)]">
                Descarga automatica de sitios pequenos/medianos
              </div>
              <div className="text-xs text-[var(--muted-foreground)] mt-1">
                5K - 350K registros
              </div>
            </div>
            <div className="p-4 rounded-lg bg-purple-500/10 border border-purple-500/20">
              <Server className="h-6 w-6 text-purple-500 mb-2" />
              <div className="font-bold text-purple-500">Stack Overflow (Completo)</div>
              <div className="text-sm text-[var(--muted-foreground)]">
                Dataset completo para analisis a escala
              </div>
              <div className="text-xs text-[var(--muted-foreground)] mt-1">
                30GB+, 300M+ registros
              </div>
            </div>
            <div className="p-4 rounded-lg bg-orange-500/10 border border-orange-500/20">
              <Home className="h-6 w-6 text-orange-500 mb-2" />
              <div className="font-bold text-orange-500">Airbnb</div>
              <div className="text-sm text-[var(--muted-foreground)]">
                Datos de listings y reviews
              </div>
              <div className="text-xs text-[var(--muted-foreground)] mt-1">
                Ideal para particionamiento
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Prerequisites */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Settings className="h-6 w-6" />
            Requisitos Previos
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <ul className="space-y-2">
            <li className="flex items-start gap-2">
              <CheckCircle className="h-5 w-5 text-green-500 shrink-0 mt-0.5" />
              <span><strong>PostgreSQL 14+</strong> instalado y corriendo</span>
            </li>
            <li className="flex items-start gap-2">
              <CheckCircle className="h-5 w-5 text-green-500 shrink-0 mt-0.5" />
              <span><strong>Python 3.11+</strong> con pip</span>
            </li>
            <li className="flex items-start gap-2">
              <CheckCircle className="h-5 w-5 text-green-500 shrink-0 mt-0.5" />
              <span><strong>7-Zip</strong> (p7zip) para descomprimir archivos Stack Exchange</span>
            </li>
            <li className="flex items-start gap-2">
              <CheckCircle className="h-5 w-5 text-green-500 shrink-0 mt-0.5" />
              <span><strong>Node.js 18+</strong> para el frontend</span>
            </li>
            <li className="flex items-start gap-2">
              <CheckCircle className="h-5 w-5 text-green-500 shrink-0 mt-0.5" />
              <span><strong>wget</strong> (opcional, para descargas mas rapidas)</span>
            </li>
          </ul>

          <CodeBlock
            title="Instalar dependencias del sistema (Ubuntu/Debian)"
            code={`sudo apt update
sudo apt install postgresql p7zip-full python3-pip nodejs npm wget`}
          />
        </CardContent>
      </Card>

      {/* Stack Exchange Database - Quick Method */}
      <Card className="border-blue-500/20">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Database className="h-6 w-6 text-blue-500" />
            Opcion 1: Stack Exchange (Metodo Rapido)
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-6">
          <p className="text-[var(--muted-foreground)]">
            Descarga automatica de sitios Stack Exchange pequenos/medianos. Ideal para desarrollo y testing.
            Usa el script <code className="bg-[var(--secondary)] px-1 rounded">import_stackoverflow.py</code>.
          </p>

          <div className="grid grid-cols-3 gap-4">
            <div className="p-4 rounded-lg bg-[var(--muted)] text-center">
              <Coffee className="h-6 w-6 mx-auto mb-2 text-blue-500" />
              <div className="font-bold">Small</div>
              <div className="text-sm text-[var(--muted-foreground)]">coffee.stackexchange</div>
              <div className="text-xs text-[var(--muted-foreground)]">~5K posts</div>
            </div>
            <div className="p-4 rounded-lg bg-blue-500/10 border border-blue-500/20 text-center">
              <Database className="h-6 w-6 mx-auto mb-2 text-blue-500" />
              <div className="font-bold">Medium (Recomendado)</div>
              <div className="text-sm text-[var(--muted-foreground)]">dba.stackexchange</div>
              <div className="text-xs text-[var(--muted-foreground)]">~75K posts</div>
            </div>
            <div className="p-4 rounded-lg bg-[var(--muted)] text-center">
              <Server className="h-6 w-6 mx-auto mb-2 text-blue-500" />
              <div className="font-bold">Large</div>
              <div className="text-sm text-[var(--muted-foreground)]">serverfault</div>
              <div className="text-xs text-[var(--muted-foreground)]">~350K posts</div>
            </div>
          </div>

          <div className="space-y-4">
            <h4 className="font-medium flex items-center gap-2">
              <Terminal className="h-5 w-5" />
              Pasos de Instalacion
            </h4>

            <div className="space-y-3">
              <div className="flex items-start gap-3">
                <span className="flex items-center justify-center w-6 h-6 rounded-full bg-blue-500 text-white text-sm font-bold shrink-0">1</span>
                <div className="flex-1">
                  <p className="font-medium">Crear la base de datos en PostgreSQL</p>
                  <CodeBlock code={`sudo -u postgres createdb stackoverflow_sample`} />
                </div>
              </div>

              <div className="flex items-start gap-3">
                <span className="flex items-center justify-center w-6 h-6 rounded-full bg-blue-500 text-white text-sm font-bold shrink-0">2</span>
                <div className="flex-1">
                  <p className="font-medium">Activar el entorno virtual del backend</p>
                  <CodeBlock code={`cd backend
source venv/bin/activate`} />
                </div>
              </div>

              <div className="flex items-start gap-3">
                <span className="flex items-center justify-center w-6 h-6 rounded-full bg-blue-500 text-white text-sm font-bold shrink-0">3</span>
                <div className="flex-1">
                  <p className="font-medium">Ejecutar el script de importacion</p>
                  <CodeBlock code={`cd ../scripts
python import_stackoverflow.py --sample-size medium`} />
                  <p className="text-sm text-[var(--muted-foreground)] mt-2">
                    Opciones: <code className="bg-[var(--secondary)] px-1 rounded">small</code>, <code className="bg-[var(--secondary)] px-1 rounded">medium</code>, <code className="bg-[var(--secondary)] px-1 rounded">large</code>
                  </p>
                </div>
              </div>

              <div className="flex items-start gap-3">
                <span className="flex items-center justify-center w-6 h-6 rounded-full bg-blue-500 text-white text-sm font-bold shrink-0">4</span>
                <div className="flex-1">
                  <p className="font-medium">Verificar la importacion</p>
                  <CodeBlock code={`psql -d stackoverflow_sample -c "SELECT COUNT(*) FROM posts;"`} />
                </div>
              </div>
            </div>
          </div>

          <div className="p-4 rounded-lg bg-blue-500/10 border border-blue-500/20">
            <h5 className="font-medium mb-2">Tablas creadas:</h5>
            <div className="flex flex-wrap gap-2 text-sm">
              {['users', 'posts', 'comments', 'votes', 'badges', 'tags', 'post_links'].map((table) => (
                <span key={table} className="px-2 py-1 rounded bg-[var(--background)] border border-[var(--border)]">
                  {table}
                </span>
              ))}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Stack Overflow Full - Manual Method */}
      <Card className="border-purple-500/20">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Server className="h-6 w-6 text-purple-500" />
            Opcion 2: Stack Overflow Completo (Metodo Manual)
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-6">
          <p className="text-[var(--muted-foreground)]">
            Descarga del dataset completo de Stack Overflow desde archive.org.
            Ideal para analisis a escala real con millones de registros.
          </p>

          <div className="p-4 rounded-lg bg-purple-500/10 border border-purple-500/20">
            <div className="flex items-center gap-2 mb-2">
              <AlertTriangle className="h-5 w-5 text-purple-500" />
              <span className="font-medium">Nota sobre el tamano</span>
            </div>
            <p className="text-sm text-[var(--muted-foreground)]">
              El dataset completo de Stack Overflow ocupa ~30GB comprimido y ~150GB descomprimido.
              Asegurate de tener suficiente espacio en disco.
            </p>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div className="p-3 rounded-lg bg-[var(--muted)] text-center">
              <div className="font-bold text-purple-500">Full</div>
              <div className="text-xs text-[var(--muted-foreground)]">Posts + Users + Comments + Votes + Badges + Tags</div>
              <div className="text-xs text-[var(--muted-foreground)] mt-1">~30GB</div>
            </div>
            <div className="p-3 rounded-lg bg-[var(--muted)] text-center">
              <div className="font-bold">Core</div>
              <div className="text-xs text-[var(--muted-foreground)]">Posts + Users</div>
              <div className="text-xs text-[var(--muted-foreground)] mt-1">~21GB</div>
            </div>
            <div className="p-3 rounded-lg bg-[var(--muted)] text-center">
              <div className="font-bold">DBA Site</div>
              <div className="text-xs text-[var(--muted-foreground)]">dba.stackexchange</div>
              <div className="text-xs text-[var(--muted-foreground)] mt-1">~500MB</div>
            </div>
            <div className="p-3 rounded-lg bg-[var(--muted)] text-center">
              <div className="font-bold">Custom</div>
              <div className="text-xs text-[var(--muted-foreground)]">Seleccion manual</div>
              <div className="text-xs text-[var(--muted-foreground)] mt-1">Variable</div>
            </div>
          </div>

          <div className="space-y-4">
            <h4 className="font-medium flex items-center gap-2">
              <Terminal className="h-5 w-5" />
              Pasos de Instalacion (2 scripts)
            </h4>

            <div className="space-y-3">
              <div className="flex items-start gap-3">
                <span className="flex items-center justify-center w-6 h-6 rounded-full bg-purple-500 text-white text-sm font-bold shrink-0">1</span>
                <div className="flex-1">
                  <p className="font-medium">Descargar el dataset con menu interactivo</p>
                  <CodeBlock code={`cd scripts
python download_stackexchange.py`} />
                  <p className="text-sm text-[var(--muted-foreground)] mt-2">
                    El script mostrara un menu con opciones: Full (30GB), Core (21GB), DBA Site (500MB), o seleccion personalizada.
                  </p>
                </div>
              </div>

              <div className="flex items-start gap-3">
                <span className="flex items-center justify-center w-6 h-6 rounded-full bg-purple-500 text-white text-sm font-bold shrink-0">2</span>
                <div className="flex-1">
                  <p className="font-medium">Crear la base de datos</p>
                  <CodeBlock code={`sudo -u postgres createdb stackexchange`} />
                </div>
              </div>

              <div className="flex items-start gap-3">
                <span className="flex items-center justify-center w-6 h-6 rounded-full bg-purple-500 text-white text-sm font-bold shrink-0">3</span>
                <div className="flex-1">
                  <p className="font-medium">Importar los archivos XML descargados</p>
                  <CodeBlock code={`python import_to_postgres.py`} />
                  <p className="text-sm text-[var(--muted-foreground)] mt-2">
                    Este script lee los XML de la carpeta <code className="bg-[var(--secondary)] px-1 rounded">data/</code> y los carga en PostgreSQL.
                  </p>
                </div>
              </div>
            </div>
          </div>

          <div className="p-4 rounded-lg bg-purple-500/10 border border-purple-500/20">
            <h5 className="font-medium mb-2">Archivos disponibles en archive.org:</h5>
            <div className="flex flex-wrap gap-2 text-xs">
              {['Posts.7z (~20GB)', 'Users.7z (~1GB)', 'Comments.7z (~6GB)', 'Votes.7z (~3GB)', 'Badges.7z (~300MB)', 'Tags.7z (~5MB)'].map((file) => (
                <span key={file} className="px-2 py-1 rounded bg-[var(--background)] border border-[var(--border)]">
                  {file}
                </span>
              ))}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Airbnb Database */}
      <Card className="border-orange-500/20">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Home className="h-6 w-6 text-orange-500" />
            Opcion 3: Airbnb (Inside Airbnb)
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-6">
          <p className="text-[var(--muted-foreground)]">
            Dataset publico de Inside Airbnb con listings, reviews y disponibilidad de alojamientos.
            Ideal para probar analisis de tablas grandes y particionamiento.
          </p>

          <div className="p-4 rounded-lg bg-orange-500/10 border border-orange-500/20">
            <div className="flex items-center gap-2 mb-2">
              <AlertTriangle className="h-5 w-5 text-orange-500" />
              <span className="font-medium">Nota sobre el tamano</span>
            </div>
            <p className="text-sm text-[var(--muted-foreground)]">
              La tabla <code className="bg-[var(--secondary)] px-1 rounded">calendar</code> puede tener millones de filas.
              Usa <code className="bg-[var(--secondary)] px-1 rounded">--skip-calendar</code> para una importacion mas rapida.
            </p>
          </div>

          <div className="space-y-4">
            <h4 className="font-medium flex items-center gap-2">
              <Terminal className="h-5 w-5" />
              Pasos de Instalacion
            </h4>

            <div className="space-y-3">
              <div className="flex items-start gap-3">
                <span className="flex items-center justify-center w-6 h-6 rounded-full bg-orange-500 text-white text-sm font-bold shrink-0">1</span>
                <div className="flex-1">
                  <p className="font-medium">Crear la base de datos</p>
                  <CodeBlock code={`sudo -u postgres createdb airbnb_sample`} />
                </div>
              </div>

              <div className="flex items-start gap-3">
                <span className="flex items-center justify-center w-6 h-6 rounded-full bg-orange-500 text-white text-sm font-bold shrink-0">2</span>
                <div className="flex-1">
                  <p className="font-medium">Ejecutar el script de importacion</p>
                  <CodeBlock code={`cd scripts
python import_airbnb.py --city amsterdam --skip-calendar`} />
                  <p className="text-sm text-[var(--muted-foreground)] mt-2">
                    Ciudades disponibles: <code className="bg-[var(--secondary)] px-1 rounded">amsterdam</code>
                  </p>
                </div>
              </div>
            </div>
          </div>

          <div className="p-4 rounded-lg bg-orange-500/10 border border-orange-500/20">
            <h5 className="font-medium mb-2">Tablas creadas:</h5>
            <div className="flex flex-wrap gap-2 text-sm">
              {['neighbourhoods', 'hosts', 'listings', 'reviews', 'calendar'].map((table) => (
                <span key={table} className="px-2 py-1 rounded bg-[var(--background)] border border-[var(--border)]">
                  {table}
                </span>
              ))}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Backend Setup */}
      <Card className="border-green-500/20">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Server className="h-6 w-6 text-green-500" />
            Levantar el Backend
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-3">
            <div className="flex items-start gap-3">
              <span className="flex items-center justify-center w-6 h-6 rounded-full bg-green-500 text-white text-sm font-bold shrink-0">1</span>
              <div className="flex-1">
                <p className="font-medium">Configurar variables de entorno</p>
                <CodeBlock code={`cd backend
cp .env.example .env
# Editar .env con tu configuracion:
# - OPENROUTER_API_KEY=tu_api_key
# - PG_TARGET_DATABASE=stackoverflow_sample`} />
              </div>
            </div>

            <div className="flex items-start gap-3">
              <span className="flex items-center justify-center w-6 h-6 rounded-full bg-green-500 text-white text-sm font-bold shrink-0">2</span>
              <div className="flex-1">
                <p className="font-medium">Instalar dependencias y levantar</p>
                <CodeBlock code={`source venv/bin/activate
pip install -r requirements.txt
python main.py`} />
              </div>
            </div>
          </div>

          <div className="p-4 rounded-lg bg-green-500/10 border border-green-500/20">
            <p className="text-sm">
              El backend estara disponible en <code className="bg-[var(--secondary)] px-1 rounded">http://localhost:8000</code>
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Frontend Setup */}
      <Card className="border-purple-500/20">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <HardDrive className="h-6 w-6 text-purple-500" />
            Levantar el Frontend
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <CodeBlock code={`cd frontend
npm install
npm run dev`} />

          <div className="p-4 rounded-lg bg-purple-500/10 border border-purple-500/20">
            <p className="text-sm">
              El frontend estara disponible en <code className="bg-[var(--secondary)] px-1 rounded">http://localhost:3000</code>
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Quick Start */}
      <Card className="border-[var(--primary)]/20 bg-[var(--primary)]/5">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Download className="h-6 w-6 text-[var(--primary)]" />
            Quick Start (Todo en uno)
          </CardTitle>
        </CardHeader>
        <CardContent>
          <CodeBlock code={`# 1. Clonar e instalar
git clone <repo>
cd Agentes_Indices

# 2. Crear BD y importar datos
sudo -u postgres createdb stackoverflow_sample
cd backend && source venv/bin/activate
cd ../scripts && python import_stackoverflow.py --sample-size medium

# 3. Levantar backend (terminal 1)
cd ../backend
cp .env.example .env  # Configurar OPENROUTER_API_KEY
python main.py

# 4. Levantar frontend (terminal 2)
cd ../frontend
npm install && npm run dev

# 5. Abrir http://localhost:3000`} />
        </CardContent>
      </Card>

      {/* Footer */}
      <div className="text-center py-8 text-sm text-[var(--muted-foreground)]">
        <p>PG Index Agents - Guia de Instalacion</p>
      </div>
    </div>
  );
}
