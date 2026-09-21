"""Start-up checks for the module system (run by ``manage.py check`` and on start)."""

from django.core.checks import Error, register

from avifly.core.registry import registry


@register("avifly")
def check_module_dependencies(app_configs, **kwargs):
    errors = []
    for module in registry.enabled_modules():
        for required in module.requires:
            if not registry.is_enabled(required):
                errors.append(
                    Error(
                        f"Module '{module.label}' needs module '{required}', which is not enabled.",
                        hint=f"Enable '{required}' in AVIFLY_MODULES or disable '{module.label}'.",
                        id="avifly.E001",
                    )
                )
    return errors
