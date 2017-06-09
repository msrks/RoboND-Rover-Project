from glob import glob
from moviepy.editor import ImageSequenceClip

clip = ImageSequenceClip(glob("drive_logs/*"), fps=60)
clip.write_videofile("video.mp4")
