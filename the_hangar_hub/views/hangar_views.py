from django.shortcuts import render, redirect
from django.http import HttpResponse, HttpResponseForbidden
from base.classes.util.log import Log
from base.classes.auth.auth import Auth
from base.services.message_service import post_error
from the_hangar_hub.models.airport import Airport
from the_hangar_hub.models.hangar import Building, Hangar
from the_hangar_hub.models.invitation import Invitation
from base.services import message_service, utility_service, email_service
from base.decorators import require_authority, require_authentication
from the_hangar_hub.services import airport_service
from base.fixtures.timezones import timezones
from decimal import Decimal
import re

log = Log()

@require_authentication()
def airport_buildings(request, airport_identifier):
    airport = airport_service.get_managed_airport(airport_identifier)
    if not airport:
        return redirect("hub:welcome")


    buildings = airport.buildings.all()

    return render(
        request, "the_hangar_hub/hangars/airport.html",
        {
            "airport": airport,
            "buildings": buildings,
        }
    )


@require_authentication()
def add_building(request, airport_identifier):
    airport = airport_service.get_managed_airport(airport_identifier)
    if not airport:
        return redirect("hub:welcome")

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
    return redirect("hub:airport_buildings", airport_identifier)


@require_authentication()
def building_hangars(request, airport_identifier, building_id):
    building = airport_service.get_managed_building(airport_identifier, building_id)
    if not building:
        return redirect("hub:airport_buildings", airport_identifier)

    hangars = building.hangars.all()

    return render(
        request, "the_hangar_hub/hangars/building.html",
        {
            "airport": building.airport,
            "building": building,
            "hangars": hangars,
        }
    )


@require_authentication()
def add_hangar(request, airport_identifier, building_id):
    building = airport_service.get_managed_building(airport_identifier, building_id)
    if not building:
        return redirect("hub:airport_buildings", airport_identifier)

    airport = building.airport
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
    return redirect("hub:building_hangars", airport_identifier, building_id)


@require_authentication()
def manage_hangar(request, airport_identifier, hangar_id):
    hangar = airport_service.get_managed_hangar(airport_identifier, hangar_id)
    if not hangar:
        return redirect("hub:airport_buildings", airport_identifier)
    airport = hangar.building.airport

    return render(
        request,
        "the_hangar_hub/hangars/hangar.html",
        {
            "airport": airport,
            "hangar": hangar,
        }
    )