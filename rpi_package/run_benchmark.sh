#!/usr/bin/env bash
set -e
echo "=================================================================="
echo "🍓 Launching Raspberry Pi Zero 2 W Velocimetry Benchmark"
echo "=================================================================="
python3 benchmark.py "$@"
