"""
train_culling.py

Train a culling classifier (ResNet) using PyTorch on the ingested dataset.
Reads from the SQLite database.
"""
import argparse
import os
import json
import random
import sqlite3
from pathlib import Path
from PIL import Image
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
import torchvision.transforms as T
import torchvision.models as models
import logging

# Setup basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class PhotoDataset(Dataset):
    def __init__(self, records, images_dir, transform=None):
        self.records = records
        self.images_dir = Path(images_dir)
        self.transform = transform

    def __len__(self):
        return len(self.records)

    def __getitem__(self, idx):
        preview_path, label = self.records[idx]
        img_path = self.images_dir / preview_path
        try:
            img = Image.open(img_path).convert('RGB')
            if self.transform:
                img = self.transform(img)
        except FileNotFoundError:
            logging.warning(f"Image not found: {img_path}. Skipping.")
            # Return a placeholder tensor and a special label (e.g., -1) to be filtered out
            return torch.zeros((3, 224, 224)), -1
        return img, label

def load_records_from_db(db_path):
    """Loads records from the SQLite database."""
    logging.info(f"Loading records from {db_path}...")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT preview_path, cull_label FROM records WHERE cull_label IS NOT NULL")
    records = cursor.fetchall()
    conn.close()
    logging.info(f"Loaded {len(records)} records.")
    return records

def build_model(num_classes=3):
    """Builds a ResNet34 model with a custom head for classification."""
    model = models.resnet34(weights=models.ResNet34_Weights.DEFAULT)
    num_ftrs = model.fc.in_features
    model.fc = nn.Sequential(
        nn.Linear(num_ftrs, 256),
        nn.ReLU(),
        nn.Dropout(0.4),
        nn.Linear(256, num_classes)
    )
    return model

def collate_fn(batch):
    """Custom collate function to filter out items that could not be loaded."""
    batch = list(filter(lambda x: x[1] != -1, batch))
    return torch.utils.data.dataloader.default_collate(batch)

def train(args):
    records = load_records_from_db(args.db_path)
    if not records:
        logging.error("No records found in the database. Aborting training.")
        return

    random.shuffle(records)
    split = int(0.8 * len(records))
    train_rec, val_rec = records[:split], records[split:]

    transform = T.Compose([
        T.Resize(256),
        T.CenterCrop(224),
        T.ToTensor(),
        T.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
    ])

    train_ds = PhotoDataset(train_rec, args.images_dir, transform)
    val_ds = PhotoDataset(val_rec, args.images_dir, transform)

    train_loader = DataLoader(train_ds, batch_size=args.batch_size, shuffle=True, num_workers=args.workers, collate_fn=collate_fn)
    val_loader = DataLoader(val_ds, batch_size=args.batch_size, shuffle=False, num_workers=args.workers, collate_fn=collate_fn)

    device = 'mps' if torch.backends.mps.is_available() else 'cuda' if torch.cuda.is_available() else 'cpu'
    logging.info(f"Using device: {device}")

    model = build_model(num_classes=3).to(device)
    criterion = nn.CrossEntropyLoss()
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-5)

    best_val_loss = float('inf')

    for epoch in range(args.epochs):
        model.train()
        total_loss = 0.0
        for imgs, labels in train_loader:
            if imgs is None: continue
            imgs, labels = imgs.to(device), labels.to(device)
            
            optimizer.zero_grad()
            out = model(imgs)
            loss = criterion(out, labels)
            loss.backward()
            optimizer.step()
            total_loss += loss.item()
        
        avg_train_loss = total_loss / len(train_loader)
        logging.info(f"Epoch {epoch+1}/{args.epochs} | Training Loss: {avg_train_loss:.4f}")

        # Validation
        model.eval()
        val_loss = 0.0
        correct = 0
        total = 0
        with torch.no_grad():
            for imgs, labels in val_loader:
                if imgs is None: continue
                imgs, labels = imgs.to(device), labels.to(device)
                
                out = model(imgs)
                loss = criterion(out, labels)
                val_loss += loss.item()
                
                preds = out.argmax(dim=1)
                correct += (preds == labels).sum().item()
                total += labels.size(0)
        
        avg_val_loss = val_loss / len(val_loader)
        accuracy = correct / total if total > 0 else 0
        logging.info(f"Validation Loss: {avg_val_loss:.4f} | Accuracy: {accuracy:.4f}")

        if avg_val_loss < best_val_loss:
            best_val_loss = avg_val_loss
            torch.save(model.state_dict(), args.out)
            logging.info(f"Saved best model to {args.out} (val_loss: {best_val_loss:.4f})")

    logging.info("Training finished.")

if __name__ == '__main__':
    p = argparse.ArgumentParser(description="Train a culling classifier.")
    p.add_argument('--db-path', default='data/nsp_plugin.db', help="Path to the SQLite database.")
    p.add_argument('--images_dir', default='data/images', help="Directory containing the preview images.")
    p.add_argument('--out', default='models/culling_model.pth', help="Path to save the trained model.")
    p.add_argument('--epochs', type=int, default=5, help="Number of training epochs.")
    p.add_argument('--batch-size', type=int, default=16, help="Batch size for training.")
    p.add_argument('--lr', type=float, default=1e-4, help="Learning rate.")
    p.add_argument('--workers', type=int, default=2, help="Number of worker processes for data loading.")
    args = p.parse_args()
    
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    train(args)