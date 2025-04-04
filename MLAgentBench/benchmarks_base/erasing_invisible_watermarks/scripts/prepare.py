"""
Prepare and split the beige box dataset into development and test sets.

Steps:
1. Download and extract the beige box dataset
2. Split images by algorithm (0-149: StegaStamp, 150-299: TreeRing)
3. Further split each algorithm's data into dev/test sets
4. Save processed data in required locations
"""

import os
import pickle
import random
import shutil
from pathlib import Path
import torch
from torchvision import transforms
from PIL import Image
import sys
import subprocess
import zipfile
import requests

def install_gdown():
    """Install gdown package if not already installed"""
    try:
        import gdown
        print("gdown is already installed")
    except ImportError:
        print("Installing gdown...")
        subprocess.check_call(["pip", "install", "gdown"])
        print("gdown installed successfully")

def download_file_from_dropbox(url, output_path):
    """Download file from Dropbox, adding dl=1 to force download"""
    # Convert sharing URL to direct download URL
    url = url.replace("dl=0", "dl=1")
    if "?" in url:
        url = url + "&dl=1"
    else:
        url = url + "?dl=1"
        
    print(f"Downloading from: {url}")
    response = requests.get(url, stream=True)
    response.raise_for_status()
    
    total_size = int(response.headers.get('content-length', 0))
    block_size = 8192
    
    with open(output_path, 'wb') as f:
        for data in response.iter_content(block_size):
            f.write(data)
            
    print(f"Downloaded to: {output_path}")

def download_and_prepare_dataset(temp_dir):
    """Download, extract and organize the dataset with dev/test split"""
    # Create directories
    dev_dir = Path("../env/data/dev")  # Development set (20%)
    test_dir = Path("./test_data/test")     # Test set (80%)
    dev_dir.mkdir(parents=True, exist_ok=True)
    test_dir.mkdir(parents=True, exist_ok=True)
    
    # Create temp directory
    temp_dir.mkdir(exist_ok=True)
    
    # URLs for the datasets
    unwatermarked_url = "https://www.dropbox.com/scl/fi/1paem2pydn70onn5hiptr/unwatermarked_mscoco.zip?rlkey=8pdsk897xvsmsqbyxb1w5a3d3&e=1&st=elauj78e"
    watermarked_url = "https://www.dropbox.com/scl/fi/ez4lgdhpve7nhjcrnck31/stable_signature_mscoco.zip?rlkey=6a0nbp6a5rz5ann7apgnaexa0&e=1&st=iyasywtu"
    
    try:
        # Download and extract files to temp directory
        print("\nDownloading and extracting datasets...")
        for data_type, url in [("unwatermarked", unwatermarked_url), ("watermarked", watermarked_url)]:
            print(f"\nProcessing {data_type} dataset...")
            zip_path = temp_dir / f"{data_type}.zip"
            download_file_from_dropbox(url, zip_path)
            
            # Extract to temp directory
            temp_extract = temp_dir / data_type
            temp_extract.mkdir(exist_ok=True)
            print(f"Extracting to {temp_extract}")
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(temp_extract)
            
            # Split into dev/test sets
            images = list(temp_extract.glob("**/*.png"))  # Recursive glob to find all PNGs
            if not images:
                print(f"No PNG files found in {temp_extract}")
                print("Contents of directory:", list(temp_extract.glob("**/*")))
                continue
                
            print(f"Found {len(images)} images")
            random.seed(42)  # For reproducibility
            
            # 80/20 split
            num_test = int(len(images) * 0.8)
            test_indices = set(random.sample(range(len(images)), num_test))
            
            # Create destination directories
            dev_dest = dev_dir / data_type
            test_dest = test_dir / data_type
            dev_dest.mkdir(exist_ok=True)
            test_dest.mkdir(exist_ok=True)
            
            # Move files to appropriate directories
            dev_count = 0
            test_count = 0
            for idx, img_path in enumerate(images):
                try:
                    if idx in test_indices:
                        shutil.copy2(img_path, test_dest / img_path.name)
                        test_count += 1
                    else:
                        shutil.copy2(img_path, dev_dest / img_path.name)
                        dev_count += 1
                except Exception as e:
                    print(f"Error copying {img_path}: {e}")
            
            print(f"Split complete for {data_type}:")
            print(f"- Development set ({dev_dest}): {dev_count} images")
            print(f"- Test set ({test_dest}): {test_count} images")
        
        # Verify the split
        for data_type in ["unwatermarked", "watermarked"]:
            dev_files = list((dev_dir / data_type).glob("*.png"))
            test_files = list((test_dir / data_type).glob("*.png"))
            print(f"\nVerification for {data_type}:")
            print(f"- Development set: {len(dev_files)} files")
            print(f"- Test set: {len(test_files)} files")
        
        # Clean up temp directory
        shutil.rmtree(temp_dir)
        
        print("\nDataset preparation completed!")
        print(f"Development data in: {dev_dir}")
        print(f"Test data in: {test_dir}")
        
        return True
        
    except Exception as e:
        print(f"\nError preparing dataset: {e}")
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
        return False

def create_directories():
    """Create necessary directories for storing split datasets"""
    directories = [
        './test_data',  # For test set (hidden from AI agents)
        '../env/data'           # For development set
    ]
    for dir_path in directories:
        os.makedirs(dir_path, exist_ok=True)
        print(f"Created directory: {dir_path}")

def prepare_dataset(data_dir, test_ratio=0.8, seed=42):
    """
    Process the beige box dataset:
    1. Split by algorithm (StegaStamp vs TreeRing)
    2. For each algorithm, split into dev/test sets
    """
    random.seed(seed)
    
    # Load and split by algorithm
    dataset = load_images_from_directory(data_dir)
    
    if not dataset['stegastamp'] and not dataset['treering']:
        print("No valid images found in the dataset!")
        sys.exit(1)
    
    # Further split each algorithm's data into dev/test sets
    for watermark_type in ['stegastamp', 'treering']:
        if not dataset[watermark_type]:
            print(f"Warning: No {watermark_type} algorithm images found")
            continue
            
        print(f"\nSplitting {watermark_type} algorithm data into dev/test sets...")
        images = dataset[watermark_type]
        num_test = int(len(images) * test_ratio)
        
        # Randomly select test images
        test_indices = random.sample(range(len(images)), num_test)
        test_images = [images[i] for i in test_indices]
        dev_images = [img for i, img in enumerate(images) if i not in test_indices]
        
        print(f"- Total {watermark_type} images: {len(images)}")
        print(f"- Test set size: {len(test_images)} images")
        print(f"- Development set size: {len(dev_images)} images")
        
        # Save test images (hidden from AI agents)
        test_data = {watermark_type: test_images}
        test_save_path = Path("./test_data") / f"test_images_{watermark_type}.pkl"
        with open(test_save_path, 'wb') as f:
            pickle.dump(test_data, f)
        print(f"- Saved {watermark_type} test data to: {test_save_path}")
        
        # Save development images
        dev_data = {watermark_type: dev_images}
        dev_save_path = Path("../env/data") / f"dev_images_{watermark_type}.pkl"
        with open(dev_save_path, 'wb') as f:
            pickle.dump(dev_data, f)
        print(f"- Saved {watermark_type} development data to: {dev_save_path}")

def load_images_from_directory(data_dir):
    """Load and split images by watermarking algorithm"""
    dataset = {'stegastamp': [], 'treering': []}
    
    # Get all image files and sort them by number
    image_files = []
    for ext in ['*.png', '*.jpg', '*.jpeg']:
        image_files.extend(list(data_dir.glob(ext)))
    
    image_files.sort(key=lambda x: int(x.stem))  # Sort by the numeric part of filename
    print(f"\nProcessing {len(image_files)} total images from beige box dataset")
    
    # Split images by algorithm based on index
    for img_path in image_files:
        try:
            img_num = int(img_path.stem)
            img = Image.open(img_path)
            img = transforms.ToTensor()(img)
            
            # Split based on algorithm (0-149: StegaStamp, 150+: TreeRing)
            if img_num < 150:
                dataset['stegastamp'].append(img)
                print(f"Loaded StegaStamp algorithm image: {img_path.name}")
            else:
                dataset['treering'].append(img)
                print(f"Loaded TreeRing algorithm image: {img_path.name}")
                
        except Exception as e:
            print(f"Error loading {img_path}: {e}")
            continue
    
    print(f"\nSplit by algorithm:")
    print(f"- StegaStamp algorithm: {len(dataset['stegastamp'])} images (from 0.png to 149.png)")
    print(f"- TreeRing algorithm: {len(dataset['treering'])} images (from 150.png to 299.png)")
    
    return dataset

def main():
    print("\n" + "="*80)
    print("DATASET PREPARATION")
    print("="*80)
    
    # Create necessary directories
    scripts_dir = Path(".")
    temp_dir = scripts_dir / "temp_data"
    
    # Download and prepare dataset
    if not download_and_prepare_dataset(temp_dir):
        print("Failed to prepare dataset. Please try again or check the error messages above.")
        sys.exit(1)
    
    # Install warm_up_kit
    print("Installing warm_up_kit package...")
    warm_up_kit_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),  # Go up one level from scripts
        "warm_up_kit"
    )
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-e", warm_up_kit_path])
    
    print("\n" + "="*80)
    print("DATASET PREPARATION COMPLETED!")
    print("- Data saved in: env/data/")
    print("="*80 + "\n")

if __name__ == "__main__":
    main()
    with open("prepared", 'w') as writer:
        pass
