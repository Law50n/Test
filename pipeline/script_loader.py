import json
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Scene:
    text: str
    visual_query: str


@dataclass
class VideoScript:
    id: str
    title: str
    description: str
    tags: list[str]
    scenes: list[Scene]

    @classmethod
    def load(cls, path: Path) -> "VideoScript":
        data = json.loads(Path(path).read_text())
        required = {"id", "title", "description", "tags", "scenes"}
        missing = required - data.keys()
        if missing:
            raise ValueError(f"{path} is missing required field(s): {sorted(missing)}")
        return cls(
            id=data["id"],
            title=data["title"],
            description=data["description"],
            tags=data["tags"],
            scenes=[Scene(text=s["text"], visual_query=s["visual_query"]) for s in data["scenes"]],
        )
