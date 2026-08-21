import json
import re
from dataclasses import dataclass
from pathlib import Path

# Script ids become tempdir prefixes and get embedded, unescaped, in ffmpeg
# concat-file paths (see assemble.concat_clips) -- keep them shell/ffmpeg-safe.
_ID_PATTERN = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


@dataclass
class Scene:
    text: str
    visual_query: str


@dataclass
class VideoScript:
    id: str
    category: str
    title: str
    description: str
    tags: list[str]
    scenes: list[Scene]

    @classmethod
    def load(cls, path: Path) -> "VideoScript":
        data = json.loads(Path(path).read_text())
        required = {"id", "category", "title", "description", "tags", "scenes"}
        missing = required - data.keys()
        if missing:
            raise ValueError(f"{path} is missing required field(s): {sorted(missing)}")
        if not _ID_PATTERN.match(data["id"]):
            raise ValueError(
                f"{path}: \"id\" must be lowercase letters/digits/hyphens only, got {data['id']!r}"
            )
        if not data["scenes"]:
            raise ValueError(f"{path} has an empty \"scenes\" list")
        scenes = []
        for i, s in enumerate(data["scenes"]):
            missing_scene_fields = {"text", "visual_query"} - s.keys()
            if missing_scene_fields:
                raise ValueError(f"{path}: scene {i} is missing field(s): {sorted(missing_scene_fields)}")
            scenes.append(Scene(text=s["text"], visual_query=s["visual_query"]))
        return cls(
            id=data["id"],
            category=data["category"],
            title=data["title"],
            description=data["description"],
            tags=data["tags"],
            scenes=scenes,
        )
