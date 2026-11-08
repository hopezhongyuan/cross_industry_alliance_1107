"""定时任务：商户超时未处理的售后单自动转平台仲裁。"""

from django.core.management.base import BaseCommand

from apps.aftersales.services import escalate_due_after_sales


class Command(BaseCommand):
    help = "扫描超时未处理的售后单并转平台仲裁（建议每小时执行一次）"

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=200, help="单次最多处理条数")

    def handle(self, *args, **options):
        count = escalate_due_after_sales(limit=options["limit"])
        self.stdout.write(f"escalated={count}")
