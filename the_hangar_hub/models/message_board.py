from django.db import models
from base.models.utility.error import Error, Log, EnvHelper
from base.classes.auth.session import Auth
from the_hangar_hub.services import airport_service

log = Log()
env = EnvHelper()


class PostGroup:
    """
    NOT A MODEL

    This is used to group messages and replies, and help determine who can see and/or update posts
    """
    post = None     # A single MessageBoardEntry object
    replies = None  # A list of MessageBoardEntry objects in response to `post`

    """
    ---------------------------------------------------------------------------
    Shortcut/Alias to Post attributes
    ---------------------------------------------------------------------------
    """
    @property
    def date_created(self):
        return self.post.date_created

    @property
    def last_updated(self):
        return self.post.last_updated

    @property
    def thread(self):
        return self.post.thread

    @property
    def user(self):
        return self.post.user

    @property
    def in_response_to(self):
        return self.post.in_response_to

    @property
    def role_display(self):
        return self.post.role_display

    @property
    def content(self):
        return self.post.content

    @property
    def visibility_code(self):
        return self.post.visibility_code

    """
    ---------------------------------------------------------------------------
    STATUS
    (flagged, reviewed, deleted)
    ---------------------------------------------------------------------------
    """

    @property
    def is_deleted(self):
        return self.post.deleted

    @property
    def is_flagged_for_review(self):
        if self.post.flagged:
            # flag remains set and is overridden by the review
            # (this prevents re-flagging/reviewing the same request multiple times)
            return not self.has_been_reviewed
        return False

    @property
    def has_been_reviewed(self):
        # Choosing to delete is a form of review
        return self.post.reviewed or self.post.deleted

    @property
    def is_clean(self):
        # Neither flagged nor deleted
        if self.is_deleted:
            return False
        if self.is_flagged_for_review:
            return False
        return True

    @property
    def is_displayed(self):
        return self.display_mode() in ["VIEW", "PLACEHOLDER"]

    """
    ---------------------------------------------------------------------------
    METADATA
    (number of replies, users who have replied, etc)
    ---------------------------------------------------------------------------
    """

    @property
    def reply_counts(self):

        direct_replies = len([x for x in self.replies if x.is_displayed])
        indirect_replies = 0

        if self.replies:
            for reply in [x for x in self.replies if x.is_displayed]:
                d, t = reply.reply_counts
                indirect_replies += t

        total_replies = direct_replies + indirect_replies
        return direct_replies, total_replies

    @property
    def direct_replies(self):
        d, t = self.reply_counts
        return d

    @property
    def total_replies(self):
        d, t = self.reply_counts
        return t

    @property
    def total_replies_display(self):
        d, t = self.reply_counts
        if t == 1:
            return f"{t} reply"
        return f"{t} replies"

    @property
    def replier_ids(self):
        """
        Returns a list of auth.User ids that have replied to this post (or replies of replies)
        """
        repliers = [x.user.id for x in self.replies]
        if self.replies:
            for reply in [x for x in self.replies]:
                repliers.extend(reply.replier_ids)
        return list(set(repliers))

    @property
    def contains_flagged_post(self):
        """
        Have replies to this post been flagged?
        (does not consider THIS post)
        """
        if self.is_deleted:
            return False
        if self.replies:
            if [x for x in self.replies if x.is_flagged_for_review]:
                return True  # Direct reply has been flagged
            if [x for x in self.replies if x.contains_flagged_post]:
                return True  # Reply to reply has been flagged
        return False

    """
    ---------------------------------------------------------------------------
    PERMISSIONS
        * Message boards will only be displayed from views that require an airport (request.airport)
    ---------------------------------------------------------------------------
    """
    def can_alter_post(self):
        user_profile = Auth.current_user_profile()

        # Posts can be altered by developers, managers, and their poster
        if user_profile.has_authority("developer"):
            return True
        elif airport_service.manages_this_airport():
            return True
        elif self.post.user.id == user_profile.id:
            # The poster can no longer alter after deletion
            # (a flagged request could be altered)
            return not self.is_deleted
        return False

    def can_view_post(self):
        user_profile = Auth.current_user_profile()

        # Messages can always be seen by developers, managers, and their poster
        # (this includes flagged and deleted posts)
        if self.can_alter_post():
            return True
        elif self.post.user.id == user_profile.id:
            # This allows viewing one's deleted post
            return True
        # Also anyone who has posted a reply downstream of this post
        elif user_profile.id in self.replier_ids:
            return True

        # Other users may not see flagged or deleted posts
        elif self.is_deleted:
            return False
        elif self.is_flagged_for_review:
            return False

        # Anyone else may view this
        return True

    def can_delete_post(self):
        if self.is_deleted:
            return False

        # If you can't view it, you can't delete it
        if not self.can_view_post():
            return False

        if self.direct_replies == 0:
            # Devs, Mgrs, and poster can delete when nobody has replied to it
            return self.can_alter_post()
        else:
            # Devs and mgrs can delete any message
            user_profile = Auth.current_user_profile()
            if user_profile.has_authority("developer"):
                return True
            elif airport_service.manages_this_airport():
                return True

        return False

    def can_recycle_post(self):
        if self.is_deleted:
            # Devs and mgrs can un-delete any message
            user_profile = Auth.current_user_profile()
            if user_profile.has_authority("developer"):
                return True
            elif airport_service.manages_this_airport():
                return True
        return False

    def can_review_post(self):
        if not self.is_flagged_for_review:
            return False

        # Devs and mgrs can review any flagged message
        user_profile = Auth.current_user_profile()
        if user_profile.has_authority("developer"):
            return True
        elif airport_service.manages_this_airport():
            return True
        return False

    def can_flag_post(self):
        if self.is_deleted:
            return False
        if self.is_flagged_for_review:
            return False
        # Anyone who can view can flag
        return self.can_view_post()


    def display_mode(self):
        """
        VIEW - Normal display
        PLACEHOLDER - Indication of flagged or deleted post
        HIDDEN - Not shown, but may be un-hidden if desired
        SKIP - Not on the page at all
        """
        if self.is_clean:
            return "VIEW"

        else:
            user_profile = Auth.current_user_profile()
            is_developer = user_profile.has_authority("developer")
            is_manager = airport_service.manages_this_airport()
            is_poster =  self.post.user.id == user_profile.id

            if self.is_flagged_for_review:
                if is_developer or is_manager:
                    return "VIEW"
                elif is_poster:
                    return "PLACEHOLDER"
                else:
                    return "SKIP"

            elif self.is_deleted:
                if is_developer:
                    return "VIEW"
                elif is_manager:
                    return "HIDDEN"
                elif is_poster:
                    return "PLACEHOLDER"
                else:
                    return "SKIP"

            # Unhandled non-clean condition?
            log.warning(f"Unknown non-clean condition in message #{self.post.id}")
            return "VIEW" if is_developer else "SKIP"


    def __init__(self, post, all_posts):
        self.post = post
        self.replies = []
        for pp in [entry for entry in all_posts if entry.in_response_to and entry.in_response_to.id == post.id]:
            self.replies.append(PostGroup(pp, all_posts))


class MessageBoardThread(models.Model):
    date_created = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)
    airport = models.ForeignKey("the_hangar_hub.Airport", on_delete=models.CASCADE,
                                related_name="message_board_threads", db_index=True)
    # tenant = models.ForeignKey("the_hangar_hub.Tenant", on_delete=models.CASCADE, related_name="message_board_threads", null=True, blank=True)
    user = models.ForeignKey("auth.User", on_delete=models.CASCADE, related_name="message_board_threads", db_index=True)
    topic = models.CharField(max_length=100)

    def posts(self):
        all_posts = self.entries.all().order_by("date_created")
        return PostGroup(all_posts[0], all_posts)

    @classmethod
    def get(cls, pk):
        try:
            return cls.objects.get(pk=pk)
        except cls.DoesNotExist:
            return None
        except Exception as ee:
            log.error(f"Could not get {cls}: {ee}")
            return None


class MessageBoardEntry(models.Model):
    date_created = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)
    thread = models.ForeignKey(MessageBoardThread, on_delete=models.CASCADE, related_name="entries", db_index=True)
    user = models.ForeignKey("auth.User", on_delete=models.CASCADE, related_name="message_board_entries", db_index=True)
    in_response_to = models.ForeignKey("the_hangar_hub.MessageBoardEntry", on_delete=models.CASCADE,
                                       related_name="replies", null=True, blank=True, db_index=True)
    role_display = models.CharField(max_length=30)
    content = models.TextField()
    visibility_code = models.CharField(max_length=1)  # [P]ublic or [D]irect
    flagged = models.BooleanField(default=False)
    reviewed = models.BooleanField(default=False)
    deleted = models.BooleanField(default=False)

    @classmethod
    def visibility_options(cls):
        return {
            "P": "Public",
            "D": "Direct Message"
        }

    @classmethod
    def get(cls, pk):
        try:
            return cls.objects.get(pk=pk)
        except cls.DoesNotExist:
            return None
        except Exception as ee:
            log.error(f"Could not get {cls}: {ee}")
            return None
