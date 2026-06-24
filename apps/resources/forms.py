"""Admin forms for resources."""

from django import forms

from .models import Resource
from .partial_date import parse_partial_date, to_input_value


class ResourceAdminForm(forms.ModelForm):
    """Edit ``recorded_date`` + ``recorded_precision`` through one flexible field.

    Editors type as much of the date as they know — ``2014``, ``2014-02`` or
    ``2014-02-10`` — and the form derives the stored date and its precision. The
    raw date/precision fields are hidden so there's a single place to enter it.
    """

    recorded = forms.CharField(
        required=False,
        label="Recorded",
        help_text=(
            "Year, year-month or full date — 2014, 2014-02 or 2014-02-10. "
            "Leave out the parts you don't know."
        ),
    )

    article_date_input = forms.CharField(
        required=False,
        label="Article date",
        help_text="Year, year-month or full date — e.g. 2005, 2005-06.",
    )

    class Meta:
        model = Resource
        exclude = (
            "recorded_date",
            "recorded_precision",
            "article_date",
            "article_date_precision",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields["recorded"].initial = to_input_value(
                self.instance.recorded_date, self.instance.recorded_precision
            )
            self.fields["article_date_input"].initial = to_input_value(
                self.instance.article_date, self.instance.article_date_precision
            )

    def clean_recorded(self):
        text = self.cleaned_data.get("recorded", "")
        try:
            self._recorded = parse_partial_date(text)
        except ValueError as exc:
            raise forms.ValidationError(str(exc)) from exc
        return text

    def clean_article_date_input(self):
        text = self.cleaned_data.get("article_date_input", "")
        try:
            self._article_date = parse_partial_date(text)
        except ValueError as exc:
            raise forms.ValidationError(str(exc)) from exc
        return text

    def save(self, commit=True):
        date, precision = getattr(self, "_recorded", (None, "day"))
        self.instance.recorded_date = date
        self.instance.recorded_precision = precision
        a_date, a_precision = getattr(self, "_article_date", (None, "day"))
        self.instance.article_date = a_date
        self.instance.article_date_precision = a_precision
        return super().save(commit=commit)
