import cv2
import numpy as np
import base64

def calculate_ela(image_matrix: np.ndarray) -> float:
    _, encoded_img = cv2.imencode('.jpg', image_matrix, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
    resaved_img = cv2.imdecode(encoded_img, cv2.IMREAD_COLOR)
    diff = cv2.absdiff(image_matrix, resaved_img)
    gray_diff = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
    return float(np.mean(gray_diff))

def analyze_noise(image_matrix: np.ndarray) -> float:
    gray = cv2.cvtColor(image_matrix, cv2.COLOR_BGR2GRAY)
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def generate_suspicion_heatmap(image_matrix: np.ndarray) -> str:
    _, encoded_img = cv2.imencode(".jpg", image_matrix, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
    resaved_img = cv2.imdecode(encoded_img, cv2.IMREAD_COLOR)
    diff = cv2.absdiff(image_matrix, resaved_img)
    gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
    normalized = cv2.normalize(gray, None, 0, 255, cv2.NORM_MINMAX)
    heat = cv2.applyColorMap(normalized, cv2.COLORMAP_INFERNO)
    overlay = cv2.addWeighted(image_matrix, 0.62, heat, 0.38, 0)

    height, width = overlay.shape[:2]
    if width > 720:
        scale = 720 / width
        overlay = cv2.resize(overlay, (720, int(height * scale)), interpolation=cv2.INTER_AREA)

    success, encoded = cv2.imencode(".jpg", overlay, [int(cv2.IMWRITE_JPEG_QUALITY), 82])
    if not success:
        return ""
    payload = base64.b64encode(encoded.tobytes()).decode("ascii")
    return f"data:image/jpeg;base64,{payload}"
