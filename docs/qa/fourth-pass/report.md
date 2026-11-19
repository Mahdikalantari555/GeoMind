# دور چهارم ممیزی GeoMind — ۵۰ ایراد تازه

مبنا: `bb64f90` (پایان دور سوم). روش: خواندن کد مسیرهای `geoagent` (رجیستری ابزار، playbookها، حلقهٔ LLM، ابزارهای GIS/advisor)، `geolearn` (versioning، scheduler)، `geodomain`، `geospatial_core`، روترهای gateway و اجزای Studio؛ سپس نوشتن **۵۸ تست نقض‌کنندهٔ پایتون** و **۵ تست vitest**، اجرای build تولیدی در Chromium با پاسخ‌های HTTP/SSE کنترل‌شده و مقایسهٔ «پیش» (build دست‌نخوردهٔ `bb64f90` در worktree جدا) با «پس». هیچ سرویس تجاری، provider واقعی یا دانلود STAC واقعی فراخوانی نشد.

- **B** = اثر در اجرای مرورگر دیده شد (۱ ردیف؛ سه نشانهٔ مستقل در همان ردیف).
- **C** = نقص با کد و تست مستقل استخراج شد؛ هر ردیف C روی نسخهٔ پیش از اصلاح قرمز است و پس از اصلاح سبز (۴۹ ردیف).
- اولویت P1 = تصمیم/محاسبهٔ گمراه‌کننده یا نشت داده؛ P2 = اختلال محدودتر.
- هیچ ردیفی از فهرست‌های ۲۸، ۵۰ و ۵۰ مورد قبلی تکرار نشده است؛ پارامترهای مختلف یک تست در صورت تفاوت ریشهٔ نقص یک ردیف شمرده شده‌اند.

> **روش تفکیکی (تصحیح این نسخه).** هر چهار فایل تست چهارم یک‌بار روی worktree دست‌نخوردهٔ `bb64f90` اجرا شد. ۵۸ تست = **۵۷ قرمز روی مبنا** + ۱ تست پارامتریِ سه‌حالته که فقط حالت `v1beta` آن روی مبنا قرمز است (دو حالت دیگر از قبل درست بودند و به‌عنوان شاهد در همان تست نگه داشته شده‌اند). در نسخهٔ اولیهٔ این گزارش ۹ ردیف از فهرست حذف شد و سه نقص تازهٔ تأییدشده جای آن‌ها نشست؛ در نتیجه تعداد ۵۰ ردیف واقعی است، نه پرکردنی:
> حذف‌شده‌ها چون روی مبنا **سبز** بودند (نقص نبودند): برخورد نام فایل نسخه در یک ثانیه، مساحت با عرض جغرافیایی منفی، قاعدهٔ reclass با شکاف ولی معکوس، رشد رجیستری ارجاع بین نوبت‌ها، playbook با `{{params.x}}` حل‌نشده (روی مبنا هم `None` می‌دهد)، `"epsg:4326 "` (فاصلهٔ ابتدا/انتها از قبل trim می‌شد)، بازتنظیم event bus روی loop جاری، خواندن `map.geojson` از بیرون سندباکس (نسخهٔ پیش فقط از پوشهٔ والا می‌خواند؛ همان باگ در ردیف ۴۲ با شاهد واقعی ثبت شده) و بخش `/v1` تکراری در روتر gateway (آدرس روتر همیشه درست بود؛ باگ واقعی در backend بود و در ردیف ۴۰ ثبت شد). یک ردیف تکراری (`_parse_dates`، #۳۵ قبلی) هم ادغام شد.
> افزوده‌ها (پس از تأیید قرمزی روی مبنا و سبزی بعد از اصلاح): `geo_zonal_stats` که ماسک نودادهٔ خودِ رستر را دور می‌ریزد (ردیف ۳۸)، `geo_polygonize` که مساحت متری را درجه‌ای برچسب می‌زند (ردیف ۳۹) و `…/v1beta/v1/…` در backend سازگار با OpenAI (ردیف ۴۰).

### شواهد مستقیم

[خوانش مختصات نقشه — پیش](before/map-hemisphere-south-west.jpg) · [پس از اصلاح](after/map-hemisphere-south-west.jpg) · [مرکز ROI ترسیم‌شده — پیش](before/map-drawn-roi-centroid.jpg) · [پس](after/map-drawn-roi-centroid.jpg) · [نسخه‌های مدل زیرناحیه‌ای](after/training-subregions.jpg) · [Acquire پیش](before/view-acquire.jpg)/[پس](after/view-acquire.jpg) · [Knowledge](after/view-knowledge.jpg) · [Operations](after/view-ops.jpg) · [Resources](after/view-resources.jpg) · [Settings](after/view-settings.jpg).

- [`before/observations.json`](before/observations.json): `hemisphereLabelsAlt = "-58.38919°N -34.56174°E"`، `rollbackPosts = [{"key":["sugarcane","karkheh"],"version":1}]`، `errors: []`.
- [`after/observations.json`](after/observations.json): `hemisphereLabelsAlt = "58.38919°S 34.56174°W"`، `drawnRoiCentroid = ["58.4166°S, 34.6282°W"]`، `rollbackPosts = [{"key":["sugarcane","karkheh","north"],"version":1}]`، ۵ بخش (`acquire/knowledge/ops/settings/resources`) بدون خطای صفحه.
- در `before/map-drawn-roi-centroid.jpg` کارت «Centroid» عدد `-58.4166°N -34.6282°E` را نشان می‌دهد؛ همان ROI در `after` با `58.4166°S 34.6282°W` رسم می‌شود.
- اسکریپت‌ها و تست‌ها: `scripts/qa/fourth-pass-live.cjs`، `libs/geolearn/tests/test_fourth_pass.py`، `libs/geoagent/tests/test_fourth_pass.py`، `libs/geodomain/tests/test_fourth_pass.py`، `server/tests/test_fourth_pass_gateway.py`، `apps/studio/src/lib/fourth-pass.test.ts`.

|# · اولویت · مدرک|مسیر و محرک → رفتار فعلی|انتظار|
|---|---|---|
|01 P1 C|`geospatial_core.gis.geodesic_polygon_area_m2`؛ جعبهٔ ۰٫۲°×۰٫۲° روی نصف‌النهار ۱۸۰ → `889737.9 km²` (انتظار ≈۴۹۳). طول‌جغرافیایی بسته‌بندی‌نشده بود.|عبور از پاد‌نصف‌النهار با unwrap طول‌جغرافیایی.|
|02 P1 C|همان تابع با حلقهٔ خودمتقاطع `[[0,0],[1,1],[1,0],[0,1]]` → `0.0` بی‌خطا؛ حلقهٔ bow-tie به‌عنوان یک چندضلعی معتبر پذیرفته شد.|حلقهٔ خودمتقاطع رد شود.|
|03 P1 C|`polygon_area_deg2` با سوراخ بزرگ‌تر از پوسته (`121°` درون `1°`)؛ `max(0, …)` نتیجه را بی‌صدا صفر کرد.|سوراخ بزرگ‌تر از پوسته خطا بدهد.|
|04 P1 C|`polygon_area_deg2({"type":"Point"})` → `0.0`؛ نوع هندسهٔ اشتباه/تایپ‌شده مساحت صفر «معتبر» داد.|نوع غیرمساحتی رد شود.|
|05 P1 C|`parse_epsg("epsg: 4326")`، `"EPSG :  4326 "` و `"EPSG:: 4326"` → `None`؛ فاصله پس از دونقطه کد CRS را حذف می‌کرد.|این شکل‌ها به 4326 نگاشت شوند.|
|06 P1 C|`parse_epsg("urn:ogc:def:crs:EPSG::4326")` → `None`.|URN استاندارد OGC پشتیبانی شود.|
|07 P1 C|`parse_epsg(WKT با AUTHORITY["EPSG","32723"])` → `None`؛ WKT رایج rasterio بی‌صدا CRS را از دست می‌داد.|کد EPSG از WKT خوانده شود.|
|08 P1 C|`parse_epsg("+proj=longlat +datum=WGS84")` → `None`.|رشتهٔ PROJ به 4326 نگاشت شود.|
|09 P1 C|`zonal_statistics(np.array([[1.0,-9999.0]]))`؛ فرستندهٔ نودادهٔ خود پروژه در میانگین شمرده شد: `mean=-4999.0` و `nodata_share=0.0`.|`-9999` پیش‌فرض حذف شود.|
|10 P1 C|`zonal_statistics` روی ناحیهٔ کاملاً نوداده؛ `mean=0.0` و `min=0.0` ساختگی برگرداند.|`count=0` و میانگین «نامعلوم» (None).|
|11 P1 C|`reclassify_array` با قاعدهٔ `{out:-9999}`؛ کلاس روی فرستندهٔ نوداده نوشته شد و از هیستوگرام ناپدید شد.|کلاس هم‌ارز نوداده رد شود.|
|12 P2 C|`reclassify_array` با `{out:2.7}`؛ `int()` مقدار را بی‌صدا به ۲ برید.|کد کلاس غیرصحیح رد شود.|
|13 P1 C|`LabelSet(labels=[aaa:1, bbb:1])`؛ `id_to_name` یکی از دو کلاس را حذف کرد (`{1:'b'}`) در حالی که `name_to_id` هر دو را نگاشت کرد.|شناسهٔ تکراری در اعتبارسنجی رد شود.|
|14 P2 C|`LabelSet` با دو برچسب هم‌نام و شناسه‌های ۱ و ۲؛ `name_to_id` یکی را حذف کرد.|نام تکراری رد شود.|
|15 P2 C|`LabelRegistry.validate_label(True)` → `True`؛ چون `bool` زیرکلاس `int` است و `True == 1` با کلاس ۱ مطابق شد.|بولین هرگز کلاس نباشد.|
|16 P2 C|`ObservationRef(observation_id="")` → URI `geo:observation/` بدون شناسه.|شناسهٔ خالی رد شود.|
|17 P1 C|`Observation(value=float("nan"))` و `value=inf` پذیرفته شد؛ مشاهدهٔ نامعتبر در انبار ثبت می‌شود.|مقدار غیرمتناهی رد شود.|
|18 P1 C|`EntityRef(type="farm/x", id="1")` → `geo:farm/x/1` که با بازخوانی به موجودیت دیگری تبدیل می‌شود.|`/` در بخش‌های URI ممنوع شود.|
|19 P2 C|`TemporalKind` عضو `PUBLISHED_at` را با نام کوچک عرضه کرد (بقیه SCREAMING_CASE).|`PUBLISHED_AT`.|
|20 P2 C|`OnlineScheduler(batch_size=0)` و `batch_size=-3` بی‌خطا ساخته شدند و `step` بدون آموزش `True` برگرداند.|اندازهٔ دستهٔ غیرمثبت رد شود.|
|21 P1 C|`save_version(("crop","r1","north"))` سپس `("crop","r1","south")`؛ شمارندهٔ نسخه بین زیرناحیه‌ها مشترک بود و هر دو نسخهٔ ۱ گرفتند؛ `list_versions` هر دو کلید را با کلید `('crop','r1')` نشان داد.|شمارش و فیلتر به ازای کلید کامل.|
|22 P1 C|`rollback_to(("crop","r1","south"), 2)` → `True` در حالی که نسخهٔ ۲ مال `north` بود؛ rollback فایل مدل زیرناحیهٔ دیگر را روی `south` کپی کرد.|نسخهٔ خارج از زیرناحیه رد شود.|
|23 P1 C|پایگاه دادهٔ قدیمی؛ `ALTER TABLE … ADD COLUMN sub_region` کلید اصلی را `(crop, region, version)` نگه می‌داشت، پس ذخیرهٔ نسخهٔ زیرناحیه ردیف همسایه را حذف می‌کرد و همهٔ ردیف‌های قدیمی زیرناحیهٔ جعلی `'1'` می‌گرفتند.|بازسازی جدول با کلید چهارجزئی و مهاجرت ایدمپوتنت.|
|24 P1 C|`registry._validate` روی `{"top_k": 9999}` با `maximum: 50` → بدون خطا؛ `minimum`/`maximum` فقط به مدل اعلام می‌شد.|کران عددی اعمال شود.|
|25 P2 C|همان اعتبارسنج؛ `minItems: 4` با سه عضو، `minLength: 1` با رشتهٔ خالی و `additionalProperties: false` با کلید ناشناخته همه پذیرفته شدند.|این قیدها اعمال شوند.|
|26 P1 C|`raster_glob="../../**/*.tif"` از سندباکس گذشت؛ فقط کلیدهای `path/file/dir` بررسی می‌شدند. در probe، `ws.glob('../../**/*.md')` ۱۰۰۸ فایل بیرونی دید.|آرگومان‌های glob هم سندباکس شوند.|
|27 P2 C|`pattern="/etc/*.conf"` و مسیرهای `~` در بررسی سندباکس رد نمی‌شدند.|مسیر مطلق/خانه‌ای رد شود.|
|28 P1 C|فراخوانی ابزار با آرگومان JSON ناقص (`'{"q":'`)؛ خطای تجزیه بلعیده شد و ابزار با آرگومان خالی `{}` اجرا شد. شاهد ثبت‌شده: `$.q: required` به‌جای «JSON ناقص».|خطای تجزیه به‌عنوان `validation_error` گزارش شود.|
|29 P1 C|حلقهٔ agent فراخوانی یکسانِ همیشه‌شکست‌خورده را تا پایان بودجهٔ مرحله‌ها تکرار کرد و سرانجام پاسخ نهایی گمراه‌کننده ساخت.|تکرار یکسان متوقف و علت گزارش شود.|
|30 P1 C|`save_playbook(ws, "..", …)` فایل را در `ws/evil.md` نوشت (بیرون از `playbooks/`) و نام خالی `playbooks/.md` ساخت.|نام slug اجباری و مسیر قفل‌شده.|
|31 P1 C|دو فایل playbook با `name: duplicate`؛ `Registry.register` استثنا داد (`duplicate tool name 'pb_duplicate'`) و کل ثبت ابزارها از کار افتاد.|نام تکراری رد و بقیه ثبت شوند.|
|32 P2 C|`draft_playbook_text` با فنس ` ```yaml ` فقط برچسب `markdown` را حذف می‌کرد؛ فایل با `yaml` در ابتدا ذخیره و بعداً «missing frontmatter» شد.|هر برچسب فنس حذف شود.|
|33 P2 C|`geo_symbology` روی میدان ثابت با `scheme: quantiles, n_classes: 4`؛ چهار کلاس `[1,1]×4` با شمارش `0,0,0,1` ساخت.|میدان ثابت رد شود.|
|34 P1 C|`geo_farm_report` نقشهٔ کلاس‌ها را با `breaks:[-0.5,0.5,1.5]` رنگ می‌کرد؛ کلاس ۲ (تنش شدید) در هیچ بازه‌ای نبود و روی نقشه رسم نمی‌شد.|شکست‌ها کل بازهٔ داده را بپوشانند.|
|35 P2 C|`geo_symbology` با شکست تکراری در حالت manual و بدون پوشش دامنه، خروجی «موفق» با کلاس خالی ساخت.|شکست تکراری/ناقص رد شود.|
|36 P1 C|`min(rows, key=lambda r: r["mean_ndvi"] or 9e9)`؛ میانگین واقعی `0.0` «غایب» تلقی شد و «بدترین تاریخ» به انتهای فهرست رفت.|صفر مقدار معتبر باشد.|
|37 P1 C|`_parse_dates` با `20241345` و `20250230`؛ regex هر ۸ رقم را می‌پذیرد و تاریخ ناموجود به ردیف‌های گزارش و CSV راه یافت.|تاریخ تقویمی معتبر لازم باشد.|
|38 P1 C|`geo_zonal_stats` با `rio_mask(filled=False)`؛ `astype` ماسک را نگه می‌دارد اما تبدیل به `ndarray` مقادیر ماسک‌شده را برمی‌گرداند و ابزار نودادهٔ خودِ رستر را میانگین گرفت: `count=4`, `mean=3.75`, `nodata_share=0.0` برای مقادیر ۱،۲،۳ و نودادهٔ ۹.|ماسک رعایت شود: `mean=2`, `nodata_share=0.25`.|
|39 P1 C|`geo_polygonize` روی CRS متری (`EPSG:32723`، پیکسل ۱۰ متر)؛ مساحت با shoelace درجه‌ای روی مختصات متری محاسبه و به‌عنوان `area_deg2: 500000.0` منتشر شد (پیکسل ۱۰۰ m²).|مساحت در واحد CRS (`area_m2`) گزارش شود.|
|40 P1 C|`OpenAICompatBackend` با `base_url=…/api/v1beta`؛ بررسی زیررشته `"/v1"` نساخته بود و آدرس `…/v1beta/v1/chat/completions` شد (۴۰۴).|افزودن `/v1` فقط بدون بخش نسخه.|
|41 P1 C|`GET /agent/files?pattern=../../**/*.txt`؛ ۱۰۰۸ مسیر بیرون از workspace برگشت.|الگو نسبی و هر تطابق درون workspace.|
|42 P1 C|`/agent/maps` ریشهٔ *والد* workspace را هم می‌خواند؛ `geojson?path=other-project/secret.geojson` در نسخهٔ پیش خوانده شد.|فقط workspace و agent workspace.|
|43 P2 C|`GET /agent/files/download?path=runs` (پوشه) → `FileResponse` روی دایرکتوری پذیرفته شد؛ preview با `IsADirectoryError` ۵۰۰ داد.|`not_a_file` (422).|
|44 P1 C|`roi_store.load_rois` روی `{bad` → `[]`؛ رابط «هیچ ROI نیست» نشان می‌داد و ذخیرهٔ بعدی همهٔ ROIهای کشیده‌شده را نابود می‌کرد.|خطای `roi_store_invalid` با 422.|
|45 P2 C|`GET/POST/DELETE /rois` خطای انبار را به استثنای خام تبدیل می‌کردند (۵۰۰ بدون پاکت خطا).|همان پاکت خطای صریح.|
|46 P1 C|`GET /providers/OpenAI/models` بدون کلید؛ درخواست بیرونی بدون اعتبارنامه ارسال می‌شد.|`provider_key_missing` بدون تماس بیرونی.|
|47 P1 C|`_valid_base(..., https_only=False)` آدرس `http://api.example.test` و `http://10.0.0.5` را مجاز می‌دانست؛ کلید در هدر روی HTTP روشن ارسال می‌شد.|HTTP فقط برای loopback.|
|48 P1 C|`_save_persisted_secrets` فایل کلیدها را با حالت `0644` نوشت.|`0600` و اصلاح فایل موجود.|
|49 P1 C|`ModelRollbackRequest.key` حداکثر ۲ بخش داشت؛ rollback مدل زیرناحیه‌ای (`3` بخش) با 422 رد شد.|۲ یا ۳ بخش پذیرفته شود.|
|50 P1 B|`MapView` خوانش مختصات؛ `-58.38919` به `58.38919°N` و `-34.56174` به `34.56174°E` تبدیل شد؛ کارت Centroid همان ROI و متن تأیید AgentRail نیز `-58.4166°N, -34.6282°E` نوشتند و کلیک Rollback روی `sugarcane-karkheh-north@v1` بدنهٔ `{"key":["sugarcane","karkheh"],"version":1}` فرستاد.|پسوند S/W بر اساس علامت و کلید کامل در rollback.|

### وضعیت پس از اصلاح

- ۵۸ تست نقض‌کنندهٔ پایتون در چهار فایل جدید: `libs/geolearn` (۴)، `libs/geoagent` (۲۵)، `libs/geodomain` (۲۱، شامل geospatial_core)، `server` (۸)؛ به‌همراه ۵ تست vitest. همه سبز، و ۵۷ مورد از ۵۸ روی `bb64f90` قرمز (به‌جز دو حالت شاهدِ تست پارامتری URL).
- مجموعهٔ کامل پایتون: **۱۸۲۶ passed، ۶ failed، ۱۰ skipped**. شش شکست باقی‌مانده همه در `libs/geomemory` پیش از این تغییرات هم قرمز بوده و به محیط (مدل بینایی/PDF/lance) وابسته‌اند؛ در `bb64f90` دقیقاً همان شش شکست بازتولید شد.
- Studio: `vitest` **۵۰ تست** (۴ فایل) و `tsc --noEmit` سبز؛ build تولیدی ساخته و در Chromium اجرا شد.
- ruff روی همهٔ فایل‌های تغییریافته: بدون خطا.

### محدودیت‌های صادقانه

- فراخوانی provider واقعی، دانلود STAC واقعی و استنتاج مدل تجاری انجام نشد؛ همهٔ مسیرهای شبکه‌ای با پاسخ‌های کنترل‌شده آزموده شدند.
- یک ردیف B سه نشانهٔ مرورگری دارد و علتش از کد و vitest آمده است. ۴۹ ردیف دیگر فقط شاهد کد/تست دارند که همه روی `bb64f90` قرمزند.
- `libs/geomemory` (۳۸٫۹k خط) و `libs/data_engine` (۲۳٫۸k خط) در این دور به‌جز مسیرهای مشترک ابزار بررسی نشدند.
