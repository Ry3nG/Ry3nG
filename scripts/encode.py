"""Assemble rendered frames into an animated WebP that stays under GitHub's ~5 MB image-proxy limit."""
import glob, os, sys
from PIL import Image

theme, frames_dir, out_dir = sys.argv[1], sys.argv[2], sys.argv[3]
BG = {'dark': (13, 17, 23), 'light': (255, 255, 255)}[theme]
LIMIT = 4.8e6
files = sorted(glob.glob(os.path.join(frames_dir, '*.png')))
SRC_FPS = 15

def build(fps, quality):
    pick = [files[min(len(files) - 1, round(i * SRC_FPS / fps))] for i in range(int(len(files) * fps / SRC_FPS))]
    ims = []
    for k, f in enumerate(pick):
        im = Image.open(f).convert('RGB')
        a = min(1, (k + 1) / (fps * .5), (len(pick) - k) / (fps * .6))    # fade in / out so the loop is seamless
        if a < 1: im = Image.blend(Image.new('RGB', im.size, BG), im, a)
        ims.append(im)
    out = os.path.join(out_dir, f'skyline-{theme}.webp')
    ims[0].save(out, save_all=True, append_images=ims[1:], duration=int(1000 / fps), loop=0, quality=quality, method=6)
    return out, os.path.getsize(out)

os.makedirs(out_dir, exist_ok=True)
for fps, q in [(15, 60), (15, 50), (12, 50), (12, 42), (10, 40), (10, 32)]:
    out, size = build(fps, q)
    print(f'{theme}: fps={fps} q={q} -> {size / 1e6:.2f} MB')
    if size <= LIMIT: break
else:
    sys.exit(f'could not get {theme} under {LIMIT / 1e6} MB')
