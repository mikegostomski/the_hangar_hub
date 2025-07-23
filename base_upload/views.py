from django.http import HttpResponse, Http404, HttpResponseForbidden
from base.classes.util.env_helper import Log, EnvHelper
from base.classes.auth.session import Auth
from base_upload.services import retrieval_service
from base_upload.models.database_file import DatabaseFile


log = Log()
env = EnvHelper()

# ToDo: Error Handling/Messages


def linked_file(request, file_id):
    """
    Retrieve a specified file and display as attachment.

    Security:
    This will only display files belonging to the authenticated owner, or files
    whose ID is saved in the session.  This prevents a user from changing the
    URL to display any file in the database.

    File IDs are automatically added to the session by the {%file_preview%} tag.
    Each app must verify permissions before displaying a file preview to a user.

    Authenticated users can always use this to view their own files
    """
    log.trace()

    # Retrieve the file
    file_instance = retrieval_service.get_file_query().get(pk=file_id)
    if not file_instance:
        return Http404()

    auth = Auth()
    user_profile = auth.get_current_user_profile()

    # Verify access to view the file
    allowed = False
    if auth.is_logged_in():
        if user_profile.username == file_instance.owner:
            allowed = True
        elif user_profile.has_authority("file_admin"):
            allowed = True

    # If not allowed via authentication, check session for specified file allowances
    if not allowed:
        allowed_files = env.get_session_variable("allowed_file_ids", [])
        if allowed_files and file_id in allowed_files:
            allowed = True

    if not allowed:
        return HttpResponseForbidden()

    else:

        # If specifically requested to download rather than open in browser
        download = request.GET.get("download")

        # If content type should not be opened in browser
        if "document" in file_instance.content_type:
            download = True
        elif "ms-" in file_instance.content_type:
            download = True

        filename = file_instance.basename
        response = HttpResponse(content_type=file_instance.content_type)

        # Audit file views (when not viewed by owner)
        if file_instance.owner != user_profile.username:
            reference_code = "DatabaseFile" if type(file_instance) is DatabaseFile else "UploadedFile"
            Auth.audit("R", "VIEW_FILE",
                reference_code=reference_code, reference_id=file_id,
                comments=f"Viewed: {filename}"
            )

        if download:
            # Force browser to download the file
            response["Content-Disposition"] = "attachment; filename=%s" % filename

    response.write(file_instance.file)
    return response
