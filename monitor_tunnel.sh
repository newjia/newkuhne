#!/bin/bash
# 持续监控并重启 Cloudflare Tunnel

LOCAL_PORT=8000
LOG_FILE=/tmp/cf_monitor.log

while true; do
    echo "$(date): 检查 Tunnel 状态..." >> $LOG_FILE
    
    # 检查是否已运行
    if ! pgrep -f "cloudflared tunnel" > /dev/null; then
        echo "$(date): Tunnel 未运行，启动中..." >> $LOG_FILE
        cloudflared tunnel --url http://localhost:$LOCAL_PORT > /tmp/cf_live.log 2>&1 &
        sleep 8
        
        # 获取并显示 URL
        URL=$(grep "trycloudflare.com" /tmp/cf_live.log | grep https | head -1 | sed 's/.*https:\/\//https:\/\//' | sed 's/ |.*//')
        if [ -n "$URL" ]; then
            echo "$(date): 新 Tunnel URL: $URL" >> $LOG_FILE
            echo "================================================"
            echo "新 URL: $URL"
            echo "================================================"
        fi
    fi
    
    # 每 30 秒检查一次
    sleep 30
done
