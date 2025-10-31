from django.db import models


class Infotext(models.Model):
    """User-editable text"""

    # Fields
    app_code = models.CharField(
        max_length=15,
        verbose_name="Application Code",
        help_text="Application that this text belongs to",
    )
    text_code = models.CharField(
        max_length=256,
        verbose_name="Text Identifier",
        help_text="Unique identifier for this text instance",
    )
    user_edited = models.CharField(
        max_length=1,
        help_text="Has this text been modified from its coded value?",
        default="N",
        choices=(("N", "No"), ("Y", "Yes")),
    )
    content = models.TextField(verbose_name="Text Content")
    last_updated = models.DateTimeField(auto_now=True)

    # Allow text to be grouped on the edit page (to find it easier)
    group_title = models.CharField(max_length=100, blank=True, null=True)

    def set_content(self, new_content):
        self.content = new_content
        self.user_edited = "Y"
        self.save()

    def __str__(self):
        return self.text_code if self.text_code else ""

    @classmethod
    def get(cls, pk):
        """
        Get from ID
        """
        try:
            return cls.objects.get(pk=pk)
        except cls.DoesNotExist:
            return None
