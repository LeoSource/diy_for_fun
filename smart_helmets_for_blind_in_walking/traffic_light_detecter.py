from ultralytics import YOLO
import cv2

# 1. 加载预训练模型（YOLOv8n，支持交通灯识别）
model = YOLO("yolov8n.pt")

# 2. 加载图片
image_path = "data/7.jpg"  # 你的图片路径
image = cv2.imread(image_path)

# 3. 推理检测
results = model(image)

# 4. 分析结果
detected_lights = []
for result in results:
    for box in result.boxes:
        cls_id = int(box.cls[0])
        cls_name = model.names[cls_id]

        if "traffic" in cls_name.lower() or "light" in cls_name.lower():
            detected_lights.append(cls_name)

# 5. 提示逻辑
if len(detected_lights) == 0:
    print("未检测到红绿灯")
else:
    print("前方有交通信号灯")
    # 进一步判断灯的颜色（基于ROI颜色分析）
    for result in results:
        for box in result.boxes:
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            cls_name = model.names[int(box.cls[0])]
            if "traffic" in cls_name.lower() or "light" in cls_name.lower():
                roi = image[y1:y2, x1:x2]
                hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)

                # 红色范围
                red_mask = cv2.inRange(hsv, (0, 70, 50), (10, 255, 255)) | cv2.inRange(hsv, (170, 70, 50), (180, 255, 255))
                # 绿色范围
                green_mask = cv2.inRange(hsv, (40, 70, 50), (80, 255, 255))

                red_ratio = cv2.countNonZero(red_mask) / (roi.size / 3)
                green_ratio = cv2.countNonZero(green_mask) / (roi.size / 3)

                if red_ratio > 0.05:
                    print("检测到红灯 🚦")
                elif green_ratio > 0.05:
                    print("检测到绿灯 🟢")
                else:
                    print("检测到交通灯，但无法确定颜色")

cv2.imshow("result", results[0].plot())
cv2.waitKey(0)
cv2.destroyAllWindows()
