// Isolated host/browser capability probe, outside UI latency measurements.
const fs = require('fs');
const { chromium } = require(process.env.HEAPLENS_PLAYWRIGHT);
(async () => {
  const browser = await chromium.launch({headless: true,
    executablePath: process.env.HEAPLENS_BROWSER});
  try {
    const cdp = await browser.newBrowserCDPSession();
    const version = await cdp.send('Browser.getVersion');
    const system = await cdp.send('SystemInfo.getInfo');
    const page = await browser.newPage({viewport: {width: 1440, height: 1000}});
    await page.goto('about:blank');
    const renderer = await page.evaluate(async () => {
      const gl = document.createElement('canvas').getContext('webgl');
      const extension = gl?.getExtension('WEBGL_debug_renderer_info');
      const frames = [];
      let previous = await new Promise(requestAnimationFrame);
      for (let i = 0; i < 30; ++i) {
        const current = await new Promise(requestAnimationFrame);
        frames.push(current - previous); previous = current;
      }
      return {userAgent: navigator.userAgent, hardwareConcurrency: navigator.hardwareConcurrency,
        webgl: !!gl, vendor: extension ? gl.getParameter(extension.UNMASKED_VENDOR_WEBGL) : null,
        renderer: extension ? gl.getParameter(extension.UNMASKED_RENDERER_WEBGL) : null,
        animationFrameIntervalsMs: frames, devicePixelRatio};
    });
    fs.writeFileSync(process.env.HEAPLENS_PROBE_OUTPUT,
      JSON.stringify({version, system, renderer}, null, 2));
    console.log(JSON.stringify({version, renderer, featureStatus: system.gpu.featureStatus}));
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
