"""Events other modules can listen to (so they don't need to reach into jobs code)."""

from django.dispatch import Signal

#: Sent after a job's totals (hectares, amounts, status) were recalculated.
#: Arguments: ``job``.
job_totals_changed = Signal()
