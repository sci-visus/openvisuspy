import torch
import torch.nn as nn
import torch.nn.functional as F

class BoundaryLoss(nn.Module):
    """
    Configurable loss function for boundary detection with probability maps.
    Supports various loss combinations: MSE, BCE, Dice, and focal versions.
    
    Args:
        loss_type (str): Main loss type - 'mse', 'bce', or 'focal'
        use_dice (bool): Whether to include Dice loss component
        alpha (float): Weight for main loss component
        beta (float): Weight for Dice loss component (if used)
        focal_gamma (float): Focusing parameter for focal loss (if used)
        smooth (float): Smoothing factor for Dice loss
    """
    def __init__(self, loss_type='mse', use_dice=True, alpha=0.7, beta=0.3, 
                 focal_gamma=2.0, smooth=1.0):
        super(BoundaryLoss, self).__init__()
        self.loss_type = loss_type.lower()
        self.use_dice = use_dice
        self.alpha = alpha
        self.beta = beta
        self.focal_gamma = focal_gamma
        self.smooth = smooth
        
        # Initialize loss functions
        if self.loss_type == 'mse':
            self.main_loss = nn.MSELoss()
        elif self.loss_type == 'bce':
            self.main_loss = nn.BCELoss()
        elif self.loss_type == 'focal':
            # Focal loss will be computed manually
            pass
        else:
            raise ValueError(f"Unsupported loss type: {loss_type}. Use 'mse', 'bce', or 'focal'")
    
    def dice_loss(self, pred, target):
        """
        Compute Dice loss between prediction and target.
        
        Args:
            pred (torch.Tensor): Predicted probability map
            target (torch.Tensor): Target probability map
            
        Returns:
            torch.Tensor: Dice loss value
        """
        # Flatten predictions and targets
        pred_flat = pred.view(-1)
        target_flat = target.view(-1)
        
        # Calculate intersection and union
        intersection = (pred_flat * target_flat).sum()
        
        # Dice coefficient: (2 * intersection) / (pred_sum + target_sum)
        # Dice loss: 1 - Dice coefficient
        return 1.0 - (2.0 * intersection + self.smooth) / (
            pred_flat.sum() + target_flat.sum() + self.smooth
        )
    
    def focal_loss(self, pred, target):
        """
        Compute focal loss for probability maps.
        
        Args:
            pred (torch.Tensor): Predicted probability map
            target (torch.Tensor): Target probability map
            
        Returns:
            torch.Tensor: Focal loss value
        """
        # For probability maps, calculate error
        error = torch.abs(pred - target)
        
        # Apply focal weighting based on error magnitude
        # This gives more weight to larger errors
        focal_weight = error.pow(self.focal_gamma)
        
        # Compute weighted MSE
        loss = (focal_weight * error.pow(2)).mean()
        return loss
    
    def forward(self, pred, target):
        """
        Compute the combined loss.
        
        Args:
            pred (torch.Tensor): Predicted probability map
            target (torch.Tensor): Target probability map
            
        Returns:
            torch.Tensor: Combined loss value
        """
        # Compute main loss component
        if self.loss_type == 'focal':
            main_loss_val = self.focal_loss(pred, target)
        else:
            main_loss_val = self.main_loss(pred, target)
        
        # If using combined loss, add Dice component
        if self.use_dice:
            dice_loss_val = self.dice_loss(pred, target)
            return self.alpha * main_loss_val + self.beta * dice_loss_val
        else:
            return main_loss_val


# Example usage:
def loss_function_examples():
    # Option 1: MSE + Dice Loss (default)
    loss_fn1 = BoundaryLoss(loss_type='mse', use_dice=True, alpha=0.7, beta=0.3)
    
    # Option 2: Pure MSE Loss
    loss_fn2 = BoundaryLoss(loss_type='mse', use_dice=False)
    
    # Option 3: BCE + Dice Loss (original implementation)
    loss_fn3 = BoundaryLoss(loss_type='bce', use_dice=True, alpha=0.5, beta=0.5)
    
    # Option 4: Focal Loss for handling difficult examples
    loss_fn4 = BoundaryLoss(loss_type='focal', use_dice=True, alpha=0.7, beta=0.3, focal_gamma=2.0)
    
    return loss_fn1, loss_fn2, loss_fn3, loss_fn4
