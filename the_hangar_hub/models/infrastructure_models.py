from django.db import models
from base.classes.util.env_helper import Log, EnvHelper
from datetime import datetime, timezone

from the_hangar_hub.models.rental_models import RentalAgreement

log = Log()
env = EnvHelper()

class Building(models.Model):
    date_created = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)

    airport = models.ForeignKey('the_hangar_hub.Airport', on_delete=models.CASCADE, related_name="buildings")
    code = models.CharField(max_length=30)
    default_rent = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)  # Default passed to hangar

    def get_hangar(self, hangar_identifier):
        if str(hangar_identifier).isnumeric():
            return self.hangars.get(pk=hangar_identifier)
        else:
            return self.hangars.get(code=hangar_identifier)

    class Meta:
        unique_together = ('airport', 'code',)

    def num_hangars(self):
        return len(self.hangars.all())

    @classmethod
    def get(cls, data):
        try:
            return cls.objects.get(pk=data)
        except cls.DoesNotExist:
            return None
        except Exception as ee:
            log.error(f"Could not get {cls}: {ee}")
            return None


class Hangar(models.Model):
    date_created = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)

    building = models.ForeignKey("the_hangar_hub.Building", on_delete=models.CASCADE, related_name="hangars")
    code = models.CharField(max_length=30)
    default_rent = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)  # Default passed to tenant

    capacity = models.IntegerField(default=1)
    electric = models.BooleanField(default=False)
    heated = models.BooleanField(default=False)
    water = models.BooleanField(default=False)
    wifi = models.BooleanField(default=False)
    shelves = models.BooleanField(default=False)
    auto_door = models.BooleanField(default=False)

    def present_rental_agreements(self):
        return RentalAgreement.present_rental_agreements().filter(hangar=self)

    def future_rentals(self):
        now = datetime.now(timezone.utc)
        return self.rentals.filter(start_date__gt=now)

    def past_rentals(self):
        now = datetime.now(timezone.utc)
        return self.rentals.filter(end_date__lte=now)

    def all_rentals(self):
        now = datetime.now(timezone.utc)
        return self.rentals.all()

    def rent(self):
        return self.default_rent or self.building.default_rent

    class Meta:
        unique_together = ('building', 'code',)

    @classmethod
    def get(cls, data):
        try:
            if str(data).isnumeric():
                return cls.objects.get(pk=data)
            else:
                return cls.objects.get(code=data, building__airport=env.request.airport)

        except cls.DoesNotExist:
            return None
        except Exception as ee:
            log.error(f"Could not get {cls}: {ee}")
            return None

    @classmethod
    def hangar_type_options(cls):
        return {
            "TH": "T-Hangar",
            "BH": "Box Hangar",
            "SH": "Shared Hangar",
            "SP": "Shade Port",
            "TD": "Tie-Down",
        }

    def __str__(self):
        return f"{self.building.airport.identifier}: {self.code}"

    def __repr__(self):
        return str(self)