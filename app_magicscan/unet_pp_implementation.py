import torch
import torch.nn as nn
import torch.nn.functional as F
from unet_implementation import DoubleConv, Down, Up, OutConv

class UNetPP5(nn.Module):
    """
    5-level U-Net++ (nested U-Net) implementation for fine-grained boundary segmentation.
    Extends U-Net with an extra encoder/decoder and nested skip connections
    progressively refining features at each scale.
    """
    def __init__(self, n_channels=3, n_classes=1, bilinear=True,
                 features=[64, 128, 256, 512, 1024]):
        super(UNetPP5, self).__init__()
        self.n_channels = n_channels
        self.n_classes = n_classes
        self.bilinear = bilinear
        
        # Encoder path (five levels)
        self.conv0_0 = DoubleConv(n_channels, features[0])
        self.conv1_0 = Down(features[0], features[1])
        self.conv2_0 = Down(features[1], features[2])
        self.conv3_0 = Down(features[2], features[3])
        self.conv4_0 = Down(features[3], features[4])

        # Up modules for nested skips
        self.up43 = Up(features[4] + features[3], features[3], bilinear)
        self.up32 = Up(features[3] + features[2], features[2], bilinear)
        self.up21 = Up(features[2] + features[1], features[1], bilinear)
        self.up10 = Up(features[1] + features[0], features[0], bilinear)

        # Nested refinement convolutions
        self.conv3_1 = DoubleConv(features[3] * 2, features[3])
        self.conv2_2 = DoubleConv(features[2] * 2, features[2])
        self.conv1_3 = DoubleConv(features[1] * 2, features[1])
        self.conv0_4 = DoubleConv(features[0] * 2, features[0])

        # Final output convolution
        self.outc = OutConv(features[0], n_classes)

    def forward(self, x):
        # Encoder
        x0_0 = self.conv0_0(x)
        x1_0 = self.conv1_0(x0_0)
        x2_0 = self.conv2_0(x1_0)
        x3_0 = self.conv3_0(x2_0)
        x4_0 = self.conv4_0(x3_0)

        # Nested skip: level 3
        x3_1 = self.conv3_1(torch.cat([
            x3_0,
            self.up43(x4_0, x3_0)
        ], dim=1))

        # Nested skip: level 2
        x2_2 = self.conv2_2(torch.cat([
            x2_0,
            self.up32(x3_1, x2_0)
        ], dim=1))

        # Nested skip: level 1
        x1_3 = self.conv1_3(torch.cat([
            x1_0,
            self.up21(x2_2, x1_0)
        ], dim=1))

        # Nested skip: level 0
        x0_4 = self.conv0_4(torch.cat([
            x0_0,
            self.up10(x1_3, x0_0)
        ], dim=1))

        # Output probability map
        logits = self.outc(x0_4)
        return torch.sigmoid(logits)

# Example usage:
# model = UNetPP5(n_channels=3, n_classes=1, bilinear=True)