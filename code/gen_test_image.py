"""生成测试用字形图片供管线验证。"""

import cv2
import numpy as np


def make_test_image(path: str, size: tuple = (256, 256)):
    """在白色背景上绘制一个'永'字简笔画样的测试图形，保存为PNG。"""
    img = np.ones((size[0], size[1], 3), dtype=np.uint8) * 255
    h, w = size

    # 绘制类似"永"字的笔画骨架
    center = w // 2
    top = 30
    bottom = h - 30

    # 点 (上方一点)
    cv2.circle(img, (center, top + 20), 8, (0, 0, 0), 2)

    # 横
    cv2.line(img, (center - 50, top + 50), (center + 50, top + 50), (0, 0, 0), 3)

    # 竖钩
    cv2.line(img, (center, top + 45), (center, bottom), (0, 0, 0), 3)

    # 撇
    cv2.line(img, (center, top + 80), (center - 50, h // 2 + 20), (0, 0, 0), 3)

    # 捺
    cv2.line(img, (center, top + 80), (center + 50, h // 2 + 20), (0, 0, 0), 3)

    # 左侧短撇
    cv2.line(img, (center - 20, h // 2 + 10), (center - 40, h - 20), (0, 0, 0), 3)

    # 右侧短捺
    cv2.line(img, (center + 20, h // 2 + 10), (center + 40, h - 20), (0, 0, 0), 3)

    cv2.imwrite(path, img)
    print(f"测试图像已生成: {path}")


if __name__ == "__main__":
    make_test_image("test_char.png")
