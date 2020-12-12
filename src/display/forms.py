from django import forms


class ImportRouteForm(forms.Form):
    CSV = "0"
    FLIGHTCONTEST_GPX = "1"
    FILE_TYPES = (
        (CSV, "csv"),
        (FLIGHTCONTEST_GPX, "FlightContest GPX file")
    )
    name = forms.CharField(max_length=100)
    file_type = forms.ChoiceField(choices=FILE_TYPES)
    file = forms.FileField()
