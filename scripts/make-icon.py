"""Render JEV's open-orbit symbol for the app and macOS menu bar."""
from pathlib import Path
import math
import subprocess
from PIL import Image, ImageDraw

root = Path(__file__).resolve().parents[1]
assets = root / 'assets'
iconset = root / 'build' / 'JEV.iconset'
iconset.mkdir(parents=True, exist_ok=True)
scale = 4
# Two tapered arcs leave a generous open center and opposing breaks.
# The taper gives the symbol a flowing silhouette even in monochrome.
def arc_points(rotation):
    outer, inner = [], []
    for n in range(201):
        t = n / 200
        angle = math.radians(-52 + 144*t + rotation)
        radius = 207
        half_width = 12 + 42 * math.sin(math.pi*t)**.75
        for edge, r in ((outer, radius+half_width), (inner, radius-half_width)):
            edge.append((512+r*math.cos(angle), 512+r*math.sin(angle)))
    return outer + inner[::-1]
shapes = [arc_points(0), arc_points(180)]
def draw_mark(canvas, colors, transform=lambda x,y:(x,y)):
    draw=ImageDraw.Draw(canvas)
    for coords,color in zip(shapes,colors):
        draw.polygon([tuple(round(v*scale) for v in transform(x,y)) for x,y in coords],fill=color)

image=Image.new('RGBA',(1024*scale,1024*scale))
ImageDraw.Draw(image).rounded_rectangle((64*scale,64*scale,960*scale,960*scale),radius=210*scale,fill='#303632')
draw_mark(image,['#f5f1e7','#b8c7b6'])
image=image.resize((1024,1024),Image.Resampling.LANCZOS)
image.save(assets/'icon.png')
paths=''.join('<path d="M '+' L '.join(f'{x:.2f} {y:.2f}' for x,y in shape)+' Z" fill="'+color+'"/>' for shape,color in zip(shapes,['#f5f1e7','#b8c7b6']))
(assets/'icon.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1024 1024"><rect x="64" y="64" width="896" height="896" rx="210" fill="#303632"/>'+paths+'</svg>\n')
for size in (16,32,128,256,512):
    for density in (1,2):
        suffix='@2x' if density==2 else ''
        image.resize((size*density,size*density),Image.Resampling.LANCZOS).save(iconset/f'icon_{size}x{size}{suffix}.png')
subprocess.run(['iconutil','-c','icns',str(iconset),'-o',str(assets/'icon.icns')],check=True)
tray=Image.new('RGBA',(640*scale,640*scale))
draw_mark(tray,['black','black'],lambda x,y:(x-192,y-192))
tray_dir=root/'electron'/'assets'
tray_dir.mkdir(exist_ok=True)
for size,suffix in ((18,''),(36,'@2x')):
    tray.resize((size,size),Image.Resampling.LANCZOS).save(tray_dir/f'searchTemplate{suffix}.png')
