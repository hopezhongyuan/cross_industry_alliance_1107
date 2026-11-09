"""定时任务：将过期未使用的优惠券置为已过期。"""

from django.core.management.base import BaseCommand

from apps.coupons.services import expire_coupons


class Command(BaseCommand):
    help = "扫描并将过期未使用的用户优惠券置为已过期（建议每日执行）"

    def handle(self, *args, **options):
        count = expire_coupons()
        self.stdout.write(f"expired={count}")
