#!/usr/bin/env bash
# Stops ComfyUI to free your graphics memory.
pkill -f "comfyui-venv/bin/python main.py" && echo "ComfyUI stopped." || echo "ComfyUI wasn't running."
