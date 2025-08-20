import os
import numpy as np
import torch
from pathlib import Path
from skimage import io
from PIL import Image
from tqdm import tqdm
import albumentations as A
from albumentations.pytorch import ToTensorV2

from unet_implementation import UNet5, UNet4, UNetPP4


class TissuePredictor:
    def __init__(self, model_path, device=None, tile_size=512, overlap=64, unet_layers=4):
        """
        Initialize the predictor.
        
        Args:
            model_path (str): Path to the trained model checkpoint.
            device (torch.device, optional): Device to use. If None, uses CUDA if available.
            tile_size (int): Size of tiles to use for prediction.
            overlap (int): Overlap between adjacent tiles.
        """
        self.tile_size = tile_size
        self.overlap = overlap
        
        if device is None:
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        else:
            self.device = device
        
        print(f"Using device: {self.device}")
        
        # Load model
        if unet_layers == 4:
            self.model = UNet4(n_channels=3, n_classes=1)
        elif unet_layers == 5:
            self.model = UNet5(n_channels=3, n_classes=1)
        elif unet_layers == 6:
            self.model = UNetPP4(n_channels=3, n_classes=1)
        else:
            raise ValueError(f"Unsupported unet_layers={unet_layers}. Use 4, 5 or 6.")
        checkpoint = torch.load(model_path, map_location=self.device, weights_only=False)
        self.model.load_state_dict(checkpoint['model_state_dict'])
        self.model.to(self.device)
        self.model.eval()
        
        # Transforms for normalization
        self.transforms = A.Compose([
            A.Normalize(mean=(0.485, 0.456, 0.406), std=(0.229, 0.224, 0.225)),
            ToTensorV2(),
        ])
    
    def load_raw_image(self, image_path, height=None, width=None, channels=3):
        """
        Load image from .raw or standard formats (.tiff, .png, .jpg).
        """
        ext = os.path.splitext(image_path)[-1].lower()

        if ext == ".raw":
            img = np.fromfile(image_path, dtype=np.uint8)
            if height is None or width is None:
                raise ValueError("Must specify height and width for raw files.")
            expected_size = height * width * channels
            if img.size != expected_size:
                raise ValueError(f"Expected size {expected_size}, got {img.size}")
            return img.reshape((height, width, channels))
        
        else:
            # Fallback for common image formats
            img = Image.open(image_path).convert("RGB")
            return np.array(img)
    
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
    
    def predict_tile(self, tile):
        """
        Predict boundary probabilities for a single tile.
        
        Args:
            tile (numpy.ndarray): Input tile (RGB image).
            
        Returns:
            numpy.ndarray: Predicted boundary probability map.
        """
        # Apply transforms
        transformed = self.transforms(image=tile)
        tile_tensor = transformed['image'].unsqueeze(0).to(self.device)
        
        with torch.no_grad():
            output = self.model(tile_tensor)
        
        # Convert to numpy array
        prob_map = output.squeeze().cpu().numpy()
        
        return prob_map
    
    def create_weight_map(self, tile_size, overlap):
        """
        Create a weight map for blending overlapping regions.
        
        Args:
            tile_size (int): Size of the tile.
            overlap (int): Overlap size.
            
        Returns:
            numpy.ndarray: Weight map for blending.
        """
        weight = np.ones((tile_size, tile_size), dtype=np.float32)
        
        # Create gradual transition at the edges
        for i in range(overlap):
            weight_value = i / overlap
            # Left edge
            weight[:, i] = weight_value
            # Right edge
            weight[:, tile_size - i - 1] = weight_value
            # Top edge
            weight[i, :] = weight_value
            # Bottom edge
            weight[tile_size - i - 1, :] = weight_value
        
        return weight
    
    def predict_image(self, image_path, output_path):
        """
        Predict boundary probabilities for an entire image using tiling and stitching.
        
        Args:
            image_path (str): Path to the input image.
            output_path (str): Path to save the output probability map.
            
        Returns:
            numpy.ndarray: Stitched prediction.
        """
        # Load image
        #img = io.imread(image_path)
        height, width = 1612, 1954  # You should set the dimensions for your raw file
        img = self.load_raw_image(image_path, height, width, channels=3)
        h, w = img.shape[:2]
        
        # Create empty probability map and weight map for stitching
        prob_map = np.zeros((h, w), dtype=np.float32)
        weight_map = np.zeros((h, w), dtype=np.float32)
        
        # Create blending weight map
        tile_weight = self.create_weight_map(self.tile_size, self.overlap)
        
        # Generate tiles
        tiles = self.generate_tiles(img, self.tile_size, self.overlap)
        
        # Process each tile
        for x1, y1, x2, y2 in tqdm(tiles, desc="Processing tiles"):
            # Extract tile
            tile = img[y1:y2, x1:x2]
            
            # Predict
            tile_prob = self.predict_tile(tile)
            
            # Add to the probability map with blending weights
            prob_map[y1:y2, x1:x2] += tile_prob * tile_weight
            weight_map[y1:y2, x1:x2] += tile_weight
        
        # Normalize the probability map by the weight map to get final predictions
        # Avoid division by zero
        weight_map = np.maximum(weight_map, 1e-8)
        prob_map = prob_map / weight_map
        
        # Ensure the output directory exists
        output_dir = os.path.dirname(output_path)
        os.makedirs(output_dir, exist_ok=True)
        
        # Save the probability map
        # We multiply by 255 to convert to an 8-bit image for easier visualization
        #prob_map_8bit = (prob_map * 255).astype(np.uint8)
        #cv2.imwrite(output_path, prob_map_8bit)
        label_img = Image.fromarray(prob_map.astype(np.float32))
        label_img.save(output_path)
        # Also save the raw floating point data
        # np.save(output_path.replace('.png', '.npy'), prob_map)
        
        return prob_map
    
    def predict_array(self, rgb_array: np.ndarray) -> np.ndarray:
        """
        Same as predict_image() but takes an RGB NumPy array that is
        already in memory (H×W×3, uint8).

        Returns
        -------
        prob_map : np.ndarray  float32 in [0,1]  (H×W)
        """
        h, w = rgb_array.shape[:2]

        # Set up blank canvases
        prob_map = np.zeros((h, w), dtype=np.float32)
        weight_map = np.zeros_like(prob_map)

        tile_weight = self.create_weight_map(self.tile_size, self.overlap)
        tiles = self.generate_tiles(rgb_array, self.tile_size, self.overlap)

        for x1, y1, x2, y2 in tiles:
            tile = rgb_array[y1:y2, x1:x2]
            tile_prob = self.predict_tile(tile)
            prob_map[y1:y2, x1:x2] += tile_prob * tile_weight
            weight_map[y1:y2, x1:x2] += tile_weight

        prob_map /= np.maximum(weight_map, 1e-8)
        return prob_map
    
    def predict_batch(self, input_dir, output_dir, file_extension='.tif'):
        """
        Predict boundary probabilities for a batch of images.
        
        Args:
            input_dir (str): Directory containing input images.
            output_dir (str): Directory to save output probability maps.
            file_extension (str): File extension of input images.
        """
        # Create output directory
        os.makedirs(output_dir, exist_ok=True)
        
        # List all image files
        input_dir = Path(input_dir)
        image_files = list(input_dir.glob(f'*{file_extension}'))
        
        print(f"Found {len(image_files)} images in {input_dir}")
        
        # Process each image
        for img_path in tqdm(image_files, desc="Processing images"):
            # Define output path
            output_filename = f"{img_path.stem}_boundary.png"
            output_path = os.path.join(output_dir, output_filename)
            
            # Predict and save
            self.predict_image(str(img_path), output_path)
            
        print(f"Batch processing complete. Results saved to {output_dir}")



