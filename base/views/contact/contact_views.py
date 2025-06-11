from django.shortcuts import redirect, render
from django.http import HttpResponseForbidden, HttpResponseRedirect, HttpResponse
from ...services import auth_service, error_service, message_service, utility_service
from base.models import Contact, Address, Phone
from base.decorators import require_authority, require_authentication
from django.db.models import Q
from django.core.paginator import Paginator

from base.classes.util.env_helper import EnvHelper, Log

log = Log()
env = EnvHelper()


@require_authority('~contact_admin')
def contact_list(request):
    """
    Contact List
    """
    log.trace()
    sort, page, keywords = utility_service.pagination_sort_info(
        request, ('last_name', 'first_name'), filter_name="keywords"
    )

    if keywords:
        contacts = Contact.objects
        for ww in keywords.split():
            if '@' in ww:
                contacts = contacts.filter(email__icontains=ww)
            else:
                contacts = contacts.filter(Q(first_name__icontains=ww) | Q(last_name__icontains=ww))
    else:
        contacts = Contact.objects.all()

    contacts = contacts.order_by(*sort)
    paginator = Paginator(contacts, 50)
    contacts = paginator.get_page(page)

    return render(request, 'base/contact/list.html', {
        'contacts': contacts,
        'keywords': keywords,
    })


@require_authority('~contact_admin')
def refresh_contact(request):
    """
    Refresh one contact
    """
    log.trace()
    contact_id = request.GET.get('contact_id')
    if contact_id:
        contact = _get_contact_or_redirect(request, contact_id)
        if type(contact) in [HttpResponseRedirect, HttpResponseForbidden]:
            return contact
    else:
        return HttpResponseForbidden()

    return render(request, 'base/contact/_contact_line.html', {
        'contact': contact,
    })


@require_authority('~contact_admin')
def contact_form(request):
    """
    Contact Form
    """
    log.trace()
    contact_id = request.GET.get('contact_id', request.POST.get('contact_id'))
    contact = None
    new_contact = False
    if not contact_id:
        return HttpResponseForbidden()

    if contact_id == 'new':
        new_contact = True
        # Required fields for creating a new contact
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        email = request.POST.get('email')
        if not (first_name and last_name and email):
            message_service.post_error("You must provide first name, last name, and email to create a new contact")
            return HttpResponseForbidden()
        contact = Contact()
        if contact.set_first_name(first_name):
            if contact.set_last_name(last_name):
                if contact.set_email(email):
                    contact.save()
                    contact_id = contact.id

    if not contact_id:
        return HttpResponseForbidden()

    if not contact:
        contact = _get_contact_or_redirect(request, contact_id)
        if type(contact) in [HttpResponseRedirect, HttpResponseForbidden]:
            return contact

    return render(request, 'base/contact/_contact_form.html', {
        'contact': contact,
        'contact_id': contact_id,
        'address_options': Address.address_types(),
        'phone_options': Phone.phone_types(),
        'new_contact': new_contact,
    })


@require_authentication()
def profile(request):
    """
    Edit Profile
    """
    log.trace()
    contact = _get_contact_or_redirect(request)
    if type(contact) in [HttpResponseRedirect, HttpResponseForbidden]:
        return contact

    authorities = auth_service.get_user().authorities

    from allauth.account.models import EmailAddress
    emails = EmailAddress.objects.filter(user=auth_service.get_user().user)

    return render(request, 'base/contact/profile.html', {
        'contact': contact,
        'user': contact.user,
        'authorities': authorities,
        'address_options': Address.address_types(),
        'phone_options': Phone.phone_types(),
        'emails': emails,
    })


@require_authentication()
def update_contact(request):
    """
    AJAX: Update contact record
    """
    log.trace()
    contact = _get_contact_or_redirect(request, request.POST.get('contact_id'))
    if type(contact) in [HttpResponseRedirect, HttpResponseForbidden]:
        return contact
    try:
        attribute = request.POST.get('attribute')
        value = request.POST.get('value')
        log.info(f"Update {contact}: change {attribute} to {value}")
        if attribute == 'first_name':
            if contact.set_first_name(value):
                contact.save()
                return HttpResponse('success')
        elif attribute == 'last_name':
            if contact.set_last_name(value):
                contact.save()
                return HttpResponse('success')
        elif attribute == 'email':
            if contact.set_email(value):
                contact.save()
                return HttpResponse('success')
        else:
            setattr(contact, attribute, value)
            contact.save()
            return HttpResponse('success')
    except Exception as ee:
        error_service.unexpected_error("Unable to save contact", ee)

    return HttpResponseForbidden()


@require_authentication()
def update_phone(request):
    """
    AJAX: Add/Update phone record
    """
    log.trace()
    contact = _get_contact_or_redirect(request, request.POST.get('contact_id'))
    if type(contact) in [HttpResponseRedirect, HttpResponseForbidden]:
        return contact

    # ADD A NEW PHONE
    if 'phone_id' not in request.POST:
        log.info(f"Adding phone for {contact}")

        pt = request.POST.get('phone_type')
        pp = request.POST.get('phone_prefix')
        pn = request.POST.get('phone_number')
        pe = request.POST.get('phone_ext')

        # Check for entry of area code into prefix
        if len(pp) == 3 and len(pn) == 7:
            pn = f"{pp}{pn}"
            pp = ''

        p = Phone()
        p.contact = contact
        if p.set_phone(pt, pp, pn, pe):
            p.save()
            return render(request, 'base/contact/_phone.html', {'phone': p, 'show_type': True, 'newline': True})
        else:
            return HttpResponseForbidden()

    # UPDATE/DELETE EXISTING PHONE
    else:
        phone = Phone.get(request.POST.get('phone_id'), contact)
        if not phone:
            message_service.post_error("Specified phone could not be edited")
            return HttpResponseForbidden()

        # DELETE
        if request.POST.get('phone_delete', 'N') == 'Y':
            log.info(f"Delete {phone} for {contact}")
            phone.delete()
            return HttpResponse('success')

        # PREFERRED
        if request.POST.get('phone_preferred', 'N') == 'Y':
            log.info(f"Prefer {phone} for {contact}")
            if phone.make_primary():
                return HttpResponse('success')

        # UPDATE TYPE
        elif request.POST.get('phone_type'):
            log.info(f"Update {phone} for {contact}")
            if phone.set_ptype(request.POST.get('phone_type')):
                phone.save()
                return HttpResponse('success')

    return HttpResponseForbidden()


@require_authentication()
def update_address(request):
    """
    AJAX: Add/Update address record
    """
    log.trace()
    contact = _get_contact_or_redirect(request, request.POST.get('contact_id'))
    if type(contact) in [HttpResponseRedirect, HttpResponseForbidden]:
        return contact

    # ADD A NEW ADDRESS
    if 'address_id' not in request.POST:
        log.info(f"Adding address for {contact}")
        a = Address()
        a.contact = contact
        if a.set_all(
            request.POST.get('address_type'),
            request.POST.get('street_1'),
            request.POST.get('street_2'),
            request.POST.get('street_3'),
            request.POST.get('city'),
            request.POST.get('state'),
            request.POST.get('zip_code'),
            request.POST.get('country'),
        ):
            a.save()
            return render(request, 'base/contact/_address.html', {'address': a})
        else:
            return HttpResponseForbidden()

    # UPDATE/DELETE EXISTING ADDRESS
    else:
        address = Address.get(request.POST.get('address_id'), contact)
        if not address:
            message_service.post_error("Specified address could not be edited")
            return HttpResponseForbidden()

        # DELETE
        if request.POST.get('address_delete', 'N') == 'Y':
            log.info(f"Delete {address} for {contact}")
            address.delete()
            return HttpResponse('success')

        # UPDATE TYPE
        elif request.POST.get('address_type'):
            log.info(f"Update {address} for {contact}")
            if address.set_atype(request.POST.get('address_type')):
                address.save()
                return HttpResponse('success')

    return HttpResponseForbidden()


def _get_contact_or_redirect(request, contact_id=None):
    log.trace([contact_id])
    contact = None

    # Only administrators can edit specified contacts
    if contact_id:
        if not auth_service.has_authority('~contact_admin'):
            contact = False
        else:
            contact = Contact.get(contact_id)
    else:
        user = auth_service.get_user()
        if user.is_authenticated:
            contact = user.contact()

    if contact:
        return contact
    else:
        message_service.post_error("You are not authorized to access the requested resource")
        if env.is_ajax:
            return HttpResponseForbidden()
        else:
            return redirect('/')
