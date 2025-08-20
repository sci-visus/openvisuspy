import torch
import os
import glob
from run_unet import main as run_unet_main

print("CUDA available:", torch.cuda.is_available())
torch.cuda.set_device(1)
print("Using GPU:", torch.cuda.current_device())
#print("Using device:", torch.cuda.get_device_name(0))

INPUT_DIR = "/uufs/chpc.utah.edu/common/home/u1419916/data/ARPA-H/tissue_boundary"
TEST_DIR = os.path.join(INPUT_DIR, "test_images_old")
MODEL_DIR = "/uufs/chpc.utah.edu/common/home/u1419916/data/ARPA-H/tissue_boundary/tissue_boundary_dataset/old_reconstruction"
TILE_SIZE = 128
OVERLAP = 64
LAYERS = 4
EPOCHS = 350
BATCH_SIZE = 8
AUGMENTATIONS = 8

OUT_PREFIX = f"FDL_fa_t{TILE_SIZE}_o{OVERLAP}_l{LAYERS}_b{BATCH_SIZE}_e{EPOCHS}_a{AUGMENTATIONS}"
MODEL_PATH = os.path.join(MODEL_DIR, f"tiles_run_{OUT_PREFIX}/models/best_model.pth")
OUTPUT_BASE = os.path.join(INPUT_DIR, f"tiles_run_{OUT_PREFIX}")

print("Model exists:", os.path.isfile(MODEL_PATH))

# Get list of test images
TEST_LIST = sorted(glob.glob(os.path.join(TEST_DIR, "*.tiff")))
PRED_LIST = [os.path.join(INPUT_DIR, "test_predictions_old", os.path.basename(os.path.splitext(f)[0] + "_pred.tif")) for f in TEST_LIST]

# Predict loop
for input_path, output_path in zip(TEST_LIST, PRED_LIST):
    print(f"\n🔍 Predicting: {os.path.basename(input_path)}")
    run_unet_main([
        "--mode", "predict",
        "--input_image", input_path,
        "--output_image", output_path,
        "--model_path", MODEL_PATH,
        "--output_dir", OUTPUT_BASE,
        "--tile_size", str(TILE_SIZE),
        "--overlap", str(OVERLAP),
        "--batch_size", str(BATCH_SIZE),
        "--unet_layers", str(LAYERS),
        "--epochs", str(EPOCHS),
    ])