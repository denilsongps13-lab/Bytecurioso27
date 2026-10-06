from pathlib import Path
import subprocess
import imageio_ffmpeg

MEDIA_DIR="/tmp/media"
Path(MEDIA_DIR).mkdir(parents=True, exist_ok=True)

def make_reel_from_poster(poster_path, article_id, seconds=8):
    out=f"{MEDIA_DIR}/reel_{article_id}.mp4"
    ffmpeg=imageio_ffmpeg.get_ffmpeg_exe()
    frames=seconds*30
    vf=(
        "scale=1120:1992:force_original_aspect_ratio=increase,"
        "crop=1080:1920,"
        f"zoompan=z='min(zoom+0.0008,1.06)':d={frames}:s=1080x1920:fps=30,"
        "format=yuv420p"
    )
    cmd=[
        ffmpeg,"-y",
        "-loop","1",
        "-i",poster_path,
        "-t",str(seconds),
        "-vf",vf,
        "-an",
        "-c:v","libx264",
        "-preset","veryfast",
        "-pix_fmt","yuv420p",
        "-movflags","+faststart",
        out,
    ]
    subprocess.run(cmd,check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
    return out
