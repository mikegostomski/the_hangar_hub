from base.fixtures.timezones import timezones
from django.shortcuts import render, redirect
from django.http import HttpResponse, HttpResponseForbidden
from django.db.models import Q
from base.classes.util.env_helper import Log, EnvHelper
from base.classes.auth.session import Auth
from the_hangar_hub.models.rental_models import Tenant, RentalAgreement
from the_hangar_hub.models.airport_manager import AirportManager
from the_hangar_hub.models.infrastructure_models import Building, Hangar
from the_hangar_hub.models.invitation import Invitation
from the_hangar_hub.models.application import HangarApplication
from base.services import message_service, date_service
from base.decorators import require_authority, require_authentication, report_errors
from the_hangar_hub.services import airport_service
from base.classes.breadcrumb import Breadcrumb
import re
from datetime import datetime, timezone
from base.models.contact.contact import Contact
from the_hangar_hub.decorators import require_airport, require_airport_manager
from base_upload.services import upload_service, retrieval_service
from base.models.utility.error import Error
from the_hangar_hub.services import stripe_service


log = Log()
env = EnvHelper()



@report_errors()
@require_airport_manager()
def my_buildings(request, airport_identifier):
    airport = request.airport

    buildings = airport.buildings.all()
    Breadcrumb.add(
        "Buildings", ("infrastructure:buildings", airport_identifier), reset=True
    )

    return render(
        request, "the_hangar_hub/airport/infrastructure/buildings.html",
        {
            "airport": airport,
            "buildings": buildings,
        }
    )


@report_errors()
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
    return redirect("infrastructure:buildings", airport_identifier)


@report_errors()
@require_airport_manager()
def my_hangars(request, airport_identifier, building_id):
    airport = request.airport
    building = airport_service.get_managed_building(airport, building_id)
    if not building:
        return redirect("infrastructure:buildings", airport.identifier)

    hangars = building.hangars.all()

    Breadcrumb.add(
        f"{building.code} Hangars", ("infrastructure:hangars", airport.identifier, building_id)
    )
    return render(
        request, "the_hangar_hub/airport/infrastructure/hangars.html",
        {
            "airport": airport,
            "building": building,
            "hangars": hangars,
        }
    )


@report_errors()
@require_airport_manager()
def add_hangar(request, airport_identifier, building_id):
    airport = request.airport

    building = airport_service.get_managed_building(airport, building_id)
    if not building:
        return redirect("infrastructure:buildings", airport.identifier)

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
    return redirect("infrastructure:hangars", airport.identifier, building_id)

@report_errors()
@require_airport_manager()
def delete_hangar(request, airport_identifier):
    try:
        airport = request.airport
        hangar_id = request.POST.get("hangar_id")
        hangar = airport_service.get_managed_hangar(airport, hangar_id)
        if not hangar:
            message_service.post_error("Specified hangar could not be found")
            return HttpResponseForbidden()

        # Only delete hangar if it has no rental history
        # (most likely for accidental hangar creation)
        if hangar.all_rentals():
            message_service.post_error("You cannot delete a hangar with rental history")
            return HttpResponseForbidden()

        hangar_code = hangar.code
        audit_comment = f"Deleted hangar {hangar_code} at {hangar.building.airport}"
        hangar.delete()
        message_service.post_success(f"Hangar {hangar_code} has been deleted")

        Auth.audit("D", "HANGAR", audit_comment, "Hangar", hangar_id)
        return HttpResponse("ok")

    except Exception as ee:
        Error.unexpected("Unable to delete hangar.", ee)
        return HttpResponseForbidden()


@report_errors()
@require_airport_manager()
def one_hangar(request, airport_identifier, hangar_id):
    airport = request.airport

    hangar = airport_service.get_managed_hangar(airport, hangar_id)
    if not hangar:
        return redirect("infrastructure:buildings", airport.identifier)
    airport = hangar.building.airport

    rentals = RentalAgreement.objects.filter(hangar=hangar)

    Breadcrumb.add(
        f"Hangar {hangar.code}", ("infrastructure:hangar", airport.identifier, hangar_id),
    )

    return render(
        request,
        "the_hangar_hub/airport/infrastructure/one_hangar/index.html",
        {
            "airport": airport,
            "hangar": hangar,
            "rentals": rentals,
            "prefill": env.get_flash_scope("prefill") or {},
            "issues": env.get_flash_scope("add_tenant_issues") or [],
        }
    )
