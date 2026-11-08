"""定时任务：扫描到期结算项，生成待发布结算批次。"""

from django.core.management.base import BaseCommand

from apps.ledger.services import create_settlement_batch


class Command(BaseCommand):
    help = "扫描到期结算项并生成待发布批次（建议每日执行一次）"

    def handle(self, *args, **options):
        batch = create_settlement_batch()
        if batch is None:
            self.stdout.write("created=0")
        else:
            self.stdout.write(f"created=1 batch_no={batch.batch_no} net_amount={batch.net_amount}")
