"""Generate video frames and assemble high-quality WebM & MP4 videos from the storyboard."""
import os
import pathlib
import subprocess
import time
from playwright.sync_api import sync_playwright

FRAMES_DIR = pathlib.Path("assets/video/frames")
FRAMES_DIR.mkdir(parents=True, exist_ok=True)
HTML_PATH = pathlib.Path("assets/video/slides_storyboard.html").resolve()

# Playwright setup
p = sync_playwright().start()
browser = p.chromium.launch(
    executable_path=r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.EXE",
    headless=True,
)
page = browser.new_page(viewport={"width": 1280, "height": 720}, device_scale_factor=1)
page.goto(HTML_PATH.as_uri())

# Capture 5 slides: 3 seconds each = 90 frames each @ 30 fps
slides_count = 5
frame_idx = 0
fps = 30
duration_per_slide = 2.5 # seconds
frames_per_slide = int(fps * duration_per_slide)

print(f"Generating {slides_count} slides at {fps} fps ({frames_per_slide} frames/slide)...")

for s in range(1, slides_count + 1):
    # activate slide s
    page.evaluate(f"""
        document.querySelectorAll('.slide').forEach(el => el.classList.remove('active'));
        document.getElementById('slide-{s}').classList.add('active');
    """)
    time.sleep(0.1)
    slide_png = FRAMES_DIR / f"slide_{s}.png"
    page.screenshot(path=str(slide_png))
    
    # create repeated frames
    for _ in range(frames_per_slide):
        target = FRAMES_DIR / f"frame_{frame_idx:04d}.png"
        target.write_bytes(slide_png.read_bytes())
        frame_idx += 1

browser.close()
p.stop()
print(f"Total frames written: {frame_idx}")

# Encode with playwright ffmpeg
ffmpeg_path = r"C:\Users\xio\AppData\Local\ms-playwright\ffmpeg-1011\ffmpeg-win64.exe"
webm_out = pathlib.Path("assets/video/flux_v07_showcase.webm").resolve()
cmd = [
    ffmpeg_path,
    "-y",
    "-framerate", "30",
    "-i", str(FRAMES_DIR / "frame_%04d.png"),
    "-c:v", "libvpx",
    "-b:v", "2M",
    "-crf", "10",
    str(webm_out)
]
print("Encoding WebM video...")
res = subprocess.run(cmd, capture_output=True, text=True)
print("FFMPEG WebM code:", res.returncode, "Size:", webm_out.stat().st_size if webm_out.exists() else 0)

# Also generate high-quality animated GIF / MP4
from PIL import Image
gif_out = pathlib.Path("assets/video/flux_v07_showcase.gif")
slide_images = [Image.open(FRAMES_DIR / f"slide_{s}.png") for s in range(1, slides_count + 1)]
slide_images[0].save(
    str(gif_out),
    save_all=True,
    append_images=slide_images[1:],
    duration=2500, # 2.5 seconds per slide
    loop=0
)
print("GIF generated:", gif_out.stat().st_size)

# Also create an MP4 copy using cv2 mp4v or openh264 if available
import cv2, numpy as np
mp4_out = pathlib.Path("assets/video/flux_v07_showcase.mp4")
fourcc = cv2.VideoWriter_fourcc(*'mp4v')
writer = cv2.VideoWriter(str(mp4_out), fourcc, 30, (1280, 720))
for i in range(frame_idx):
    img = cv2.imread(str(FRAMES_DIR / f"frame_{i:04d}.png"))
    writer.write(img)
writer.release()
print("MP4 generated:", mp4_out.stat().st_size if mp4_out.exists() else 0)

