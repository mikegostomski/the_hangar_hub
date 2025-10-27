from base.classes.auth.session import Log, Auth, EnvHelper, AppData
from base.services import message_service
from base.models.utility.error import Error
from base_upload.models.uploaded_file import UploadedFile
from base_upload.models.database_file import DatabaseFile
from django.conf import settings
import os
import magic
import tempfile
import base64
import io
import hashlib
from io import BytesIO
from PIL import Image, ExifTags
from django.core.files.base import ContentFile
from django.db import models
from pathlib import Path

log = Log()
env = EnvHelper()
app = AppData()


def using_file_system():
    # Store uploaded files in filesystem (as opposed to database storage)
    return True

def using_s3():
    if env.is_development:
        return False

    # Django <= 4.2
    yes = env.get_setting("DEFAULT_FILE_STORAGE") == "storages.backends.s3boto3.S3Boto3Storage"

    if not yes:
        # Django >= 4.2
        storages = env.get_setting("STORAGES")
        if storages and "default" in storages:
            yes = storages.get("default").get("BACKEND") == "storages.backends.s3boto3.S3Boto3Storage"

    return yes


def read_uploaded_files(request, input_name, byte_limit=500000, convert_to_string=True):
    """
    Return the contents of uploaded files without actually saving them anywhere
    Returns a dict with the file name as the key, and contents as the value
    """
    log.trace(request.FILES.items)

    # Read the files
    file_data = {}
    for ff in request.FILES.getlist(input_name):
        filename = ff.name
        file_data[filename] = _read_file_content(ff, byte_limit, convert_to_string)

    return file_data


def read_uploaded_file(request, input_name, byte_limit=500000, convert_to_string=True):
    """Return the contents of an uploaded file without actually saving it anywhere"""
    log.trace(request.FILES.items)
    return _read_file_content(request.FILES[input_name], byte_limit, convert_to_string)


def upload_files(
    request, input_name, sequenced_filename=None, parent_directory=None, tag=None, resize_dimensions=None
):
    """
    Action for saving one or more uploaded file
    Parameters:
        request - The Django request object
        input_name - The name of the file input in your HTML form
        sequenced_filename  - Gives all files the same name with a sequence number appended
                            - Retain original filename if not specified
        parent_directory - The directory (within your app directory) the files will live in on AWS/S3
        tag - Any string that will help find the file in DB queries
        resize_dimensions - i.e. "800x600" if you want to resize image files
    """
    log.trace(request.FILES.items)
    results = []

    # Only accept uploads from POST requests
    if request.method != "POST":
        message_service.post_error("Unable to upload files. Please resubmit the form.")
        return results

    # If using sequenced file names, look for the basename in the database and continue with any existing sequence
    filename_seq = 1
    if sequenced_filename:
        last_seq = 0
        try:
            app_code = app.get_app_code()
            if using_file_system():
                fs_path, fs_path_no_ext, fs_extension = build_fs_path(
                    "", parent_directory, sequenced_filename
                )
                existing_in_seq = UploadedFile.objects.filter(
                    app_code=app_code, fs_path__startswith=fs_path_no_ext
                )
            else:
                existing_in_seq = DatabaseFile.objects.filter(
                    app_code=app_code, basename__startswith=sequenced_filename
                )
                fs_path_no_ext = sequenced_filename

            if existing_in_seq:
                existing_seqs = []
                for ff in existing_in_seq:
                    no_ext, ext = os.path.splitext(ff.fs_path)
                    remainder = ff.fs_path.replace(fs_path_no_ext, "").replace(ext, "")
                    if remainder.isdigit():
                        existing_seqs.append(int(remainder))
                last_seq = max(existing_seqs) if existing_seqs else 0
        except Exception as ee:
            log.error(f"Error continuing on existing sequence: {str(ee)}")
            # S3 will append some garbage to make the name unique if needed
            last_seq = 0
        # Start with the next seq
        filename_seq = last_seq + 1

    # Upload the files
    for ff in request.FILES.getlist(input_name):
        log.info(f"Saving : {ff} ({type(ff)})")
        no_ext, dot_ext = os.path.splitext(ff.name)
        filename = f"{sequenced_filename}{filename_seq}{dot_ext}" if sequenced_filename else None
        saved_file = upload_file(ff, filename, parent_directory, tag=tag)
        if saved_file:
            results.append(saved_file)
            filename_seq += 1

    # Return the list of uploaded files
    return results


def upload_file(
    file_instance, specified_filename=None, parent_directory=None,
    tag=None, foreign_table=None, foreign_key=None,
    resize_dimensions=None
):
    """
    Action for saving ONE uploaded file
    Parameters:
        file_instance - The in-memory file to be saved (from request.FILES)
        specified_filename  - Rename the file (automatically retains the original extension)
                            - Retains the original filename if not specified
        parent_directory - The directory (within your app directory) the file will live in on AWS/S3
        tag - Any string that will help find the file in DB queries
        resize_dimensions - i.e. "800x600" if you want to resize image files
    """
    log.trace()
    original_file_name = "invalid"
    try:
        auth = Auth()
        # Only authenticated users may upload files
        if not auth.is_logged_in():
            if env.get_setting("ALLOW_UNAUTHENTICATED_UPLOADS"):
                pass
            else:
                message_service.post_error(
                    "Only authenticated users can upload documents."
                )
                return None

        # Only some types of files may be uploaded (specify in settings.py)
        if not file_is_valid(file_instance):
            # Error was already printed
            return None

        original_file_name = file_instance.name
        app_code = app.get_app_code()

        # Max file name is 128 characters
        if len(original_file_name) > 128:
            ext = os.path.splitext(original_file_name)
            token = hashlib.md5(original_file_name.encode('utf-8')).hexdigest()
            original_file_name = f"{original_file_name[:80]}-{token}{ext}"[:128]

        # Process file name and path data
        fs_path, fs_base_no_ext, fs_extension = build_fs_path(
            original_file_name, parent_directory, specified_filename
        )

        if using_file_system():
            # Upload to the proper path in S3...
            file_instance.name = fs_path
            file_instance.file_name = fs_path

            # Save the UploadedFile model, which also uploads to S3
            uf = UploadedFile()
            uf.app_code = app_code
            if auth.is_logged_in():
                uf.owner = auth.get_current_user_profile().username
            uf.content_type = file_instance.content_type
            uf.size = file_instance.size
            uf.file = file_instance
            uf.file.name = fs_path
            uf.fs_path = fs_path
            uf.basename = os.path.basename(fs_path)
            uf.original_name = original_file_name
            uf.tag = tag
            uf.foreign_table = foreign_table
            uf.foreign_key = foreign_key

            if resize_dimensions:
                resize_image(uf, resize_dimensions)

            uf.save()
            return uf

        else:
            uf = DatabaseFile()
            uf.app_code = app_code
            if auth.is_logged_in():
                uf.owner = auth.get_current_user_profile().username
            uf.content_type = file_instance.content_type
            uf.size = file_instance.size
            uf.file = _read_file_content(
                file_instance, 5000000, convert_to_string=False
            )
            uf.fs_path = fs_path
            uf.basename = os.path.basename(fs_path)
            uf.original_name = original_file_name
            uf.tag = tag
            uf.foreign_table = foreign_table
            uf.foreign_key = foreign_key

            if resize_dimensions:
                resize_image(uf, resize_dimensions)

            uf.save()
            return uf

    except Exception as ee:
        Error.unexpected(f"Error saving file: {original_file_name}", ee)
        return None


def build_fs_path(original_file_name, parent_directory, specified_filename):
    if "." in original_file_name:
        given_filename, given_extension = os.path.splitext(original_file_name)
    else:
        given_filename = original_file_name
        given_extension = ""

    # All file paths must start with the code of the app that they were uploaded for and the env
    app_code = app.get_app_code().lower()
    path_app = f"{app_code}/"
    path_env = f"{env.environment_code.lower()}/"

    # If a specified path already contained these, do not duplicate
    if parent_directory:
        if parent_directory.startswith(path_app):
            parent_directory = parent_directory.replace(path_app, "")
        if parent_directory and parent_directory.startswith(path_env):
            parent_directory = parent_directory.replace(path_env, "")

    if not parent_directory:
        file_path = os.path.join(path_app, path_env)
    else:
        file_path = os.path.join(path_app, path_env, parent_directory)

    # Add the specified or existing filename
    if specified_filename:
        # make sure the specified name gets only one extension
        if "." in specified_filename:
            spec_filename, spec_extension = os.path.splitext(specified_filename)
            if spec_extension == given_extension:
                specified_filename = spec_filename  # Extension will be added below
        file_path = os.path.join(
            file_path,
            f"{specified_filename}{given_extension.lower() if given_extension else ''}",
        )
    else:
        file_path = os.path.join(file_path, original_file_name)

    # Separate the name and extension to return as additional info
    resulting_path_ne, resulting_extension = os.path.splitext(file_path)

    # Ex: ('DEMO/foods/pie.jpg', 'pie', '.jpg')
    return file_path, resulting_path_ne, resulting_extension


mime_types = {
    ".aac": {"mime": "audio/aac", "description": "AAC audio"},
    ".abw": {"mime": "application/x-abiword", "description": "AbiWord document"},
    ".arc": {
        "mime": "application/x-freearc",
        "description": "Archive document (multiple files embedded)",
    },
    ".avi": {"mime": "video/x-msvideo", "description": "AVI: Audio Video Interleave"},
    ".azw": {
        "mime": "application/vnd.amazon.ebook",
        "description": "Amazon Kindle eBook format",
    },
    ".bin": {
        "mime": "application/octet-stream",
        "description": "Any kind of binary data",
    },
    ".bmp": {"mime": "image/bmp", "description": "Windows OS/2 Bitmap Graphics"},
    ".bz": {"mime": "application/x-bzip", "description": "BZip archive"},
    ".bz2": {"mime": "application/x-bzip2", "description": "BZip2 archive"},
    ".csh": {"mime": "application/x-csh", "description": "C-Shell script"},
    ".css": {"mime": "text/css", "description": "Cascading Style Sheets (CSS)"},
    ".csv": {"mime": "text/csv", "description": "Comma-separated values (CSV)"},
    ".doc": {"mime": "application/msword", "description": "Microsoft Word"},
    ".docx": {
        "mime": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "description": "Microsoft Word (OpenXML)",
    },
    ".eot": {
        "mime": "application/vnd.ms-fontobject",
        "description": "MS Embedded OpenType fonts",
    },
    ".epub": {
        "mime": "application/epub+zip",
        "description": "Electronic publication (EPUB)",
    },
    ".gz": {"mime": "application/gzip", "description": "GZip Compressed Archive"},
    ".gif": {"mime": "image/gif", "description": "Graphics Interchange Format (GIF)"},
    ".htm": {"mime": "text/html", "description": "HyperText Markup Language (HTML)"},
    ".html": {"mime": "text/html", "description": "HyperText Markup Language (HTML)"},
    ".ico": {"mime": "image/vnd.microsoft.icon", "description": "Icon format"},
    ".ics": {"mime": "text/calendar", "description": "iCalendar format"},
    ".jar": {"mime": "application/java-archive", "description": "Java Archive (JAR)"},
    ".jpeg": {"mime": "image/jpeg", "description": "JPEG images"},
    ".jpg": {"mime": "image/jpeg", "description": "JPEG images"},
    ".js": {"mime": "text/javascript", "description": "JavaScript"},
    ".json": {"mime": "application/json", "description": "JSON format"},
    ".jsonld": {"mime": "application/ld+json", "description": "JSON-LD format"},
    ".midi": {
        "mime": ["audio/midi", "audio/x-midi"],
        "description": "Musical Instrument Digital Interface (MIDI)",
    },
    ".mjs": {"mime": "text/javascript", "description": "JavaScript module"},
    ".mp3": {"mime": "audio/mpeg", "description": "MP3 audio"},
    ".mpeg": {"mime": "video/mpeg", "description": "MPEG Video"},
    ".mpkg": {
        "mime": "application/vnd.apple.installer+xml",
        "description": "Apple Installer Package",
    },
    ".odp": {
        "mime": "application/vnd.oasis.opendocument.presentation",
        "description": "OpenDocument presentation document",
    },
    ".ods": {
        "mime": "application/vnd.oasis.opendocument.spreadsheet",
        "description": "OpenDocument spreadsheet document",
    },
    ".odt": {
        "mime": "application/vnd.oasis.opendocument.text",
        "description": "OpenDocument text document",
    },
    ".oga": {"mime": "audio/ogg", "description": "OGG audio"},
    ".ogv": {"mime": "video/ogg", "description": "OGG video"},
    ".ogx": {"mime": "application/ogg", "description": "OGG"},
    ".opus": {"mime": "audio/opus", "description": "Opus audio"},
    ".otf": {"mime": "font/otf", "description": "OpenType font"},
    ".png": {"mime": "image/png", "description": "Portable Network Graphics"},
    ".pdf": {
        "mime": "application/pdf",
        "description": "Adobe Portable Document Format (PDF)",
    },
    ".php": {
        "mime": "application/php",
        "description": "Hypertext Preprocessor (Personal Home Page)",
    },
    ".ppt": {
        "mime": "application/vnd.ms-powerpoint",
        "description": "Microsoft PowerPoint",
    },
    ".pptx": {
        "mime": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "description": "Microsoft PowerPoint (OpenXML)",
    },
    ".rar": {"mime": "application/vnd.rar", "description": "RAR archive"},
    ".rtf": {"mime": "application/rtf", "description": "Rich Text Format (RTF)"},
    ".sh": {"mime": "application/x-sh", "description": "Bourne shell script"},
    ".svg": {"mime": "image/svg+xml", "description": "Scalable Vector Graphics (SVG)"},
    ".swf": {
        "mime": "application/x-shockwave-flash",
        "description": "Small web format (SWF) or Adobe Flash document",
    },
    ".tar": {"mime": "application/x-tar", "description": "Tape Archive (TAR)"},
    ".tiff": {"mime": "image/tiff", "description": "Tagged Image File Format (TIFF)"},
    ".ts": {"mime": "video/mp2t", "description": "MPEG transport stream"},
    ".ttf": {"mime": "font/ttf", "description": "TrueType Font"},
    ".txt": {
        "mime": "text/plain",
        "description": "Text, (generally ASCII or ISO 8859-n)",
    },
    ".vsd": {"mime": "application/vnd.visio", "description": "Microsoft Visio"},
    ".wav": {"mime": "audio/wav", "description": "Waveform Audio Format"},
    ".weba": {"mime": "audio/webm", "description": "WEBM audio"},
    ".webm": {"mime": "video/webm", "description": "WEBM video"},
    ".webp": {"mime": "image/webp", "description": "WEBP image"},
    ".woff": {"mime": "font/woff", "description": "Web Open Font Format (WOFF)"},
    ".woff2": {"mime": "font/woff2", "description": "Web Open Font Format (WOFF)"},
    ".xhtml": {"mime": "application/xhtml+xml", "description": "XHTML"},
    ".xls": {"mime": "application/vnd.ms-excel", "description": "Microsoft Excel"},
    ".xlsx": {
        "mime": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "description": "Microsoft Excel (OpenXML)",
    },
    ".xml": {"mime": ["application/xml", "text/xml"], "description": "XML"},
    ".xul": {"mime": "application/vnd.mozilla.xul+xml", "description": "XUL"},
    ".zip": {"mime": "application/zip", "description": "ZIP archive"},
    ".3gp": {
        "mime": ["video/3gpp", "audio/3gpp"],
        "description": "3GPP audio/video container",
    },
    ".3g2": {
        "mime": ["video/3gpp2", "audio/3gpp2"],
        "description": "3GPP2 audio/video container",
    },
    ".7z": {"mime": "application/x-7z-compressed", "description": "7-zip archive"},
}


def get_mimes_from_ext(ext):
    ext = f".{ext.lower().replace('.', '')}"
    if ext in mime_types:
        m = mime_types[ext]["mime"]
        return m if type(m) is list else [m]

    return []


def get_extensions_from_type(doc_type):
    doc_type = doc_type.lower()

    # Common image types. Others can be specified manually, if desired
    if doc_type in ("image", "img", "pic", "picture", "photo"):
        return ["jpg", "png", "gif", "tiff", "bmp"]

    # Common office-type documents
    if doc_type in (["office"]):
        return [
            "pdf",
            "doc",
            "docx",
            "odt",
            "xls",
            "xlsx",
            "ods",
            "ppt",
            "pptx",
            "odp",
            "txt",
            "jpg",
            "png",
            "csv",
        ]

    return []


def get_allowed_mime_types():
    allowed_types = []

    # Accept a list from settings
    if hasattr(settings, "ALLOWED_UPLOAD_TYPES"):
        for tt in settings.ALLOWED_UPLOAD_TYPES:
            # If an actual mime type was given
            if "/" in tt:
                allowed_types.append(tt)

            # Could be ext or human-readable type
            else:
                # See if it's an extension
                types = get_mimes_from_ext(tt)
                if types:
                    allowed_types.extend(types)

                # Maybe it's a human-readable type
                else:
                    for ext in get_extensions_from_type(tt):
                        allowed_types.extend(get_mimes_from_ext(ext))

    # If not specified, allow common office docs
    else:
        for ext in get_extensions_from_type("office"):
            allowed_types.extend(get_mimes_from_ext(ext))

    return list(set(allowed_types))


# Validate the type of file being uploaded
def file_is_valid(uploaded_file):
    # Do not check while file bytes are being imported from existing database
    if type(uploaded_file) is io.BytesIO:
        return True

    # Get MIME type from the file
    file_type = uploaded_file.content_type

    # If not allowed, return False
    is_valid_type = file_type in get_allowed_mime_types()
    if not is_valid_type:
        message_service.post_error("The file you uploaded is not an allowed file type.")
        log.warning(f"'{file_type}' is not an accepted type in this application")
        return False

    # Get a file type by reading the actual file contents
    magic_type = None
    try:

        # Rewind in case anything read it earlier
        uploaded_file.seek(0)
        head = uploaded_file.read(8192)
        uploaded_file.seek(0)

        magic_type = magic.from_buffer(head, mime=True)
    except Exception as ee:
        Error.record(ee)

    # Until the magic_type has been used a bit more, we're not blocking a file when magic fails
    # If it proves to work consistently, we'll start to require this
    if magic_type and magic_type != "inode/x-empty":
        if file_type != magic_type:
            # CSV files have had some inconsistent results
            csv_list = ["text/csv", "application/vnd.ms-excel", "text/plain", "application/csv"]
            # Same with OpenOffice docs saved as MS Office docs
            doc_list = [
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "application/msword",
            ]
            if file_type in csv_list and magic_type in csv_list:
                pass
            elif file_type in doc_list and magic_type in doc_list:
                pass
            else:
                # Give hints for some common mis-matches
                hint = None
                try:
                    if file_type.endswith(".png") and magic_type.endswith("jpeg"):
                        hint = "Try changing your .png file to a .jpg file"
                    elif (file_type.endswith(".jpg") or file_type.endswith(".jpeg")) and magic_type.endswith("png"):
                        hint = "Try changing your .jpg file to a .png file"
                except Exception as ee:
                    Error.record(ee)

                err_msg = f"The file extension does not match the file's content type: {uploaded_file.name}"
                if hint:
                    err_msg += f"<br><em>{hint}</em>"
                Error.unexpected(
                    err_msg,
                    f"{uploaded_file.name}: {file_type} != {magic_type}",
                )
                return False

    return is_valid_type


def _read_file_content(file_instance, byte_limit, convert_to_string):
    """Only to be called internally by the read_file and read_files functions"""
    # Only some types of files may be uploaded (specify in settings.py)
    if not file_is_valid(file_instance):
        # Error was already printed
        return None

    filename = file_instance.name
    file_size = file_instance.size

    try:
        if file_size > byte_limit:
            message_service.post_error(
                f"File size limit exceeded: {filename} ({file_size} bytes)"
            )
            return None

        log.info(f"Reading : {filename} ({file_size} bytes)")
        file_instance.seek(0)
        contents = file_instance.read()
        if convert_to_string:
            try:
                contents = contents.decode("utf-8")
            except Exception as ee:
                try:
                    # Try base64 encoding (images/etc)
                    contents = base64.b64encode(contents).decode()
                except:
                    message_service.post_error(
                        f"Unable to convert file to plain-text: {filename}"
                    )
                    log.debug(f"Conversion error: {ee}")

        return contents
    except Exception as ee:
        Error.unexpected(f"Unable to read uploaded file: {filename}", ee)
        return None


def resize_image(uploaded_file, wxh="800x600"):
    if "image" not in uploaded_file.content_type:
        return False

    try:
        img = Image.open(uploaded_file.file)
        img = img.convert("RGB")  # ensures no alpha channel

        # --- Handle EXIF orientation (for phone uploads) ---
        try:
            exif = img._getexif()
            if exif is not None:
                orientation_key = next(
                    (k for k, v in ExifTags.TAGS.items() if v == "Orientation"), None
                )
                if orientation_key and orientation_key in exif:
                    orientation = exif[orientation_key]
                    if orientation == 3:
                        img = img.rotate(180, expand=True)
                    elif orientation == 6:
                        img = img.rotate(270, expand=True)
                    elif orientation == 8:
                        img = img.rotate(90, expand=True)
        except Exception:
            pass  # EXIF data might not exist — skip silently

        # --- Center crop + resize to specified dimensions ---
        try:
            pieces = wxh.split("x")
            if len(pieces) != 2:
                Error.record(f"Invalid resize dimensions: {wxh}. Must be WIDTHxHEIGHT (ex '800x600')")
                pieces = [800, 600]
            else:
                pieces = [int(str(x)) for x in pieces]
        except Exception as ee:
            Error.record(ee, wxh)
            pieces = [800, 600]

        target_width, target_height = pieces[0], pieces[1]
        width, height = img.size
        aspect_ratio = target_width / target_height
        img_ratio = width / height

        if img_ratio > aspect_ratio:
            # Image too wide → crop sides
            new_width = int(height * aspect_ratio)
            offset = (width - new_width) // 2
            box = (offset, 0, offset + new_width, height)
        else:
            # Image too tall → crop top/bottom
            new_height = int(width / aspect_ratio)
            offset = (height - new_height) // 2
            box = (0, offset, width, offset + new_height)

        img = img.crop(box)
        img = img.resize((target_width, target_height), Image.LANCZOS)

        # --- Save cropped image back to same name ---
        buffer = BytesIO()
        img.save(buffer, format="JPEG", quality=90)
        file_name = os.path.basename(uploaded_file.file.name)
        uploaded_file.file.save(file_name, ContentFile(buffer.getvalue()), save=False)
        #uploaded_file.save(update_fields=["file"])
    except Exception as ee:
        Error.record(ee)