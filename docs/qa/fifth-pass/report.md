# دور پنجم ممیزی GeoMind — مسیرهای علمی METRIC و پایداری persist پاسخ (دور ناقص)

تاریخ: ۱۹–۲۰ نوامبر ۲۰۲۶. مبنا: `39a21f6` (پس از فیکس‌های نقشهٔ استودیو و جریان
first-run workspace — به کامیت‌های `cd7f989` و `df9eb34` مراجعه شود). این دور
**ناقص است**: جلسه در میانهٔ بازبینی اجرای زندهٔ دانلود واقعی بسته شد. پوشش این
دور: ماژول‌های علمی `data_engine` (کسری ET، کیفیت، مقاومت آیرودینامیک) که هیچ‌یک
از چهار دور قبل بررسی‌شان نکرده بودند، به‌علاوه مسیر persist پاسخ QA در
`geomemory`. اجرای زندهٔ استودیو (جست‌وجوی STAC واقعی در UI — موفق؛ شروع job
دانلود — شروع شد ولی تکمیل/شکستش در همین جلسه تأیید نشد) در بخش «باز» ثبت شده است.

## یافته‌ها

|# · اولویت · مدرک|مسیر و محرک → رفتار پیش از اصلاح|انتظار (پس از اصلاح)|
|---|---|---|
|01 P1 C|`instantaneous_et.calculate_etrf` با `etr_inst=NaN` (افت دادهٔ هواشناسی) → `np.where(etr>0.01, …, 0.0)` پیکسل را **خشک‌کل** گزارش می‌کرد (`ETrF=[0.88, 0.0, 1.10]` — پروب زنده). همان الگو در `calculate_etof`، `daily_et` (۳ نقطه) و `latent_heat_flux.calculate_et_fraction` (۲ نقطه) — **۷ نقطه**. در دموی استاد، یک لغزش شبکهٔ Open-Meteo کل محصول ETa را صفر نشان می‌داد.|Reference ET گمشده «نامعلوم» (NaN) بماند؛ ET_daily نیز NaN — هرگز صفر بی‌صدا.|
|02 P1 C|`sensible_heat_flux.calculate` مسیر fallback فیزیکی: `H = rho·cp·dT/nanmean(rah)` — مقاومت آیرودینامیک به **یک اسکالر میانگین صحنه** فرومی‌ریخت و ساختار مکانی wet/dry را نابود می‌کرد.|تقسیم پیکسل‌به‌پیکسل بر `rah` (اصلاح شد؛ تستِ واریانس مکانی سبز).|
|03 P2 C|`instantaneous_et` با `use_temperature_lambda=True` بدون آرگومان دما → `TypeError` (`None - 273.15`) — پروب زنده تأیید کرد.|با هشدار لاگ به λ ثابت برگردد (تفاوت علمی <۲٪).|
|04 P2 C|`et/quality.check_spatial_consistency`: `valid_mask = ones` و NaNها با `nan_to_num(0)` در همسایگی میانگین می‌شدند → پیکسل‌های واقعیِ اطراف گپ به‌عنوان outlier پرچم می‌خوردند (پروب: ۴/۱۲ پیکسل حلقهٔ گپ).|میانگین همسایگی فقط از پیکسل‌های معتبر؛ گپ پرچم نمی‌زند (تست سبز).|
|05 P2 C|همان ماژول: `et_violation_count = sum(~valid)` پیکسل NaN را «تخلف از کران» می‌شمرد.|NaN جداگانه `et_nan_count` می‌شود؛ تخلف فقط بین مقادیر متناهی.|
|06 P2 C|`geomemory.workspace_qa._persist_answer` ردیف answer را INSERT ساده می‌کرد در حالی که `qa.chat_service` (وقتی conn داشته باشد) همان id را قبلاً persist و commit کرده است → `UNIQUE` violation و کرش کل `_write_tx`. امروز مسیر facade آن را فعال نمی‌کند (تلهٔ نهفته) — تستی که conn را تزریق می‌کند روی مبنا قرمز بود.|UPSERT idempotent با `ON CONFLICT(id) DO UPDATE`؛ تست سبز.|
|07 P3 D|`chat_service` خطای persist را با `except Exception: pass` بلعید؛ `anchor_pixels` عبارت مردهٔ `np.where(valid_mask)`؛ `sensible_heat_flux` محاسبهٔ تکراری z0h/d/rho و `if 'rho' not in locals()` همیشه False؛ پایداری وِیکر stability-loop در مسیر کالیبره (H=dt_a·dT) صرفاً لاگ می‌شود نه مصرف (محدودیت مستند، نه تغییر علمی بدون تصمیم مالک).|ثبت شفاف؛ cleanup جزئی فقط برای لاگ بی‌صدا انجام شد.|

|08 P1 B|`planetary_computer_fetcher` مسیر دانلود واقعی: (الف) پنجرهٔ برش با UTM zone **حدس‌زده از مرکز ROI** ساخته می‌شد در حالی که گرید خودِ صحنه zone دیگری است (ROI در ۴۸٫۰۵°E → zone 39؛ تایل لندست ۱۶۶/۰۳۸ → EPSG:32638) — پنجرهٔ wrong-CRS وارد reprojection شد و **هر ۸ باند با ZeroDivisionError** مرد (لاگ fetcher، job واقعی `f417006bcb43`)؛ (ب) پیام خطای نهایی به‌جای این، «insufficient valid pixel coverage» می‌گفت که گمراه‌کننده بود؛ (ج) پیش‌فرض `min_coverage_ratio=1` (۱۰۰٪) هیچ صحنهٔ واقعی (لبه‌های nodata) را نمی‌پذیرفت.|برش در CRS خود صحنه (`_bounds_in_crs`)، حذف reprojection زائد، هشدار باند با traceback، آستانهٔ پیش‌فرض ۰٫۹ — job واقعی `b0ed29111af4` **completed**: ۸ باند + MTL.json در workspace، ۸ asset با sha256 ثبت، tile PNG از باند red رندر شد (HTTP 200).|

|09 P2 B|`POST /models/train` با فضای کاری بدون candidate → job «completed» با نتیجهٔ خالی و **هیچ توضیحی**؛ در دمو استاد دکمهٔ Train می‌خورد، «completed» می‌بیند ولی هیچ مدلی ظاهر نمی‌شود (تأیید زنده: job `6a4ac214534e`).|gateway وقتی نتیجهٔ pipeline خالی است، `detail` صریح می‌گذارد: «no accepted feedback / candidate memories to train on — nothing trained» (تست سرور اضافه شد).|

## وضعیت پس از اصلاح

- تست‌های نقض‌کنندهٔ دور پنجم: `libs/data_engine/tests/test_fifth_pass.py` (۱۴ تست)، `server/tests/test_model_train.py` (۱ تست جدید) و
  `libs/geomemory/tests/unit/test_fifth_pass.py` (۱ تست) — همه سبز.
- data_engine کامل: **۲۰۰ passed, 1 failed** (همان `test_init_custom` ویندوزیِ مستند). سرور: **۲۲۹ passed**.
- geomemory unit: **۵۴۸ passed, 3 failed** (هر سه از قبل مستند و وابسته به محیط:
  cli dashboard، lance، olmoearth). یک flake گذرا در `test_api_backend` زیر بار
  سرورهای در حال اجرا دیده شد که در اجرای مجدد سبز شد.
- ruff روی همهٔ فایل‌های تغییریافته: بدون خطا.

## باز (ادامهٔ این دور در جلسهٔ بعد)

- بازبینی `pipeline/metric_pipeline.py` (۱۷۳۱ خط)، `dt_calibration` (انتخاب anchor
  و dT)، و `validation/` — این دور کسری‌ها/کیفیت/H/fetcher را دید؛ fetcher با
  دانلود واقعی end-to-end وریفای شد (یافتهٔ ۰۸).
- بازبینی `geomemory` مسیرهای ingest dedup/revision و امتیازدهی hybrid search با تست نقض‌کننده.
- تست زندهٔ Training Lab و جریان SSE واقعی استودیو.

محدودیت صادقانه: در این دور هیچ provider تجاری یا استنتاج LLM واقعی فراخوانی
نشد؛ جست‌وجوی STAC زنده بود ولی دانلود کامل باند به پایان نرسید.
