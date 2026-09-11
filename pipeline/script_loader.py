import json
import re
from dataclasses import dataclass, field
from pathlib import Path

# Script ids become tempdir prefixes and get embedded, unescaped, in ffmpeg
# concat-file paths (see assemble.concat_clips) -- keep them shell/ffmpeg-safe.
_ID_PATTERN = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
VISUAL_MODES = {"photo", "video", "generated"}
FORMATS = {"short", "longform", "compilation"}


@dataclass
class Scene:
    text: str
    visual_query: str
    local_image: Path | None = None


@dataclass
class VideoScript:
    id: str
    category: str
    title: str
    description: str
    tags: list[str]
    scenes: list[Scene]
    visual_mode: str = "photo"
    # Appended to every generate_image() prompt when visual_mode=="generated"
    # so a whole series reads as one consistent, recognizable look rather
    # than each scene being independently AI-generated with no throughline.
    image_style_prompt: str = ""
    # Overrides thumbnail.py's default heuristic (highlight the last word of
    # the title) -- that default works fine for a title ending on a strong
    # word ("...Boils Water") but picks something weak for one that doesn't
    # ("...Actually Works"). Case-insensitive substring match against the
    # title.
    thumbnail_highlight: str = ""
    # Which scene's visual becomes the thumbnail background (0 = first,
    # the old fixed behavior). A later scene sometimes has a more striking
    # image than the cold-open shot.
    thumbnail_scene: int = 0
    # "short": the existing per-scene Ken Burns/video/generated pipeline.
    # "longform": one continuous narration track held under a small set of
    # slowly-panning background_images (crossfading between them every few
    # minutes) instead of cutting to a new visual every scene -- see
    # run.py::build_longform. Requires background_images.
    format: str = "short"
    background_images: list[Path] = field(default_factory=list)
    # "compilation" only: paths to other longform-format scripts, stitched
    # together into one sitting with a short spoken transition between
    # each. See run.py::build_compilation.
    episodes: list[Path] = field(default_factory=list)

    @classmethod
    def load(cls, path: Path) -> "VideoScript":
        data = json.loads(Path(path).read_text())
        video_format = data.get("format", "short")
        if video_format not in FORMATS:
            raise ValueError(f"{path}: \"format\" must be one of {sorted(FORMATS)}, got {video_format!r}")
        is_compilation = video_format == "compilation"

        required = {"id", "category", "title", "description", "tags"}
        if not is_compilation:
            required.add("scenes")
        missing = required - data.keys()
        if missing:
            raise ValueError(f"{path} is missing required field(s): {sorted(missing)}")
        if not _ID_PATTERN.match(data["id"]):
            raise ValueError(
                f"{path}: \"id\" must be lowercase letters/digits/hyphens only, got {data['id']!r}"
            )

        episodes = [(Path(path).resolve().parent / p).resolve() for p in data.get("episodes", [])]
        if is_compilation:
            if not episodes:
                raise ValueError(f"{path}: format is \"compilation\" but \"episodes\" is empty")
            for p in episodes:
                if not p.exists():
                    raise ValueError(f"{path}: episodes entry {p} does not exist")
            return cls(
                id=data["id"],
                category=data["category"],
                title=data["title"],
                description=data["description"],
                tags=data["tags"],
                scenes=[],
                format=video_format,
                episodes=episodes,
            )

        if not data["scenes"]:
            raise ValueError(f"{path} has an empty \"scenes\" list")
        thumbnail_scene = data.get("thumbnail_scene", 0)
        if not (0 <= thumbnail_scene < len(data["scenes"])):
            raise ValueError(
                f"{path}: \"thumbnail_scene\" {thumbnail_scene} is out of range "
                f"for {len(data['scenes'])} scene(s)"
            )
        visual_mode = data.get("visual_mode", "photo")
        if visual_mode not in VISUAL_MODES:
            raise ValueError(f"{path}: \"visual_mode\" must be one of {sorted(VISUAL_MODES)}, got {visual_mode!r}")
        background_images = [
            (Path(path).resolve().parent / p).resolve() for p in data.get("background_images", [])
        ]
        if video_format == "longform" and not background_images:
            raise ValueError(f"{path}: format is \"longform\" but \"background_images\" is empty")
        for p in background_images:
            if not p.exists():
                raise ValueError(f"{path}: background_images entry {p} does not exist")
        scenes = []
        for i, s in enumerate(data["scenes"]):
            missing_scene_fields = {"text", "visual_query"} - s.keys()
            if missing_scene_fields:
                raise ValueError(f"{path}: scene {i} is missing field(s): {sorted(missing_scene_fields)}")
            local_image = s.get("local_image")
            if local_image:
                # Resolved relative to the script file itself, not the cwd
                # the pipeline happens to be run from, so a script and its
                # own asset folder stay portable together.
                local_image = (Path(path).resolve().parent / local_image).resolve()
                if not local_image.exists():
                    raise ValueError(f"{path}: scene {i}'s local_image {local_image} does not exist")
            scenes.append(Scene(text=s["text"], visual_query=s["visual_query"], local_image=local_image))
        return cls(
            id=data["id"],
            category=data["category"],
            title=data["title"],
            description=data["description"],
            tags=data["tags"],
            scenes=scenes,
            visual_mode=visual_mode,
            image_style_prompt=data.get("image_style_prompt", ""),
            thumbnail_highlight=data.get("thumbnail_highlight", ""),
            thumbnail_scene=thumbnail_scene,
            format=video_format,
            background_images=background_images,
        )
