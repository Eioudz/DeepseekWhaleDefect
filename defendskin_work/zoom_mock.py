"""Zoom crop of the rest preview around the chest to inspect hand placement."""
import os
from PIL import Image

W = os.path.dirname(os.path.abspath(__file__))
img = Image.open(os.path.join(W, "mock_restsite.png"))
crop = img.crop((140, 360, 480, 570))
crop = crop.resize((crop.width * 2, crop.height * 2), Image.NEAREST)
crop.save(os.path.join(W, "mock_zoom.png"))
print("saved mock_zoom.png", crop.size)