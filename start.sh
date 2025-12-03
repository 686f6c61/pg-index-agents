#!/bin/bash

# PostgreSQL Index Agents - Interactive Development Script

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$PROJECT_DIR/backend"
FRONTEND_DIR="$PROJECT_DIR/frontend"
BACKEND_PID_FILE="/tmp/index_agents_backend.pid"
FRONTEND_PID_FILE="/tmp/index_agents_frontend.pid"
BACKEND_LOG="/tmp/index_agents_backend.log"
FRONTEND_LOG="/tmp/index_agents_frontend.log"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[OK]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

check_requirements() {
    print_status "Verificando requisitos..."

    # Check Python
    if ! command -v python3 &> /dev/null; then
        print_error "Python 3 no está instalado"
        return 1
    fi

    # Check Node.js
    if ! command -v node &> /dev/null; then
        print_error "Node.js no está instalado"
        return 1
    fi

    # Check npm
    if ! command -v npm &> /dev/null; then
        print_error "npm no está instalado"
        return 1
    fi

    print_success "Todos los requisitos satisfechos"
    return 0
}

is_backend_running() {
    if [ -f "$BACKEND_PID_FILE" ] && kill -0 "$(cat "$BACKEND_PID_FILE")" 2>/dev/null; then
        curl -s http://localhost:8000/health > /dev/null 2>&1
        return $?
    fi
    return 1
}

is_frontend_running() {
    if [ -f "$FRONTEND_PID_FILE" ] && kill -0 "$(cat "$FRONTEND_PID_FILE")" 2>/dev/null; then
        curl -s http://localhost:3000 > /dev/null 2>&1
        return $?
    fi
    return 1
}

start_backend() {
    print_status "Iniciando backend..."

    cd "$BACKEND_DIR" || return 1

    # Kill any existing process on port 8000
    EXISTING_PID=$(lsof -ti:8000 2>/dev/null)
    if [ -n "$EXISTING_PID" ]; then
        print_warning "Matando proceso existente en puerto 8000 (PID: $EXISTING_PID)"
        kill -9 $EXISTING_PID 2>/dev/null
        sleep 1
    fi

    rm -f "$BACKEND_PID_FILE"

    if [ -d "venv" ]; then
        source venv/bin/activate
    else
        print_error "Entorno virtual no encontrado. Ejecuta: python3 -m venv venv && pip install -r requirements.txt"
        return 1
    fi

    nohup python main.py > "$BACKEND_LOG" 2>&1 &
    echo $! > "$BACKEND_PID_FILE"

    print_status "Esperando que el backend inicie..."
    for i in {1..10}; do
        if curl -s http://localhost:8000/health > /dev/null 2>&1; then
            print_success "Backend iniciado en http://localhost:8000 (PID: $(cat "$BACKEND_PID_FILE"))"
            return 0
        fi
        sleep 1
    done

    print_error "El backend no pudo iniciar. Revisa: $BACKEND_LOG"
    tail -20 "$BACKEND_LOG"
    return 1
}

start_frontend() {
    print_status "Iniciando frontend..."

    cd "$FRONTEND_DIR" || return 1

    EXISTING_PID=$(lsof -ti:3000 2>/dev/null)
    if [ -n "$EXISTING_PID" ]; then
        print_warning "Matando proceso existente en puerto 3000 (PID: $EXISTING_PID)"
        kill -9 $EXISTING_PID 2>/dev/null
        sleep 1
    fi

    rm -f "$FRONTEND_PID_FILE"

    if [ ! -d "node_modules" ]; then
        print_status "Instalando dependencias del frontend..."
        npm install
    fi

    nohup npm run dev > "$FRONTEND_LOG" 2>&1 &
    echo $! > "$FRONTEND_PID_FILE"

    print_status "Esperando que el frontend inicie..."
    for i in {1..15}; do
        if curl -s http://localhost:3000 > /dev/null 2>&1; then
            print_success "Frontend iniciado en http://localhost:3000 (PID: $(cat "$FRONTEND_PID_FILE"))"
            return 0
        fi
        sleep 1
    done

    print_warning "El frontend aún puede estar compilando. Revisa: $FRONTEND_LOG"
    return 0
}

stop_backend() {
    print_status "Deteniendo backend..."

    if [ -f "$BACKEND_PID_FILE" ]; then
        PID=$(cat "$BACKEND_PID_FILE")
        if kill -0 "$PID" 2>/dev/null; then
            kill "$PID"
            sleep 2
            if kill -0 "$PID" 2>/dev/null; then
                kill -9 "$PID"
            fi
            print_success "Backend detenido"
        else
            print_warning "El backend no estaba corriendo"
        fi
        rm -f "$BACKEND_PID_FILE"
    else
        PID=$(lsof -ti:8000 2>/dev/null)
        if [ -n "$PID" ]; then
            kill "$PID" 2>/dev/null
            print_success "Backend detenido (encontrado por puerto)"
        else
            print_warning "El backend no estaba corriendo"
        fi
    fi
}

stop_frontend() {
    print_status "Deteniendo frontend..."

    if [ -f "$FRONTEND_PID_FILE" ]; then
        PID=$(cat "$FRONTEND_PID_FILE")
        if kill -0 "$PID" 2>/dev/null; then
            kill "$PID"
            sleep 2
            if kill -0 "$PID" 2>/dev/null; then
                kill -9 "$PID"
            fi
            print_success "Frontend detenido"
        else
            print_warning "El frontend no estaba corriendo"
        fi
        rm -f "$FRONTEND_PID_FILE"
    else
        PID=$(lsof -ti:3000 2>/dev/null)
        if [ -n "$PID" ]; then
            kill "$PID" 2>/dev/null
            print_success "Frontend detenido (encontrado por puerto)"
        else
            print_warning "El frontend no estaba corriendo"
        fi
    fi
}

show_status() {
    echo ""
    # Backend status
    if is_backend_running; then
        echo -e "  Backend:  ${GREEN}●${NC} Corriendo en ${CYAN}http://localhost:8000${NC}"
    else
        echo -e "  Backend:  ${RED}●${NC} Detenido"
    fi

    # Frontend status
    if is_frontend_running; then
        echo -e "  Frontend: ${GREEN}●${NC} Corriendo en ${CYAN}http://localhost:3000${NC}"
    else
        echo -e "  Frontend: ${RED}●${NC} Detenido"
    fi
    echo ""
}

show_logs_backend() {
    clear
    echo -e "${BOLD}=== Logs del Backend (últimas 50 líneas) ===${NC}"
    echo ""
    tail -50 "$BACKEND_LOG" 2>/dev/null || echo "No hay logs del backend"
    echo ""
    echo -e "${YELLOW}Presiona Enter para volver al menú...${NC}"
    read
}

show_logs_frontend() {
    clear
    echo -e "${BOLD}=== Logs del Frontend (últimas 50 líneas) ===${NC}"
    echo ""
    tail -50 "$FRONTEND_LOG" 2>/dev/null || echo "No hay logs del frontend"
    echo ""
    echo -e "${YELLOW}Presiona Enter para volver al menú...${NC}"
    read
}

follow_logs_backend() {
    clear
    echo -e "${BOLD}=== Siguiendo Logs del Backend (Ctrl+C para salir) ===${NC}"
    echo ""
    tail -f "$BACKEND_LOG" 2>/dev/null || echo "No hay logs del backend"
}

follow_logs_frontend() {
    clear
    echo -e "${BOLD}=== Siguiendo Logs del Frontend (Ctrl+C para salir) ===${NC}"
    echo ""
    tail -f "$FRONTEND_LOG" 2>/dev/null || echo "No hay logs del frontend"
}

open_browser() {
    if command -v xdg-open &> /dev/null; then
        xdg-open "http://localhost:3000" &
    elif command -v open &> /dev/null; then
        open "http://localhost:3000" &
    else
        print_warning "No se pudo abrir el navegador automáticamente"
    fi
}

show_menu() {
    clear
    echo -e "${BOLD}${CYAN}"
    echo "  ╔════════════════════════════════════════════════════════════╗"
    echo "  ║         PostgreSQL Index Agents - Panel de Control         ║"
    echo "  ╚════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"

    show_status

    echo -e "${BOLD}  Servicios:${NC}"
    echo "    1) Iniciar todo"
    echo "    2) Detener todo"
    echo "    3) Reiniciar todo"
    echo "    4) Iniciar solo backend"
    echo "    5) Iniciar solo frontend"
    echo "    6) Detener solo backend"
    echo "    7) Detener solo frontend"
    echo ""
    echo -e "${BOLD}  Logs:${NC}"
    echo "    8) Ver logs del backend"
    echo "    9) Ver logs del frontend"
    echo "    f) Seguir logs del backend (tail -f)"
    echo "    g) Seguir logs del frontend (tail -f)"
    echo ""
    echo -e "${BOLD}  Otros:${NC}"
    echo "    o) Abrir en navegador"
    echo "    r) Refrescar estado"
    echo "    q) Salir"
    echo ""
    echo -e "${CYAN}  URLs:${NC}"
    echo "    Frontend: http://localhost:3000"
    echo "    Backend:  http://localhost:8000"
    echo "    API Docs: http://localhost:8000/docs"
    echo ""
}

# Interactive mode (default when no arguments)
interactive_mode() {
    check_requirements || exit 1

    while true; do
        show_menu
        echo -n -e "  ${BOLD}Selecciona una opción: ${NC}"
        read -r choice

        case $choice in
            1)
                echo ""
                start_backend
                start_frontend
                echo ""
                print_success "Servicios iniciados"
                echo -e "${YELLOW}Presiona Enter para continuar...${NC}"
                read
                ;;
            2)
                echo ""
                stop_frontend
                stop_backend
                echo ""
                print_success "Servicios detenidos"
                echo -e "${YELLOW}Presiona Enter para continuar...${NC}"
                read
                ;;
            3)
                echo ""
                stop_frontend
                stop_backend
                sleep 2
                start_backend
                start_frontend
                echo ""
                print_success "Servicios reiniciados"
                echo -e "${YELLOW}Presiona Enter para continuar...${NC}"
                read
                ;;
            4)
                echo ""
                start_backend
                echo -e "${YELLOW}Presiona Enter para continuar...${NC}"
                read
                ;;
            5)
                echo ""
                start_frontend
                echo -e "${YELLOW}Presiona Enter para continuar...${NC}"
                read
                ;;
            6)
                echo ""
                stop_backend
                echo -e "${YELLOW}Presiona Enter para continuar...${NC}"
                read
                ;;
            7)
                echo ""
                stop_frontend
                echo -e "${YELLOW}Presiona Enter para continuar...${NC}"
                read
                ;;
            8)
                show_logs_backend
                ;;
            9)
                show_logs_frontend
                ;;
            f|F)
                follow_logs_backend
                ;;
            g|G)
                follow_logs_frontend
                ;;
            o|O)
                open_browser
                print_success "Abriendo navegador..."
                sleep 1
                ;;
            r|R)
                # Just refresh - the loop will redraw the menu
                ;;
            q|Q)
                echo ""
                print_status "Saliendo..."
                exit 0
                ;;
            *)
                print_warning "Opción no válida"
                sleep 1
                ;;
        esac
    done
}

# Handle command line arguments for backwards compatibility
case "$1" in
    start)
        check_requirements
        start_backend
        start_frontend
        echo ""
        print_success "Todos los servicios iniciados!"
        echo ""
        echo "  Frontend: http://localhost:3000"
        echo "  Backend:  http://localhost:8000"
        echo "  API Docs: http://localhost:8000/docs"
        echo ""
        ;;
    stop)
        stop_frontend
        stop_backend
        print_success "Todos los servicios detenidos"
        ;;
    restart)
        stop_frontend
        stop_backend
        sleep 2
        start_backend
        start_frontend
        ;;
    status)
        echo ""
        echo "=== PostgreSQL Index Agents - Estado ==="
        show_status
        ;;
    logs)
        echo "=== Backend Logs (últimas 50 líneas) ==="
        tail -50 "$BACKEND_LOG" 2>/dev/null || echo "No hay logs del backend"
        echo ""
        echo "=== Frontend Logs (últimas 20 líneas) ==="
        tail -20 "$FRONTEND_LOG" 2>/dev/null || echo "No hay logs del frontend"
        ;;
    "")
        # No arguments - run interactive mode
        interactive_mode
        ;;
    *)
        echo "Uso: $0 [start|stop|restart|status|logs]"
        echo ""
        echo "Sin argumentos: Modo interactivo (recomendado)"
        echo ""
        echo "Comandos:"
        echo "  start   - Iniciar backend y frontend"
        echo "  stop    - Detener todos los servicios"
        echo "  restart - Reiniciar todos los servicios"
        echo "  status  - Mostrar estado de los servicios"
        echo "  logs    - Mostrar logs recientes"
        exit 1
        ;;
esac
