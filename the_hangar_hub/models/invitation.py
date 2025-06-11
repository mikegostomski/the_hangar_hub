from django.db import models
from base.classes.util.log import Log
from base.services import utility_service, message_service, email_service, auth_service
from base.classes.auth.auth import Auth
from the_hangar_hub.models.airport import Airport
from django.contrib.auth.models import User
from datetime import datetime, timezone

log = Log()


class Invitation(models.Model):
    date_created = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)

    airport = models.ForeignKey(Airport, models.CASCADE, related_name="invites", blank=False, null=False, db_index=True)
    email = models.CharField(max_length=128, blank=False, null=False, db_index=True)
    verification_code = models.CharField(max_length=30, blank=False, null=False)
    role = models.CharField(max_length=8, blank=False, null=False)

    invited_by = models.ForeignKey(User, models.CASCADE, related_name="has_invited", blank=False, null=False)
    tenant = models.ForeignKey('the_hangar_hub.Tenant', models.CASCADE, related_name="invitations", blank=True, null=True, db_index=True)
    hangar = models.ForeignKey('the_hangar_hub.Hangar', models.CASCADE, related_name="invitations", blank=True, null=True)
    resulting_user = models.ForeignKey(User, models.CASCADE, related_name="invitations", blank=True, null=True, db_index=True)

    status_code = models.CharField(max_length=1, blank=False, null=False, default="I")
    status_change_date = models.DateTimeField(auto_now_add=True)

    def change_status(self, new_status):
        self.status_code = new_status
        self.status_change_date = datetime.now(timezone.utc)

    @property
    def status_description(self):
        return {
            "I": "Invited (not sent)",
            "S": "Invitation Sent",
            "A": "Accepted",
            "R": "Invitation Revoked",
            "E": "Invitation Expired",
        }.get(self.status_code) or self.status_code

    @property
    def role_description(self):
        return {
            "MANAGER": "Airport Manager",
            "TENANT": "Hangar Tenant",
        }.get(self.role) or self.role

    @property
    def invited_by_user_profile(self):
        return auth_service.lookup_user(self.invited_by)

    @property
    def resulting_user_profile(self):
        if self.resulting_user:
            return auth_service.lookup_user(self.resulting_user)
        else:
            return None

    def is_invalid(self, post_errors=False):
        msg = None
        if self.status_code in ["E", "R"]:
            msg = "This invitation has expired"
        elif self.status_code == "A":
            msg = "This invitation has already been accepted"
        if msg and post_errors:
            message_service.post_error(msg)
        return msg

    def is_valid(self, post_errors=False):
        return not self.is_invalid(post_errors)


    def send(self):
        """
        Send this invitation
        """
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
                context={"invite": self},
                max_recipients=1,
                include_context=True
            ):
                self.status_code = "S"
                self.save()
                return True
        return False

    @classmethod
    def invite(cls, airport, email_address, role, hangar=None):
        """
        Invite someone to join specified airport via their email address
        """
        inviter = Auth().get_user()

        try:
            existing = cls.objects.get(
                airport=airport, email__iexact=email_address, role=role, invited_by=inviter.user
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
                invited_by=inviter.user,
                status_code="I",  # Initiated
            )
            ii.save()
            return ii
        except Exception as ee:
            log.error(f"Could not create invitation: {ee}")
            message_service.post_error(f"Unable to invite {email_address}")
            return Invitation()  # Likely will be followed by .send()

    @classmethod
    def get(cls, key):
        try:
            if str(key).isnumeric():
                return cls.objects.get(pk=key)
            else:
                return cls.objects.get(verification_code=key)
        except cls.DoesNotExist:
            return None
        except Exception as ee:
            log.error(f"Could not get {cls}: {ee}")
            return None
