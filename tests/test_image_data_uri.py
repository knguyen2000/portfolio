import base64
import io

from PIL import Image

from utils.image_data import image_to_data_uri


def _make_png(path, size=(800, 600)):
    Image.new("RGBA", size, (10, 20, 30, 255)).save(path, format="PNG")


def test_returns_png_data_uri(tmp_path):
    p = tmp_path / "a.png"
    _make_png(p)
    uri = image_to_data_uri(str(p), max_width=250)
    assert uri.startswith("data:image/png;base64,")


def test_downscales_to_max_width(tmp_path):
    p = tmp_path / "a.png"
    _make_png(p)
    uri = image_to_data_uri(str(p), max_width=250)
    raw = base64.b64decode(uri.split(",", 1)[1])
    assert Image.open(io.BytesIO(raw)).width == 250


def test_does_not_upscale_small_images(tmp_path):
    p = tmp_path / "a.png"
    _make_png(p, size=(100, 100))
    uri = image_to_data_uri(str(p), max_width=250)
    raw = base64.b64decode(uri.split(",", 1)[1])
    assert Image.open(io.BytesIO(raw)).width == 100


def test_missing_file_returns_none(tmp_path):
    assert image_to_data_uri(str(tmp_path / "nope.png"), max_width=250) is None
