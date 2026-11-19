# دور سوم ممیزی GeoMind — ۵۰ ایراد تازه

مبنا: `e5ad41d` (پایان دور دوم). روش: خواندن کد مسیرهای gateway/geolearn/Studio، نوشتن ۲۳ تست نقض‌کننده برای Python و ۸ تست برای مشتری، اجرای build تولیدی در Chromium با پاسخ‌های HTTP/SSE کنترل‌شده و بدون سرویس تجاری. **B** = اثر در اجرای مرورگر دیده شد؛ **C** = نقص از کد و تست مستقل استخراج شد و سناریوی ستون دوم بازتولید مستقل آن است. اولویت P1 = تصمیم/عمل گمراه‌کننده یا مانع کار؛ P2 = اختلال محدودتر. هیچ ردیفی از فهرست‌های ۲۸ و ۵۰ مورد قبلی تکرار نشده است؛ این‌ها مسیرهای دیگری در همان قابلیت‌ها یا لایه‌های تحلیل و انتقال‌اند. پارامترسازی‌های یک تست یک ردیف شمرده شده‌اند.

### شواهد مستقیم

*تصاویر «پیش/پس» عمداً در git نگهداری نمی‌شوند (`.gitignore`: `docs/qa/**/*.jpg`). با اجرای `scripts/qa/*.cjs` روی build تولیدی به‌صورت محلی بازتولید می‌شوند؛ شاهد ماشین‌خوان در فایل‌های `observations.json` همین پوشه‌ها باقی می‌ماند. ارجاع‌های زیر برای مشخص‌کردن «کدام تصویر چه چیزی را نشان می‌دهد» است، نه پیوند قابل کلیک.*

- [`before/observations.json`](before/observations.json): `mounted:false` و «Cannot read properties of undefined (reading 'nav_map')» با `gm.lang=old-locale`؛ [`after/observations.json`](after/observations.json): `mounted:true`, `errors:[]`.
- [`before/live-observations.json`](before/live-observations.json): `doubleClickPosts:2`، `sameSceneNewRoiDownload:false`، `dateFieldNames:[null,null]`، `staleScenes:true`، `compositionPosts:1`، `duplicateFinal:true`؛ [`after/live-observations.json`](after/live-observations.json): `1`, `true`, `["Start date","End date"]`, `false`, `0`, `false`.
- در تصویر «کلیک دوباره و ROI دوم — پیش» کارت صحنه با timestamp ثابت `2024-06-01T16:24:35Z` ساعت `04:24` و بدون نیم‌روز نشان داده شد؛ در تصویر «پایان استریم — پس از اصلاح» پاسخ کامل یک‌بار و toast خطای جست‌وجو دیده می‌شود.
- تصاویر وضعیت را نشان می‌دهند نه علت را؛ ۳۰ ردیف C فقط با کد/تست پشتیبانی می‌شوند. اسکریپت‌ها: `scripts/qa/third-pass.cjs`، `scripts/qa/third-pass-live.cjs`، `libs/geolearn/tests/test_third_pass.py`، `server/tests/test_third_pass.py`، `apps/studio/src/lib/third-pass.test.ts`.

|# · اولویت · مدرک|مسیر و محرک → رفتار فعلی|انتظار|
|---|---|---|
|01 P1 C|`geolearn.confidence.shannon_entropy(normalized=False)`؛ چهار کلاس برابر → `1.0`؛ نتیجهٔ تقسیم بر `log2(4)` همیشه clip می‌شد.|آنتروپی غیرنرمال بر حسب بیت (۲) برگردد.|
|02 P1 C|`ConfidenceModel.evaluate`؛ `compute_final_confidence` خودش آنتروپی را بر `ln2` نرمال می‌کند و آرگومان ورودی از قبل نرمال بود؛ جریمهٔ ۰.۳ عملاً ثابت شد.|ترکیب با یک‌بار نرمال‌سازی و بدون clip پنهان.|
|03 P1 C|`ConfidenceModel(calibration_curve=IsotonicCalibrator())`؛ کالیبراتور مستقیم در `CalibrationCurve` پیچیده می‌شد و مسیر کالیبراسیون نمونه‌ها نادیده گرفته می‌شد.|کالیبراتور داده‌شده مستقیماً استفاده شود.|
|04 P1 C|`ConfidenceModel(threshold=0).evaluate([0,0])`؛ ردیف با جرم صفر «پذیرفته» شد.|جرم صفر همیشه abstain باشد.|
|05 P1 C|`evaluate([NaN,.5])`؛ پیش‌بینی پذیرفته با confidence نامعلوم تولید شد.|ورودی غیرمتناهی رد شود.|
|06 P2 C|`IsotonicCalibrator.fit`؛ هدف `2` بی‌خطا به‌عنوان احتمال کالیبره شد.|هدف غیردودویی رد شود.|
|07 P2 C|`fit([.4],[1]).fit([],[])`؛ refit خالی مدل قبلی را نگه داشت و `calibrate(.4)` همان پیش‌بینی قدیمی بود.|refit خالی مدل را پاک کند.|
|08 P1 C|`PageHinkley.update(NaN)`؛ `n_instances` قبل از رد مقدار زیاد شده و میانگین/انحراف با نمونهٔ نامعتبر آلوده شد.|رد ورودی بدون تغییر آماره‌ها.|
|09 P2 C|`PageHinkley.check(np.float32(.25))`؛ اسکالر NumPy از نوع `Real` نیست، پس با `y_true=None` مقایسه و باقیماندهٔ صفر ثبت شد.|باقیماندهٔ عددی با اندازهٔ واقعی مصرف شود.|
|10 P2 C|`StreamingWindow.update_classifier(batch_size=-1)`؛ مقدار غیرمثبت بی‌خطا «آموزش» را گزارش کرد.|اندازهٔ دستهٔ نامعتبر رد شود.|
|11 P2 C|`StreamingWindow.add` / `OnlineScheduler.add`؛ آرایهٔ فراخواننده بدون کپی ذخیره شد؛ تغییر بعدی، برچسب تاریخی را عوض کرد.|نمونه در لحظهٔ افزودن کپی شود.|
|12 P1 C|`OnlineScheduler.maybe_train(current_time=0)`؛ زمان صفر با «تنظیم‌نشده» یکی گرفته شد و بازهٔ زمانی هرگز فعال نشد.|ساعت صفر معتبر باشد.|
|13 P1 C|`OnlineScheduler.step(..., new_samples=[([2],1)], force=True)`؛ force فقط بافر قبلی را آموزش داد و نمونه‌های تازه را دور ریخت.|نمونه‌های در انتظار هم وارد شوند.|
|14 P1 C|`SceneSearchRequest/SceneDownloadRequest`؛ `2024-02-30` و بازهٔ معکوس پذیرفته شد و تا لایهٔ STAC رفت.|تاریخ تقویمی و ترتیب بازه در schema اعتبارسنجی شود.|
|15 P1 C|`data._require_roi_polygon`؛ فقط وجود `coordinates` بررسی می‌شد؛ حلقهٔ باز، خودمتقاطع و خارج از WGS84 به جست‌وجو/دانلود رسید.|حلقهٔ بسته، در محدوده و بدون خودتقاطع لازم باشد.|
|16 P1 C|`POST /rois` با نقاط هم‌خط `[[1,1],[2,2],[3,3]]`؛ ROI با مساحت صفر ساخته شد.|هندسهٔ مساحت‌صفر رد شود.|
|17 P2 C|`RoiCreateRequest(name="   ")`؛ نام فاصله‌ای معتبر شد و ROI بی‌نام در فهرست ثبت شد.|نام خالی/فاصله‌ای رد شود.|
|18 P1 C|`catalog()`؛ `GEOMIND_APPROVED_PROVIDER_BASES=https://[bad` در `urlsplit` استثنا داد و کل `GET /providers` شکست.|مبناهای بد نادیده گرفته شوند، فهرست سالم بماند.|
|19 P1 C|`catalog()`؛ `GEOMEMORY_LLM_API_BASE_URL=https://example.test/v1?token=…` بدون اعتبارسنجی منتشر شد و توکن را در UI نشان داد.|مبنای دارای query/credential منتشر نشود.|
|20 P2 C|`GET /data/tiles?...&bands=1,,2`؛ جزء خالی حذف شد و شمارهٔ باندها بی‌صدا جابه‌جا شد.|ورودی ناقص ۴۲۲ بدهد.|
|21 P2 C|`App` کلیدهای میان‌بر؛ فشردن نگه‌داشتن `Ctrl+K` یا Enter در حال IME چند بار پالت/نما را عوض کرد.|رویداد تکراری و ترکیب IME نادیده گرفته شود.|
|22 P1 B|`AgentRail` + `api.streamAgentChat.final`؛ قاب نهایی `final:true` به متن قبلی الصاق شد؛ در اجرای مرورگر «Lead complete» دو بار آمد.|قاب نهایی جایگزین متن جزئی شود.|
|23 P2 C|`AgentRail` textarea؛ Enter هنگام انتخاب IME پیام را فرستاد (قبل از تأیید حروف).|در حال ترکیب ارسال نشود.|
|24 P1 B|`AcquireView.download`؛ دو کلیک پشت‌سرهم روی Download دو `POST /data/download` فرستاد و دو job ساخت.|درخواست تکراری برای همان صحنه/ROI تا پاسخ سرور مسدود شود.|
|25 P1 B|`AcquireView.jobFor`؛ ROI را از state جاری می‌خواند؛ پس از دانلود در ROI A، در ROI B دکمهٔ Download برای همان صحنه ناپدید شد.|هویت job و لایه با ROI لحظهٔ کلیک تعیین شود.|
|26 P1 C|`AcquireView.onDone`؛ پاسخ بدون `band_files` همچنان لایهٔ raster با `tileUrl: undefined` و پیام موفقیت ثبت کرد.|پیش‌نمایش ساختگی اعلام نشود؛ هشدار صریح.|
|27 P2 B|`AcquireView` + `i18n.time`؛ زمان صحنه با `slice(0,5)` کوتاه شد؛ timestamp `16:24Z` به‌صورت `04:24` بدون نیم‌روز نمایش یافت.|کوتاه‌سازی با فرمت locale و حفظ AM/PM.|
|28 P1 B|`AcquireView.search`؛ جست‌وجوی ناموفق پس از تغییر ROI، نتایج صحنهٔ قبلی را حفظ کرد و کارت‌های کهنه زیر ROI جدید ماندند.|شروع جست‌وجو نتایج قبلی را پاک کند.|
|29 P2 B|`AcquireView` فیلدهای تاریخ؛ هیچ نام قابل‌دسترسی نداشتند (`getAttribute('aria-label')` برابر null).|هر ورودی برچسب داشته باشد.|
|30 P2 C|`KnowledgeView` ورودی سؤال؛ Enter در حال IME جست‌وجو را شروع کرد.|ترکیب IME نادیده گرفته شود.|
|31 P1 C|`KnowledgeView.ask`؛ بازگشت دوباره در حالت loading (Enter/کلیک پیشنهادها) درخواست دوم موازی فرستاد.|درخواست هم‌زمان دوم مسدود شود.|
|32 P2 C|`KnowledgeView` دکمهٔ Ask با سؤال فاصله‌ای فعال بود.|سؤال خالی غیرفعال باشد.|
|33 P1 C|`api.probeGateway`؛ `setTimeout` فقط در مسیر موفق پاک می‌شد؛ با رد شدن fetch تایمر باقی ماند و شمارندهٔ تایمرها صفر نشد.|تایمر در `finally` پاک شود.|
|34 P1 C|`api.streamAgentChat`؛ `buffer += decode(...)`؛ اگر `\r\n` بین دو chunk شکسته شود، `/\/\r\n/g` هرگز جایگزین نمی‌شود و قاب بسته نمی‌شود (تست: پیام گم شد).|نرمال‌سازی بعد از پیوستن بافر انجام شود.|
|35 P2 C|`api.streamAgentChat`؛ `line.slice(5).trim()` فضای معنادار JSON و چند خط `data:` را بدون جداکننده به هم چسباند.|فقط یک فاصلهٔ اختیاری حذف و خطوط با `\n` جمع شوند.|
|36 P2 C|`api.streamAgentChat`؛ فیلد `final` از payload خوانده نمی‌شد، پس مصرف‌کننده راهی برای تفکیک متن جزئی از نهایی نداشت.|`final` در رویداد منتقل شود.|
|37 P2 C|`api.streamAgentChat`؛ اگر `onEvent` استثنا می‌داد، `reader` آزاد نمی‌شد و خطا با «JSON نامعتبر» یکی گرفته می‌شد.|`onEvent` بیرون از `try` باشد و reader در `finally` آزاد شود.|
|38 P1 C|`api.searchScenes/requestDownload`؛ هندسهٔ ROI نامعتبر بی‌صدا با `WORLD_POLYGON` جایگزین شد؛ دانلود روی کل کره ارسال می‌شد.|هندسهٔ نامعتبر خطای صریح بدهد و درخواستی نرود.|
|39 P1 C|`api.listAssets` / `api.listModelVersions`؛ `Date.parse(v) || Date.now()`؛ timestamp واقعی `1970-01-01T00:00:00Z` (مقدار ۰) با «امروز» جایگزین شد.|صفر معتبر بماند؛ تاریخ نامعتبر «—».|
|40 P1 C|`i18n.makeFormatters.date/time`؛ مقدار نامعتبر `RangeError` در `Intl` داد و رندر نمای مصرف‌کننده را شکست.|تاریخ نامعلوم «—» شود.|
|41 P1 B|`store` مقدار `gm.lang` را بدون اعتبارسنجی به‌عنوان `Lang` پذیرفت؛ `old-locale` باعث `t("nav_map") === undefined` و unmount شد.|فقط `fa`/`en` پذیرفته و بقیه به انگلیسی برگردد.|
|42 P2 C|`store` نوشتن `localStorage.setItem("gm.lang")` بدون محافظ؛ با خطای quota/حالت خصوصی، effect استثنا داد.|شکست ذخیره‌سازی مانع رندر نشود.|
|43 P2 C|`MapView.finish`؛ نام پیش‌فرض ROI از `workspace.split("-")[0]` ساخته می‌شد؛ با مسیر workspace، پیشوند مسیر (`/home/...`) در نام آمد.|نام از basename مسیر ساخته شود.|
|44 P1 C|`MapView.saveRoi`؛ دکمه‌ها برای هندسهٔ مساحت‌صفر فعال بودند و فقط gateway (ردیف ۱۶) جلوی ثبت را می‌گرفت.|دکمه‌های ذخیره/ارسال برای مساحت صفر غیرفعال شوند.|
|45 P2 C|`MapCanvas`؛ پس از حرکت ماوس و خروج از نقشه، خط پیش‌نمایش به آخرین نقطه چسبیده ماند.|خروج نشانگر پیش‌نمایش را پاک کند.|
|46 P1 C|`MapCanvas`؛ پس از «پایان» رسم، کلیک بعدی روی نقشه هندسهٔ نهایی را جابه‌جا کرد و نشانگر crosshair ماند؛ deps افکت هم حالت پایان را نداشت.|پس از پایان، رسم و نشانگر قفل شود تا reset.|
|47 P2 C|`MapCanvas`؛ مختصات بدون `wrap()` ذخیره شد؛ کلیک روی نقشهٔ تکرارشده طول جغرافیایی خارج از ±۱۸۰ تولید کرد.|طول جغرافیایی نرمال شود.|
|48 P2 C|`ProviderPicker.request`؛ پاسخ بدون بدنهٔ JSON (مثلاً ۲۰۴) به‌عنوان موفقیت `null` برگشت و در ادامه کرش کرد.|بدنهٔ نامعتبر خطای صریح بدهد.|
|49 P2 C|`ProviderPicker` مقدار `gm.provider-library.v1`؛ آرایه/رشته/آیتم غیرآرایه باعث خطا در `Object.entries`/`saved[base]` شد.|ساختار ذخیره‌شده اعتبارسنجی و پاک‌سازی شود.|
|50 P2 C|`ProviderPicker` پاسخ `GET /providers`؛ اگر شیء خطا برگردد، `list[0]`/`catalog.map` بی‌خطا شکست می‌خورد.|آرایه نبودن پاسخ تشخیص داده شود.|

### بازتولید

```bash
source /tmp/useqa
python -m pytest -q --import-mode=importlib libs/geolearn/tests/test_third_pass.py server/tests/test_third_pass.py
(cd apps/studio && npm run check && npm test)
export LD_LIBRARY_PATH=/tmp/al/lib NODE_PATH=/tmp/qa/node_modules
node scripts/qa/third-pass.cjs before        # و after
node scripts/qa/third-pass-live.cjs before   # و after
```

پیش از اصلاح: ۱۳ تست `geolearn` و ۱۰ مورد پارامتری `server` شکست خوردند (`/tmp/thirdmlpre`, `/tmp/thirdgwpre`)؛ ۸ تست مشتری روی build مبنای `e5ad41d` شکست خورد و اسکریپت مرورگر `before` مقادیر جدول را ثبت کرد.

## پس از اصلاح

هر ۵۰ ردیف بالا در این شاخه اصلاح شد و برای هر کدام تست یا assertion بازتولید مستقل اضافه شد. مجموعه‌های هدفمند: `libs/geolearn` + `server/tests` برابر ۳۴۵ تست هدفمند و ۵۴۰ تست در مجموعهٔ کامل سبز؛ Studio `tsc` سبز، ۴۵ تست (۳۷ قبلی + ۸ جدید) سبز، build سبز؛ هر دو اسکریپت مرورگر در فاز `after` سبزند و `observations.json`/`live-observations.json` تفاوت‌های جدول را تأیید می‌کنند. جزئیات در [`after/observations.json`](after/observations.json) و [`after/live-observations.json`](after/live-observations.json).

محدودیت‌ها: اجرای مرورگر از APIهای کنترل‌شدهٔ محلی استفاده می‌کند و ۵۰ سناریوی مستقل e2e نیست؛ استنتاج ارائه‌دهندهٔ تجاری، دانلود واقعی STAC و رفتار مرورگر روی سرویس بیرونی آزموده نشده است. خروجی ML و gateway با داده و stub مصنوعی سنجیده شده، نه با مدل واقعی. تصاویر `before` برای مقایسه حفظ شده‌اند و اسکریپت‌ها در فاز `after` روی همان مسیرها بازنویسی نمی‌کنند.
