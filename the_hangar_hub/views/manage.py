
from the_hangar_hub.models.airport import Airport

from base.fixtures.timezones import timezones

from django.shortcuts import render, redirect
from django.urls import reverse
from django.http import HttpResponse, HttpResponseForbidden
from django.db.models import Q
import the_hangar_hub.models
from base.classes.util.env_helper import Log, EnvHelper
from base.classes.auth.session import Auth
from the_hangar_hub.models import Tenant
from the_hangar_hub.models.airport import Airport
from the_hangar_hub.models.hangar import Building, Hangar
from the_hangar_hub.models.invitation import Invitation
from the_hangar_hub.models.application import HangarApplication
from base.services import message_service, utility_service, email_service, date_service
from base.decorators import require_authority, require_authentication
from the_hangar_hub.services import airport_service
from decimal import Decimal
from base.classes.breadcrumb import Breadcrumb
from django.contrib.auth.models import User
import re
from datetime import datetime, timezone
from base.models.contact.contact import Contact
from the_hangar_hub.decorators import require_airport, require_airport_manager

log = Log()
env = EnvHelper()


@require_authentication()
@require_airport()
def claim_airport(request, airport_identifier):
    airport = request.airport

    # Airport must be inactive
    if airport.is_active():
        return redirect("airport:welcome", airport.identifier)

    if request.method == "POST":
        referral_code = request.POST.get("referral_code")
        if referral_code:
            pass


    # Any inactive airport can be claimed.
    # Display page with instructions/referral code
    return render(
        request, "the_hangar_hub/airport/management/claim.html",
        {
            "airport": airport,
        }
    )

    # Get existing airport managers (including inactive ones)
    managers = airport_service.get_managers(airport)
    is_manager = is_inactive = False

    # If managers exist, see if this user is already one of them
    if managers:
        for manager in managers:
            if manager.user == request.user:
                is_manager = True
                log.info(f"Is already a manager for {airport.identifier}")
                if manager.status != "A":
                    log.warning(f"Is a non-active manager for {airport.identifier}")
                    is_inactive = True
                elif not manager.user.is_active:
                    log.warning(f"Is a manager, but a non-active user")
                    is_inactive = True
                break

        # Since managers exist for this airport, this user must be an active manager or ask an existing one for access
        if is_inactive or not is_manager:
            if not is_manager:
                message_service.post_error(
                    "This airport already has a manager. You'll need to request access from existing management."
                )
            else:
                message_service.post_error(
                    "Your airport management status is inactive. You'll need to request access from existing management."
                )

            return render(
                request, "the_hangar_hub/airport/access_denied.html",
                {"airport": airport}
            )

    # Since no managers exist for this airport, auto-assign this user to be the manager for this airport
    else:
        log.info(f"No managers exist for {airport}")
        if airport_service.set_airport_manager(airport, request.user):
            message_service.post_success(f"You are now the airport manager for {airport.identifier}")
        else:
            message_service.post_error(f"Unable to record you as the manager for {airport.identifier}")

    return redirect("manage:airport", airport.identifier)


@require_authentication()
@require_airport()
@require_airport_manager()
def my_airport(request, airport_identifier):
    airport = request.airport
    return render(
        request, "the_hangar_hub/airport/management/airport.html",
        {
            "airport": airport,
            "managers": airport.management.all(),
            "invitations": airport_service.get_pending_invitations(airport, "MANAGER"),
            "timezone_options": timezones,
        }
    )

@require_authentication()
@require_airport()
@require_airport_manager()
def update_airport(request, airport_identifier):
    airport = request.airport
    attribute = request.POST.get("attribute")
    value = request.POST.get("value")

    try:
        prev_value = getattr(airport, attribute)
        setattr(airport, attribute, value)
        airport.save()
        message_service.post_success("Airport data updated")

        Auth.audit(
            "U", "AIRPORT",
            f"Updated airport data: {attribute}",
            reference_code="Airport", reference_id=airport.id,
            previous_value=prev_value, new_value=value
        )
    except Exception as ee:
        message_service.post_error(f"Could not update airport data: {ee}")

    return HttpResponse("ok")


@require_authentication()
@require_airport()
@require_airport_manager()
def add_manager(request, airport_identifier):
    airport = request.airport
    invitee = request.POST.get("invitee")
    log.trace([airport, invitee])

    # Check for existing user
    existing_user = Auth.lookup_user_profile(invitee)
    # If user already has an account, just add them as a manager
    if existing_user:
        if airport_service.set_airport_manager(airport, existing_user):
            message_service.post_success(f"Added airport manager: {invitee}")
        else:
            message_service.post_error(f"Could not add airport manager: {invitee}")
        return render(
            request, "the_hangar_hub/airport/management/_manager_table.html",
            {
                "airport": airport,
                "managers": airport_service.get_managers(airport=airport),
                "invitations": airport_service.get_pending_invitations(airport, "MANAGER")
            }
        )

    # Since user did not have an account, an email is needed to invite them
    if "@" not in invitee:
        message_service.post_error("The given user information could not be found. Please enter an email address.")
        return HttpResponseForbidden()

    # Create and send an invitation
    Invitation.invite_manager(airport, invitee)
    return render(
        request, "the_hangar_hub/airport/management/_manager_table.html",
        {
            "airport": airport,
            "managers": airport_service.get_managers(airport=airport),
            "invitations": airport_service.get_pending_invitations(airport, "MANAGER")
        }
    )


@require_authentication()
@require_airport()
@require_airport_manager()
def my_buildings(request, airport_identifier):
    airport = request.airport

    buildings = airport.buildings.all()
    Breadcrumb.add(
        "Buildings", ("manage:buildings", airport_identifier), reset=True
    )

    return render(
        request, "the_hangar_hub/airport/management/buildings.html",
        {
            "airport": airport,
            "buildings": buildings,
        }
    )


@require_authentication()
@require_airport()
@require_airport_manager()
def add_building(request, airport_identifier):
    airport = request.airport


    building_code = request.POST.get("building_code")
    if not building_code:
        # Default building code is airport_code-#
        building_code = f"{airport.identifier}-[1]"

    if building_code.isnumeric():
        # Building codes cannot be numeric (to distinguish between id and code)
        building_code = f"{airport.identifier}-{building_code}"

    default_rent = request.POST.get("default_rent") or 0.0
    if default_rent:
        default_rent = default_rent.replace("$", "").replace(",", "")

    airport_buildings = [x.code for x in airport.buildings.all()]

    # Bulk Processing
    # If building code contains a number in [brackets], add that many buildings with incrementing ID in the code
    if "[" in building_code:
        bits = re.split('[\[\]]', building_code)
        if len(bits) != 3:
            message_service.post_error("Invalid building code")
        else:
            pre = bits[0]
            num = int(bits[1])
            post = bits[2]
            if not (pre or post):
                pre = f"{airport.identifier}-"
            seq = 1
            for ii in range(num):
                building_code = f"{pre}{seq}{post}".strip()
                while building_code in airport_buildings:
                    seq += 1
                    building_code = f"{pre}{seq}{post}".strip()
                Building.objects.create(
                    airport=airport, code=building_code, default_rent=default_rent
                )
                airport_buildings.append(building_code)

                ii += 1
                seq += 1
    else:
        if building_code in airport_buildings:
            message_service.post_error("Building code already exists")
        else:

            Building.objects.create(airport=airport, code=building_code, default_rent=default_rent)
    return redirect("manage:buildings", airport_identifier)


@require_authentication()
@require_airport()
@require_airport_manager()
def my_hangars(request, airport_identifier, building_id):
    airport = request.airport
    building = airport_service.get_managed_building(airport, building_id)
    if not building:
        return redirect("manage:buildings", airport.identifier)

    hangars = building.hangars.all()

    Breadcrumb.add(
        f"{building.code} Hangars", ("manage:hangars", airport.identifier, building_id)
    )
    return render(
        request, "the_hangar_hub/airport/management/hangars.html",
        {
            "airport": airport,
            "building": building,
            "hangars": hangars,
        }
    )


@require_authentication()
@require_airport()
@require_airport_manager()
def add_hangar(request, airport_identifier, building_id):
    airport = request.airport

    building = airport_service.get_managed_building(airport, building_id)
    if not building:
        return redirect("manage:buildings", airport.identifier)

    hangar_code = request.POST.get("hangar_code")
    default_rent = request.POST.get("default_rent") or 0.0
    capacity = int(request.POST.get("capacity") or 1)
    electric = request.POST.get("electric") or 0

    # Hangar codes are unique to the airport (not just the building)
    airport_hangars = [x.code for x in Hangar.objects.filter(building__airport=airport)]

    if not hangar_code:
        # Default hangar code is building_code-#
        hangar_code = f"{building.code}-[1]"

    elif hangar_code.isnumeric():
        # Hangar codes cannot be numeric (to distinguish between id and code)
        hangar_code = f"{building.code}-{hangar_code}"

    # Bulk Processing
    # If hangar code contains a number in [brackets], add that many hangars with incrementing ID in the code
    if "[" in hangar_code:
        bits = re.split('[\[\]]', hangar_code)
        if len(bits) != 3:
            message_service.post_error("Invalid hangar code")
        else:
            pre = bits[0]
            num = int(bits[1])
            post = bits[2]
            if not (pre or post):
                pre = f"{building.code}-"
            seq = 1
            for ii in range(num):
                hangar_code = f"{pre}{seq}{post}".strip()
                while hangar_code in airport_hangars:
                    seq += 1
                    hangar_code = f"{pre}{seq}{post}".strip()
                Hangar.objects.create(
                    building=building, default_rent=default_rent, code=hangar_code, capacity=capacity, electric=electric
                )
                airport_hangars.append(hangar_code)

                ii += 1
                seq += 1
    else:
        if hangar_code in airport_hangars:
            message_service.post_error("Hangar code already exists")
        else:
            Hangar.objects.create(
                building=building, default_rent=default_rent, code=hangar_code, capacity=capacity, electric=electric
            )
    return redirect("manage:hangars", airport.identifier, building_id)


@require_authentication()
@require_airport()
@require_airport_manager()
def one_hangar(request, airport_identifier, hangar_id):
    airport = request.airport

    hangar = airport_service.get_managed_hangar(airport, hangar_id)
    if not hangar:
        return redirect("manage:buildings", airport.identifier)
    airport = hangar.building.airport

    rentals = the_hangar_hub.models.tenant.Rental.objects.filter(hangar=hangar)

    Breadcrumb.add(
        f"Hangar {hangar.code}", ("manage:hangar", airport.identifier, hangar_id),
    )

    return render(
        request,
        "the_hangar_hub/airport/management/one_hangar.html",
        {
            "airport": airport,
            "hangar": hangar,
            "rentals": rentals,
            "prefill": env.get_flash_scope("prefill") or {},
            "issues": env.get_flash_scope("add_tenant_issues") or [],
        }
    )


@require_authentication()
@require_airport()
@require_airport_manager()
def add_tenant(request, airport_identifier, hangar_id):
    log.trace([airport_identifier, hangar_id])
    airport = request.airport

    hangar = airport_service.get_managed_hangar(airport, hangar_id)
    if not hangar:
        return redirect("manage:buildings", airport_identifier)

    # Process Parameters
    issues = []
    email = request.POST.get("email")
    first_name = request.POST.get("first_name")
    last_name = request.POST.get("last_name")
    start_date = request.POST.get("start_date")
    end_date = request.POST.get("end_date")
    rent = request.POST.get("rent")
    deposit = request.POST.get("deposit")
    notes = request.POST.get("notes")

    application_id = request.POST.get("application_id")
    application = HangarApplication.get(application_id) if application_id else None

    if not email:
        issues.append("Email address is required")

    if start_date:
        start_date = date_service.string_to_date(start_date, airport.timezone)
        if not start_date:
            issues.append("Invalid Start Date")
    else:
        start_date = datetime.now(timezone.utc)

    if end_date:
        end_date = date_service.string_to_date(end_date, airport.timezone)
    else:
        end_date = None

    if rent:
        rent = str(rent).replace('$', '').replace(',', '')
    else:
        rent = hangar.rent()
    if not rent:
        issues.append("Rent is required")

    if deposit:
        deposit = str(deposit).replace('$', '').replace(',', '')
    else:
        deposit = None


    prefill = {
        "email": email,
        "first_name": first_name,
        "last_name": last_name,
        "start_date": start_date.strftime("%Y-%m-%d") if start_date else None,
        "end_date": end_date.strftime("%Y-%m-%d") if end_date else None,
        "rent": rent,
        "deposit": deposit,
        "notes": notes,
    }
    log.trace(prefill)

    if issues:
        env.set_flash_scope("add_tenant_issues", issues)
        env.set_flash_scope("prefill", prefill)
        return redirect("manage:hangar", airport.identifier, hangar_id)


    user = contact = tenant = None

    # If application was given, get user from it
    if application:
        user = application.user
        contact = user.contact

    else:
        # Look for existing user via email
        existing_user_profile = Auth.lookup_user_profile(email)
        if existing_user_profile.id:
            user = existing_user_profile.user
            contact = existing_user_profile.contact()
            if not existing_user_profile.is_active:
                try:
                    user.is_active = True
                    user.save()
                except Exception as ee:
                    log.error(f"Unable to activate User: {user} ({ee})")

    # If not an existing user, look for existing contact record
    if not user:
        try:
            contact = Contact.objects.get(email__iexact=email)
        except Contact.DoesNotExist:
            pass

    # If user or contact exists, look for existing tenant record
    if user or contact:
        try:
            tenant = Tenant.objects.get(Q(user=user) | Q(contact=contact))
        except Tenant.DoesNotExist:
            pass

    # Contact must be created if not already found
    if not contact:
        try:
            contact = Contact()
            contact.first_name = first_name
            contact.last_name = last_name
            contact.email = email
            contact.save()
        except Exception as ee:
            log.error(f"Error creating contact: {ee}")
            issues.append("Unable to create contact record.")
    if issues:
        env.set_flash_scope("add_tenant_issues", issues)
        env.set_flash_scope("prefill", prefill)
        return redirect("manage:hangar", airport_identifier, hangar_id)

    # If tenant record ws not found, create one now
    if not tenant:
        try:
            tenant = Tenant()
            tenant.contact = contact
            tenant.user = user
            tenant.save()
        except Exception as ee:
            log.error(f"Error creating tenant: {ee}")
            issues.append("Unable to create tenant record.")
    if issues:
        env.set_flash_scope("add_tenant_issues", issues)
        env.set_flash_scope("prefill", prefill)
        return redirect("manage:hangar", airport.identifier, hangar_id)

    # Create the rental record
    try:
        rental = the_hangar_hub.models.tenant.Rental()
        rental.tenant = tenant
        rental.hangar = hangar
        rental.start_date = start_date
        rental.end_date = end_date
        rental.rent = rent
        rental.deposit = deposit
        rental.notes = notes
        rental.save()

        message_service.post_success("New tenant has been added")
        if application:
            application.deselect()
            application.status_code = "A"
            application.save()
    except Exception as ee:
        log.error(f"Error creating rental: {ee}")
        issues.append("Unable to create rental record.")
        env.set_flash_scope("add_tenant_issues", issues)
        env.set_flash_scope("prefill", prefill)



    # If not an existing user, send an invitation
    if not user:
        Invitation.invite_tenant(airport, email, tenant=tenant, hangar=hangar)

    return redirect("manage:hangar",airport_identifier, hangar.code)


@require_authentication()
@require_airport()
@require_airport_manager()
def application_dashboard(request, airport_identifier):
    log.trace([airport_identifier])
    airport = request.airport

    unreviewed = []
    incomplete = []
    for application in airport.applications.filter(status_code__in=["S", "I"]):
        if application.status_code == "S":
            unreviewed.append(application)
        elif application.status_code == "I":
            incomplete.append(application)

    Breadcrumb.add("Application Dashboard", ["manage:application_dashboard", airport.identifier], reset=True)
    return render(
        request, "the_hangar_hub/airport/management/applications/dashboard.html",
        {
            "unreviewed_applications": unreviewed,
            "incomplete_applications": incomplete,
        }
    )


@require_authentication()
@require_airport()
@require_airport_manager()
def change_wl_priority(request, airport_identifier):
    log.trace([airport_identifier])

    application = HangarApplication.get(request.POST.get("application_id"))
    if not application:
        message_service.post_error("Application not found. Could not update priority.")
        return HttpResponseForbidden()
    elif application.airport != request.airport:
        message_service.post_error("Application is for a different airport. If you are working in multiple tabs, try refreshing the page.")
        return HttpResponseForbidden()

    new_priority = request.POST.get("new_priority")
    if new_priority is None or new_priority not in application.wl_group_options():
        message_service.post_error("Invalid priority selection. Could not update priority.")
        return HttpResponseForbidden()

    Auth.audit(
        "U", "WAITLIST", "Updated priority", previous_value=application.wl_group_code, new_value=new_priority
    )
    application.wl_group_code = new_priority
    application.wl_index = None
    application.save()

    return render(
        request, "the_hangar_hub/airport/management/applications/_waitlist.html",
        {}
    )

@require_authentication()
@require_airport()
@require_airport_manager()
def change_wl_index(request, airport_identifier):
    application_id = request.POST.get("application_id")
    movement = request.POST.get("movement")

    # If resetting to timestamp-based order
    if movement == "reset":
        request.airport.get_waitlist().reindex_applications(group_code=None, restore_default=True)


    # Otherwise, changing one application
    else:
        application = HangarApplication.get(application_id)
        if not application:
            message_service.post_error("Application not found. Could not update waitlist position.")
            return HttpResponseForbidden()
        elif application.airport != request.airport:
            message_service.post_error("Application is for a different airport. If you are working in multiple tabs, try refreshing the page.")
            return HttpResponseForbidden()

        waitlist = request.airport.get_waitlist()
        current_position = application.wl_index
        max_position = waitlist.applications_per_group().get(application.wl_group_code)

        # Determine new position in waitlist
        if movement == "top":
            new_position = 1
        elif movement == "up":
            new_position = current_position - 1
        elif movement == "down":
            new_position = current_position + 1
        else:
            new_position = max_position
        if new_position < 1:
            new_position = 1
        if new_position > max_position:
            new_position = max_position

        log.trace([airport_identifier, application_id, movement, current_position, new_position])

        if new_position != current_position:

            for app in waitlist.applications:
                if app.wl_group_code != application.wl_group_code:
                    continue
                if app.id == application.id:
                    app.wl_index = new_position
                    app.save()
                # If moved to top, all others above it must move down one
                elif movement == "top":
                    if app.wl_index < current_position:
                        app.wl_index += 1
                        app.save()
                # If moved to bottom, all others below it must move up one
                elif movement == "bottom":
                    if app.wl_index > current_position:
                        app.wl_index -= 1
                        app.save()
                # If moved up or down one, swap with the one above/below it
                elif movement in ["up", "down"]:
                    if app.wl_index == new_position:
                        app.wl_index = current_position
                        app.save()

            Auth.audit(
                "U", "WAITLIST", "Updated index", previous_value=current_position, new_value=new_position
            )

    return render(
        request, "the_hangar_hub/airport/management/applications/_waitlist.html",
        {}
    )
