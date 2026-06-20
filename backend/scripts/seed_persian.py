"""Seed script — 30 Persian-language issues with rich timeline items.

Usage:
    docker compose exec api python -m scripts.seed_persian
"""

import asyncio
import random
from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.config import settings
from app.db.models.issue import Issue, IssueSeverity, IssueStatus
from app.db.models.issue_timeline import IssueTimeline, TimelineEventType
from app.db.models.inbox_item import InboxItem

NOW = datetime.now(tz=timezone.utc)

ISSUES_DATA = [
    # Blocker
    dict(
        title="خرابی کامل صفحه پرداخت در اندروید ۱۴",
        description=(
            "پس از آخرین بروزرسانی اندروید ۱۴، صفحه پرداخت به طور کامل کرش می‌کند. "
            "کاربران قادر به تکمیل خرید نیستند و پیام خطای «NullPointerException» در لاگ‌ها مشاهده می‌شود. "
            "این مشکل روی تمام دستگاه‌های Pixel و Samsung با اندروید ۱۴ تایید شده است."
        ),
        severity=IssueSeverity.blocker, status=IssueStatus.in_progress, is_release_blocker=True,
        labels=["پرداخت", "اندروید", "کرش"],
        environment_name="production", environment_os="Android 14", environment_browser=None,
        reproduction_steps=[
            {"step_order": 1, "description": "وارد حساب کاربری شوید", "expected_result": "ورود موفق", "actual_result": "ورود موفق"},
            {"step_order": 2, "description": "محصولی را به سبد خرید اضافه کنید", "expected_result": "محصول اضافه شود", "actual_result": "محصول اضافه می‌شود"},
            {"step_order": 3, "description": "روی دکمه «پرداخت» کلیک کنید", "expected_result": "صفحه پرداخت باز شود", "actual_result": "اپلیکیشن کرش می‌کند"},
        ],
        comments=[
            ("sajjad", "این باگ باید فوری بررسی بشه. تیم پرداخت لطفاً در جریان باشه."),
            ("priya", "کرش را روی Pixel 8 Pro و Samsung Galaxy S24 تأیید کردم. stacktrace رو ضمیمه می‌کنم."),
            ("tom", "بررسی کردم، مشکل از تغییر API پرداخت در اندروید ۱۴ هست. در حال رفع هستم."),
            ("sajjad", "ممنون تام. آیا می‌تونیم تا فردا صبح یه hotfix بزنیم؟"),
            ("tom", "بله، فیکس آماده‌ست. در حال تست نهایی هستم."),
        ],
        status_changes=[("new", "in_progress", "sajjad")],
    ),
    # Blocker
    dict(
        title="حلقه بی‌نهایت refresh توکن احراز هویت",
        description=(
            "هنگامی که توکن دسترسی منقضی می‌شود، سیستم وارد یک حلقه بی‌نهایت برای refresh شدن می‌شود "
            "و کاربر از سیستم خارج نمی‌شود اما هیچ درخواستی هم موفق نمی‌شود. "
            "این مشکل باعث می‌شود که کاربر در یک حالت بلاتکلیف گیر کند."
        ),
        severity=IssueSeverity.blocker, status=IssueStatus.regression, is_regression=True, is_release_blocker=True,
        labels=["احراز هویت", "توکن", "regression"],
        environment_name="staging", environment_os="iOS 17", environment_browser=None,
        reproduction_steps=[
            {"step_order": 1, "description": "وارد سیستم شوید و ۲ ساعت صبر کنید تا توکن منقضی شود", "expected_result": "توکن خودکار refresh شود", "actual_result": "درخواست‌ها شروع به fail شدن می‌کنند"},
            {"step_order": 2, "description": "هر API call را بررسی کنید", "expected_result": "refresh موفق و ادامه کار", "actual_result": "حلقه بی‌نهایت درخواست‌های ۴۰۱"},
        ],
        comments=[
            ("ana", "این regression از نسخه v2.3.1 شروع شده. تغییر در middleware احراز هویت مقصر اصلیه."),
            ("sajjad", "آنا، میشه بگی دقیقاً کدوم commit این مشکل رو ایجاد کرده؟"),
            ("ana", "بله، commit 8f3d2a1 - تغییر در refreshTokenInterceptor. Revert می‌کنم."),
            ("priya", "بعد از revert آنا، تست کردم و مشکل حل شده. منتظر merge هستیم."),
        ],
        status_changes=[("new", "regression", "ana")],
    ),
    # Critical
    dict(
        title="اعلان‌های push در iOS 17 ارسال نمی‌شوند",
        description=(
            "پس از آپدیت به iOS 17، اعلان‌های push برای بیش از ۶۰٪ از کاربران iOS دریافت نمی‌شوند. "
            "بررسی‌های اولیه نشان می‌دهد مشکل از ثبت device token در سرور است."
        ),
        severity=IssueSeverity.critical, status=IssueStatus.triaged,
        labels=["iOS", "push notification", "حیاتی"],
        environment_name="production", environment_os="iOS 17",
        reproduction_steps=[
            {"step_order": 1, "description": "دستگاه را به iOS 17 آپدیت کنید", "expected_result": "اعلان‌ها مثل قبل کار کنند", "actual_result": "هیچ اعلانی دریافت نمی‌شود"},
            {"step_order": 2, "description": "یک اعلان تست از پنل ادمین ارسال کنید", "expected_result": "اعلان دریافت شود", "actual_result": "اعلان نمی‌رسد"},
        ],
        comments=[
            ("priya", "با تیم Apple Developer بررسی کردیم. تغییر API در iOS 17 باعث شده device token format عوض بشه."),
            ("marcus", "این مشکل روی ۶۰٪ درآمد اعلان‌محور ما تأثیر می‌ذاره. اولویت باید بالاتر بره."),
            ("ana", "داریم روی راه‌حل کار می‌کنیم. تا آخر هفته patch آماده می‌شه."),
        ],
        status_changes=[("new", "triaged", "priya")],
    ),
    # Critical
    dict(
        title="Rate limiting روی endpoint ورود اعمال نمی‌شود",
        description=(
            "endpoint /api/auth/login هیچ محدودیتی برای تعداد درخواست‌ها ندارد. "
            "این آسیب‌پذیری امنیتی جدی است و امکان حملات brute-force را فراهم می‌کند."
        ),
        severity=IssueSeverity.critical, status=IssueStatus.in_progress, is_release_blocker=True,
        labels=["امنیت", "rate limiting", "ورود"],
        environment_name="production",
        curl_command="curl -X POST https://api.example.com/auth/login -d '{\"username\":\"test\",\"password\":\"test\"}' --repeat 1000",
        reproduction_steps=[
            {"step_order": 1, "description": "یک اسکریپت ارسال ۱۰۰۰ درخواست به endpoint ورود بنویسید", "expected_result": "پس از ۵ تلاش ناموفق، IP مسدود شود", "actual_result": "همه درخواست‌ها پردازش می‌شوند بدون هیچ محدودیتی"},
        ],
        comments=[
            ("marcus", "این یه نقص امنیتی جدیه. باید فوری رفع بشه."),
            ("ana", "داریم Redis-based rate limiting پیاده می‌کنیم. ۵ تلاش در ۱۵ دقیقه."),
            ("sajjad", "آنا، مطمئن بشید که IP-based و account-based هر دو پوشش داده بشن."),
            ("ana", "بله، هر دو لایه رو پیاده می‌کنم. تا فردا آماده‌ست."),
        ],
        status_changes=[("new", "in_progress", "marcus")],
    ),
    # Major
    dict(
        title="آپلود تصویر پروفایل برای فایل‌های بالای ۵ مگابایت خطا می‌دهد",
        description=(
            "کاربران هنگام آپلود تصویر پروفایل با حجم بیشتر از ۵ مگابایت با پیغام خطای «500 Internal Server Error» مواجه می‌شوند. "
            "Nginx timeout روی ۳۰ ثانیه تنظیم شده اما پردازش تصویر بیشتر طول می‌کشد."
        ),
        severity=IssueSeverity.major, status=IssueStatus.new,
        labels=["آپلود", "تصویر", "پروفایل"],
        environment_name="production", environment_browser="Chrome 120",
        reproduction_steps=[
            {"step_order": 1, "description": "به صفحه ویرایش پروفایل بروید", "expected_result": "صفحه باز شود", "actual_result": "صفحه باز می‌شود"},
            {"step_order": 2, "description": "یک تصویر بالای ۵ مگابایت انتخاب کنید", "expected_result": "تصویر resize و ذخیره شود", "actual_result": "خطای ۵۰۰ دریافت می‌شود"},
        ],
        comments=[
            ("priya", "این مشکل رو با یه عکس ۸ مگابایتی تأیید کردم."),
            ("tom", "فکر می‌کنم باید worker timeout رو افزایش بدیم یا پردازش رو async کنیم."),
        ],
        status_changes=[],
    ),
    # Major
    dict(
        title="صفحه‌بندی در نتایج جستجو خراب می‌شود",
        description=(
            "وقتی کاربر به صفحه دوم یا بعدی نتایج جستجو می‌رود، نتایج تکراری نمایش داده می‌شوند "
            "یا برخی نتایج حذف می‌شوند. مشکل از کش نادرست cursor در API است."
        ),
        severity=IssueSeverity.major, status=IssueStatus.fixed,
        labels=["جستجو", "صفحه‌بندی"],
        environment_name="staging",
        reproduction_steps=[
            {"step_order": 1, "description": "یک جستجو با بیش از ۲۰ نتیجه انجام دهید", "expected_result": "۲۰ نتیجه اول نمایش داده شود", "actual_result": "۲۰ نتیجه نمایش داده می‌شود"},
            {"step_order": 2, "description": "روی «صفحه بعد» کلیک کنید", "expected_result": "نتایج ۲۱ تا ۴۰ نمایش داده شود", "actual_result": "نتایج تکراری از صفحه اول نمایش داده می‌شود"},
        ],
        comments=[
            ("tom", "باگ رو پیدا کردم. cursor باید encode بشه قبل از cache شدن."),
            ("priya", "فیکس رو تست کردم. کار می‌کنه. آماده merge هستیم."),
            ("sajjad", "merged و deploy شد."),
        ],
        status_changes=[("new", "in_progress", "tom"), ("in_progress", "fixed", "tom")],
    ),
    # Major
    dict(
        title="حالت تاریک در هنگام راه‌اندازی اپ چشمک می‌زند",
        description=(
            "هنگام باز کردن اپ در حالت تاریک، یک flash سفید کوتاه قبل از نمایش UI دیده می‌شود. "
            "این مشکل از تأخیر در خواندن تنظیمات تم از storage ناشی می‌شود."
        ),
        severity=IssueSeverity.major, status=IssueStatus.triaged,
        labels=["حالت تاریک", "UI", "performance"],
        environment_name="production", environment_os="iOS 16",
        reproduction_steps=[
            {"step_order": 1, "description": "گوشی را روی حالت تاریک تنظیم کنید", "expected_result": "اپ در حالت تاریک باز شود", "actual_result": "اپ با یک flash سفید باز می‌شود"},
        ],
        comments=[
            ("tom", "مشکل از جایی هست که تم رو بعد از render اول اعمال می‌کنیم. باید قبل از mount اول اعمال بشه."),
            ("priya", "این مشکل خیلی از کاربران رو آزار می‌ده. تأیید می‌کنم."),
        ],
        status_changes=[("new", "triaged", "sajjad")],
    ),
    # Major
    dict(
        title="خطای ۴۰۳ در دسترسی به گزارش‌های پروژه برای نقش viewer",
        description=(
            "کاربران با نقش viewer هنگام دسترسی به گزارش‌های پروژه با خطای ۴۰۳ مواجه می‌شوند. "
            "بررسی کد نشان می‌دهد middleware مجوزها به اشتباه نقش viewer را فیلتر می‌کند."
        ),
        severity=IssueSeverity.major, status=IssueStatus.in_progress,
        labels=["مجوزها", "گزارش", "کنترل دسترسی"],
        environment_name="production",
        reproduction_steps=[
            {"step_order": 1, "description": "با حساب کاربری viewer وارد شوید", "expected_result": "ورود موفق", "actual_result": "ورود موفق"},
            {"step_order": 2, "description": "به بخش گزارش‌های پروژه بروید", "expected_result": "گزارش‌ها نمایش داده شوند", "actual_result": "خطای ۴۰۳ Forbidden"},
        ],
        comments=[
            ("ana", "مشکل در middleware مجوزهاست. Policy برای viewer به اشتباه تنظیم شده."),
            ("sajjad", "چند نفر گزارش دادن. لطفاً اولویت رو بالا ببر."),
            ("ana", "در حال رفع هستم. تا فردا آماده می‌شه."),
        ],
        status_changes=[("new", "in_progress", "ana")],
    ),
    # Major
    dict(
        title="خطا در export داده‌ها به فرمت CSV برای بیش از ۱۰۰۰۰ رکورد",
        description=(
            "وقتی کاربر می‌خواهد بیش از ۱۰۰۰۰ رکورد را به CSV export کند، فرآیند بعد از ۳۰ ثانیه timeout می‌شود. "
            "عملیات باید به صورت async و با stream انجام شود."
        ),
        severity=IssueSeverity.major, status=IssueStatus.new,
        labels=["export", "CSV", "performance"],
        environment_name="production",
        reproduction_steps=[
            {"step_order": 1, "description": "به بخش گزارش‌ها بروید و Export CSV را انتخاب کنید", "expected_result": "فایل CSV دانلود شود", "actual_result": "بعد از ۳۰ ثانیه timeout می‌شود"},
        ],
        comments=[
            ("marcus", "این یه مشکل بزرگ برای مشتریان enterprise ماست."),
            ("ana", "پیشنهاد می‌دم از streaming response استفاده کنیم به جای load همه داده‌ها در memory."),
        ],
        status_changes=[],
    ),
    # Minor
    dict(
        title="تاریخ در صفحه نمایش منطقه زمانی اشتباه نشان می‌دهد",
        description=(
            "تاریخ‌ها همیشه به وقت UTC نمایش داده می‌شوند و منطقه زمانی کاربر در نظر گرفته نمی‌شود. "
            "باید از تنظیمات منطقه زمانی کاربر استفاده شود."
        ),
        severity=IssueSeverity.minor, status=IssueStatus.verified,
        labels=["تاریخ", "منطقه زمانی", "UI"],
        environment_name="production",
        comments=[
            ("priya", "با کاربران در ایران تأیید شد. ساعت ۳:۳۰ صبح نمایش داده می‌شه به جای ۷ صبح."),
            ("tom", "فیکس کردم. از Intl.DateTimeFormat با timezone کاربر استفاده می‌کنیم."),
            ("priya", "تست کردم و درسته. verified."),
        ],
        status_changes=[("new", "fixed", "tom"), ("fixed", "verified", "priya")],
    ),
    # Minor
    dict(
        title="غلط تایپی در متن صفحه ورود",
        description="در صفحه ورود به سیستم، متن «فراموش کردی رمز عبورت رو؟» دارای غلط تایپی است و باید «رمز عبور خود را فراموش کرده‌اید؟» باشد.",
        severity=IssueSeverity.minor, status=IssueStatus.closed,
        labels=["UI", "متن"],
        environment_name="production",
        comments=[
            ("priya", "متن رو اصلاح کردم."),
            ("sajjad", "merge شد."),
        ],
        status_changes=[("new", "fixed", "priya"), ("fixed", "closed", "sajjad")],
    ),
    # Enhancement
    dict(
        title="اضافه کردن swipe-to-dismiss روی کارت‌های اعلان",
        description=(
            "کاربران درخواست کرده‌اند که بتوانند اعلان‌ها را با کشیدن به کنار (swipe) ببندند. "
            "این قابلیت در اکثر اپ‌های مشابه وجود دارد و تجربه کاربری را بهبود می‌دهد."
        ),
        severity=IssueSeverity.enhancement, status=IssueStatus.new,
        labels=["UX", "اعلان", "gesture"],
        environment_name="production",
        comments=[
            ("marcus", "۱۵ درخواست از کاربران داریم برای این قابلیت. ارزش پیاده‌سازی داره."),
            ("tom", "می‌تونم این رو با react-swipeable پیاده کنم. یک هفته وقت می‌بره."),
        ],
        status_changes=[],
    ),
    # Enhancement
    dict(
        title="پشتیبانی از ورود با Google و Apple",
        description=(
            "کاربران می‌خواهند با حساب Google یا Apple وارد سیستم شوند. "
            "پیاده‌سازی OAuth 2.0 با این ارائه‌دهندگان لازم است."
        ),
        severity=IssueSeverity.enhancement, status=IssueStatus.triaged,
        labels=["احراز هویت", "OAuth", "SSO"],
        environment_name="production",
        comments=[
            ("sajjad", "این یه قابلیت استراتژیک برای جذب کاربر جدیده."),
            ("ana", "پیاده‌سازی Google OAuth حدود ۳ روز طول می‌کشه. Apple Sign-in یه هفته."),
            ("marcus", "اول با Google شروع کنیم، بعد Apple."),
        ],
        status_changes=[("new", "triaged", "sajjad")],
    ),
    # Critical
    dict(
        title="دیتابیس connection pool در ساعت شلوغی تمام می‌شود",
        description=(
            "در ساعات اوج ترافیک (۱۸ تا ۲۲)، connection pool دیتابیس تمام می‌شود و درخواست‌ها با خطای «too many connections» fail می‌شوند. "
            "حداکثر connection‌های فعلی ۱۰۰ تا است که کافی نیست."
        ),
        severity=IssueSeverity.critical, status=IssueStatus.in_progress, is_release_blocker=True,
        labels=["دیتابیس", "performance", "connection pool"],
        environment_name="production",
        comments=[
            ("ana", "log‌های Postgres رو بررسی کردم. max_connections باید از ۱۰۰ به ۳۰۰ افزایش پیدا کنه."),
            ("sajjad", "آیا PgBouncer هم نیاز داریم؟"),
            ("ana", "بله، PgBouncer رو هم باید نصب کنیم برای connection pooling بهتر."),
            ("marcus", "این مشکل مستقیماً روی درآمد تأثیر می‌ذاره. ASAP رفع بشه."),
        ],
        status_changes=[("new", "in_progress", "ana")],
    ),
    # Major
    dict(
        title="فیلتر تاریخ در گزارش‌های فروش کار نمی‌کند",
        description=(
            "وقتی کاربر بازه تاریخی را در گزارش فروش تنظیم می‌کند، فیلتر اعمال نمی‌شود "
            "و همه داده‌ها بدون در نظر گرفتن بازه زمانی نمایش داده می‌شوند."
        ),
        severity=IssueSeverity.major, status=IssueStatus.new,
        labels=["گزارش", "فیلتر", "تاریخ"],
        environment_name="production",
        reproduction_steps=[
            {"step_order": 1, "description": "به بخش گزارش فروش بروید", "expected_result": "گزارش‌ها نمایش داده شوند", "actual_result": "گزارش‌ها نمایش داده می‌شوند"},
            {"step_order": 2, "description": "یک بازه تاریخ تنظیم کنید مثلاً ماه جاری", "expected_result": "فقط داده‌های ماه جاری نمایش داده شود", "actual_result": "همه داده‌ها از ابتدا نمایش داده می‌شوند"},
        ],
        comments=[
            ("priya", "بررسی کردم. query parameter تاریخ به backend ارسال نمی‌شه."),
            ("tom", "مشکل در frontend هست. داریم رفع می‌کنیم."),
        ],
        status_changes=[],
    ),
    # Blocker
    dict(
        title="صفحه سفید پس از ورود در Safari iOS",
        description=(
            "کاربران Safari در iOS پس از ورود موفق، با یک صفحه سفید مواجه می‌شوند "
            "و redirect به داشبورد اتفاق نمی‌افتد. مشکل مربوط به cookie SameSite policy است."
        ),
        severity=IssueSeverity.blocker, status=IssueStatus.in_progress, is_release_blocker=True,
        labels=["Safari", "iOS", "احراز هویت", "cookie"],
        environment_name="production", environment_browser="Safari 17", environment_os="iOS 17",
        reproduction_steps=[
            {"step_order": 1, "description": "با Safari روی iOS وارد سیستم شوید", "expected_result": "به داشبورد هدایت شوید", "actual_result": "صفحه سفید نمایش داده می‌شود"},
        ],
        comments=[
            ("tom", "مشکل از SameSite=Strict روی session cookie هست. Safari با این تنظیم مشکل داره."),
            ("ana", "باید به SameSite=Lax تغییر بدیم و همزمان امنیت رو بررسی کنیم."),
            ("sajjad", "این روی ۳۰٪ کاربران iOS ما تأثیر می‌ذاره. اولویت اول باشه."),
        ],
        status_changes=[("new", "in_progress", "tom")],
    ),
    # Minor
    dict(
        title="دکمه بازگشت در صفحه تنظیمات درست کار نمی‌کند",
        description="در صفحه تنظیمات حساب کاربری، دکمه «بازگشت» به صفحه قبلی نمی‌رود بلکه به داشبورد می‌رود.",
        severity=IssueSeverity.minor, status=IssueStatus.new,
        labels=["UI", "navigation"],
        environment_name="production", environment_browser="Firefox 121",
        comments=[
            ("priya", "تأیید می‌کنم. history.back() باید استفاده بشه نه redirect صریح به داشبورد."),
        ],
        status_changes=[],
    ),
    # Major
    dict(
        title="نوتیفیکیشن‌های ایمیل به پوشه spam می‌روند",
        description=(
            "ایمیل‌های اعلان سیستم به پوشه spam کاربران می‌روند. "
            "بررسی نشان می‌دهد که SPF، DKIM و DMARC به درستی تنظیم نشده‌اند."
        ),
        severity=IssueSeverity.major, status=IssueStatus.triaged,
        labels=["ایمیل", "spam", "deliverability"],
        environment_name="production",
        comments=[
            ("ana", "SPF record رو بررسی کردم. آدرس IP سرور mail در آن نیست."),
            ("sajjad", "با تیم DevOps هماهنگ کردم. دارن DNS records رو اصلاح می‌کنن."),
            ("marcus", "تا وقتی این حل نشه، rate engagement ایمیل‌های ما خیلی پایینه."),
        ],
        status_changes=[("new", "triaged", "sajjad")],
    ),
    # Enhancement
    dict(
        title="نمایش پیشرفت آپلود فایل با نوار پیشرفت",
        description=(
            "هنگام آپلود فایل‌های بزرگ، کاربران هیچ نشانه‌ای از پیشرفت عملیات ندارند. "
            "یک نوار پیشرفت (progress bar) باید اضافه شود."
        ),
        severity=IssueSeverity.enhancement, status=IssueStatus.new,
        labels=["UX", "آپلود", "UI"],
        environment_name="production",
        comments=[
            ("tom", "می‌تونیم از XMLHttpRequest progress event استفاده کنیم."),
            ("priya", "از کاربران بازخورد مثبت داشتیم برای این قابلیت."),
        ],
        status_changes=[],
    ),
    # Critical
    dict(
        title="Memory leak در سرویس پردازش تصویر",
        description=(
            "سرویس پردازش تصویر به مرور زمان حافظه بیشتری مصرف می‌کند و هر ۶ ساعت یکبار crash می‌کند. "
            "پروفایل‌گیری نشان می‌دهد Buffer‌های تصویر آزاد نمی‌شوند."
        ),
        severity=IssueSeverity.critical, status=IssueStatus.in_progress,
        labels=["memory leak", "performance", "تصویر"],
        environment_name="production",
        reproduction_steps=[
            {"step_order": 1, "description": "سرویس پردازش تصویر را مانیتور کنید", "expected_result": "مصرف RAM ثابت بماند", "actual_result": "هر ساعت حدود ۵۰۰MB RAM اضافه مصرف می‌شود"},
            {"step_order": 2, "description": "پس از ۶ ساعت وضعیت سرویس را بررسی کنید", "expected_result": "سرویس در حال اجرا باشد", "actual_result": "سرویس crash کرده"},
        ],
        comments=[
            ("ana", "مشکل در image processing pipeline پیدا کردم. stream رو بعد از پردازش نمی‌بندیم."),
            ("sajjad", "آنا ممنون. این مشکل هر شب سرویس رو پایین میاره."),
            ("ana", "فیکس آماده‌ست. باید تست load انجام بدیم قبل از deploy."),
            ("priya", "load test رو انجام دادم. ۲۴ ساعت بدون leak. آماده deploy."),
        ],
        status_changes=[("new", "in_progress", "ana")],
    ),
    # Major
    dict(
        title="درگاه پرداخت زرین‌پال در محیط staging کار نمی‌کند",
        description=(
            "یکپارچه‌سازی با درگاه پرداخت زرین‌پال در محیط staging با خطای «invalid_merchant» fail می‌شود. "
            "کلید API محیط staging باید جداگانه تنظیم شود."
        ),
        severity=IssueSeverity.major, status=IssueStatus.fixed,
        labels=["پرداخت", "زرین‌پال", "staging"],
        environment_name="staging",
        comments=[
            ("ana", "merchant ID staging با production یکی هست. باید جدا باشن."),
            ("sajjad", "با تیم زرین‌پال تماس گرفتم. کلید staging رو دریافت کردیم."),
            ("ana", "کلید جدید رو در environment variables تنظیم کردم. مشکل حل شد."),
            ("priya", "تأیید می‌کنم. پرداخت تست در staging کار می‌کنه."),
        ],
        status_changes=[("new", "in_progress", "ana"), ("in_progress", "fixed", "ana")],
    ),
    # Minor
    dict(
        title="مرتب‌سازی ستون‌های جدول در موبایل کار نمی‌کند",
        description="در نمای موبایل، کلیک روی سرستون‌های جدول برای مرتب‌سازی هیچ اثری ندارد.",
        severity=IssueSeverity.minor, status=IssueStatus.triaged,
        labels=["موبایل", "UI", "جدول"],
        environment_name="production", environment_browser="Chrome Mobile",
        comments=[
            ("tom", "touch event handler رو چک کردم. event روی mobile bind نشده."),
            ("priya", "تأیید می‌کنم روی Android و iOS."),
        ],
        status_changes=[("new", "triaged", "priya")],
    ),
    # Enhancement
    dict(
        title="افزودن حالت آفلاین برای مشاهده داده‌های کش‌شده",
        description=(
            "وقتی کاربر اینترنت ندارد، اپ یک صفحه خطا نشان می‌دهد. "
            "با Service Worker و IndexedDB می‌توان داده‌های آخر را نمایش داد."
        ),
        severity=IssueSeverity.enhancement, status=IssueStatus.new,
        labels=["آفلاین", "PWA", "UX"],
        environment_name="production",
        comments=[
            ("tom", "می‌تونیم این رو با Workbox پیاده کنیم. پیش‌بینی ۲ هفته وقت."),
            ("marcus", "این برای کاربران با اینترنت ضعیف خیلی مفیده."),
        ],
        status_changes=[],
    ),
    # Major
    dict(
        title="API versioning باعث می‌شود کلاینت‌های قدیمی خطا بگیرند",
        description=(
            "پس از release نسخه v2 API، کلاینت‌های موبایل با نسخه‌های قدیمی‌تر از v1.8 "
            "با خطاهای parsing مواجه می‌شوند. backward compatibility حفظ نشده است."
        ),
        severity=IssueSeverity.major, status=IssueStatus.in_progress,
        labels=["API", "backward compatibility", "versioning"],
        environment_name="production",
        comments=[
            ("ana", "endpoint‌های v1 باید deprecated flag بگیرن و redirect به v2 داشته باشن."),
            ("marcus", "باید به کاربران ۳۰ روز مهلت برای آپدیت اپ بدیم."),
            ("sajjad", "کمپین push notification برای آپدیت اجباری رو برنامه‌ریزی می‌کنم."),
        ],
        status_changes=[("new", "in_progress", "ana")],
    ),
    # Critical
    dict(
        title="نشت اطلاعات کاربران در response headers",
        description=(
            "بررسی security نشان می‌دهد که response headers شامل اطلاعات حساس مانند نسخه server، "
            "framework و stack trace در محیط production هستند. این اطلاعات باید حذف شوند."
        ),
        severity=IssueSeverity.critical, status=IssueStatus.fixed, is_release_blocker=True,
        labels=["امنیت", "headers", "information disclosure"],
        environment_name="production",
        comments=[
            ("ana", "X-Powered-By, Server, X-Debug-Info headers رو شناسایی کردم."),
            ("marcus", "این یه آسیب‌پذیری امنیتی جدیه. فوری رفع بشه."),
            ("ana", "middleware اضافه کردم که این headers رو حذف می‌کنه."),
            ("priya", "تأیید می‌کنم. headers حساس دیگه در response نیستن."),
            ("sajjad", "عالی. merge شد."),
        ],
        status_changes=[("new", "in_progress", "ana"), ("in_progress", "fixed", "ana")],
    ),
    # Minor
    dict(
        title="loading spinner در حین ذخیره تنظیمات نمایش داده نمی‌شود",
        description="وقتی کاربر تنظیمات را ذخیره می‌کند، هیچ نشانه‌ای از پردازش وجود ندارد و دکمه فعال می‌ماند.",
        severity=IssueSeverity.minor, status=IssueStatus.fixed,
        labels=["UI", "UX", "loading"],
        environment_name="production",
        comments=[
            ("tom", "یک loading state به دکمه ذخیره اضافه کردم."),
            ("priya", "تأیید شد. merge شد."),
        ],
        status_changes=[("new", "fixed", "tom")],
    ),
    # Enhancement
    dict(
        title="اضافه کردن قابلیت export به فرمت PDF برای گزارش‌ها",
        description=(
            "کاربران می‌خواهند گزارش‌ها را به فرمت PDF خروجی بگیرند. "
            "می‌توان از کتابخانه WeasyPrint یا Puppeteer استفاده کرد."
        ),
        severity=IssueSeverity.enhancement, status=IssueStatus.triaged,
        labels=["export", "PDF", "گزارش"],
        environment_name="production",
        comments=[
            ("ana", "WeasyPrint رو بررسی کردم. برای گزارش‌های ما مناسبه."),
            ("marcus", "این قابلیت برای مشتریان enterprise خیلی مهمه."),
            ("sajjad", "در roadmap Q2 قرار می‌دیم."),
        ],
        status_changes=[("new", "triaged", "sajjad")],
    ),
    # Major
    dict(
        title="جستجوی فارسی در نتایج اشتباه برمی‌گرداند",
        description=(
            "جستجو با کلمات فارسی نتایج نامرتبط برمی‌گرداند یا هیچ نتیجه‌ای نشان نمی‌دهد. "
            "موتور جستجوی فعلی از text search فارسی پشتیبانی نمی‌کند."
        ),
        severity=IssueSeverity.major, status=IssueStatus.in_progress,
        labels=["جستجو", "فارسی", "i18n"],
        environment_name="production",
        reproduction_steps=[
            {"step_order": 1, "description": "در نوار جستجو یک کلمه فارسی مانند «پرداخت» تایپ کنید", "expected_result": "نتایج مرتبط با پرداخت نمایش داده شود", "actual_result": "هیچ نتیجه‌ای یا نتایج نامرتبط نمایش داده می‌شود"},
        ],
        comments=[
            ("sajjad", "این مشکل از Elasticsearch configuration هست. باید Persian analyzer اضافه کنیم."),
            ("ana", "کار روی این رو شروع کردم. فرهنگ لغت فارسی رو integrate می‌کنم."),
            ("marcus", "۷۰٪ کاربران ما فارسی‌زبانن. این مشکل خیلی مهمه."),
        ],
        status_changes=[("new", "in_progress", "ana")],
    ),
    # Major
    dict(
        title="خطا در sync کردن تقویم با Google Calendar",
        description=(
            "یکپارچه‌سازی با Google Calendar درست کار نمی‌کند. رویدادها sync نمی‌شوند "
            "و خطای «insufficient_permissions» در log‌ها دیده می‌شود."
        ),
        severity=IssueSeverity.major, status=IssueStatus.new,
        labels=["تقویم", "Google Calendar", "sync"],
        environment_name="production",
        comments=[
            ("priya", "اسکوپ OAuth باید calendar.events.write رو هم شامل بشه."),
            ("tom", "این رو می‌تونم در Sprint بعدی رفع کنم."),
        ],
        status_changes=[],
    ),
    # Minor
    dict(
        title="فونت اعداد فارسی در گزارش‌ها نادرست است",
        description="اعداد فارسی در گزارش‌های PDF با فونت اشتباه نمایش داده می‌شوند و ناخوانا هستند.",
        severity=IssueSeverity.minor, status=IssueStatus.triaged,
        labels=["فونت", "فارسی", "PDF", "گزارش"],
        environment_name="production",
        comments=[
            ("tom", "باید Vazirmatn font رو به خروجی PDF اضافه کنیم."),
            ("priya", "تأیید می‌کنم. اعداد فارسی با فونت‌های Latin نمایش داده می‌شن."),
        ],
        status_changes=[("new", "triaged", "priya")],
    ),
    # Critical
    dict(
        title="سرویس ارسال SMS در اوقات شلوغی fail می‌شود",
        description=(
            "سرویس ارسال SMS برای تأیید حساب در ساعات اوج مصرف fail می‌شود. "
            "بررسی نشان می‌دهد rate limit API سرویس SMS رسیده و queue مدیریت نمی‌شود."
        ),
        severity=IssueSeverity.critical, status=IssueStatus.in_progress,
        labels=["SMS", "queue", "reliability"],
        environment_name="production",
        reproduction_steps=[
            {"step_order": 1, "description": "بیش از ۱۰۰ ثبت‌نام همزمان انجام دهید", "expected_result": "همه کدهای تأیید ارسال شوند", "actual_result": "بعد از ۵۰ درخواست، SMS‌ها ارسال نمی‌شوند"},
        ],
        comments=[
            ("ana", "باید یه retry queue با exponential backoff پیاده کنیم."),
            ("sajjad", "آیا می‌تونیم با سرویس SMS دیگه‌ای هم fallback داشته باشیم؟"),
            ("ana", "بله، Kavenegar رو به عنوان fallback اضافه می‌کنم."),
            ("marcus", "این مستقیماً روی ثبت‌نام کاربران جدید تأثیر می‌ذاره."),
        ],
        status_changes=[("new", "in_progress", "ana")],
    ),
    # Major
    dict(
        title="پیوند دعوت‌نامه‌های تیم پس از ۲۴ ساعت منقضی نمی‌شوند",
        description=(
            "پیوندهای دعوت به تیم باید ۲۴ ساعته باشند اما بررسی نشان می‌دهد "
            "این پیوندها هیچ‌وقت منقضی نمی‌شوند که یک نقص امنیتی است."
        ),
        severity=IssueSeverity.major, status=IssueStatus.fixed,
        labels=["امنیت", "دعوت‌نامه", "token expiry"],
        environment_name="production",
        comments=[
            ("ana", "expiry timestamp در دیتابیس ذخیره می‌شه ولی check نمی‌شه."),
            ("sajjad", "فیکس کردم. حالا expiry check قبل از استفاده از token انجام می‌شه."),
            ("priya", "تأیید شد. لینک‌های قدیمی‌تر از ۲۴ ساعت دیگه کار نمی‌کنن."),
        ],
        status_changes=[("new", "in_progress", "sajjad"), ("in_progress", "fixed", "sajjad")],
    ),
]


async def clear_issue_data(db: AsyncSession) -> None:
    print("Clearing issue-related data...")
    await db.execute(text("TRUNCATE issue_embeddings CASCADE"))
    await db.execute(text("TRUNCATE inbox_items CASCADE"))
    await db.execute(text("TRUNCATE issue_timeline CASCADE"))
    await db.execute(text("TRUNCATE issue_cycles CASCADE"))
    await db.execute(text("TRUNCATE issue_attachments CASCADE"))
    await db.execute(text("TRUNCATE regression_history CASCADE"))
    await db.execute(text("TRUNCATE issues CASCADE"))
    await db.commit()
    print("  Cleared all issue data.")


async def seed_persian(session: AsyncSession) -> None:
    from sqlalchemy import select
    from app.db.models.user import User
    from app.db.models.project import Project
    from app.db.models.release import Release

    # Load users
    users_result = await session.execute(select(User).where(User.is_active == True))
    users = {u.username: u for u in users_result.scalars().all()}
    if not users:
        print("ERROR: No users found. Run the main seed first.")
        return

    admin = users.get("admin") or next(iter(users.values()))
    sajjad = users.get("sajjad", admin)
    priya = users.get("priya", admin)
    tom = users.get("tom", admin)
    ana = users.get("ana", admin)
    marcus = users.get("marcus", admin)
    user_map = {"admin": admin, "sajjad": sajjad, "priya": priya, "tom": tom, "ana": ana, "marcus": marcus}

    # Load project and release
    proj_result = await session.execute(select(Project).limit(1))
    project = proj_result.scalar_one_or_none()
    if not project:
        print("ERROR: No project found. Run the main seed first.")
        return

    rel_result = await session.execute(
        select(Release).where(Release.project_id == project.id).limit(1)
    )
    release = rel_result.scalar_one_or_none()
    if not release:
        print("ERROR: No release found. Run the main seed first.")
        return

    print(f"Seeding 30 Persian issues into project '{project.name}' / release '{release.version}'...")

    reporters = [sajjad, priya, ana]
    assignees = [tom, ana, priya, sajjad, None]

    issues = []
    all_timeline = []

    for i, data in enumerate(ISSUES_DATA, start=1):
        comments = data.pop("comments", [])
        status_changes = data.pop("status_changes", [])

        reporter = random.choice(reporters)
        assignee = random.choice(assignees)
        filed_at = NOW - timedelta(days=random.randint(1, 30), hours=random.randint(0, 23))

        issue = Issue(
            issue_number=i,
            project_id=project.id,
            release_id=release.id,
            reporter_id=reporter.id,
            assignee_id=assignee.id if assignee else None,
            filed_at=filed_at,
            **data,
        )
        issues.append((issue, comments, status_changes, filed_at, reporter, assignee))

    issue_objs = []
    for item in issues:
        issue_obj, comments, status_changes, filed_at, reporter, assignee = item
        session.add(issue_obj)
        issue_objs.append((issue_obj, comments, status_changes, filed_at, reporter, assignee))

    await session.flush()
    print(f"  Flushed {len(issue_objs)} issues")

    for issue_obj, comments, status_changes, filed_at, reporter, assignee in issue_objs:
        # Filed event
        all_timeline.append(IssueTimeline(
            issue_id=issue_obj.id,
            actor_id=reporter.id,
            event_type=TimelineEventType.filed,
            body="ایشو ثبت شد.",
            created_at=filed_at,
        ))

        # Assignment event
        if assignee:
            all_timeline.append(IssueTimeline(
                issue_id=issue_obj.id,
                actor_id=sajjad.id,
                event_type=TimelineEventType.assigned,
                meta={"assignee_id": str(assignee.id)},
                created_at=filed_at + timedelta(hours=random.randint(1, 4)),
            ))

        # Status change events
        event_time = filed_at + timedelta(hours=2)
        for from_status, to_status, actor_username in status_changes:
            actor = user_map.get(actor_username, sajjad)
            all_timeline.append(IssueTimeline(
                issue_id=issue_obj.id,
                actor_id=actor.id,
                event_type=TimelineEventType.status_changed,
                meta={"from": from_status, "to": to_status},
                created_at=event_time,
            ))
            event_time += timedelta(hours=random.randint(2, 12))

        # Comment events
        comment_time = filed_at + timedelta(hours=random.randint(1, 6))
        for username, body in comments:
            actor = user_map.get(username, sajjad)
            all_timeline.append(IssueTimeline(
                issue_id=issue_obj.id,
                actor_id=actor.id,
                event_type=TimelineEventType.comment,
                body=body,
                created_at=comment_time,
            ))
            comment_time += timedelta(hours=random.randint(1, 8))

    session.add_all(all_timeline)
    await session.commit()
    print(f"  Created {len(all_timeline)} timeline events")
    print("\nPersian seed complete. Run reindex to embed issues.")


async def main() -> None:
    engine = create_async_engine(settings.database_url, echo=False)
    async_session = async_sessionmaker(engine, expire_on_commit=False)
    async with async_session() as session:
        await clear_issue_data(session)
        await seed_persian(session)
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
