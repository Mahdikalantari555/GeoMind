// Build apps/studio with VITE_GEOMIND_DEMO=1 first. No external traffic.
// NODE_PATH=/tmp/qa/node_modules node scripts/qa/studio-smoke.cjs
const p = require("puppeteer-core"),
  chrome = require("@sparticuz/chromium");
const fs = require("node:fs");
(async () => {
  const browser = await p.launch({
    args: chrome.args,
    executablePath: await chrome.executablePath(),
    headless: true,
  });
  try {
    const page = await browser.newPage(),
      errors = [];
    page.on("pageerror", (e) => errors.push(e.message));
    await page.setViewport({ width: 1440, height: 900 });
    await page.setRequestInterception(true);
    const base = "https://studio.test";
    const models = ["qa-chat-small", "qa-chat-large"];
    let applied;
    page.on("request", async (r) => {
      if (r.isNavigationRequest() && r.url().startsWith(base + "/"))
        return r.respond({
          contentType: "text/html",
          body: fs.readFileSync("apps/studio/dist/index.html"),
        });
      const path = new URL(r.url()).pathname;
      const body =
        path === "/api/v1/providers"
          ? [
              {
                name: "QA synthetic",
                base: "https://provider.invalid/v1",
                keyEnv: "GEOMEMORY_QA_KEY",
              },
            ]
          : path.endsWith("/models")
            ? models
            : path === "/api/v1/workspace/settings"
              ? (applied = JSON.parse(r.postData()))
              : null;
      if (body)
        return r.respond({
          contentType: "application/json",
          body: JSON.stringify(body),
        });
      return r.abort();
    });
    await page.goto(base + "/#/settings");
    const button = (text) => page.locator(`button::-p-text(${text})`).click();
    for (const [i, name] of [
      "map",
      "acquire",
      "resources",
      "knowledge",
      "training",
      "ops",
      "settings",
    ].entries()) {
      await page.click(`header nav button:nth-child(${i + 1})`);
      if (name === "acquire") {
        await button("Search scenes");
        await page.waitForFunction(() =>
          document.querySelector("main")?.textContent.includes("Download"),
        );
      }
      if (name === "settings") {
        await button("Add provider");
        await button("Fetch models");
        await page.locator("fieldset input[type=checkbox]").click();
        await button("Use:");
        await page.waitForFunction(() =>
          document.body.innerText.includes("Applied to workspace"),
        );
        if (applied.llm_model_id !== models[0]) throw Error("Wrong model");
      }
      await page.screenshot({
        path: `docs/qa/studio/${name}.jpg`, // gitignored: QA screenshots stay local
        type: "jpeg",
        quality: 68,
      });
      console.log(
        name,
        await page.$eval("main", (el) => el.innerText.slice(0, 80)),
      );
    }
    if (errors.length) throw Error(errors.join("\n"));
  } finally {
    await browser.close();
  }
})().catch((e) => {
  console.error(e);
  process.exitCode = 1;
});
