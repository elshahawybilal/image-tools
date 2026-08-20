import io
import os
import re

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from PIL import Image, ImageDraw, ImageFont, UnidentifiedImageError, features


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



def cropper_template(
    request,
    error_message=None,
):
    return templates.TemplateResponse(
        request=request,
        name="cropper.html",
        context={"page_title": "Image Cropper", "error_message": error_message},
    )


def compressor_template(
    request,
    error_message=None,
):
    return templates.TemplateResponse(
        request=request,
        name="compressor.html",
        context={
            "page_title": "Image Compressor",
            "error_message": error_message,
        },
    )


def rotate_flip_template(request, error_message=None):
    return templates.TemplateResponse(
        request=request,
        name="rotate-flip.html",
        context={"page_title": "Rotate & Flip Image", "error_message": error_message},
    )


def watermark_template(
    request,
    error_message=None,
):
    return templates.TemplateResponse(
        request=request,
        name="watermark.html",
        context={
            "page_title": "Image Watermark",
            "error_message": error_message,
        },
    )


def get_compression_details(original_format):
    if original_format == "JPEG":
        return {
            "target_format": "JPG",
            "extension": "jpg",
            "media_type": "image/jpeg",
            "save_format": "JPEG",
        }

    if original_format == "PNG":
        return {
            "target_format": "PNG",
            "extension": "png",
            "media_type": "image/png",
            "save_format": "PNG",
        }

    if original_format == "WEBP":
        return {
            "target_format": "WEBP",
            "extension": "webp",
            "media_type": "image/webp",
            "save_format": "WEBP",
        }

    return None


def get_compression_save_options(
    original_format,
    quality,
):
    if original_format == "JPEG":
        return {
            "quality": quality,
            "optimize": True,
            "progressive": True,
        }

    if original_format == "WEBP":
        return {
            "quality": quality,
            "method": 6,
        }

    if original_format == "PNG":
        return {
            "optimize": True,
            "compress_level": 9,
        }

    return {}


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
        <loc>https://imagekitbox.com/compressor</loc>
    </url>
    <url>
        <loc>https://imagekitbox.com/cropper</loc>
    </url>
    <url>
        <loc>https://imagekitbox.com/rotate-flip</loc>
    </url>
    <url>
        <loc>https://imagekitbox.com/watermark</loc>
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



@app.get(
    "/cropper",
    response_class=HTMLResponse,
)
def cropper_page(request: Request):
    return cropper_template(request=request)


@app.get(
    "/rotate-flip",
    response_class=HTMLResponse,
)
def rotate_flip_page(request: Request):
    return rotate_flip_template(request=request)


@app.get(
    "/watermark",
    response_class=HTMLResponse,
)
def watermark_page(
    request: Request,
):
    return watermark_template(
        request=request
    )


@app.get(
    "/compressor",
    response_class=HTMLResponse,
)
def compressor_page(
    request: Request,
):
    return compressor_template(
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


@app.post(
    "/compress",
    response_class=HTMLResponse,
)
async def compress_image(
    request: Request,
    image: UploadFile = File(...),
    quality: int = Form(80),
):
    if quality < 10 or quality > 95:
        return compressor_template(
            request=request,
            error_message=(
                "Quality must be between "
                "10 and 95."
            ),
        )

    file_data = await image.read(
        MAX_FILE_SIZE + 1
    )

    if not file_data:
        return compressor_template(
            request=request,
            error_message=(
                "Please choose an image."
            ),
        )

    if len(file_data) > MAX_FILE_SIZE:
        return compressor_template(
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
            source_image.seek(0)
            source_image.load()

            original_format = (
                source_image.format or ""
            ).upper()

            compression_details = (
                get_compression_details(
                    original_format
                )
            )

            if compression_details is None:
                output_buffer.close()

                return compressor_template(
                    request=request,
                    error_message=(
                        "Image Compressor currently "
                        "supports JPG, PNG and WEBP "
                        "images."
                    ),
                )

            compressed_image = prepare_image(
                source_image,
                compression_details[
                    "target_format"
                ],
            )

            try:
                compressed_image.save(
                    output_buffer,
                    format=compression_details[
                        "save_format"
                    ],
                    **get_compression_save_options(
                        original_format,
                        quality,
                    ),
                )

            finally:
                compressed_image.close()

    except UnidentifiedImageError:
        output_buffer.close()

        return compressor_template(
            request=request,
            error_message=(
                "The selected file is not "
                "a valid image."
            ),
        )

    except Exception:
        output_buffer.close()

        return compressor_template(
            request=request,
            error_message=(
                "The image could not be compressed. "
                "Please try another image."
            ),
        )

    compressed_size = output_buffer.tell()
    original_size = len(file_data)

    if original_size > 0:
        saved_percent = max(
            0.0,
            (
                (original_size - compressed_size)
                / original_size
            ) * 100,
        )
    else:
        saved_percent = 0.0

    output_buffer.seek(0)

    safe_name = clean_file_name(
        image.filename
    )

    download_name = (
        f"{safe_name}_compressed."
        f"{compression_details['extension']}"
    )

    headers = {
        "Content-Disposition": (
            "attachment; "
            f'filename="{download_name}"'
        ),
        "X-Original-Size": str(
            original_size
        ),
        "X-Compressed-Size": str(
            compressed_size
        ),
        "X-Saved-Percent": (
            f"{saved_percent:.2f}"
        ),
    }

    return StreamingResponse(
        output_buffer,
        media_type=compression_details[
            "media_type"
        ],
        headers=headers,
    )


@app.post(
    "/crop",
    response_class=HTMLResponse,
)
async def crop_image(
    request: Request,
    image: UploadFile = File(...),
    x: int = Form(...),
    y: int = Form(...),
    width: int = Form(...),
    height: int = Form(...),
):
    if x < 0 or y < 0 or width <= 0 or height <= 0:
        return cropper_template(
            request=request,
            error_message="Please select a valid crop area.",
        )

    file_data = await image.read(MAX_FILE_SIZE + 1)

    if not file_data:
        return cropper_template(request=request, error_message="Please choose an image.")

    if len(file_data) > MAX_FILE_SIZE:
        return cropper_template(
            request=request,
            error_message="The image is too large. Maximum file size is 20 MB.",
        )

    output_buffer = io.BytesIO()

    try:
        with Image.open(io.BytesIO(file_data)) as source_image:
            source_image.verify()

        with Image.open(io.BytesIO(file_data)) as source_image:
            source_image.seek(0)
            source_image.load()
            image_width, image_height = source_image.size
            right, bottom = x + width, y + height

            if x >= image_width or y >= image_height or right > image_width or bottom > image_height:
                output_buffer.close()
                return cropper_template(
                    request=request,
                    error_message="The selected crop area is outside the image.",
                )

            original_format = (source_image.format or "PNG").upper()
            cropped_image = source_image.crop((x, y, right, bottom))

            if original_format == "JPEG":
                final_image = prepare_image(cropped_image, "JPG")
                extension, media_type, save_format = "jpg", "image/jpeg", "JPEG"
                save_options = get_save_options("JPG")
            elif original_format == "WEBP":
                final_image = prepare_image(cropped_image, "WEBP")
                extension, media_type, save_format = "webp", "image/webp", "WEBP"
                save_options = get_save_options("WEBP")
            else:
                final_image = prepare_image(cropped_image, "PNG")
                extension, media_type, save_format = "png", "image/png", "PNG"
                save_options = get_save_options("PNG")

            try:
                final_image.save(output_buffer, format=save_format, **save_options)
            finally:
                final_image.close()
                cropped_image.close()

    except UnidentifiedImageError:
        output_buffer.close()
        return cropper_template(
            request=request,
            error_message="The selected file is not a valid image.",
        )
    except Exception:
        output_buffer.close()
        return cropper_template(
            request=request,
            error_message="The image could not be cropped. Please try another image.",
        )

    output_buffer.seek(0)
    safe_name = clean_file_name(image.filename)
    download_name = f"{safe_name}_cropped.{extension}"

    return StreamingResponse(
        output_buffer,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{download_name}"'},
    )

@app.post(
    "/rotate-flip",
    response_class=HTMLResponse,
)
async def rotate_flip_image(
    request: Request,
    image: UploadFile = File(...),
    action: str = Form(...),
):
    actions = {
        "rotate_90": ("rotated_90", Image.Transpose.ROTATE_270),
        "rotate_180": ("rotated_180", Image.Transpose.ROTATE_180),
        "rotate_270": ("rotated_270", Image.Transpose.ROTATE_90),
        "flip_horizontal": ("flipped_horizontal", Image.Transpose.FLIP_LEFT_RIGHT),
        "flip_vertical": ("flipped_vertical", Image.Transpose.FLIP_TOP_BOTTOM),
    }

    if action not in actions:
        return rotate_flip_template(
            request=request,
            error_message="Please choose a valid rotate or flip option.",
        )

    file_data = await image.read(MAX_FILE_SIZE + 1)

    if not file_data:
        return rotate_flip_template(request=request, error_message="Please choose an image.")

    if len(file_data) > MAX_FILE_SIZE:
        return rotate_flip_template(
            request=request,
            error_message="The image is too large. Maximum file size is 20 MB.",
        )

    output_buffer = io.BytesIO()

    try:
        with Image.open(io.BytesIO(file_data)) as source_image:
            source_image.verify()

        with Image.open(io.BytesIO(file_data)) as source_image:
            source_image.seek(0)
            source_image.load()

            original_format = (source_image.format or "PNG").upper()
            suffix, method = actions[action]
            transformed_image = source_image.transpose(method)

            if original_format == "JPEG":
                final_image = prepare_image(transformed_image, "JPG")
                extension, media_type, save_format = "jpg", "image/jpeg", "JPEG"
                save_options = get_save_options("JPG")
            elif original_format == "WEBP":
                final_image = prepare_image(transformed_image, "WEBP")
                extension, media_type, save_format = "webp", "image/webp", "WEBP"
                save_options = get_save_options("WEBP")
            else:
                final_image = prepare_image(transformed_image, "PNG")
                extension, media_type, save_format = "png", "image/png", "PNG"
                save_options = get_save_options("PNG")

            try:
                final_image.save(output_buffer, format=save_format, **save_options)
            finally:
                final_image.close()
                transformed_image.close()

    except UnidentifiedImageError:
        output_buffer.close()
        return rotate_flip_template(
            request=request,
            error_message="The selected file is not a valid image.",
        )
    except Exception:
        output_buffer.close()
        return rotate_flip_template(
            request=request,
            error_message="The image could not be rotated or flipped. Please try another image.",
        )

    output_buffer.seek(0)
    safe_name = clean_file_name(image.filename)
    download_name = f"{safe_name}_{suffix}.{extension}"

    return StreamingResponse(
        output_buffer,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{download_name}"'},
    )

def load_watermark_font(font_size):
    font_paths = [
        "arial.ttf",
        "Arial.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]

    for font_path in font_paths:
        try:
            return ImageFont.truetype(
                font_path,
                font_size,
            )
        except Exception:
            continue

    return ImageFont.load_default()


def parse_hex_color(hex_color):
    if not re.fullmatch(
        r"#[0-9A-Fa-f]{6}",
        hex_color or "",
    ):
        hex_color = "#ffffff"

    return (
        int(hex_color[1:3], 16),
        int(hex_color[3:5], 16),
        int(hex_color[5:7], 16),
    )


def create_text_watermark_layer(
    text,
    font,
    fill_color,
    stroke_width,
    stroke_fill,
    rotation,
):
    test_image = Image.new(
        "RGBA",
        (10, 10),
        (0, 0, 0, 0),
    )
    test_draw = ImageDraw.Draw(test_image)

    bbox = test_draw.textbbox(
        (0, 0),
        text,
        font=font,
        stroke_width=stroke_width,
    )

    text_width = max(
        1,
        bbox[2] - bbox[0],
    )
    text_height = max(
        1,
        bbox[3] - bbox[1],
    )

    padding = max(
        10,
        text_height // 2,
    )

    layer = Image.new(
        "RGBA",
        (
            text_width + padding * 2,
            text_height + padding * 2,
        ),
        (0, 0, 0, 0),
    )

    draw = ImageDraw.Draw(layer)

    draw.text(
        (
            padding - bbox[0],
            padding - bbox[1],
        ),
        text,
        font=font,
        fill=fill_color,
        stroke_width=stroke_width,
        stroke_fill=stroke_fill,
    )

    test_image.close()

    if rotation != 0:
        rotated_layer = layer.rotate(
            rotation,
            expand=True,
            resample=Image.Resampling.BICUBIC,
        )

        layer.close()
        return rotated_layer

    return layer


def add_single_watermark(
    image,
    watermark_layer,
    position,
):
    image_width, image_height = image.size
    mark_width, mark_height = watermark_layer.size

    margin = max(
        10,
        int(
            min(
                image_width,
                image_height,
            ) * 0.03
        ),
    )

    if position == "top_left":
        x = margin
        y = margin

    elif position == "top_right":
        x = (
            image_width
            - mark_width
            - margin
        )
        y = margin

    elif position == "center":
        x = (
            image_width
            - mark_width
        ) // 2
        y = (
            image_height
            - mark_height
        ) // 2

    elif position == "bottom_left":
        x = margin
        y = (
            image_height
            - mark_height
            - margin
        )

    else:
        x = (
            image_width
            - mark_width
            - margin
        )
        y = (
            image_height
            - mark_height
            - margin
        )

    image.alpha_composite(
        watermark_layer,
        (
            max(0, x),
            max(0, y),
        ),
    )


def add_repeated_watermark(
    image,
    watermark_layer,
):
    image_width, image_height = image.size
    mark_width, mark_height = watermark_layer.size

    horizontal_gap = max(
        30,
        mark_width // 2,
    )

    vertical_gap = max(
        30,
        mark_height,
    )

    step_x = mark_width + horizontal_gap
    step_y = mark_height + vertical_gap

    y = -(mark_height // 2)
    row_number = 0

    while y < image_height:
        x = -(mark_width // 2)

        if row_number % 2:
            x -= step_x // 2

        while x < image_width:
            image.alpha_composite(
                watermark_layer,
                (x, y),
            )

            x += step_x

        y += step_y
        row_number += 1


@app.post(
    "/watermark",
    response_class=HTMLResponse,
)
async def add_watermark(
    request: Request,
    image: UploadFile = File(...),
    watermark_text: str = Form(...),
    position: str = Form("bottom_right"),
    opacity: int = Form(60),
    font_size: int = Form(8),
    text_color: str = Form("#ffffff"),
    outline: str | None = Form(None),
    rotation: int = Form(0),
    repeat_watermark: str | None = Form(None),
):
    watermark_text = watermark_text.strip()

    if not watermark_text:
        return watermark_template(
            request=request,
            error_message=(
                "Please enter watermark text."
            ),
        )

    if len(watermark_text) > 100:
        return watermark_template(
            request=request,
            error_message=(
                "Watermark text must be "
                "100 characters or less."
            ),
        )

    valid_positions = {
        "top_left",
        "top_right",
        "center",
        "bottom_left",
        "bottom_right",
    }

    if position not in valid_positions:
        return watermark_template(
            request=request,
            error_message=(
                "Please choose a valid "
                "watermark position."
            ),
        )

    if not 10 <= opacity <= 100:
        return watermark_template(
            request=request,
            error_message=(
                "Opacity must be between "
                "10 and 100."
            ),
        )

    if not 2 <= font_size <= 30:
        return watermark_template(
            request=request,
            error_message=(
                "Font size must be between "
                "2 and 30."
            ),
        )

    if rotation not in {
        -45,
        0,
        45,
    }:
        return watermark_template(
            request=request,
            error_message=(
                "Please choose a valid rotation."
            ),
        )

    file_data = await image.read(
        MAX_FILE_SIZE + 1
    )

    if not file_data:
        return watermark_template(
            request=request,
            error_message=(
                "Please choose an image."
            ),
        )

    if len(file_data) > MAX_FILE_SIZE:
        return watermark_template(
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
            source_image.seek(0)
            source_image.load()

            original_format = (
                source_image.format or "PNG"
            ).upper()

            working_image = source_image.convert(
                "RGBA"
            )

            image_width, image_height = (
                working_image.size
            )

            actual_font_size = max(
                12,
                int(
                    min(
                        image_width,
                        image_height,
                    )
                    * (
                        font_size / 100
                    )
                ),
            )

            font = load_watermark_font(
                actual_font_size
            )

            red, green, blue = (
                parse_hex_color(
                    text_color
                )
            )

            alpha = int(
                255
                * (
                    opacity / 100
                )
            )

            fill_color = (
                red,
                green,
                blue,
                alpha,
            )

            outline_enabled = (
                outline == "on"
            )

            repeat_enabled = (
                repeat_watermark == "on"
            )

            if outline_enabled:
                stroke_width = max(
                    1,
                    actual_font_size // 20,
                )

                stroke_fill = (
                    0,
                    0,
                    0,
                    alpha,
                )

            else:
                stroke_width = 0
                stroke_fill = None

            watermark_layer = (
                create_text_watermark_layer(
                    watermark_text,
                    font,
                    fill_color,
                    stroke_width,
                    stroke_fill,
                    rotation,
                )
            )

            try:
                if repeat_enabled:
                    add_repeated_watermark(
                        working_image,
                        watermark_layer,
                    )

                else:
                    add_single_watermark(
                        working_image,
                        watermark_layer,
                        position,
                    )

            finally:
                watermark_layer.close()

            if original_format == "JPEG":
                final_image = (
                    add_white_background(
                        working_image
                    )
                )

                extension = "jpg"
                media_type = "image/jpeg"
                save_format = "JPEG"
                save_options = (
                    get_save_options(
                        "JPG"
                    )
                )

            elif original_format == "WEBP":
                final_image = prepare_image(
                    working_image,
                    "WEBP",
                )

                extension = "webp"
                media_type = "image/webp"
                save_format = "WEBP"
                save_options = (
                    get_save_options(
                        "WEBP"
                    )
                )

            else:
                final_image = prepare_image(
                    working_image,
                    "PNG",
                )

                extension = "png"
                media_type = "image/png"
                save_format = "PNG"
                save_options = (
                    get_save_options(
                        "PNG"
                    )
                )

            try:
                final_image.save(
                    output_buffer,
                    format=save_format,
                    **save_options,
                )

            finally:
                final_image.close()
                working_image.close()

    except UnidentifiedImageError:
        output_buffer.close()

        return watermark_template(
            request=request,
            error_message=(
                "The selected file is "
                "not a valid image."
            ),
        )

    except Exception:
        output_buffer.close()

        return watermark_template(
            request=request,
            error_message=(
                "The watermark could not "
                "be added. Please try "
                "another image."
            ),
        )

    output_buffer.seek(0)

    safe_name = clean_file_name(
        image.filename
    )

    download_name = (
        f"{safe_name}_watermarked."
        f"{extension}"
    )

    return StreamingResponse(
        output_buffer,
        media_type=media_type,
        headers={
            "Content-Disposition": (
                "attachment; "
                f'filename="{download_name}"'
            )
        },
    )
