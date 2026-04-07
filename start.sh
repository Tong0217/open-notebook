#!/bin/bash

# Get script directory (compatible with sh)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Stop existing services first to avoid duplicates
sh "$SCRIPT_DIR/stop.sh"
sleep 2

export HF_HUB_CACHE=/home/tong/Desktop/workspace/model

# ============================================
# Unset proxy settings for local connections
# Prevents SOCKS proxy from interfering with localhost database connections
# ============================================
unset http_proxy
unset https_proxy
unset HTTP_PROXY
unset HTTPS_PROXY
unset all_proxy
unset ALL_PROXY
unset no_proxy
unset NO_PROXY
echo "🔧 Proxy settings unset for local connections"

# ============================================
# Start GPU Model Router (gpu-mux)
# ============================================
# 暂时禁用 - 当前不需要 GPU 服务
# GPU_MUX_DIR="$SCRIPT_DIR/gpu-mux"
# echo "Starting GPU Model Router..."
# mkdir -p "$SCRIPT_DIR/logs"
# cd "$GPU_MUX_DIR"
# 
# # 激活虚拟环境：优先使用 gpu-mux 自己的，否则使用主项目的
# if [ -d ".venv" ]; then
#     . .venv/bin/activate
# elif [ -d "venv" ]; then
#     . venv/bin/activate
# elif [ -d "$SCRIPT_DIR/.venv" ]; then
#     . "$SCRIPT_DIR/.venv/bin/activate"
# fi
# 
# # 日志放到外层的 logs 目录
# nohup python3 main.py > "$SCRIPT_DIR/logs/gpu-mux.log" 2>&1 &
# echo $! > "$SCRIPT_DIR/logs/gpu-mux.pid"
# echo "GPU Model Router started on port 8002, PID: $(cat "$SCRIPT_DIR/logs/gpu-mux.pid")"
# echo "  Log: $SCRIPT_DIR/logs/gpu-mux.log"
# cd "$SCRIPT_DIR"
# sleep 2

# ============================================
# Start Open Notebook services
# ============================================
cd "$SCRIPT_DIR" && make start-all
