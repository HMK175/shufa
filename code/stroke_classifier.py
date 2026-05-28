"""Small CNN for single-stroke type classification."""

from typing import Tuple

import torch
import torch.nn as nn


class StrokeClassifier(nn.Module):
    def __init__(self, num_classes: int, in_channels: int = 1):
        super().__init__()
        self.features = nn.Sequential(
            nn.Conv2d(in_channels, 24, kernel_size=3, padding=1),
            nn.BatchNorm2d(24),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2),
            nn.Conv2d(24, 48, kernel_size=3, padding=1),
            nn.BatchNorm2d(48),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2),
            nn.Conv2d(48, 96, kernel_size=3, padding=1),
            nn.BatchNorm2d(96),
            nn.ReLU(inplace=True),
            nn.AdaptiveAvgPool2d((1, 1)),
        )
        self.classifier = nn.Sequential(
            nn.Flatten(),
            nn.Dropout(p=0.15),
            nn.Linear(96, num_classes),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.classifier(self.features(x))


def load_checkpoint(path: str, map_location: str = "cpu") -> Tuple[StrokeClassifier, dict]:
    checkpoint = torch.load(path, map_location=map_location)
    classes = checkpoint["classes"]
    model = StrokeClassifier(num_classes=len(classes))
    model.load_state_dict(checkpoint["model_state"])
    model.eval()
    return model, checkpoint
