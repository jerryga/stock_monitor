#!/bin/bash

# Network connectivity check
echo "Checking network connectivity..."
for i in {1..5}; do
  if ping -c 1 -w 2 8.8.8.8 &> /dev/null; then
    echo "Network connectivity confirmed!"
    break
  else
    echo "Network check $i failed, retrying..."
    sleep 5
  fi
done

# Run the main Python script
python /app/main.py
