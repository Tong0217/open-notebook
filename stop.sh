#!/bin/bash

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "🛑 Stopping all services..."

# ============================================
# Unset proxy settings for local connections
# Prevents SOCKS proxy from interfering with Docker and local operations
# ============================================
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY all_proxy ALL_PROXY no_proxy NO_PROXY

# ============================================
# Stop GPU Model Router (gpu-mux)
# ============================================
# 暂时禁用 - 当前不需要 GPU 服务
# echo "🔌 Stopping GPU Model Router..."
# # 先尝试新的 PID 文件位置（外层 logs）
# if [ -f "$SCRIPT_DIR/logs/gpu-mux.pid" ]; then
#     PID=$(cat "$SCRIPT_DIR/logs/gpu-mux.pid")
#     if kill -0 "$PID" 2>/dev/null; then
#         kill "$PID" 2>/dev/null
#         echo "  GPU Model Router stopped (PID: $PID)"
#     else
#         echo "  GPU Model Router not running"
#     fi
#     rm -f "$SCRIPT_DIR/logs/gpu-mux.pid"
# # 再尝试旧的位置（兼容）
# elif [ -f "$SCRIPT_DIR/gpu-mux/logs/router.pid" ]; then
#     PID=$(cat "$SCRIPT_DIR/gpu-mux/logs/router.pid")
#     if kill -0 "$PID" 2>/dev/null; then
#         kill "$PID" 2>/dev/null
#         echo "  GPU Model Router stopped (PID: $PID)"
#     else
#         echo "  GPU Model Router not running"
#     fi
#     rm -f "$SCRIPT_DIR/gpu-mux/logs/router.pid"
# fi
# # 强制释放端口 (跨平台兼容)
# if command -v lsof &>/dev/null; then
#     lsof -ti:8002 | xargs kill -9 2>/dev/null || true
# elif command -v fuser &>/dev/null; then
#     fuser -k 8002/tcp 2>/dev/null || true
# fi
# # Also stop vllm-omni container if running
# docker compose -f "$SCRIPT_DIR/gpu-mux/vllm-omni/docker-compose.yml" down 2>/dev/null || true

# ============================================
# Stop other TTS services
# ============================================
# Kill Speaches (use SIGKILL because it ignores SIGTERM)
echo "📊 Stopping Speaches..."
pkill -9 -f "speaches.main:create_app" 2>/dev/null || echo "Speaches not running"


# Kill Open Notebook services with SIGKILL for reliability
echo "🛑 Stopping Open Notebook services..."
pkill -9 -f "surreal-commands-worker" 2>/dev/null || true
pkill -9 -f "run_api.py" 2>/dev/null || true
pkill -9 -f "next dev" 2>/dev/null || true

# Also try graceful shutdown via Makefile as fallback
make stop-all 2>/dev/null || true

# Wait for processes to terminate
sleep 2

# Verify all stopped
if pgrep -f "surreal-commands-worker\\|run_api.py\\|next dev\\|speaches.main" > /dev/null; then
    echo "⚠️  Some services still running, forcing kill..."
    pkill -9 -f "surreal-commands-worker" 2>/dev/null || true
    pkill -9 -f "run_api.py" 2>/dev/null || true
    pkill -9 -f "next dev" 2>/dev/null || true
    pkill -9 -f "speaches.main" 2>/dev/null || true
fi

# Kill orphaned multiprocessing helper processes
pkill -9 -f "multiprocessing.resource_tracker" 2>/dev/null || true
pkill -9 -f "multiprocessing.spawn" 2>/dev/null || true

echo "✅ All services stopped!"
