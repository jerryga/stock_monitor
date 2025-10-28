#!/bin/bash

# 启动监控脚本（后台运行，日志输出到 monitor.log）
#echo "[INFO] Start main.py..."
#nohup python main.py > monitor.log 2>&1 &

echo "[INFO] Start main.py..."
python main.py

# 启动 Flask Web 页面（前台运行）
#echo "[INFO] 启动 Flask 应用..."
#python app.py
