# Writing a module

A module is a normal Django app inside `avifly/` that registers what it adds. As an
example, here is the outline of an "invoices" module that would add invoice numbers and
due dates on top of payments.

## 1. The app config

```python
# avifly/invoices/apps.py
from django.utils.translation import gettext_lazy as _

from avifly.core.modules import AviflyModule
from avifly.core.registry import Component, MenuItem, PermissionSection, Registry


class InvoicesConfig(AviflyModule):
    default = True               # required: apps.py also imports the base class
    name = "avifly.invoices"
    label = "invoices"
    verbose_name = _("Invoices")
    requires = ("core", "jobs", "money")   # checked at start-up
    url_prefix = "invoices/"               # where urls.py is mounted

    def register(self, registry: Registry) -> None:
        registry.add_menu_item(MenuItem(
            key="invoices", label=_("Invoices"), url_name="invoices:list",
            icon="file-earmark-text", permission="invoices.view_invoice", order=35,
        ))
        registry.add_permission_section(PermissionSection(
            key="invoices", label=_("Invoices"), model="invoices.invoice", order=35,
        ))
        registry.add_component("jobs.job_detail", Component(
            key="invoices.job_panel",
            template_name="invoices/components/job_panel.html",
            permission="invoices.view_invoice",
            get_context=lambda request, job: {"invoice": job.invoices.first()},
        ))
```

Turn it on by adding `avifly.invoices` to `AVIFLY_MODULES` in `.env`.

## 2. What you can plug into

| Registry call | Used for |
|---|---|
| `add_menu_item(MenuItem(..., area="main" \| "settings" \| "quick"))` | navigation, settings page, dashboard buttons |
| `add_component(slot, Component(...))` | a template rendered into another page |
| `add_lookup(LookupList(Model, fields=...))` | an editable list under Settings (model subclasses `core.models.LookupModel`) |
| `add_permission_section(PermissionSection(...))` | a row in the role editor |
| `add_trashable(TrashableModel(Model, permission=...))` | deleted rows listed in the bin (model subclasses `SoftDeleteModel`) |
| `add_media_folder("invoices/", "invoices.view_invoice")` | who may open uploaded files in that folder |
| `add_extension(point, obj)` | anything another module defines as an extension point |

Slots available today:
- `core.dashboard`
- `jobs.job_detail`
- `customers.customer_detail` and `customers.customer_actions`
- `equipment.equipment_detail` and `equipment.equipment_actions`

Extension points:

| Extension point | What goes in it |
|---|---|
| `jobs.job_form` | `JobFormSection` subclasses, e.g. the payment section |
| `imports.importers` | `BaseImporter` subclasses |
| `customers.customer_delete_blockers`, `customers.field_delete_blockers`, `equipment.delete_blockers` | callables returning a reason, or `None` |

Events: `avifly.jobs.signals.job_totals_changed(job=...)` fires whenever a job's totals
are recalculated.

## 3. A new file importer

```python
from avifly.imports.base import BaseImporter, ImportedRecord, ImportFileError


class SmartFarmImporter(BaseImporter):
    key = "smartfarm"            # stored on imported days; keep it stable
    label = "DJI SmartFarm export"
    description = "Operation records exported from SmartFarm Web."
    accept = ".csv,.xlsx"

    def parse(self, upload) -> list[ImportedRecord]:
        ...  # one ImportedRecord per day of work; raise ImportFileError for bad files
```

Register it with `registry.add_extension(IMPORTERS, SmartFarmImporter())` in any
module's `register()`. It then appears on the import page. Each record's
`external_id` stops the same flight from being imported twice.

## 4. Conventions

- Business lists are data (lookup models), not code constants.
- Models with money or history: subclass `TimeStampedModel` + `SoftDeleteModel`, and
  register them with auditlog in `register()`.
- Views use `core.mixins.PermissionRequired`. Every page needs sign-in by default
  (`LoginRequiredMiddleware`).
- Templates extend `base.html`. Forms render themselves with Bootstrap through the
  project's form renderer.
- Add tests next to the module (`avifly/<module>/tests/`). Run `make check`.
