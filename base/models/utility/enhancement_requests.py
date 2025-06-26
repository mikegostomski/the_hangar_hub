from django.db import models
from base.classes.util.env_helper import EnvHelper, Log
from base.classes.util.date_helper import DateHelper
from base.classes.auth.session import Auth

log = Log()
env = EnvHelper()

class EnhancementRequestManager(models.Manager):
    def get_queryset(self):
        return super(EnhancementRequestManager, self).get_queryset().prefetch_related('votes')

class EnhancementRequest(models.Model):
    objects = EnhancementRequestManager()

    date_created = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey("auth.User", models.CASCADE, related_name="enhancement_requests", db_index=True)

    status_code = models.CharField(max_length=1, default="N", db_index=True)
    request_type_code = models.CharField(max_length=1, default="F")
    summary = models.CharField(max_length=120)
    detail = models.TextField()

    def cu_vote(self):
        try:
            return self.votes.get(user=Auth.current_user())
        except:
            return None

    def get_vote_stats(self):
        votes = [x.value for x in self.votes.all()]
        score = sum(votes)
        num = len(votes)
        return votes, score, num

    def score(self):
        v, s, n = self.get_vote_stats()
        return s

    def num_votes(self):
        v, s, n = self.get_vote_stats()
        return n

    def votes_display(self):
        v, s, n = self.get_vote_stats()
        x = "+" if s > 0 else ""
        return f"{x}{s} ({n} votes)"

    @staticmethod
    def status_options():
        return {
            "N": "New",
            "C": "Completed",
            "M": "Merged",
            "D": "Deleted",
        }

    @property
    def status(self):
        return self.status_options().get(self.status_code) or self.status_code

    @staticmethod
    def request_type_options():
        return {
            "F": "Feature Request",
            "B": "Bug Report",
        }

    @property
    def request_type(self):
        return self.request_type_options().get(self.request_type_code) or self.request_type_code

    @property
    def date_created_helper(self):
        return DateHelper(self.date_created)

    @classmethod
    def get(cls, pk):
        try:
            return cls.objects.get(pk=pk)
        except cls.DoesNotExist:
            return None
        except Exception as ee:
            log.error(f"Could not get {cls}: {ee}")
            return None


class EnhancementVote(models.Model):
    date_created = models.DateTimeField(auto_now_add=True)
    enhancement = models.ForeignKey(EnhancementRequest, models.CASCADE, related_name="votes", db_index=True)
    user = models.ForeignKey("auth.User", models.CASCADE, related_name="enhancement_votes", db_index=True)
    value = models.IntegerField()  # +1/-1

    class Meta:
        unique_together = ('enhancement', 'user',)

    @classmethod
    def get(cls, pk):
        try:
            return cls.objects.get(pk=pk)
        except cls.DoesNotExist:
            return None
        except Exception as ee:
            log.error(f"Could not get {cls}: {ee}")
            return None