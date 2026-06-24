import time
from django.core.management.base import BaseCommand
from apps.settings.services import JobQueueService

class Command(BaseCommand):
    help = "Run the NexoPOS queue worker to process pending enqueued jobs."

    def add_arguments(self, parser):
        parser.add_argument(
            "--daemon",
            action="store_true",
            help="Run the queue worker in a loop (daemon mode).",
        )
        parser.add_argument(
            "--sleep",
            type=int,
            default=5,
            help="Seconds to sleep when no jobs are found (only in daemon mode).",
        )
        parser.add_argument(
            "--queue",
            type=str,
            default="default",
            help="The specific queue to process.",
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("Starting NexoPOS Queue Worker..."))
        
        handlers = JobQueueService.handlers()

        daemon_mode = options["daemon"]
        sleep_time = options["sleep"]
        queue_name = options["queue"]

        self.stdout.write(f"Loaded {len(handlers)} job handlers: {', '.join(sorted(handlers.keys()))}")
        self.stdout.write(f"Listening on queue: '{queue_name}'")

        if daemon_mode:
            self.stdout.write("Running in daemon mode. Press Ctrl+C to exit.")
            try:
                while True:
                    result = JobQueueService.runNext(handlers, queue=queue_name)
                    if result:
                        if result["status"] == "completed":
                            self.stdout.write(self.style.SUCCESS(f"Processed job {result['job_id']} successfully."))
                        else:
                            self.stdout.write(self.style.ERROR(f"Job {result['job_id']} failed: {result['reason']}"))
                    else:
                        time.sleep(sleep_time)
            except KeyboardInterrupt:
                self.stdout.write(self.style.WARNING("Queue worker stopped by user."))
        else:
            self.stdout.write("Running in single-run mode...")
            processed_count = 0
            while True:
                result = JobQueueService.runNext(handlers, queue=queue_name)
                if not result:
                    break
                processed_count += 1
                if result["status"] == "completed":
                    self.stdout.write(self.style.SUCCESS(f"Processed job {result['job_id']} successfully."))
                else:
                    self.stdout.write(self.style.ERROR(f"Job {result['job_id']} failed: {result['reason']}"))
            self.stdout.write(self.style.SUCCESS(f"Queue worker finished. Processed {processed_count} job(s)."))
