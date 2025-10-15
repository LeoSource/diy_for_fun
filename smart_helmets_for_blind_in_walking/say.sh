#!/bin/bash

# 检查是否提供文本参数
if [ $# -eq 0 ]; then
    echo "用法: ./say.sh \"要播放的文字\""
    exit 1
fi

# # 替换为你的模型路径
# MODEL_PATH=zh_CN-huayan-medium.onnx
# CONFIG_PATH="./zh_CN-huayan-medium.onnx.json"
# echo "$*"
# # 核心命令：文本 → Piper合成 → ffplay播放
# echo "你好啊" | piper \

#     --model zh_CN-huayan-medium.onnx \

#     # --config "$CONFIG_PATH" \

#     --output_file welcome.wav

#     # --output-file | ffplay -autoexit -hide_banner -loglevel error -f s16le -ar 22050 -ac 1 -

echo "$*" | piper \
  --model ./zh_CN-huayan-medium.onnx \
#   --output_file welcome.wav
  --output-raw | ffplay -autoexit -hide_banner -loglevel error -f s16le -ar 22050 -ac 1 -