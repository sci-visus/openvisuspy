import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
from tqdm import tqdm
import time
import copy
import torch
import torch.nn as nn
import torch.optim as optim
from tqdm import tqdm
import time
import copy
import matplotlib.pyplot as plt
from pathlib import Path
import json
from sklearn.metrics import precision_recall_curve, average_precision_score, f1_score, jaccard_score


class DoubleConv(nn.Module):
    """Double convolution block for U-Net"""
    def __init__(self, in_channels, out_channels, mid_channels=None):
        super().__init__()
        if not mid_channels:
            mid_channels = out_channels
        self.double_conv = nn.Sequential(
            nn.Conv2d(in_channels, mid_channels, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(mid_channels),
            nn.ReLU(inplace=True),
            nn.Conv2d(mid_channels, out_channels, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(out_channels),
            nn.ReLU(inplace=True)
        )

    def forward(self, x):
        return self.double_conv(x)

class Down(nn.Module):
    """Downscaling with maxpool then double conv"""
    def __init__(self, in_channels, out_channels):
        super().__init__()
        self.maxpool_conv = nn.Sequential(
            nn.MaxPool2d(2),
            DoubleConv(in_channels, out_channels)
        )

    def forward(self, x):
        return self.maxpool_conv(x)

class Up(nn.Module):
    """Upscaling then double conv"""
    def __init__(self, in_channels, out_channels, bilinear=True):
        super().__init__()
        #print(f"Creating Up module with in_channels={in_channels}, out_channels={out_channels}")

        # Use transposed conv if bilinear is False
        if bilinear:
            self.up = nn.Upsample(scale_factor=2, mode='bilinear', align_corners=True)
            self.conv = DoubleConv(in_channels, out_channels)
            #self.conv = DoubleConv(in_channels, out_channels, in_channels // 2)
        else:
            self.up = nn.ConvTranspose2d(in_channels, in_channels // 2, kernel_size=2, stride=2)
            self.conv = DoubleConv(in_channels, out_channels)

    def forward(self, x1, x2):
        #print("  Up module - Before upsample, x1 shape:", x1.shape)
        x1 = self.up(x1)
        #print("  Up module - After upsample, x1 shape:", x1.shape)

        # Handle padding if needed
        diffY = x2.size()[2] - x1.size()[2]
        diffX = x2.size()[3] - x1.size()[3]

        if diffX > 0 or diffY > 0:
            x1 = F.pad(x1, [diffX // 2, diffX - diffX // 2,
                            diffY // 2, diffY - diffY // 2])
            #print("  Up module - After padding, x1 shape:", x1.shape)

        # Concatenate along channel dimension
        x = torch.cat([x2, x1], dim=1)
        #print("  Up module - After concatenation, shape:", x.shape)

        # This is where the error likely happens
        #print("  Up module - Before conv, shape:", x.shape)
        result = self.conv(x)
        #print("  Up module - After conv, shape:", result.shape)

        return result

class OutConv(nn.Module):
    """Output convolution"""
    def __init__(self, in_channels, out_channels):
        super(OutConv, self).__init__()
        self.conv = nn.Conv2d(in_channels, out_channels, kernel_size=1)

    def forward(self, x):
        return self.conv(x)

class UNet5(nn.Module):
    def __init__(self, n_channels=3, n_classes=1, bilinear=True, features=[64, 128, 256, 512]):
        super(UNet5, self).__init__()
        self.n_channels = n_channels
        self.n_classes = n_classes
        self.bilinear = bilinear

        self.inc = DoubleConv(n_channels, features[0])
        self.down1 = Down(features[0], features[1])
        self.down2 = Down(features[1], features[2])
        self.down3 = Down(features[2], features[3])
        factor = 2 if bilinear else 1
        self.down4 = Down(features[3], features[3] * 2 // factor)
        self.up1 = Up(features[3] * 2, features[3] // factor, bilinear)
        self.up2 = Up(features[3], features[2] // factor, bilinear)
        self.up3 = Up(features[2], features[1] // factor, bilinear)
        self.up4 = Up(features[1], features[0], bilinear)
        self.outc = OutConv(features[0], n_classes)

    def forward(self, x):
        x1 = self.inc(x)
        x2 = self.down1(x1)
        x3 = self.down2(x2)
        x4 = self.down3(x3)
        x5 = self.down4(x4)
        x = self.up1(x5, x4)
        x = self.up2(x, x3)
        x = self.up3(x, x2)
        x = self.up4(x, x1)
        logits = self.outc(x)
        return torch.sigmoid(logits)  # Sigmoid for boundary probability


class UNet4(nn.Module):
    def __init__(self, n_channels=3, n_classes=1, bilinear=True, features=[64, 128, 256, 512]):
        super(UNet4, self).__init__()
        self.n_channels = n_channels
        self.n_classes = n_classes
        self.bilinear = bilinear

        # Input conv
        # Input: [B, 3, 256, 256] -> Output: [B, 64, 256, 256]
        self.inc = DoubleConv(n_channels, features[0])

        # Downsampling path (4 levels instead of 5)
        # Input: [B, 64, 256, 256] -> Output: [B, 128, 128, 128]
        self.down1 = Down(features[0], features[1])
        # Input: [B, 128, 128, 128] -> Output: [B, 256, 64, 64]
        self.down2 = Down(features[1], features[2])
        # Input: [B, 256, 64, 64] -> Output: [B, 512, 32, 32]
        self.down3 = Down(features[2], features[3])

        # Adjust factor for bilinear upsampling
        factor = 2 if bilinear else 1

        # Upsampling path
        # Input: [B, 512, 32, 32] + skip[B, 256, 64, 64] -> Output: [B, 128, 64, 64]
        # After concat: [B, 512+256, 64, 64] = [B, 768, 64, 64]
        self.up1 = Up(features[3] + features[2], features[2] // factor, bilinear)

        # Input: [B, 128, 64, 64] + skip[B, 128, 128, 128] -> Output: [B, 64, 128, 128]
        # After concat: [B, 128+128, 128, 128] = [B, 256, 128, 128]
        self.up2 = Up(features[2] // factor + features[1], features[1] // factor, bilinear)

        # Input: [B, 64, 128, 128] + skip[B, 64, 256, 256] -> Output: [B, 64, 256, 256]
        # After concat: [B, 64+64, 256, 256] = [B, 128, 256, 256]
        self.up3 = Up(features[1] // factor + features[0], features[0], bilinear)

        # Output convolution
        # Input: [B, 64, 256, 256] -> Output: [B, 1, 256, 256]
        self.outc = OutConv(features[0], n_classes)

    def forward(self, x):
        #print("Input shape:", x.shape)

        # Encoder path
        x1 = self.inc(x)
        #print("After inc shape:", x1.shape)

        x2 = self.down1(x1)
        #print("After down1 shape:", x2.shape)

        x3 = self.down2(x2)
        #print("After down2 shape:", x3.shape)

        x4 = self.down3(x3)
        #print("After down3 shape:", x4.shape)

        # Decoder path with skip connections
        #print("Before up1, x4 shape:", x4.shape, "x3 shape:", x3.shape)
        x = self.up1(x4, x3)
        #print("After up1 shape:", x.shape)

        #print("Before up2, x shape:", x.shape, "x2 shape:", x2.shape)
        x = self.up2(x, x2)
        #print("After up2 shape:", x.shape)

        #print("Before up3, x shape:", x.shape, "x1 shape:", x1.shape)
        x = self.up3(x, x1)
        #print("After up3 shape:", x.shape)

        logits = self.outc(x)
        #print("Output shape:", logits.shape)

        return torch.sigmoid(logits)
    
class UNetPP4(nn.Module):
    """
    4-level U-Net++ (nested U-Net) for fine-grained boundary segmentation.
    Uses 4 encoder/decoder levels with dense skip connections to sharpen features.
    """
    def __init__(self, n_channels=3, n_classes=1, bilinear=True,
                 features=[64, 128, 256, 512]):
        super(UNetPP4, self).__init__()
        self.n_channels = n_channels
        self.n_classes  = n_classes
        self.bilinear   = bilinear

        # Encoder path (four levels)
        self.conv0_0 = DoubleConv(n_channels,   features[0])
        self.conv1_0 = Down(features[0],       features[1])
        self.conv2_0 = Down(features[1],       features[2])
        self.conv3_0 = Down(features[2],       features[3])

        # Up modules for nested skips
        self.up32 = Up(features[3] + features[2], features[2], bilinear)
        self.up21 = Up(features[2] + features[1], features[1], bilinear)
        self.up10 = Up(features[1] + features[0], features[0], bilinear)

        # Nested refinement convolutions
        self.conv2_1 = DoubleConv(features[2] * 2, features[2])
        self.conv1_2 = DoubleConv(features[1] * 2, features[1])
        self.conv0_3 = DoubleConv(features[0] * 2, features[0])

        # Final output convolution
        self.outc = OutConv(features[0], n_classes)

    def forward(self, x):
        # Encoder
        x0_0 = self.conv0_0(x)
        x1_0 = self.conv1_0(x0_0)
        x2_0 = self.conv2_0(x1_0)
        x3_0 = self.conv3_0(x2_0)

        # Nested skip: level 2
        x2_1 = self.conv2_1(torch.cat([
            x2_0,
            self.up32(x3_0, x2_0)
        ], dim=1))

        # Nested skip: level 1
        x1_2 = self.conv1_2(torch.cat([
            x1_0,
            self.up21(x2_1, x1_0)
        ], dim=1))

        # Nested skip: level 0
        x0_3 = self.conv0_3(torch.cat([
            x0_0,
            self.up10(x1_2, x0_0)
        ], dim=1))

        # Output probability map
        logits = self.outc(x0_3)
        return torch.sigmoid(logits)

# Loss function for boundary detection
class BoundaryLossOld(nn.Module):
    def __init__(self, weight_bce=0.5, weight_dice=0.5):
        super(BoundaryLossOld, self).__init__()
        self.weight_bce = weight_bce
        self.weight_dice = weight_dice
        self.bce = nn.BCELoss()
        
    def dice_loss(self, pred, target):
        smooth = 1.0
        
        # Flatten predictions and targets
        pred_flat = pred.view(-1)
        target_flat = target.view(-1)
        
        intersection = (pred_flat * target_flat).sum()
        
        return 1 - (2. * intersection + smooth) / (pred_flat.sum() + target_flat.sum() + smooth)
        
    def forward(self, pred, target):
        bce_loss = self.bce(pred, target)
        dice_loss = self.dice_loss(pred, target)
        
        return self.weight_bce * bce_loss + self.weight_dice * dice_loss
class BoundaryLoss(nn.Module):
    def __init__(self, alpha=0.25, gamma=2.0, weight_focal=0.5, weight_dice=0.5):
        super(BoundaryLoss, self).__init__()
        self.alpha = alpha  # Weighting factor for the rare class
        self.gamma = gamma  # Focusing parameter
        self.weight_focal = weight_focal
        self.weight_dice = weight_dice
        self.eps = 1e-6  # Small epsilon to prevent log(0)
        
    def focal_loss(self, pred, target):
        """
        Focal Loss implementation for binary segmentation
        FL(p_t) = -alpha * (1 - p_t)^gamma * log(p_t)
        where p_t is the predicted probability of the target class
        """
        # Flatten predictions and targets
        pred_flat = pred.view(-1)
        target_flat = target.view(-1)
        
        # Calculate BCE loss
        bce = -(target_flat * torch.log(pred_flat + self.eps) + 
                (1 - target_flat) * torch.log(1 - pred_flat + self.eps))
        
        # Calculate weights
        pt = torch.exp(-bce)
        focal_weight = self.alpha * (1 - pt)**self.gamma
        
        # Apply weights to BCE loss
        focal_loss = focal_weight * bce
        
        return focal_loss.mean()
        
    def dice_loss(self, pred, target):
        smooth = 1.0
        
        # Flatten predictions and targets
        pred_flat = pred.view(-1)
        target_flat = target.view(-1)
        
        intersection = (pred_flat * target_flat).sum()
        
        return 1 - (2. * intersection + smooth) / (pred_flat.sum() + target_flat.sum() + smooth)
        
    def forward(self, pred, target):
        focal_loss = self.focal_loss(pred, target)
        dice_loss = self.dice_loss(pred, target)
        
        return self.weight_focal * focal_loss + self.weight_dice * dice_loss
# class Trainer:
#     def __init__(self, model, device, criterion, optimizer, scheduler=None):
#         """
#         Initialize the trainer.
#
#         Args:
#             model: The U-Net model.
#             device: The device to use (cuda or cpu).
#             criterion: Loss function.
#             optimizer: Optimizer.
#             scheduler: Learning rate scheduler (optional).
#         """
#         self.model = model
#         self.device = device
#         self.criterion = criterion
#         self.optimizer = optimizer
#         self.scheduler = scheduler
#
#     def train_epoch(self, dataloader):
#         """Train for one epoch"""
#         self.model.train()
#         epoch_loss = 0
#
#         with tqdm(dataloader, desc="Training", leave=False) as pbar:
#             for images, targets in pbar:
#                 images = images.to(self.device)
#                 # Convert from [B, H, W, C] to [B, C, H, W]
#                 #targets = targets.permute(0, 3, 1, 2)
#                 targets = targets.to(self.device)
#
#                 # Forward pass
#                 self.optimizer.zero_grad()
#                 outputs = self.model(images)
#                 loss = self.criterion(outputs, targets)
#
#                 # Backward pass
#                 loss.backward()
#                 self.optimizer.step()
#
#                 epoch_loss += loss.item()
#                 pbar.set_postfix(loss=f"{loss.item():.4f}")
#
#         return epoch_loss / len(dataloader)
#
#     def validate(self, dataloader):
#         """Validate the model"""
#         self.model.eval()
#         val_loss = 0
#
#         with torch.no_grad():
#             with tqdm(dataloader, desc="Validation", leave=False) as pbar:
#                 for images, targets in pbar:
#                     images = images.to(self.device)
#                     targets = targets.permute(0, 3, 1, 2)
#                     targets = targets.to(self.device)
#
#                     outputs = self.model(images)
#                     loss = self.criterion(outputs, targets)
#
#                     val_loss += loss.item()
#                     pbar.set_postfix(loss=f"{loss.item():.4f}")
#
#         return val_loss / len(dataloader)
#
#     def train(self, train_loader, val_loader, num_epochs, save_dir):
#         """
#         Train the model.
#
#         Args:
#             train_loader: Training data loader.
#             val_loader: Validation data loader.
#             num_epochs: Number of epochs to train for.
#             save_dir: Directory to save models.
#         """
#         best_loss = float('inf')
#         best_model_wts = copy.deepcopy(self.model.state_dict())
#
#         start_time = time.time()
#
#         # Create save directory if it doesn't exist
#         Path(save_dir).mkdir(parents=True, exist_ok=True)
#
#         for epoch in range(num_epochs):
#             print(f"Epoch {epoch+1}/{num_epochs}")
#
#             # Train
#             train_loss = self.train_epoch(train_loader)
#
#             # Validate
#             val_loss = self.validate(val_loader)
#
#             # Update learning rate
#             if self.scheduler is not None:
#                 self.scheduler.step(val_loss)  # For ReduceLROnPlateau
#
#             # Save model if it's the best so far
#             if val_loss < best_loss:
#                 best_loss = val_loss
#                 best_model_wts = copy.deepcopy(self.model.state_dict())
#                 torch.save({
#                     'epoch': epoch,
#                     'model_state_dict': self.model.state_dict(),
#                     'optimizer_state_dict': self.optimizer.state_dict(),
#                     'loss': best_loss,
#                 }, f"{save_dir}/best_model.pth")
#
#             # Also save the latest model
#             torch.save({
#                 'epoch': epoch,
#                 'model_state_dict': self.model.state_dict(),
#                 'optimizer_state_dict': self.optimizer.state_dict(),
#                 'loss': val_loss,
#             }, f"{save_dir}/latest_model.pth")
#
#             print(f"Train Loss: {train_loss:.4f}, Val Loss: {val_loss:.4f}")
#
#             # Early stopping could be added here
#
#         time_elapsed = time.time() - start_time
#         print(f"Training complete in {time_elapsed // 60:.0f}m {time_elapsed % 60:.0f}s")
#         print(f"Best Validation Loss: {best_loss:.4f}")
#
#         # Load best model weights
#         self.model.load_state_dict(best_model_wts)
#         return self.model

# def train_unet(train_img_dir, train_label_dir, val_img_dir, val_label_dir,
#                model_save_dir, num_epochs=100, batch_size=8, learning_rate=1e-4):
#     """
#     Main function to train the U-Net model.
#
#     Args:
#         train_img_dir: Directory with training images.
#         train_label_dir: Directory with training labels.
#         val_img_dir: Directory with validation images.
#         val_label_dir: Directory with validation labels.
#         model_save_dir: Directory to save models.
#         num_epochs: Number of epochs to train for.
#         batch_size: Batch size for training.
#         learning_rate: Learning rate for optimizer.
#     """
#     # Create data loaders
#     train_loader, val_loader = create_dataloaders(
#         train_img_dir, train_label_dir, val_img_dir, val_label_dir,
#         batch_size=batch_size
#     )
#
#     # Set device
#     device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
#     print(f"Using device: {device}")
#
#     # Create model
#     model = UNet5(n_channels=3, n_classes=1)
#     model = model.to(device)
#
#     # Define loss function and optimizer
#     criterion = BoundaryLoss(weight_bce=0.5, weight_dice=0.5)
#     optimizer = optim.Adam(model.parameters(), lr=learning_rate)
#
#     # Learning rate scheduler
#     scheduler = optim.lr_scheduler.ReduceLROnPlateau(
#         optimizer, mode='min', factor=0.5, patience=5, verbose=True
#     )
#
#     # Create trainer and train the model
#     trainer = Trainer(model, device, criterion, optimizer, scheduler)
#     model = trainer.train(train_loader, val_loader, num_epochs, model_save_dir)
#
#     return model
#

class MetricsTracker:
    """Class to track and visualize training metrics"""

    def __init__(self, save_dir):
        self.metrics = {
            'train_loss': [],
            'val_loss': [],
            'val_iou': [],
            'val_f1': [],
            'val_ap': [],
            'learning_rates': []
        }
        self.save_dir = Path(save_dir)
        self.save_dir.mkdir(parents=True, exist_ok=True)

    def update(self, metrics_dict):
        """Update tracked metrics with new values"""
        for key, value in metrics_dict.items():
            if key in self.metrics:
                self.metrics[key].append(value)

    def save_metrics(self):
        """Save metrics to JSON file"""
        metrics_file = self.save_dir / 'training_metrics.json'
        with open(metrics_file, 'w') as f:
            json.dump(self.metrics, f, indent=4)

    def plot_metrics(self):
        """Plot training and validation metrics"""
        # Create figure with subplots
        fig, axes = plt.subplots(2, 2, figsize=(15, 10))

        # Plot loss curves
        axes[0, 0].plot(self.metrics['train_loss'], label='Train Loss')
        axes[0, 0].plot(self.metrics['val_loss'], label='Validation Loss')
        axes[0, 0].set_xlabel('Epoch')
        axes[0, 0].set_ylabel('Loss')
        axes[0, 0].set_title('Training and Validation Loss')
        axes[0, 0].legend()
        axes[0, 0].grid(True)

        # Plot IoU and F1 scores
        epochs = range(1, len(self.metrics['val_iou']) + 1)
        axes[0, 1].plot(epochs, self.metrics['val_iou'], 'o-', label='IoU')
        axes[0, 1].plot(epochs, self.metrics['val_f1'], 'o-', label='F1 Score')
        axes[0, 1].set_xlabel('Epoch')
        axes[0, 1].set_ylabel('Score')
        axes[0, 1].set_title('Validation Metrics')
        axes[0, 1].legend()
        axes[0, 1].grid(True)

        # Plot Average Precision
        axes[1, 0].plot(epochs, self.metrics['val_ap'], 'o-', color='green')
        axes[1, 0].set_xlabel('Epoch')
        axes[1, 0].set_ylabel('Average Precision')
        axes[1, 0].set_title('Validation Average Precision')
        axes[1, 0].grid(True)

        # Plot learning rate
        axes[1, 1].plot(epochs, self.metrics['learning_rates'], 'o-', color='purple')
        axes[1, 1].set_xlabel('Epoch')
        axes[1, 1].set_ylabel('Learning Rate')
        axes[1, 1].set_title('Learning Rate Schedule')
        axes[1, 1].set_yscale('log')
        axes[1, 1].grid(True)

        # Adjust layout and save figure
        plt.tight_layout()
        plt.savefig(self.save_dir / 'training_metrics.png', dpi=300)
        plt.close()


class EnhancedTrainer:
    def __init__(self, model, device, criterion, optimizer, scheduler=None, threshold=0.5):
        """
        Initialize the trainer with metrics tracking.

        Args:
            model: The U-Net model.
            device: The device to use (cuda or cpu).
            criterion: Loss function.
            optimizer: Optimizer.
            scheduler: Learning rate scheduler (optional).
            threshold: Threshold for binary predictions.
        """
        self.model = model
        self.device = device
        self.criterion = criterion
        self.optimizer = optimizer
        self.scheduler = scheduler
        self.threshold = threshold

    def train_epoch(self, dataloader):
        """Train for one epoch and return average loss"""
        self.model.train()
        epoch_loss = 0

        with tqdm(dataloader, desc="Training", leave=False) as pbar:
            for images, targets in pbar:
                images = images.to(self.device)
                #targets.
                #targets = targets.permute(0, 3, 1, 2)
                targets = targets.unsqueeze(1)  # Add channel dimension
                targets = targets.to(self.device)

                # Forward pass
                self.optimizer.zero_grad()
                outputs = self.model(images)
                loss = self.criterion(outputs, targets)

                # Backward pass
                loss.backward()
                self.optimizer.step()

                epoch_loss += loss.item()
                pbar.set_postfix(loss=f"{loss.item():.4f}")

        return epoch_loss / len(dataloader)

    def validate(self, dataloader):
        """
        Validate the model and calculate performance metrics.

        Returns:
            dict: Dictionary containing validation metrics.
        """
        self.model.eval()
        val_loss = 0
        all_preds = []
        all_targets = []

        with torch.no_grad():
            with tqdm(dataloader, desc="Validation", leave=False) as pbar:
                for images, targets in pbar:
                    images = images.to(self.device)
                    #targets = targets.permute(0, 3, 1, 2)
                    targets = targets.unsqueeze(1)  # Add channel dimension
                    targets = targets.to(self.device)

                    outputs = self.model(images)
                    loss = self.criterion(outputs, targets)

                    val_loss += loss.item()
                    pbar.set_postfix(loss=f"{loss.item():.4f}")

                    # Collect predictions and targets for metrics calculation
                    pred_np = outputs.cpu().numpy().flatten()
                    target_np = targets.cpu().numpy().flatten()

                    all_preds.append(pred_np)
                    all_targets.append(target_np)

        # Concatenate all batches
        all_preds = np.concatenate(all_preds)
        all_targets = np.concatenate(all_targets)

        # Calculate metrics
        binary_preds = (all_preds > self.threshold).astype(np.uint8)
        iou = jaccard_score(all_targets > 0.5, binary_preds, average='binary')
        f1 = f1_score(all_targets > 0.5, binary_preds, average='binary')
        ap = average_precision_score(all_targets > 0.5, all_preds)

        # Return all metrics
        metrics = {
            'val_loss': val_loss / len(dataloader),
            'val_iou': iou,
            'val_f1': f1,
            'val_ap': ap
        }

        return metrics

    def train(self, train_loader, val_loader, num_epochs, save_dir, starting_epoch=0):
        """
        Train the model with comprehensive metrics tracking.

        Args:
            train_loader: Training data loader.
            val_loader: Validation data loader.
            num_epochs: Number of epochs to train for.
            save_dir: Directory to save models and metrics.
        """
        best_loss = float('inf')
        best_model_wts = copy.deepcopy(self.model.state_dict())
        metrics_tracker = MetricsTracker(save_dir)

        start_time = time.time()

        # Create save directory if it doesn't exist
        Path(save_dir).mkdir(parents=True, exist_ok=True)

        for epoch in range(starting_epoch, starting_epoch + num_epochs):
            print(f"Epoch {epoch + 1}/{num_epochs}")

            # Train
            train_loss = self.train_epoch(train_loader)

            # Validate and get metrics
            val_metrics = self.validate(val_loader)

            # Get current learning rate
            current_lr = self.optimizer.param_groups[0]['lr']

            # Update metrics tracker
            metrics_tracker.update({
                'train_loss': train_loss,
                'val_loss': val_metrics['val_loss'],
                'val_iou': val_metrics['val_iou'],
                'val_f1': val_metrics['val_f1'],
                'val_ap': val_metrics['val_ap'],
                'learning_rates': current_lr
            })

            # Update learning rate
            if self.scheduler is not None:
                if isinstance(self.scheduler, torch.optim.lr_scheduler.ReduceLROnPlateau):
                    self.scheduler.step(val_metrics['val_loss'])
                else:
                    self.scheduler.step()

            # Save model if it's the best so far
            if val_metrics['val_loss'] < best_loss:
                best_loss = val_metrics['val_loss']
                best_model_wts = copy.deepcopy(self.model.state_dict())
                torch.save({
                    'epoch': epoch,
                    'model_state_dict': self.model.state_dict(),
                    'optimizer_state_dict': self.optimizer.state_dict(),
                    'loss': best_loss,
                    'metrics': val_metrics,
                }, f"{save_dir}/best_model.pth")

            # Save checkpoint at regular intervals
            if (epoch + 1) % 5 == 0 or epoch == num_epochs - 1:
                torch.save({
                    'epoch': epoch,
                    'model_state_dict': self.model.state_dict(),
                    'optimizer_state_dict': self.optimizer.state_dict(),
                    'metrics': val_metrics,
                }, f"{save_dir}/model_epoch_{epoch + 1}.pth")

            # Display metrics
            print(f"Train Loss: {train_loss:.4f}, Val Loss: {val_metrics['val_loss']:.4f}")
            print(
                f"IoU: {val_metrics['val_iou']:.4f}, F1: {val_metrics['val_f1']:.4f}, AP: {val_metrics['val_ap']:.4f}")
            print(f"Learning Rate: {current_lr:.6f}")

            # Save and plot metrics after each epoch
            metrics_tracker.save_metrics()
            metrics_tracker.plot_metrics()

        time_elapsed = time.time() - start_time
        print(f"Training complete in {time_elapsed // 60:.0f}m {time_elapsed % 60:.0f}s")
        print(f"Best Validation Loss: {best_loss:.4f}")

        # Load best model weights
        self.model.load_state_dict(best_model_wts)
        return self.model


def train_unet_with_tracking(train_loader,
                             val_loader,
                             model_save_dir,
                             unet_layers=4,
                             num_epochs=10,
                             learning_rate=1e-4,
                             starting_epoch=0,
                             checkpoint=None,
                             focal_alpha=None,
                             focal_gamma=None,
                             weight_focal=None,
                             weight_dice=None
                             ):
    """
    Main function to train the U-Net model with comprehensive metrics tracking.

    Args:
        train_img_dir: Directory with training images.
        train_label_dir: Directory with training labels.
        val_img_dir: Directory with validation images.
        val_label_dir: Directory with validation labels.
        model_save_dir: Directory to save models and metrics.
        num_epochs: Number of epochs to train for.

        learning_rate: Learning rate for optimizer.
    """
    # Create data loaders
    #  = create_dataloaders(
    #     train_img_dir, train_label_dir, val_img_dir, val_label_dir,
    #     batch_size=batch_size
    # )

    # Set device
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Using device: {device}")
    print(f"Unet layers: {unet_layers}")

    # Create model
    if unet_layers == 4:
        model = UNet4(n_channels=3, n_classes=1)
        print("Unet4")
    elif unet_layers == 5:
        model = UNet5(n_channels=3, n_classes=1)
        print("Unet5")
    elif unet_layers == 6:
        model = UNetPP4(n_channels=3, n_classes=1)
        print("UnetPP4")
    else:
        raise ValueError(f"Unsupported unet_layers={unet_layers}. Use 4, 5 or 6.")
    model = model.to(device)

    # Load model state if checkpoint is provided
    if checkpoint is not None:
        if isinstance(checkpoint, dict) and 'model_state_dict' in checkpoint:
            model.load_state_dict(checkpoint['model_state_dict'])
        else:
            model.load_state_dict(checkpoint)




    # Define loss function and optimizer
    criterion = BoundaryLoss(alpha=focal_alpha, gamma=focal_gamma, weight_focal=weight_focal, weight_dice=weight_dice)
    optimizer = optim.Adam(model.parameters(), lr=learning_rate)
    # Load optimizer state if available in checkpoint
    if checkpoint is not None and isinstance(checkpoint, dict) and 'optimizer_state_dict' in checkpoint:
        optimizer.load_state_dict(checkpoint['optimizer_state_dict'])

    # Learning rate scheduler
    # Option 1: ReduceLROnPlateau
    scheduler = optim.lr_scheduler.ReduceLROnPlateau(
        optimizer, mode='min', factor=0.5, patience=5, verbose=True
    )

    # Option 2: Cosine Annealing (alternative)
    # scheduler = optim.lr_scheduler.CosineAnnealingLR(
    #     optimizer, T_max=num_epochs, eta_min=learning_rate/100
    # )

    # Create enhanced trainer and train the model
    trainer = EnhancedTrainer(model, device, criterion, optimizer, scheduler)
    model = trainer.train(train_loader, val_loader, num_epochs, model_save_dir,
                          starting_epoch=starting_epoch)

    return model


def visualize_predictions(model, val_loader, device, num_samples=4, save_path=None):
    """
    Visualize model predictions compared to ground truth.

    Args:
        model: Trained U-Net model.
        val_loader: Validation data loader.
        device: Device to use for inference.
        num_samples: Number of samples to visualize.
        save_path: Path to save visualization. If None, display instead.
    """
    model.eval()
    fig, axes = plt.subplots(num_samples, 3, figsize=(15, 5 * num_samples))

    if num_samples == 1:
        axes = axes.reshape(1, -1)

    dataiter = iter(val_loader)
    samples_processed = 0

    with torch.no_grad():
        while samples_processed < num_samples:
            images, targets = next(dataiter)
            images = images.to(device)
            batch_size = images.size(0)

            outputs = model(images)

            # Process only what we need
            max_samples = min(batch_size, num_samples - samples_processed)

            for i in range(max_samples):
                idx = samples_processed + i

                # Get the i-th image, target, and prediction
                img = images[i].cpu().permute(1, 2, 0).numpy()
                # Denormalize image
                img = img * np.array([0.229, 0.224, 0.225]) + np.array([0.485, 0.456, 0.406])
                img = np.clip(img, 0, 1)

                target = targets[i].cpu().numpy().squeeze()
                pred = outputs[i].cpu().numpy().squeeze()

                # Plot image
                axes[idx, 0].imshow(img)
                axes[idx, 0].set_title(f"Original Image")
                axes[idx, 0].axis('off')

                # Plot ground truth
                axes[idx, 1].imshow(target, cmap='jet', vmin=0, vmax=1)
                axes[idx, 1].set_title(f"Ground Truth")
                axes[idx, 1].axis('off')

                # Plot prediction
                axes[idx, 2].imshow(pred, cmap='jet', vmin=0, vmax=1)
                axes[idx, 2].set_title(f"Predicted Boundaries")
                axes[idx, 2].axis('off')

            samples_processed += max_samples
            if samples_processed >= num_samples:
                break

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=200, bbox_inches='tight')
        plt.close()
    else:
        plt.show()
