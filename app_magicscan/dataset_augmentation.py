import os
os.environ['NO_ALBUMENTATIONS_UPDATE'] = '1'
import numpy as np
from pathlib import Path
from PIL import Image
from skimage import io
from sklearn.model_selection import train_test_split
import torch
from torch.utils.data import Dataset, DataLoader
import albumentations as A
from albumentations.pytorch import ToTensorV2
import torch
from torchvision import transforms
from torchvision.transforms import functional as F
import random
#import cv2
import numpy as np

import torch
from torch.utils.data import Dataset, DataLoader, ConcatDataset


class TissueBoundaryDatasetOriginal(Dataset):
    """Dataset that provides only original, non-augmented images"""

    def __init__(self, img_dir, label_dir, transform=None):
        # Same setup as your original TissueBoundaryDataset
        self.img_dir = img_dir
        self.label_dir = label_dir
        self.transform = transform
        self.img_files = sorted([f for f in os.listdir(img_dir) if f.endswith(('.png', '.jpg', '.tif'))])

    def __len__(self):
        return len(self.img_files)

    def __getitem__(self, idx):
        # Load image and mask - same as your original implementation
        img_path = os.path.join(self.img_dir, self.img_files[idx])
        #img = cv2.imread(img_path)
        #img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        img = np.array(Image.open(img_path), dtype=np.uint8)
        #label = np.array(Image.open(label_path), dtype=np.float32)
        mask_path = os.path.join(self.label_dir, self.img_files[idx])
        if not os.path.exists(mask_path):
            for ext in ['.png', '.jpg', '.tif']:
                potential_path = os.path.splitext(mask_path)[0] + ext
                if os.path.exists(potential_path):
                    mask_path = potential_path
                    break

        #image = np.array(Image.open(img_path), dtype=np.uint8)
        mask = np.array(Image.open(mask_path), dtype=np.float32)
        #mask = cv2.imread(mask_path, cv2.IMREAD_GRAYSCALE)
        mask = (mask - mask.min()) / (mask.max() - mask.min()) if mask.max() > 1.0 else mask

        # Apply only basic transforms (normalization, to tensor, etc), NO augmentation
        if self.transform:
            transformed = self.transform(image=img, mask=mask)
            img = transformed['image']
            mask = transformed['mask']

        # Convert to tensors if not already
        if not isinstance(img, torch.Tensor):
            img = torch.from_numpy(img.transpose(2, 0, 1)).float()
        if not isinstance(mask, torch.Tensor):
            mask = torch.from_numpy(mask[np.newaxis, :, :]).float()

        return img, mask


class TissueBoundaryDatasetWAug(Dataset):
    """
    Dataset for tissue boundary segmentation with configurable augmentation.
    """

    def __init__(self, img_dir, label_dir, transform=None, aug_probability=0.8, aug_intensity='medium'):
        """
        Args:
            img_dir (str): Directory with input images.
            label_dir (str): Directory with label masks.
            transform (callable, optional): Basic transforms for both train and val.
            aug_probability (float): Probability of applying augmentation (0-1).
            aug_intensity (str): Augmentation intensity: 'light', 'medium', or 'heavy'.
        """
        self.img_dir = img_dir
        self.label_dir = label_dir
        self.transform = transform
        self.aug_probability = aug_probability

        # Get list of image files
        self.img_files = sorted([f for f in os.listdir(img_dir) if f.endswith(('.png', '.jpg', '.tif'))])

        # Set up augmentation pipeline based on intensity
        #self.setup_augmentations(aug_intensity)

    # def setup_augmentations(self, intensity):
    #     """Configure augmentation pipeline based on intensity level"""

    #     # Base values for each intensity level
    #     if intensity == 'light':
    #         rotate_limit = 15
    #         scale_limit = 0.0
    #         shift_limit = 0.1
    #         brightness_limit = 0.01
    #         contrast_limit = 0.01
    #         elastic_alpha = 20
    #     elif intensity == 'medium':
    #         rotate_limit = 30
    #         scale_limit = 0.0
    #         shift_limit = 0.15
    #         brightness_limit = 0.02
    #         contrast_limit = 0.02
    #         elastic_alpha = 40
    #     elif intensity == 'heavy':
    #         rotate_limit = 0
    #         scale_limit = 0.0
    #         shift_limit = 0
    #         brightness_limit = 0.03
    #         contrast_limit = 0.03
    #         elastic_alpha = 60
    #     else:
    #         raise ValueError(f"Unknown intensity level: {intensity}")

    #     # Create augmentation pipeline
    #     self.augmentation = A.Compose([
    #         A.HorizontalFlip(p=0.5),
    #         A.VerticalFlip(p=0.5),
    #         A.RandomRotate90(p=0.5),
    #         A.ShiftScaleRotate(
    #             shift_limit=shift_limit,
    #             scale_limit=scale_limit,
    #             rotate_limit=rotate_limit,
    #             p=0.8),
    #         A.OneOf([
    #             A.ElasticTransform(alpha=elastic_alpha, sigma=50, p=0.7),
    #             A.GridDistortion(p=0.5),
    #             A.OpticalDistortion(distort_limit=0.2,  p=0.5),
    #         ], p=0.5),
    #         # A.RandomBrightnessContrast(
    #         #     brightness_limit=brightness_limit,
    #         #     contrast_limit=contrast_limit,
    #         #     p=0.5),
    #         # A.GaussNoise( p=0.3),
    #     ], p=self.aug_probability)

    def __len__(self):
        return len(self.img_files)

    def __getitem__(self, idx):
        # Load image
        img_path = os.path.join(self.img_dir, self.img_files[idx])
        #img = cv2.imread(img_path)
        #img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        img = np.array(Image.open(img_path), dtype=np.uint8)
        # Load mask (assuming same filename but in label_dir)
        mask_path = os.path.join(self.label_dir, self.img_files[idx])
        # Handle different possible mask extensions
        if not os.path.exists(mask_path):
            for ext in ['.png', '.jpg', '.tif']:
                potential_path = os.path.splitext(mask_path)[0] + ext
                if os.path.exists(potential_path):
                    mask_path = potential_path
                    break

        mask = np.array(Image.open(mask_path), dtype=np.float32)
        # mask = cv2.imread(mask_path, cv2.IMREAD_GRAYSCALE)
        mask = (mask-mask.min()) / (mask.max()-mask.min()) if mask.max() > 1.0 else mask

        # Apply base transforms if provided
        if self.transform:
            transformed = self.transform(image=img, mask=mask)
            img = transformed['image']
            mask = transformed['mask']

        else:
            # Apply augmentations with configured probability
            print("THEORY: I NEVER GET PRINTED")
            transformed = self.augmentation(image=img, mask=mask)
            img = transformed['image']
            mask = transformed['mask']

        # Convert to tensors if not already done
        if not isinstance(img, torch.Tensor):
            img = torch.from_numpy(img.transpose(2, 0, 1)).float()
        if not isinstance(mask, torch.Tensor):
            mask = torch.from_numpy(mask[np.newaxis, :, :]).float()

        return img, mask

def create_dataloaders_with_originals(train_img_dir, train_label_dir, val_img_dir, val_label_dir,
                                      batch_size=8, num_workers=4, augmentation_copies=2,
                                      aug_intensity='heavy'):
    """
    Create training and validation dataloaders with both original and augmented data.

    Args:
        train_img_dir (str): Directory with training images.
        train_label_dir (str): Directory with training labels.
        val_img_dir (str): Directory with validation images.
        val_label_dir (str): Directory with validation labels.
        batch_size (int): Batch size for training.
        num_workers (int): Number of workers for data loading.
        augmentation_copies (int): Number of augmented versions per original image.
        aug_intensity (str): One of 'light', 'medium', 'heavy'.

    Returns:
        tuple: (train_loader, val_loader)
    """
    # Dataset with original data only (no augmentation)
    # original_dataset = TissueBoundaryDatasetOriginal(
    #     train_img_dir,
    #     train_label_dir,
    #     transform=get_transforms('train')
    # )

    # Create several augmented datasets with 100% augmentation probability
    augmented_datasets = []
    for i in range(augmentation_copies+1):
        aug_dataset = TissueBoundaryDatasetWAug(
            train_img_dir,
            train_label_dir,
            transform=get_transforms('train'),
            aug_probability=1.0,  # Always apply augmentation
            aug_intensity=aug_intensity
        )
        augmented_datasets.append(aug_dataset)

    # Combine original and augmented datasets
    #combined_train_dataset = ConcatDataset([original_dataset] + augmented_datasets)
    combined_train_dataset = ConcatDataset(augmented_datasets)

    # Create validation dataset (no augmentation)
    val_dataset = TissueBoundaryDatasetOriginal(
        val_img_dir,
        val_label_dir,
        transform=get_transforms('val')
    )

    # Create data loaders
    train_loader = DataLoader(
        combined_train_dataset,
        batch_size=batch_size,
        shuffle=True,
        num_workers=num_workers,
        pin_memory=True,
        drop_last=True
    )

    val_loader = DataLoader(
        val_dataset,
        batch_size=batch_size,
        shuffle=False,
        num_workers=num_workers,
        pin_memory=True
    )

    return train_loader, val_loader

class TissueBoundaryDataset(Dataset):
    def __init__(self, img_dir, label_dir, transform=None):
        """
        Dataset for tissue boundary detection.
        
        Args:
            img_dir (str): Directory containing image tiles.
            label_dir (str): Directory containing label tiles.
            transform (callable, optional): Albumentations transform operations.
        """
        self.img_dir = Path(img_dir)
        self.label_dir = Path(label_dir)
        self.transform = transform
        
        self.img_files = sorted(list(self.img_dir.glob("*.tif")))
        self.bdry_file = sorted(list(self.label_dir.glob("*.tif")))

    def __len__(self):
        return len(self.img_files)
    
    def __getitem__(self, idx):
        img_path = self.img_files[idx]
        label_path = self.bdry_file[idx]
        
        # Load image and label
        image = np.array(Image.open(img_path), dtype=np.uint8)
        label = np.array(Image.open(label_path), dtype=np.float32)
        
        # Reshape label if needed
        if len(label.shape) == 2:
            label = label[..., np.newaxis]
        
        # Apply transforms
        if self.transform:
            augmented = self.transform(image=image, mask=label)
            image = augmented['image']
            label = augmented['mask']
        
        return image, label

def get_transforms(phase):
    """
    Get transforms for training and validation.
    
    Args:
        phase (str): 'train' or 'val'
    """
    if phase == 'train':
        return A.Compose([
            A.RandomRotate90(p=0.5),
            A.HorizontalFlip(p=0.5),  # 50% chance of horizontal flip
            A.VerticalFlip(p=0.5),  # 50% chance of vertical flip
            A.ShiftScaleRotate(shift_limit=0.0625, scale_limit=0.1, rotate_limit=45, p=0.5),
            A.OneOf([
                A.ElasticTransform(alpha=120, sigma=120 * 0.05, p=0.5),
                A.GridDistortion(p=0.5),
                A.OpticalDistortion(distort_limit=1.0,  p=0.5),
            ], p=0.3),
            A.OneOf([
                A.HueSaturationValue(hue_shift_limit=10, sat_shift_limit=15, val_shift_limit=10, p=0.5),
                A.CLAHE(clip_limit=4.0, p=0.5),
                A.RandomBrightnessContrast(brightness_limit=0.2, contrast_limit=0.2, p=0.5),
            ], p=0.5),
            A.Normalize(mean=(0.485, 0.456, 0.406), std=(0.229, 0.224, 0.225)),
            ToTensorV2(),
        ])
    else:
        return A.Compose([
            A.Normalize(mean=(0.485, 0.456, 0.406), std=(0.229, 0.224, 0.225)),
            ToTensorV2(),
        ])

def create_dataloaders(train_img_dir, train_label_dir, val_img_dir, val_label_dir, batch_size=8, num_workers=4):
    """
    Create training and validation dataloaders.
    
    Args:
        train_img_dir (str): Directory with training images.
        train_label_dir (str): Directory with training labels.
        val_img_dir (str): Directory with validation images.
        val_label_dir (str): Directory with validation labels.
        batch_size (int): Batch size for training.
        num_workers (int): Number of workers for data loading.
        
    Returns:
        tuple: (train_loader, val_loader)
    """
    train_dataset = TissueBoundaryDataset(
        train_img_dir, 
        train_label_dir,
        transform=get_transforms('train')
    )
    
    val_dataset = TissueBoundaryDataset(
        val_img_dir,
        val_label_dir,
        transform=get_transforms('val')
    )
    
    train_loader = DataLoader(
        train_dataset,
        batch_size=batch_size,
        shuffle=True,
        num_workers=num_workers,
        pin_memory=True,
        drop_last=True
    )
    
    val_loader = DataLoader(
        val_dataset,
        batch_size=batch_size,
        shuffle=False,
        num_workers=num_workers,
        pin_memory=True
    )
    
    return train_loader, val_loader
