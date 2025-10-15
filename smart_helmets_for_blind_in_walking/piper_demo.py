from piper import PiperVoice
import os

# 加载模型
# voice = PiperVoice.load("zh_CN-huayan-medium.onnx")

# # 要朗读的文本
# text = "Hello world! 你好，世界！"

# # 输出音频
# with open("hello.wav", "wb") as f:
#     voice.synthesize(text, f)

# 播放
os.system("ffplay -nodisp -autoexit welcome.wav")
