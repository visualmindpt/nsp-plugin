"""
train_lut.py

Train a small neural network to predict a 3D LUT or color transform for the target style.
This is a placeholder example using a simple MLP on image embeddings -> LUT vector.
"""
import os, json
import torch, torch.nn as nn
from torch.utils.data import Dataset, DataLoader
import numpy as np

class EmbeddingLUTDataset(Dataset):
    def __init__(self, meta_path, emb_path):
        self.meta = [json.loads(l) for l in open(meta_path,'r',encoding='utf8')]
        self.emb = np.load(emb_path)
    def __len__(self): return len(self.meta)
    def __getitem__(self, idx):
        e = self.emb[idx].astype('float32')
        dv = np.array(self.meta[idx].get('develop_vector',[]), dtype='float32')
        targ = np.zeros(64, dtype='float32')
        targ[:min(len(dv),64)] = dv[:64]
        return e, targ

class LUTNet(nn.Module):
    def __init__(self, in_dim, out_dim=64):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(in_dim,512), nn.ReLU(), nn.Dropout(0.2),
            nn.Linear(512,256), nn.ReLU(),
            nn.Linear(256,out_dim)
        )
    def forward(self,x): return self.net(x)

def train(args):
    ds = EmbeddingLUTDataset(args.meta, args.emb)
    dl = DataLoader(ds, batch_size=32, shuffle=True, num_workers=2)
    device = 'cuda' if torch.cuda.is_available() else 'mps' if torch.backends.mps.is_available() else 'cpu'
    in_dim = np.load(args.emb).shape[1]
    model = LUTNet(in_dim=in_dim).to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=1e-4, weight_decay=1e-5)
    loss_fn = nn.L1Loss()
    for epoch in range(args.epochs):
        model.train()
        total = 0.0
        for emb, targ in dl:
            emb = emb.to(device); targ = targ.to(device)
            opt.zero_grad()
            out = model(emb)
            loss = loss_fn(out, targ)
            loss.backward(); opt.step()
            total += loss.item()
        print(f"Epoch {epoch+1} loss={total/len(dl):.4f}")
    os.makedirs('models', exist_ok=True)
    torch.save(model.state_dict(), args.out)
    print("Saved LUT model:", args.out)

if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--meta', default='data/records.jsonl')
    p.add_argument('--emb', default='data/embeddings.npy')
    p.add_argument('--epochs', type=int, default=20)
    p.add_argument('--out', default='models/lut_net.pth')
    args = p.parse_args()
    train(args)
