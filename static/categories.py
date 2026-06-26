from pydantic import BaseModel


class AICategory(BaseModel):
    id: int
    title: str
    alias: str


TEXT = AICategory(
    id=0,
    title="текст",
    alias="text"
)

IMAGE = AICategory(
    id=1,
    title="изображение",
    alias="image"
)

VIDEO = AICategory(
    id=2,
    title="видео",
    alias="video"
)

cat_list = [TEXT, IMAGE, VIDEO]

cat_dict = {
    "text": TEXT,
    "image": IMAGE,
    "video": VIDEO
}
