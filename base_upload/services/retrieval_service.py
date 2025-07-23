from base_upload.models.uploaded_file import UploadedFile
from base_upload.models.database_file import DatabaseFile
from base_upload.services import upload_service
from base.classes.auth.session import Auth, Log, AppData

log = Log()

# Base queries that can have further filtering applied to them by the calling app


def get_file_query():
    if upload_service.using_s3():
        return UploadedFile.objects
    else:
        return DatabaseFile.objects


def get_all_files():
    app_code = AppData().get_app_code()
    if upload_service.using_s3():
        return get_file_query().filter(app_code=app_code).exclude(status="D")
    else:
        return get_file_query().filter(app_code=app_code).exclude(status="D")


def get_user_files(username=None):
    auth = Auth()
    if auth.is_logged_in() and not username:
        username = auth.get_current_user_profile().username

    return get_all_files().filter(owner=username)
