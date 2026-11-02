export default async (page) => {
  const measure = () => ({ w: innerWidth, docH: document.documentElement.scrollHeight, overflow: document.documentElement.scrollHeight - innerHeight });
  await page.setViewportSize({ width: 1366, height: 768 });
  const d = await page.evaluate(measure);
  await page.setViewportSize({ width: 1440, height: 900 });
  const l = await page.evaluate(measure);
  await page.setViewportSize({ width: 390, height: 844 });
  const m = await page.evaluate(measure);
  return { desktop1366: d, laptop1440: l, mobile390: m };
};
