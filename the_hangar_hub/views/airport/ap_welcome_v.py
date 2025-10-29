from django.http import HttpResponse, HttpResponseForbidden, FileResponse
from django.db.models import Q
from django.core.paginator import Paginator
from base.classes.util.env_helper import Log, EnvHelper
from base.classes.auth.session import Auth
from the_hangar_hub.models.infrastructure_models import Building, Hangar
from base.services import message_service, utility_service
from base.decorators import require_authority, require_authentication, report_errors
from the_hangar_hub.services import airport_service, tenant_s, application_service
from the_hangar_hub.decorators import require_airport, require_airport_manager
from base.models.utility.error import Error
from base_upload.services import retrieval_service
from base_upload.services import upload_service
from the_hangar_hub.models.airport import CustomizedContent, BlogEntry
from django.shortcuts import render, redirect
from the_hangar_hub.models.airport import Airport, Amenities, Amenity


log = Log()
env = EnvHelper()


@report_errors()
# @require_authentication()  # ToDo: Maybe not required?
@require_airport()
def welcome(request, airport_identifier):
    """
    An individual airport's landing page
    """
    airport = request.airport

    # Airport Status
    # ==============
    if not airport.is_active():
        return render(request, "the_hangar_hub/error_pages/airport_inactive.html")
    if not airport.is_current():
        message_service.post_error("ToDo: When airport is not current???")
    has_hangars = Hangar.objects.filter(building__airport=airport).count()
    has_billing_data = airport.has_billing_data()

    # User Status
    # ===========
    is_manager = airport_service.manages_this_airport()
    rentals = tenant_s.get_rental_agreements(Auth.current_user())
    is_tenant = bool(rentals)
    on_waitlist = airport.get_waitlist().current_user_position()
    active_applications = application_service.get_active_applications(airport=airport)

    # if is_manager and not has_hangars:
    #     return redirect("airport:manage", airport_identifier)

    airport = request.airport
    customized_content = airport.customized_content
    blog_entries = airport.blog_entries.all()[:9]


    return render(
        request, "the_hangar_hub/airport/customized/welcome.html",
        {
            # "is_manager": is_manager,
            # "is_tenant": is_tenant,
            # "on_waitlist": on_waitlist,
            # "active_applications": active_applications,

            "custom_content": customized_content,
            "blog_entries": blog_entries,

        }
    )


@require_airport_manager()
def customize_content(request, airport_identifier):
    """View for airport managers to customize their airport page."""
    airport = request.airport
    customized_content = airport.customized_content
    if not customized_content:
        customized_content = CustomizedContent.objects.create(airport=airport)

    if request.method == 'POST':
        log.info(f"Customizing airport content ({customized_content})")
        has_issues = False

        # Display name is on the airport model
        display_name = request.POST.get("display_name")
        if display_name:
            try:
                airport.display_name = display_name
                airport.save()
            except Exception as ee:
                Error.unexpected("Unable to save airport name", ee, display_name)
                has_issues = True

        try:
            contact_phone = request.POST.get("contact_phone")
            contact_email = request.POST.get("contact_email")
            url = request.POST.get("url")
            contact_address = request.POST.get("contact_address")
            frequencies = request.POST.get("frequencies")
            hours_m = request.POST.get("hours_m")
            hours_t = request.POST.get("hours_t")
            hours_w = request.POST.get("hours_w")
            hours_r = request.POST.get("hours_r")
            hours_f = request.POST.get("hours_f")
            hours_s = request.POST.get("hours_s")
            hours_u = request.POST.get("hours_u")
            after_hours = request.POST.get("after_hours")
            avgas = request.POST.get("avgas")
            jeta = request.POST.get("jeta")
            mogas = request.POST.get("mogas")

            if url and not url.startswith("http"):
                url = f"https://{url}"

            if avgas:
                avgas = utility_service.convert_to_decimal(avgas)
                if not avgas:
                    message_service.post_error("Invalid dollar amount for Avgas")
                    avgas = customized_content.avgas_price
                    has_issues = True

            if jeta:
                jeta = utility_service.convert_to_decimal(jeta)
                if not jeta:
                    message_service.post_error("Invalid dollar amount for Jet A")
                    jeta = customized_content.jeta_price
                    has_issues = True

            if mogas:
                mogas = utility_service.convert_to_decimal(mogas)
                if not mogas:
                    message_service.post_error("Invalid dollar amount for Mogas")
                    mogas = customized_content.mogas_price
                    has_issues = True

            try:
                customized_content.contact_phone = contact_phone
                customized_content.contact_email = contact_email
                customized_content.url = url
                customized_content.contact_address = contact_address
                customized_content.frequencies = frequencies
                customized_content.hours_m = hours_m
                customized_content.hours_t = hours_t
                customized_content.hours_w = hours_w
                customized_content.hours_r = hours_r
                customized_content.hours_f = hours_f
                customized_content.hours_s = hours_s
                customized_content.hours_u = hours_u
                customized_content.after_hours = after_hours
                customized_content.avgas_price = avgas or None
                customized_content.jeta_price = jeta or None
                customized_content.mogas_price = mogas or None
                customized_content.save()
            except Exception as ee:
                Error.unexpected("Unable to save custom airport content", ee)
                has_issues = True

        except Exception as ee:
            Error.unexpected("Unable to process submitted input", ee)
            has_issues = True

        if not has_issues:
            return redirect("airport:welcome", airport_identifier)

    amenity_options = sorted(
        Amenity.objects.filter(Q(approved=True) | Q(proposed_by_airport=airport)),
        key=lambda x: x.sort_val
    )

    return render(request, "the_hangar_hub/airport/customized/management/index.html", {
        'custom_content': customized_content,
        'airport': airport,
        "amenity_options": amenity_options,
    })


@require_airport()
def logo(request, airport_identifier):
    # Make sure the airport model has been queried
    airport = request.airport
    if not airport:
        airport = Airport.get(airport_identifier)
    if airport:
        logo_file = airport.get_logo()
        if logo_file:
            return retrieval_service.render_as_image(logo_file)

    # If airport was not found, or does not have a logo, display HangarHub logo
    response = FileResponse(open("the_hangar_hub/static/images/logo/hh-logo.png", "rb"))
    response["Content-Disposition"] = f'inline; filename="HangarHub-logo.png"'
    return response



@report_errors()
@require_airport_manager()
def upload_logo(request, airport_identifier):
    airport = request.airport
    uploaded_file = None
    try:
        if request.method == 'POST':
            # Delete any previously-uploaded images
            for img in retrieval_service.get_file_query().filter(
                    tag=f"logo:{airport.id}", foreign_table="Airport", foreign_key=airport.id
            ):
                img.delete()

            uploaded_file = upload_service.upload_file(
                request.FILES.get('logo_file'),
                tag=f"logo:{airport.id}",
                foreign_table="Airport", foreign_key=airport.id,
                # resize_dimensions="800x600",
                specified_filename='logo',
                parent_directory=f'airports/{airport.identifier}/uploads'
            )
            log.info(f"Uploaded Logo File: {uploaded_file}")


        if uploaded_file:
            Auth.audit(
                "C", "AIRPORT",
                f"Uploaded logo file",
                reference_code="Airport", reference_id=airport.id
            )

            return HttpResponse("ok")
    except Exception as ee:
        message_service.post_error(f"Could not upload logo file: {ee}")

    return HttpResponseForbidden()


@require_airport_manager()
def manage_amenities(request, airport_identifier):
    airport = request.airport
    mode = request.POST.get("mode")
    amenity_id = request.POST.get("amenity_id")
    amenity_title = request.POST.get("amenity_title")
    try:
        if mode == "create" and amenity_title:
            amenity = Amenity.objects.create(title=amenity_title, proposed_by_user=Auth.current_user(), proposed_by_airport=airport)
        else:
            amenity = Amenity.get(amenity_id)

        if not amenity:
            message_service.post_error("Could not update amenity")
            return HttpResponseForbidden()

        if mode == "remove":
            rel = Amenities.get(airport, amenity)
            if not rel:
                message_service.post_warning("Specified amenity does not appear to have been selected.")
                # Consider this a success, despite the warning, since the object to be removed doesn't exist
            else:
                rel.delete()
                message_service.post_success(f'Removed "{amenity.title}"')
        else:
            rel = Amenities.get(airport, amenity)
            if rel:
                # Already selected
                message_service.post_warning("Specified amenity appears to have been previously selected.")
                # Consider this a success
            else:
                Amenities.objects.create(airport=airport, amenity=amenity)

    except Exception as ee:
        Error.unexpected("unable to save amenity", ee, [mode, amenity_id, amenity_title])

    amenity_options = sorted(
        Amenity.objects.filter(Q(approved=True) | Q(proposed_by_airport=airport)),
        key=lambda x: x.sort_val
    )
    return render(
        request, "the_hangar_hub/airport/customized/management/amenities/_amenities.html",
        {
            "amenity_options": amenity_options
        }
    )


@require_airport_manager()
def manage_blog(request, airport_identifier):
    airport = request.airport

    # Get 10 entries at a time
    sort, page = utility_service.pagination_sort_info(request, "date_created", "desc")
    entries = BlogEntry.objects.filter(airport=airport).order_by(*sort)
    paginator = Paginator(entries, 10)
    entries = paginator.get_page(page)

    # Images uploaded prior to blog entry creation will be linked to BlogEntry ID 0
    pending_images = retrieval_service.get_file_query().filter(tag=f"blog:{airport.id}", foreign_table="BlogEntry", foreign_key=0)
    # for pi in pending_images:
    #     pi.delete()
    # pending_images = []

    return render(
        request, "the_hangar_hub/airport/customized/management/blog/blog_mgmt.html",
        {
            "entries": entries,
            "pending_images": pending_images,
        }
    )

@require_airport_manager()
def blog_post(request, airport_identifier):
    airport = request.airport

    title = request.POST.get("title")
    content = request.POST.get("content")
    entry_id = request.POST.get("entry_id")
    prefill = {"title": title, "content": content, "entry_id": entry_id,}

    # May be modifying an existing post
    blog_entry = BlogEntry.get(entry_id) if entry_id else None
    if entry_id and not blog_entry:
        env.set_flash_scope("prefill", prefill)
        message_service.post_error("Unable to locate original post for update")
        return redirect("airport:manage_blog", airport_identifier)

    try:
        if blog_entry:
            blog_entry.title = title
            blog_entry.content = content
            blog_entry.save()
            img_key = blog_entry.id * -1
        else:
            blog_entry = BlogEntry.objects.create(airport=airport, title=title, content=content)
            img_key = 0
            
        if blog_entry:
            # Attach uploaded images
            new_images = retrieval_service.get_file_query().filter(
                tag=f"blog:{airport.id}", foreign_table="BlogEntry", foreign_key=img_key
            )
            prev_images = retrieval_service.get_file_query().filter(
                tag=f"blog:{airport.id}", foreign_table="BlogEntry", foreign_key=blog_entry.id
            )
            if new_images and prev_images:
                for img in prev_images:
                    img.delete()
            for img in new_images:
                # Handle multiple files, although each upload currently replaces the previous (limiting to one)
                img.foreign_key = blog_entry.id
                img.save()

    except Exception as ee:
        Error.unexpected("Unable to save blog entry", ee)
        env.set_flash_scope("prefill", prefill)

    return redirect("airport:manage_blog", airport_identifier)


@require_airport_manager()
def blog_upload(request, airport_identifier, entry_id=None):
    airport = request.airport
    uploaded_file = None
    try:
        if request.method == 'POST':

            # Staged images have a foreign_key of 0 or (entry_id * -1)
            if entry_id:
                img_key = int(entry_id)*-1
                the_file = request.FILES.get('entry_file')
            else:
                img_key = 0
                the_file = request.FILES.get('blog_file')

            # Delete any previously-uploaded images
            for img in retrieval_service.get_file_query().filter(
                    tag=f"blog:{airport.id}", foreign_table="BlogEntry", foreign_key=img_key
            ):
                img.delete()


            uploaded_file = upload_service.upload_file(
                the_file,
                tag=f"blog:{airport.id}",
                foreign_table="BlogEntry", foreign_key=img_key,
                resize_dimensions="800x600",
                # specified_filename='airport_logo',
                # parent_directory=f'airports/{airport.identifier}/logo'
            )
            log.info(f"Uploaded File: {uploaded_file}")


        if uploaded_file:
            Auth.audit(
                "C", "AIRPORT",
                f"Uploaded blog file",
                reference_code="Airport", reference_id=airport.id
            )

            return HttpResponse("ok")
    except Exception as ee:
        message_service.post_error(f"Could not upload blog file: {ee}")

    return HttpResponseForbidden()


@require_airport_manager()
def blog_update_form(request, airport_identifier):
    airport = request.airport

    entry_id = request.POST.get("entry_id")
    entry = BlogEntry.get(entry_id)
    if not entry:
        message_service.post_error(f"Entry to be updated was not found")
        return HttpResponseForbidden()

    return render(
        request, "the_hangar_hub/airport/customized/management/blog/blog_edit.html",
        {
            "entry": entry
        }
    )

def blog_popup(request, airport_identifier):
    airport = request.airport
    entry_id = request.GET.get("entry_id")
    entry = BlogEntry.get(entry_id)
    if not entry:
        message_service.post_error(f"Blog entry was not found")
        return HttpResponseForbidden()

    return render(
        request, "the_hangar_hub/airport/customized/management/blog/_popup.html",
        {
            "entry": entry
        }
    )


@require_airport_manager()
def blog_delete(request, airport_identifier):
    airport = request.airport
    try:
        if request.method == 'POST':
            entry_id = request.POST.get("entry_id")
            entry = BlogEntry.get(entry_id)
            if not entry:
                log.info(f"Entry to be deleted was not found: {entry_id}")
                # Don't post an error since it was apparently already deleted
                return HttpResponse("ok")

            # Delete any associated files
            try:
                for img in retrieval_service.get_file_query().filter(
                    tag=f"blog:{airport.id}", foreign_table="BlogEntry", foreign_key=entry.id
                ):
                    img.delete()
            except Exception as ee:
                log.debug("Error deleting blog files")
                Error.record(ee, entry)

            entry.delete()
            message_service.post_success("Blog entry deleted")
            return HttpResponse("ok")

    except Exception as ee:
        message_service.post_error(f"Could not delete blog file: {ee}")

    return HttpResponseForbidden()
