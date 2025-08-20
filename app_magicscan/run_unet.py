import argparse
import os
import numpy as np
from pathlib import Path
import torch

# Import from our modules (assuming they're in the same directory)
from image_tiling_utility import TissueDatasetPreparation
from dataset_augmentation import create_dataloaders_with_originals
from unet_implementation import train_unet_with_tracking, visualize_predictions
from inference_pipeline import TissuePredictor
from unet_pp_implementation import UNetPP5
#
# # 1. Preprocess the data (tiling and splitting)
# python run_unet.py --mode preprocess --image_dir "C:\Users\jediati\Desktop\JEDIATI\data\ARPA-H\tes
# t_unet_train\train_im" --label_dir "C:\Users\jediati\Desktop\JEDIATI\data\ARPA-H\test_unet_train\label_im" --output_dir "C:\Users\jediati\Desktop\JEDIATI\data\ARPA-H\test_unet_train\output"
#
# # 2. Train the model with tracking
# python complete_workflow.py --mode train --output_dir /path/to/processed_data --epochs 100 --batch_size 8 --learning_rate 1e-4
#
# # 3. Run prediction on new images
# python complete_workflow.py --mode predict --model_path /path/to/processed_data/models/best_model.pth --input_image /path/to/new_image.tif --output_image /path/to/prediction_output.tif

# python run_unet.py --mode train --image_dir "C:\Users\jediati\Desktop\JEDIATI\data\ARPA-H\test_unet_train\train_im" --label_dir "C:\U
# sers\jediati\Desktop\JEDIATI\data\ARPA-H\test_unet_train\label_im" --output_dir "C:\Users\jediati\Desktop\JEDIATI\data\ARPA-H\test_unet_train\output256_4layer" --batch_size 4 --epochs 3 --unet_layers 4 --tile_size 256 --overlap 32


def main(args=None):

    parser = argparse.ArgumentParser(description='UNET for Tissue Boundary Detection')
    parser.add_argument('--mode', type=str, required=True, choices=['preprocess', 'train', 'predict'],
                        help='Operation mode: preprocess, train, or predict')

    # Paths for data
    parser.add_argument('--image_dir', type=str, help='Directory containing original images')
    parser.add_argument('--label_dir', type=str, help='Directory containing label images')
    parser.add_argument('--output_dir', type=str, help='Directory to save outputs')

    # Model parameters
    parser.add_argument('--model_path', type=str, help='Path to the trained model')
    parser.add_argument('--batch_size', type=int, default=8, help='Batch size for training')
    parser.add_argument('--epochs', type=int, default=200, help='Number of epochs for training')
    parser.add_argument('--learning_rate', type=float, default=1e-5, help='Learning rate')
    parser.add_argument('--augmentations', type=int, default=8, help='number of augmented copies')

    parser.add_argument('--weight_dice', type=float, default=0.3, help='non-zero [0-1] for weight of dice loss component')
    parser.add_argument('--weight_focal', type=float, default=0.7, help='non-zero [0-1] for weight of focal loss component')
    parser.add_argument('--focal_alpha', type=float, default=0.25, help='non-zero [0-1] for weight of focal loss alpha component')
    parser.add_argument('--focal_gamma', type=float, default=3.0, help='non-zero [0-1] for weight of focal loss gamma component (0 makes this BCE)')
    

    # Tiling parameters
    parser.add_argument('--tile_size', type=int, default=128, help='Size of tiles')
    parser.add_argument('--unet_layers', type=int, default=6, help='Which U-Net: 4=UNet4, 5=UNet5, 6=UNetPP5')
    parser.add_argument('--overlap', type=int, default=64, help='Overlap between tiles')

    # Prediction parameters
    parser.add_argument('--input_image', type=str, help='Path to input image for prediction')
    parser.add_argument('--output_image', type=str, help='Path to save prediction output')

    if args is None:
        args = parser.parse_args()
    else:
        args = parser.parse_args(args)

    # Create output directory if it doesn't exist
    if args.output_dir:
        os.makedirs(args.output_dir, exist_ok=True)

    if args.mode == 'preprocess':
        if not (args.image_dir and args.label_dir and args.output_dir):
            parser.error("Preprocessing mode requires image_dir, label_dir, and output_dir")

        print("Preprocessing data...")
        preprocessor = TissueDatasetPreparation(
            args.image_dir,
            args.label_dir,
            args.output_dir,
            tile_size=args.tile_size,
            overlap=args.overlap
        )
        preprocessor.process_files()

    elif args.mode == 'train':
        if not args.output_dir:
            parser.error("Training mode requires output_dir for saving models")

        train_img_dir = os.path.join(args.output_dir, 'train', 'images')
        train_label_dir = os.path.join(args.output_dir, 'train', 'labels')
        val_img_dir = os.path.join(args.output_dir, 'val', 'images')
        val_label_dir = os.path.join(args.output_dir, 'val', 'labels')

        model_save_dir = os.path.join(args.output_dir, 'models')
        os.makedirs(model_save_dir, exist_ok=True)

        print("Training UNET model...")
        print(f"Using {args.unet_layers} layer unet")
        train_loader, val_loader = create_dataloaders_with_originals(
            train_img_dir,
            train_label_dir,
            val_img_dir,
            val_label_dir,
            batch_size=args.batch_size,
            augmentation_copies=args.augmentations,  # Creates 3 augmented versions of each original image
            aug_intensity='heavy'  # Use heavy augmentation for maximum diversity
        )

        # Check if model_path argument is defined
        starting_epoch = 0
        checkpoint = None
        if hasattr(args, 'model_path') and args.model_path:
            print(f"Loading model from checkpoint: {args.model_path}")
            checkpoint = torch.load(args.model_path, weights_only=False)
            starting_epoch = int(os.path.basename(args.model_path).split('_')[-1].split('.')[0]) + 1
            print(f"Continuing training from epoch {starting_epoch}")

        model = train_unet_with_tracking(
            train_loader,
            val_loader,
            model_save_dir,
            unet_layers=args.unet_layers,
            num_epochs=args.epochs,
            learning_rate=args.learning_rate,
            starting_epoch=starting_epoch,
            checkpoint=checkpoint,
            focal_alpha=args.focal_alpha,
            focal_gamma=args.focal_gamma,
            weight_focal=args.weight_focal,
            weight_dice=args.weight_dice
        )
        # model = train_unet_with_tracking(
        #     train_loader,
        #     val_loader,
        #     model_save_dir,
        #     num_epochs=args.epochs,
        #     learning_rate=args.learning_rate
        # )

        # Create validation dataset to visualize results



        # Visualize some predictions
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        visualization_path = os.path.join(args.output_dir, 'prediction_samples.png')
        visualize_predictions(model, val_loader, device, num_samples=4, save_path=visualization_path)
        print(f"Saved prediction visualization to {visualization_path}")

    elif args.mode == 'predict':
        if not (args.model_path and args.input_image ):
            parser.error("Prediction mode requires model_path, input_image, and output_image")
        if not args.output_image:
            args.output_image = os.path.splitext(args.input_image)[0] + "_pred.tif"
        print("Running prediction...")
        predictor = TissuePredictor(
            args.model_path,
            tile_size=args.tile_size,
            overlap=args.overlap,
            unet_layers=args.unet_layers
        )

        predictor.predict_image(args.input_image, args.output_image)
        print(f"Prediction saved to {args.output_image}")
    elif args.mode == 'deserialize':
        if not (args.model_path):
            parser.error("Deserialize mode requires model_path")
        

if __name__ == "__main__":
    main()