import ffmpeg
import subprocess
from pathlib import Path
from subplz.utils import get_tqdm
from subplz.files import normalize_text, write_sub_failed

tqdm, trange = get_tqdm()

# Define paths
alass_dir = Path(__file__).parent.parent / 'alass'
alass_path = alass_dir / 'alass-linux64'


def extract_subtitles(video_path: Path, output_subtitle_path: Path) -> None:
    try:
        (
            ffmpeg
            .input(str(video_path))
            .output(str(output_subtitle_path), map='0:s:0', c='srt', loglevel="quiet")
            .global_args("-hide_banner")
            .run(overwrite_output=True)
        )
        return output_subtitle_path
    except ffmpeg.Error as e:
        raise RuntimeError(f"Failed to extract subtitles: {e.stderr.decode()}\nCommand: {str(e.cmd)}")


def get_subtitle_path(video_path, lang_ext):
    stem = Path(video_path).stem
    parent = Path(video_path).parent
    ext = f".{lang_ext}" if lang_ext else ""
    return parent / f"{stem}{ext}.srt"


def sync_alass(source, input_sources, be):
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)

    with tqdm(source.streams) as bar:
        for batches in bar:
            video_path = batches[2][0].path

            subtitle_path = get_subtitle_path(video_path, input_sources.lang_ext_original)
            target_subtitle_path = get_subtitle_path(video_path, input_sources.lang_ext)
            incorrect_subtitle_path = get_subtitle_path(video_path, input_sources.lang_ext_incorrect)
            if subtitle_path is None and incorrect_subtitle_path is None:
                print(f"❗ Skipping syncing {subtitle_path} since --lang-ext-original and --lang-ext-incorrect were empty")
                continue
            if str(subtitle_path) == str(incorrect_subtitle_path):
                print(f"❗ Skipping syncing {subtitle_path} since the name matches the incorrect timed subtitle")

            if not subtitle_path.exists():
                print(f'⛏️ Extracting subtitles from {video_path} to {subtitle_path}')
                extract_subtitles(video_path, subtitle_path)
                if not subtitle_path.exists():
                    error_message = f"❗ Failed to extract subtitles; file not found: {subtitle_path}"
                    print(error_message)
                    write_sub_failed(source, subtitle_path, error_message)
                    continue
            if not incorrect_subtitle_path.exists():
                print(f"❗ Subtitle with incorrect timing not found: {incorrect_subtitle_path}")
                continue

            print(f'🤝 Aligning {incorrect_subtitle_path} based on {subtitle_path}')
            cmd = [
                alass_path,
                # *['-' + h for h in alass_args],
                str(subtitle_path),
                str(incorrect_subtitle_path),
                str(target_subtitle_path)
            ]
            try:
                subprocess.run(cmd, check=True, stderr=subprocess.PIPE, text=True)
                source.writer.written = True
            except subprocess.CalledProcessError as e:
                print(f"Alass command failed: {e}")
