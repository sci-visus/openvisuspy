import os
import random
import re

import numpy as np
from pathlib import Path
from skimage import io
from PIL import Image
from sklearn.model_selection import train_test_split
import torch
from torch.utils.data import Dataset, DataLoader
#import albumentations as A
#from albumentations.pytorch import ToTensorV2


def parse_filename( filename):
    match = re.search(r'_(\d+)x(\d+)(x3)?\.raw$', filename)
    if match:
        h, w = map(int, match.groups()[:2])
        channels = 3 if match.group(3) else 1
        return h, w, channels
    return None


def load_raw_image(filepath):
    h, w, channels = parse_filename(os.path.basename(filepath))
    if h is None or w is None:
        raise ValueError(f"Could not parse dimensions from filename: {filepath}")
    dtype = np.float32 if channels == 1 else np.ubyte
    image = np.fromfile(filepath, dtype=dtype).reshape((h, w, channels) if channels == 3 else (h, w))
    return image.astype(np.float32)



class TissueDatasetPreparation:
    def __init__(self, image_dir, label_dir, output_dir, tile_size=128, overlap=16):
        """
        Initialize the tiling utility.
        
        Args:
            image_dir (str): Directory containing the input RGB images.
            label_dir (str): Directory containing the boundary probability maps.
            output_dir (str): Directory to save the tiled images and labels.
            tile_size (int): Size of each tile (square).
            overlap (int): Overlap between adjacent tiles.
        """
        self.image_dir = Path(image_dir)
        self.label_dir = Path(label_dir)
        self.output_dir = Path(output_dir)
        self.tile_size = tile_size
        self.overlap = overlap
        
        # Create output directories
        self.train_img_dir = self.output_dir / "train" / "images"
        self.train_label_dir = self.output_dir / "train" / "labels"
        self.val_img_dir = self.output_dir / "val" / "images"
        self.val_label_dir = self.output_dir / "val" / "labels"
        
        os.makedirs(self.train_img_dir, exist_ok=True)
        os.makedirs(self.train_label_dir, exist_ok=True)
        os.makedirs(self.val_img_dir, exist_ok=True)
        os.makedirs(self.val_label_dir, exist_ok=True)
    
    def generate_tiles(self, img, tile_size, overlap):
        """Generate coordinates for tiling an image."""
        h, w = img.shape[:2]
        stride = tile_size - overlap
        
        tiles = []
        for y in range(0, h - tile_size + 1, stride):
            for x in range(0, w - tile_size + 1, stride):
                tiles.append((x, y, x + tile_size, y + tile_size))
        
        # Handle edge cases
        if h % stride != 0:
            for x in range(0, w - tile_size + 1, stride):
                y = h - tile_size
                tiles.append((x, y, x + tile_size, y + tile_size))
        
        if w % stride != 0:
            for y in range(0, h - tile_size + 1, stride):
                x = w - tile_size
                tiles.append((x, y, x + tile_size, y + tile_size))
        
        # Handle corner case
        if h % stride != 0 and w % stride != 0:
            tiles.append((w - tile_size, h - tile_size, w, h))
        
        return tiles
    
    def process_and_save_tile(self, img, label, x1, y1, x2, y2, filename, is_train):
        filename = os.path.basename(filename)
        """Process and save a single tile with its label."""
        img_tile = img[y1:y2, x1:x2]
        label_tile = label[y1:y2, x1:x2]
        
        # Skip tiles with minimal boundary information (optional)
        # You can adjust this threshold based on your data
        if np.mean(label_tile) < 0.01:
            # If tile has very little boundary information, randomly keep only some
            if np.random.random() > 0.2:  # Keep 20% of non-boundary tiles
                return
        
        # Save tiles
        img = Image.fromarray(img_tile.astype(np.uint8))
        label_img = Image.fromarray(label_tile.astype(np.float32))
        if is_train:
            print("writing:",self.train_img_dir / f"{filename}_{x1}_{y1}.tif")
            img.save(self.train_img_dir / f"{filename}_{x1}_{y1}.tif")
            label_img.save(self.train_label_dir / f"{filename}_{x1}_{y1}.tif")
        else:
            print("writing:", self.val_img_dir / f"{filename}_{x1}_{y1}.tif")
            img.save(self.val_img_dir / f"{filename}_{x1}_{y1}.tif")
            label_img.save(self.val_label_dir /  f"{filename}_{x1}_{y1}.tif")



    def process_files(self, val_split=0.2, random_state=42):
        """Process all files, tile them, and split into train/validation sets."""
        print("looking in directory:", self.image_dir)
        image_files = sorted([f for f in self.image_dir.glob("*.raw") if f.is_file()])
        label_files = sorted([f for f in self.label_dir.glob("*.raw") if f.is_file()])
        print("found image files:")
        for i in image_files:
            print(i)
        #assume they will have same sorted order
        if len(image_files) != len(label_files):
            print("missing files - images and labels don't match")
            return
        for imname, labelname in zip(image_files, label_files):
            print(os.path.basename(imname), "-->", os.path.basename(labelname))
        
        # Process training files
        for imname, labelname in zip(image_files, label_files):
            img = load_raw_image(imname)
            label = load_raw_image(labelname).astype(np.float32)
            
            # Normalize label if necessary
            if label.max() > 1.0:
                label = label / label.max()

            # these are just boxes
            tiles = self.generate_tiles(img, self.tile_size, self.overlap)
            count_train = 0
            count_val = 0
            for x1, y1, x2, y2 in tiles:
                print(x1, y1, x2, y2)
                is_train = random.random() > val_split
                if is_train:
                    count_train = count_train + 1
                else:
                    count_val = count_val + 1
                self.process_and_save_tile(img, label, x1, y1, x2, y2, imname, is_train=is_train)
        print(f"Using {count_train} training and {count_val} validation tiles")
        print(f"Processing complete. Train tiles saved to {self.train_img_dir}")
        print(f"Validation tiles saved to {self.val_img_dir}")

