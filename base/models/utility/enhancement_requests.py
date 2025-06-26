from django.db import models
from base.classes.util.env_helper import EnvHelper, Log
from base.classes.util.date_helper import DateHelper

log = Log()
env = EnvHelper()


class EnhancementRequest(models.Model):
    date_created = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey("auth.User", models.CASCADE, related_name="enhancement_requests", db_index=True)

    status_code = models.CharField(max_length=1, default="N", db_index=True)
    summary = models.CharField(max_length=120)
    detail = models.TextField()

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

    @property
    def date_created_helper(self):
        return DateHelper(self.date_created)


class EnhancementVote(models.Model):
    date_created = models.DateTimeField(auto_now_add=True)
    enhancement = models.ForeignKey(EnhancementRequest, models.CASCADE, related_name="votes", db_index=True)
    user = models.ForeignKey("auth.User", models.CASCADE, related_name="enhancement_votes", db_index=True)
    value = models.IntegerField()  # +1/-1
