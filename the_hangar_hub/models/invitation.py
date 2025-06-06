from django.db import models
from base.classes.util.log import Log
from base.services import utility_service, message_service, email_service
from base.classes.auth.auth import Auth
from the_hangar_hub.models.airport import Airport
from django.contrib.auth.models import User

log = Log()


class Invitation(models.Model):
    date_created = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)

    airport = models.ForeignKey(Airport, models.CASCADE, related_name="invites", blank=False, null=False, db_index=True)
    email = models.CharField(max_length=128, blank=False, null=False, db_index=True)
    verification_code = models.CharField(max_length=30, blank=False, null=False)
    role = models.CharField(max_length=8, blank=False, null=False)

    invited_by = models.ForeignKey(User, models.CASCADE, related_name="has_invited", blank=False, null=False)
    resulting_user = models.ForeignKey(User, models.CASCADE, related_name="invitations", blank=True, null=True, db_index=True)

    status_code = models.CharField(max_length=1, blank=False, null=False, default="I")
    status_change_date = models.DateTimeField(auto_now_add=True)

    def send(self):
        if not self.id:
            # Error would have already been posted (ie: invite().send() when invite() fails)
            pass
        elif self.status_code == "A":
            message_service.post_warning("Did not send invitation because it was already accepted.")
        elif self.status_code == "E":
            message_service.post_warning("Did not send invitation because it has expired.")
        elif self.status_code == "R ":
            message_service.post_warning("Did not send invitation because it was revoked.")
        else:
            inviter = Auth.lookup_user(self.invited_by)
            if email_service.send(
                subject=f"Invitation to join {self.airport.identifier} on The Hanger Hub",
                sender=inviter.email,
                sender_display_name=inviter.display_name,
                to=self.email,
                email_template="the_hangar_hub/airport/invitations/invitation_email.html",
                context={"invitation": self},
                max_recipients=1,
            ):
                self.status_code = "S"
                self.save()
                return True
        return False


    @property
    def status_description(self):
        return {
            "I": "Invited (not sent)",
            "S": "Invitation Sent",
            "A": "Accepted",
            "R": "Invitation Revoked",
            "E": "Invitation Expired",
        }.get(self.status_code) or self.status_code

    @classmethod
    def invite(cls, airport, email_address, role):
        inviter = Auth().get_user()

        try:
            existing = cls.objects.get(
                airport=airport, email__iexact=email_address, role=role, invited_by=inviter.django_user()
            )
            if existing:
                # If re-inviting after expiration or revocation, reset the status
                if existing.status_code in ["E", "R"]:
                    existing.status_code = "I"
                    existing.save()
                # Otherwise do not alter or duplicate the invitation
                return existing
        except cls.DoesNotExist:
            pass
        except Exception as ee:
            log.error(f"Could not look for existing invites: {ee}")

        try:
            ii = Invitation(
                airport=airport,
                email=email_address,
                role=role,
                verification_code=utility_service.generate_verification_code(30),
                invited_by=inviter.django_user(),
                status_code="I",  # Initiated
            )
            ii.save()
            return ii
        except Exception as ee:
            log.error(f"Could not create invitation: {ee}")
            message_service.post_error(f"Unable to invite {email_address}")
            return Invitation()  # Likely will be followed by .send()

    @classmethod
    def get(cls, pk):
        try:
            return cls.objects.get(pk=pk)
        except cls.DoesNotExist:
            return None
        except Exception as ee:
            log.error(f"Could not get {cls}: {ee}")
            return None
