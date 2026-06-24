# type: ignore
from django.core.management.base import BaseCommand

from apps.settings.services import SchedulerService


class Command(BaseCommand):
    help = "Queue due NexoPOS-style scheduled jobs for every active branch."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Queue due jobs even if the same job already exists in the current schedule window.",
        )

    def handle(self, *args, **options):
        result = SchedulerService.enqueueDue(force=options["force"])
        self.stdout.write(f"Scheduler checked at {result['checked_at']}.")

        for item in result["enqueued"]:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Queued {item['job']} for branch #{item['branch_id']} as job #{item['job_id']} ({item['schedule']})."
                )
            )

        for item in result["skipped"]:
            label = item.get("job") or "branch"
            self.stdout.write(self.style.WARNING(f"Skipped {label} for branch #{item['branch_id']}: {item['reason']}."))

        self.stdout.write(
            self.style.SUCCESS(
                f"Scheduler complete. Queued {len(result['enqueued'])} job(s), skipped {len(result['skipped'])} item(s)."
            )
        )
