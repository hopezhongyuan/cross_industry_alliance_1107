"""定时任务：关闭支付超时订单并释放库存/时段。"""

from django.core.management.base import BaseCommand

from apps.orders.order_services import close_expired_orders


class Command(BaseCommand):
    help = "扫描并关闭支付超时订单（建议每分钟执行一次）"

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=200, help="单次最多处理条数")

    def handle(self, *args, **options):
        count = close_expired_orders(limit=options["limit"])
        self.stdout.write(f"closed={count}")
