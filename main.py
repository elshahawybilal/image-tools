import io
import os
import re

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from PIL import Image, UnidentifiedImageError, features


app = FastAPI(
    title="Image Tools",
)


app.mount(
    "/static",
    StaticFiles(directory="static"),
    name="static",
)


templates = Jinja2Templates(
    directory="templates"
)


MAX_FILE_SIZE = 20 * 1024 * 1024


FORMAT_DETAILS = {
    "JPG": {
        "pillow_format": "JPEG",
        "extension": "jpg",
        "media_type": "image/jpeg",
    },
    "PNG": {
        "pillow_format": "PNG",
        "extension": "png",
        "media_type": "image/png",
    },
    "WEBP": {
        "pillow_format": "WEBP",
        "extension": "webp",
        "media_type": "image/webp",
    },
    "BMP": {
        "pillow_format": "BMP",
        "extension": "bmp",
        "media_type": "image/bmp",
    },
    "TIFF": {
        "pillow_format": "TIFF",
        "extension": "tiff",
        "media_type": "image/tiff",
    },
    "GIF": {
        "pillow_format": "GIF",
        "extension": "gif",
        "media_type": "image/gif",
    },
    "ICO": {
        "pillow_format": "ICO",
        "extension": "ico",
        "media_type": "image/x-icon",
    },
    "TGA": {
        "pillow_format": "TGA",
        "extension": "tga",
        "media_type": "image/x-tga",
    },
    "PPM": {
        "pillow_format": "PPM",
        "extension": "ppm",
        "media_type": "image/x-portable-pixmap",
    },
    "PGM": {
        "pillow_format": "PPM",
        "extension": "pgm",
        "media_type": "image/x-portable-graymap",
    },
    "PBM": {
        "pillow_format": "PPM",
        "extension": "pbm",
        "media_type": "image/x-portable-bitmap",
    },
    "JPEG 2000": {
        "pillow_format": "JPEG2000",
        "extension": "jp2",
        "media_type": "image/jp2",
    },
    "DDS": {
        "pillow_format": "DDS",
        "extension": "dds",
        "media_type": "image/vnd-ms.dds",
    },
}


FORMAT_ORDER = [
    "JPG",
    "PNG",
    "WEBP",
    "BMP",
    "TIFF",
    "GIF",
    "ICO",
    "TGA",
    "PPM",
    "PGM",
    "PBM",
    "JPEG 2000",
    "DDS",
]


def check_feature(feature_name):
    try:
        return bool(features.check(feature_name))
    except (ValueError, TypeError):
        return False


def is_format_available(format_name):
    details = FORMAT_DETAILS.get(format_name)

    if details is None:
        return False

    pillow_format = details["pillow_format"]

    if pillow_format == "WEBP":
        return check_feature("webp")

    if pillow_format == "JPEG2000":
        return check_feature("jpg_2000")

    Image.init()

    return (
        pillow_format in Image.SAVE
        or pillow_format in Image.SAVE_ALL
    )


def get_available_formats():
    return [
        format_name
        for format_name in FORMAT_ORDER
        if is_format_available(format_name)
    ]


def add_white_background(image):
    rgba_image = image.convert("RGBA")

    background = Image.new(
        "RGB",
        rgba_image.size,
        "white",
    )

    background.paste(
        rgba_image,
        mask=rgba_image.getchannel("A"),
    )

    rgba_image.close()

    return background


def prepare_image(
    image,
    target_format,
):
    if target_format in {
        "JPG",
        "BMP",
    }:
        if (
            image.mode in ("RGBA", "LA")
            or (
                image.mode == "P"
                and "transparency" in image.info
            )
        ):
            return add_white_background(image)

        return image.convert("RGB")

    if target_format == "PBM":
        return image.convert("1")

    if target_format == "PGM":
        return image.convert("L")

    if target_format == "PPM":
        return image.convert("RGB")

    if target_format == "GIF":
        if image.mode in ("P", "L"):
            return image.copy()

        return (
            image.convert("RGBA")
            .convert(
                "P",
                palette=Image.Palette.ADAPTIVE,
            )
        )

    if target_format == "PNG":
        if image.mode in {
            "1",
            "L",
            "LA",
            "P",
            "RGB",
            "RGBA",
        }:
            return image.copy()

        if "A" in image.getbands():
            return image.convert("RGBA")

        return image.convert("RGB")

    if target_format == "TIFF":
        if image.mode in {
            "1",
            "L",
            "LA",
            "P",
            "RGB",
            "RGBA",
        }:
            return image.copy()

        if "A" in image.getbands():
            return image.convert("RGBA")

        return image.convert("RGB")

    if target_format in {
        "WEBP",
        "ICO",
        "TGA",
        "JPEG 2000",
        "DDS",
    }:
        if image.mode in (
            "RGB",
            "RGBA",
        ):
            return image.copy()

        if "A" in image.getbands():
            return image.convert("RGBA")

        return image.convert("RGB")

    return image.copy()


def get_save_options(
    target_format,
):
    if target_format == "JPG":
        return {
            "quality": 95,
            "optimize": True,
            "progressive": True,
        }

    if target_format == "PNG":
        return {
            "optimize": True,
            "compress_level": 6,
        }

    if target_format == "WEBP":
        return {
            "quality": 95,
            "method": 6,
        }

    if target_format == "TIFF":
        return {
            "compression": "tiff_deflate",
        }

    if target_format == "GIF":
        return {
            "optimize": True,
        }

    return {}


def clean_file_name(file_name):
    file_name = os.path.basename(
        file_name or "image"
    )

    name_without_extension = os.path.splitext(
        file_name
    )[0]

    cleaned_name = re.sub(
        r"[^A-Za-z0-9_-]+",
        "_",
        name_without_extension,
    )

    cleaned_name = cleaned_name.strip("_")

    if not cleaned_name:
        cleaned_name = "image"

    return cleaned_name[:80]


def converter_template(
    request,
    error_message=None,
):
    return templates.TemplateResponse(
        request=request,
        name="converter.html",
        context={
            "page_title": "Image Converter",
            "formats": get_available_formats(),
            "error_message": error_message,
        },
    )


def resize_template(
    request,
    error_message=None,
):
    return templates.TemplateResponse(
        request=request,
        name="resize.html",
        context={
            "page_title": "Image Resizer",
            "error_message": error_message,
        },
    )


@app.get(
    "/sitemap.xml",
    include_in_schema=False,
)
def sitemap():
    sitemap_content = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <url>
        <loc>https://imagekitbox.com/</loc>
    </url>
    <url>
        <loc>https://imagekitbox.com/converter</loc>
    </url>
    <url>
        <loc>https://imagekitbox.com/resize</loc>
    </url>
    <url>
        <loc>https://imagekitbox.com/about</loc>
    </url>
    <url>
        <loc>https://imagekitbox.com/privacy</loc>
    </url>
    <url>
        <loc>https://imagekitbox.com/terms</loc>
    </url>
    <url>
        <loc>https://imagekitbox.com/contact</loc>
    </url>
</urlset>
"""

    return Response(
        content=sitemap_content,
        media_type="application/xml",
    )


@app.get(
    "/robots.txt",
    include_in_schema=False,
)
def robots():
    robots_content = """User-agent: *
Allow: /

Sitemap: https://imagekitbox.com/sitemap.xml
"""

    return Response(
        content=robots_content,
        media_type="text/plain",
    )


@app.get(
    "/",
    response_class=HTMLResponse,
)
def home(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "page_title": "Image Tools",
        },
    )


@app.get(
    "/about",
    response_class=HTMLResponse,
)
def about_page(
    request: Request,
):
    return templates.TemplateResponse(
        request=request,
        name="about.html",
        context={
            "page_title": "About Image Tools",
        },
    )


@app.get(
    "/privacy",
    response_class=HTMLResponse,
)
def privacy_page(
    request: Request,
):
    return templates.TemplateResponse(
        request=request,
        name="privacy.html",
        context={
            "page_title": "Privacy Policy",
        },
    )


@app.get(
    "/terms",
    response_class=HTMLResponse,
)
def terms_page(
    request: Request,
):
    return templates.TemplateResponse(
        request=request,
        name="terms.html",
        context={
            "page_title": "Terms of Use",
        },
    )


@app.get(
    "/contact",
    response_class=HTMLResponse,
)
def contact_page(
    request: Request,
):
    return templates.TemplateResponse(
        request=request,
        name="contact.html",
        context={
            "page_title": "Contact",
        },
    )


@app.get(
    "/converter",
    response_class=HTMLResponse,
)
def converter_page(
    request: Request,
):
    return converter_template(
        request=request
    )


@app.get(
    "/resize",
    response_class=HTMLResponse,
)
def resize_page(
    request: Request,
):
    return resize_template(
        request=request
    )


@app.post(
    "/convert",
    response_class=HTMLResponse,
)
async def convert_image(
    request: Request,
    image: UploadFile = File(...),
    target_format: str = Form(...),
):
    target_format = (
        target_format.strip().upper()
    )

    if target_format not in FORMAT_DETAILS:
        return converter_template(
            request=request,
            error_message=(
                "The selected output format "
                "is not supported."
            ),
        )

    if not is_format_available(
        target_format
    ):
        return converter_template(
            request=request,
            error_message=(
                f"{target_format} is not "
                "available on this server."
            ),
        )

    file_data = await image.read(
        MAX_FILE_SIZE + 1
    )

    if not file_data:
        return converter_template(
            request=request,
            error_message=(
                "Please choose an image."
            ),
        )

    if len(file_data) > MAX_FILE_SIZE:
        return converter_template(
            request=request,
            error_message=(
                "The image is too large. "
                "Maximum file size is 20 MB."
            ),
        )

    format_details = FORMAT_DETAILS[
        target_format
    ]

    output_buffer = io.BytesIO()

    try:
        with Image.open(
            io.BytesIO(file_data)
        ) as source_image:
            source_image.verify()

        with Image.open(
            io.BytesIO(file_data)
        ) as source_image:
            source_image.seek(0)
            source_image.load()

            converted_image = prepare_image(
                source_image,
                target_format,
            )

            try:
                converted_image.save(
                    output_buffer,
                    format=format_details[
                        "pillow_format"
                    ],
                    **get_save_options(
                        target_format
                    ),
                )

            finally:
                converted_image.close()

    except UnidentifiedImageError:
        output_buffer.close()

        return converter_template(
            request=request,
            error_message=(
                "The selected file is not "
                "a valid image."
            ),
        )

    except Exception:
        output_buffer.close()

        return converter_template(
            request=request,
            error_message=(
                "The image could not be converted. "
                "Please try another image or format."
            ),
        )

    output_buffer.seek(0)

    safe_name = clean_file_name(
        image.filename
    )

    download_name = (
        f"{safe_name}."
        f"{format_details['extension']}"
    )

    headers = {
        "Content-Disposition": (
            "attachment; "
            f'filename="{download_name}"'
        )
    }

    return StreamingResponse(
        output_buffer,
        media_type=format_details[
            "media_type"
        ],
        headers=headers,
    )


@app.post(
    "/resize",
    response_class=HTMLResponse,
)
async def resize_image(
    request: Request,
    image: UploadFile = File(...),
    width: int = Form(...),
    height: int = Form(...),
):
    if width <= 0 or height <= 0:
        return resize_template(
            request=request,
            error_message=(
                "Width and height must "
                "be greater than zero."
            ),
        )

    if width > 10000 or height > 10000:
        return resize_template(
            request=request,
            error_message=(
                "Maximum width and height "
                "are 10000 pixels."
            ),
        )

    file_data = await image.read(
        MAX_FILE_SIZE + 1
    )

    if not file_data:
        return resize_template(
            request=request,
            error_message=(
                "Please choose an image."
            ),
        )

    if len(file_data) > MAX_FILE_SIZE:
        return resize_template(
            request=request,
            error_message=(
                "The image is too large. "
                "Maximum file size is 20 MB."
            ),
        )

    output_buffer = io.BytesIO()

    try:
        with Image.open(
            io.BytesIO(file_data)
        ) as source_image:
            source_image.verify()

        with Image.open(
            io.BytesIO(file_data)
        ) as source_image:
            source_image.load()

            original_format = (
                source_image.format or "PNG"
            )

            resized_image = source_image.resize(
                (width, height),
                Image.Resampling.LANCZOS,
            )

            if original_format == "JPEG":
                final_image = prepare_image(
                    resized_image,
                    "JPG",
                )

                extension = "jpg"
                media_type = "image/jpeg"
                save_format = "JPEG"
                save_options = get_save_options(
                    "JPG"
                )

            elif original_format == "WEBP":
                final_image = prepare_image(
                    resized_image,
                    "WEBP",
                )

                extension = "webp"
                media_type = "image/webp"
                save_format = "WEBP"
                save_options = get_save_options(
                    "WEBP"
                )

            else:
                final_image = prepare_image(
                    resized_image,
                    "PNG",
                )

                extension = "png"
                media_type = "image/png"
                save_format = "PNG"
                save_options = get_save_options(
                    "PNG"
                )

            try:
                final_image.save(
                    output_buffer,
                    format=save_format,
                    **save_options,
                )

            finally:
                final_image.close()
                resized_image.close()

    except UnidentifiedImageError:
        output_buffer.close()

        return resize_template(
            request=request,
            error_message=(
                "The selected file is not "
                "a valid image."
            ),
        )

    except Exception:
        output_buffer.close()

        return resize_template(
            request=request,
            error_message=(
                "The image could not be resized."
            ),
        )

    output_buffer.seek(0)

    safe_name = clean_file_name(
        image.filename
    )

    download_name = (
        f"{safe_name}_resized."
        f"{extension}"
    )

    headers = {
        "Content-Disposition": (
            "attachment; "
            f'filename="{download_name}"'
        )
    }

    return StreamingResponse(
        output_buffer,
        media_type=media_type,
        headers=headers,
    )