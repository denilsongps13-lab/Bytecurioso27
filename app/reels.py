from pathlib import Path
import subprocess
import imageio_ffmpeg

MEDIA_DIR="/tmp/media"
Path(MEDIA_DIR).mkdir(parents=True, exist_ok=True)

def make_reel_from_poster(poster_path, article_id, seconds=7):
    out=f"{MEDIA_DIR}/reel_{article_id}.mp4"
    ffmpeg=imageio_ffmpeg.get_ffmpeg_exe()
    cmd=[
        ffmpeg,"-y",
        "-loop","1",
        "-framerate","30",
        "-i",poster_path,
        "-t",str(seconds),
        "-vf","scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2,format=yuv420p",
        "-an",
        "-c:v","libx264",
        "-preset","veryfast",
        "-movflags","+faststart",
        out,
    ]
    subprocess.run(cmd,check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
    return out
