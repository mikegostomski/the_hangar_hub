from django.db import models
from base.classes.util.log import Log
from datetime import datetime, timezone

from the_hangar_hub.models.tenant import Rental

log = Log()


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
    capacity = models.IntegerField(default=1)
    electric = models.BooleanField(default=False)
    default_rent = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)  # Default passed to tenant

    def current_rentals(self):
        return Rental.current_rentals().filter(hangar=self)

    def future_rentals(self):
        now = datetime.now(timezone.utc)
        return self.rentals.filter(start_date__gt=now)

    def past_rentals(self):
        now = datetime.now(timezone.utc)
        return self.rentals.filter(end_date__lte=now)

    def rent(self):
        return self.default_rent or self.building.default_rent

    class Meta:
        unique_together = ('building', 'code',)

    @classmethod
    def get(cls, data):
        try:
            return cls.objects.get(pk=data)
        except cls.DoesNotExist:
            return None
        except Exception as ee:
            log.error(f"Could not get {cls}: {ee}")
            return None

    def __str__(self):
        return f"{self.building.airport.identifier}: {self.code}"

    def __repr__(self):
        return str(self)