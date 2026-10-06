from pathlib import Path
import subprocess
import imageio_ffmpeg

MEDIA_DIR="/tmp/media"
Path(MEDIA_DIR).mkdir(parents=True, exist_ok=True)

def make_reel_from_poster(poster_path, article_id, seconds=6):
    out=f"{MEDIA_DIR}/reel_{article_id}.mp4"
    ffmpeg=imageio_ffmpeg.get_ffmpeg_exe()
    frames=seconds*24
    vf=(
        "scale=760:1352:force_original_aspect_ratio=increase,"
        "crop=720:1280,"
        f"zoompan=z='min(zoom+0.0007,1.04)':d={frames}:s=720x1280:fps=24,"
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
        "-preset","ultrafast",
        "-threads","1",
        "-pix_fmt","yuv420p",
        "-movflags","+faststart",
        out,
    ]
    subprocess.run(cmd,check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
    return out
