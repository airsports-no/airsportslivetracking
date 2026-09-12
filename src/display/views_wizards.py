from django import forms
from formtools.wizard.views import SessionWizardView


class SessionWizardOverrideView(SessionWizardView):
    def post(self, *args, **kwargs):
        # django-formtools >=2.6 added a per-request cache (_resolved_form_list/
        # _cache_signature) that get_form_list() populates on first call, and its own
        # post() unconditionally deletes both after a valid form - see get_form_list()'s
        # docstring. get_form() below builds forms directly without ever calling
        # get_form_list(), so on any request that only goes through this override, formtools'
        # del raised AttributeError
        # (Sentry PYTHON-DJANGO-N). Call get_form_list() once here, unconditionally, before
        # any of those bypasses run, so the cache is always primed regardless of which
        # get_form() branch this request's step actually uses. Safe against recursion: a
        # condition_dict callable that calls back into get_form_list() (e.g. via
        # get_cleaned_data_for_step -> get_form() -> get_form_list()) is caught by
        # formtools' own _check_cond_started guard.
        self.get_form_list()
        return super().post(*args, **kwargs)

    # Hack to avoid get_form_list() which leads to recursion error with conditional steps.
    def get_form(self, step=None, data=None, files=None):
        """
        Constructs the form for a given `step`. If no `step` is defined, the
        current step will be determined automatically.

        The form will be initialized using the `data` argument to prefill the
        new form. If needed, instance or queryset (for `ModelForm` or
        `ModelFormSet`) will be added too.
        """
        if step is None:
            step = self.steps.current
        form_class = self.form_list[step]
        kwargs = self.get_form_kwargs(step)
        kwargs.update(
            {
                "data": data,
                "files": files,
                "prefix": self.get_form_prefix(step, form_class),
                "initial": self.get_form_initial(step),
            }
        )
        if issubclass(form_class, (forms.ModelForm, forms.models.BaseInlineFormSet)):
            kwargs.setdefault("instance", self.get_form_instance(step))
        elif issubclass(form_class, forms.models.BaseModelFormSet):
            kwargs.setdefault("queryset", self.get_form_instance(step))
        return form_class(**kwargs)
