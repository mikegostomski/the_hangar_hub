from django.shortcuts import render, redirect
from base.classes.util.log import Log
from base.decorators import require_authentication
from base_upload.services import upload_service, retrieval_service
from django.core.paginator import Paginator
from base.services import utility_service

log = Log()

def landing_page(request):
    """
    A landing page
    """
    log.trace()

    return render(
        request, 'landing.html', {}
    )


@require_authentication()
def upload_form(request):
    log.trace()
    sort_by, page = utility_service.pagination_sort_info(request, 'date_created', 'desc')
    uploaded_files = retrieval_service.get_all_files().order_by(*sort_by)

    # Paginate the results
    paginator = Paginator(uploaded_files, 10)
    uploaded_files = paginator.get_page(page)

    return render(
        request, 'upload_sample.html',
        {'uploaded_files': uploaded_files}
    )


@require_authentication()
def upload_action(request, seqno=None):
    """
    Upload a file and store it in S3
    """
    log.trace([seqno])

    if request.method == 'POST':

        # IF NOT SAVING FILE
        if request.POST.get('display_only'):
            files = upload_service.read_uploaded_files(request, 'sample_file', convert_to_string="base64")
            return render(request, 'unsaved_upload.html', {'files': files})

        # IF SAVING FILE
        else:
            # Input name is coming from the form so that multiple demo forms could use the same action
            input_name = request.POST.get('input_name', 'sample_file')
            # Upload the file and rename to sequenced file name (test-1, test-2, etc)
            uploads = upload_service.upload_files(request, input_name, 'test-', 'Tests')
            if uploads:
                for uf in uploads:
                    log.info(f"Uploaded: {uf.original_name} - {uf.size}")

    return redirect('upload_form')
