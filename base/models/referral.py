from django.db import models
from django.contrib.auth.models import User
from base.classes.util.log import Log
from base.services import utility_service
from datetime import datetime, timezone, timedelta
from base.models.utility.variable import Variable
from base.classes.auth.session import Auth


log = Log()


class Referral(models.Model):
    date_created = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="referrals")
    code = models.CharField(max_length=10, unique=True, db_index=True)
    status_code = models.CharField(max_length=1, default="A")

    # New (referred) user may be offered a discount (percentage if less than 1)
    discount = models.DecimalField(max_digits=5, decimal_places=2)

    # Referrer may get a reward (percentage if less than 1)
    reward = models.DecimalField(max_digits=5, decimal_places=2)
    reward_type_code = models.CharField(max_length=1, default="C")
    reward_balance = models.DecimalField(max_digits=8, decimal_places=2)
    reward_cap = models.DecimalField(max_digits=8, decimal_places=2)

    # Collections of rewards may be infinite, or until a date, or for number of days after referral accepted
    reward_expiration_date = models.DateTimeField(null=True, blank=True)
    reward_expiration_days = models.IntegerField(null=True, blank=True)

    def apply_recurring_reward(self, tx_amount, referral_date):
        """
        Add reward to reward_balance.
        This applies only to percentage rewards collected on transactions by referred users
        """
        if not self._can_collect_this_reward(referral_date):
            return 0

        if self.reward >= 1.0:
            return 0

        reward_amount = self.reward * tx_amount
        if self.reward_cap and self.reward_balance + reward_amount > self.reward_cap:
            reward_amount = self.reward_cap - self.reward_balance

        self.reward_balance += reward_amount
        self.save()
        return reward_amount

    def apply_single_reward(self, referral_date):
        """
        Add reward to reward_balance.
        This applies only to per-referral rewards
        """
        if not self._can_collect_this_reward(referral_date):
            return 0

        if self.reward < 1.0:
            return 0

        reward_amount = self.reward
        if self.reward_cap and self.reward_balance + reward_amount > self.reward_cap:
            reward_amount = self.reward_cap - self.reward_balance

        self.reward_balance += reward_amount
        self.save()
        return reward_amount


    @property
    def can_refer(self):
        return self.status_code in ["A"]

    @property
    def can_collect_rewards(self):
        if self.reward_cap and self.reward_balance >= self.reward_cap:
            return False

        if self.reward_expiration_date:
            now = datetime.now(timezone.utc)
            if self.reward_expiration_date > now:
                return False

        return self.status_code in ["A", "L"]

    @staticmethod
    def status_options():
        return {
            "A": "Active",  # Can refer others, can collect rewards
            "L": "Legacy",  # Can no longer refer others, but can still collect reward
            "E": "Expired", # Can no longer refer or collect rewards after an expiration date/period
            "R": "Revoked", # Can no longer refer or collect rewards after admin removal
        }

    @property
    def status(self):
        return self.status_options().get(self.status_code) or self.status_code

    @staticmethod
    def reward_type_options():
        return {
            "C": "Credit",      # Rewards are credited to account
            "D": "Dollars",     # Rewards are paid in cash
        }

    @property
    def reward_type(self):
        return self.reward_type_options().get(self.reward_type_code) or self.reward_type_code

    @classmethod
    def reward_description(cls, reward_instance=None):
        log.trace([reward_instance])
        you_get = None
        they_get = None
        details = None

        if reward_instance:
            reward = reward_instance.reward
            reward_expiration_date = reward_instance.reward_expiration_date
            reward_expiration_days = reward_instance.reward_expiration_days
            reward_type_code = reward_instance.reward_type_code
            reward_cap = reward_instance.reward_cap
            discount = reward_instance.discount
        else:
            reward = Variable.get_value("referral_reward", 0, "decimal")
            reward_expiration_date = Variable.get_value("referral_reward_expiration_date", None, "date")
            reward_expiration_days = Variable.get_value("referral_reward_expiration_days", 0, "int")
            reward_type_code = Variable.get_value("referral_reward_type_code", "C")
            reward_cap = Variable.get_value("referral_reward_cap", 500, "decimal")
            discount = Variable.get_value("referral_discount", 0, "decimal")

        if not discount:
            they_get = "Access to our wonderful service."
        elif discount < 1:
            they_get = f"A {int(discount * 100)}% discount."
        else:
            they_get = f"A ${int(discount)} statement credit."

        if not reward:
            you_get = "A warm fuzzy feeling."
        else:
            if reward < 1:
                you_get = f"{int(reward * 100)}% commission on referred purchases"
                if reward_expiration_days:
                    you_get += f" made within {reward_expiration_days} days of referral."
            else:
                you_get = f"${reward} per referral."

            details = ""
            if reward_expiration_date:
                details += f"Offer expires {reward_expiration_date}. "
            if reward_cap:
                details += f"Maximum reward value: {reward_cap}. "
            if reward_type_code == "C":
                details += f"Reward will be distributed as an account credit. "
            elif reward_type_code == "D":
                details += f"Reward will be paid out in cash. "

        return you_get, they_get, details.strip() if details else None

    def populate(self, user=None):
        # Generate a unique referral code
        self.code = utility_service.generate_verification_code(10)
        while Referral.objects.filter(code=self.code).count() > 0 or self.code.isnumeric():
            self.code = utility_service.generate_verification_code(10)

        if user is None:
            user = Auth.current_user()

        self.user = user
        self.status_code = "A"
        self.reward_balance = 0
        self.reward = Variable.get_value("referral_reward", 0, "decimal")
        self.reward_expiration_date = Variable.get_value("referral_reward_expiration_date", None, "date")
        self.reward_expiration_days = Variable.get_value("referral_reward_expiration_days", 0, "int")
        self.reward_type_code = Variable.get_value("referral_reward_type_code", "C")
        self.reward_cap = Variable.get_value("referral_reward_cap", 500, "decimal")
        self.discount = Variable.get_value("referral_discount", 0, "decimal")

    def _can_collect_this_reward(self, referral_date):
        if not self.can_collect_rewards:
            return False

        if self.reward_expiration_days:
            if not referral_date:
                log.error("Cannot collect reward - Referral date is not known.")
                return False

            now = datetime.now(timezone.utc)
            if (referral_date + timedelta(days=self.reward_expiration_days)) > now:
                log.info("Reward collection period has expired")
                return False

        return True

    @classmethod
    def get(cls, id_or_code):
        try:
            if str(id_or_code).isnumeric():
                return cls.objects.get(pk=id_or_code)
            else:
                return cls.objects.get(code=id_or_code.upper())
        except cls.DoesNotExist:
            return None
        except Exception as ee:
            log.error(f"Could not get {cls}: {ee}")
            return None
