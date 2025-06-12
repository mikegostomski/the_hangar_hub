from django.db import models
from base.classes.util.log import Log
from base.services import utility_service, message_service, email_service, auth_service
from base.classes.auth.session import Auth
from the_hangar_hub.models.airport import Airport
from django.contrib.auth.models import User
from datetime import datetime, timezone
from the_hangar_hub.services import airport_service

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
        return auth_service.lookup_user_profile(self.invited_by)

    @property
    def resulting_user_profile(self):
        if self.resulting_user:
            return auth_service.lookup_user_profile(self.resulting_user)
        else:
            return None

    def is_inactive(self, post_errors=False):
        msg = None
        if self.status_code in ["E", "R"]:
            msg = "This invitation has expired"
        elif self.status_code == "A":
            msg = "This invitation has already been accepted"
        if msg and post_errors:
            message_service.post_error(msg)
        return msg

    def is_active(self, post_errors=False):
        return not self.is_inactive(post_errors)

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
            inviter = Auth.lookup_user_profile(self.invited_by)
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

    def accept(self):
        """
        Accept an invitation and do any necessary processing
        """
        if self.status_code in ["E", "R"]:
            log.warning("Cannot accept an expired invitation")
            return False
        elif self.status_code == "A":
            log.warning("Invitation has already been accepted")
            return False

        # Invitations can only be accepted by the invited user
        user_profile = Auth.current_user_profile()
        if self.email.lower() not in user_profile.emails:
            log.warning("Invitation can only be accepted by the invited person")
            return False

        # Django user object is used for all relations
        user = user_profile.user

        # Accept airport manager invitation
        if self.role == "MANAGER":
            if airport_service.set_airport_manager(self.airport, user):
                message_service.post_success(f"bi-airplane You are now a manager for {self.airport.display_name}")
                self.resulting_user = user
                self.change_status("A")
                self.save()
                return True

        elif self.role == "TENANT" and self.hangar:
            if not self.tenant.user:
                self.tenant.user = user
                self.tenant.save()

            self.resulting_user = user
            self.change_status("A")
            self.save()
            return True

        return False

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

    @classmethod
    def invite_manager(cls, airport, email_address):
        """
        Invite someone to be an airport manager
        """
        return Invitation(
            airport=airport,
            email=email_address,
            role="MANAGER",
            verification_code=utility_service.generate_verification_code(30),
            invited_by=Auth.current_user(),
            status_code="I",  # Initiated
        )._finalize().send()


    @classmethod
    def invite_tenant(cls, airport, email_address, tenant, hangar):
        """
        Invite someone to be an airport tenant
        """
        return Invitation(
            airport=airport,
            tenant=tenant,
            hangar=hangar,
            email=email_address,
            role="TENANT",
            verification_code=utility_service.generate_verification_code(30),
            invited_by=Auth.current_user(),
            status_code="I",  # Initiated
        )._finalize().send()

    @classmethod
    def find(cls):
        """Find any active invitations for the current user"""
        user_profile = Auth.current_user_profile()
        invitations = []
        for email in user_profile.emails:
            invitations.extend(list(Invitation.objects.filter(email__iexact=email, status_code__in=["I", "S"])))
        log.debug(f"{user_profile} has {len(invitations)} invitations")
        return invitations


    def _check_preexisting(self):
        try:
            # Look for other invitations from this inviter
            existing = Invitation.objects.get(
                airport=self.airport,
                role=self.role,
                invited_by=self.invited_by,
                email__iexact=self.email_address,
                hangar=self.hangar
            )
            if existing:
                # If re-inviting after expiration or revocation, reset the status
                if existing.status_code in ["E", "R"]:
                    existing.status_code = "I"
                    existing.save()
                # Otherwise do not alter or duplicate the invitation
                return existing
        except Invitation.DoesNotExist:
            pass
        except Exception as ee:
            log.error(f"Could not look for existing invites: {ee}")
        return None

    def _finalize(self):
        try:
            # Before saving, look for an existing invite that can be reused
            reuse = self._check_preexisting()
            if reuse:
                del self
                return reuse
            else:
                self.save()
                return self
        except Exception as ee:
            log.error(f"Could not create invitation: {ee}")
        message_service.post_error(f"Unable to invite {self.email}")
        return Invitation()  # Likely will be followed by .send()


