export default async (page) => {
  await page.setViewportSize({ width: 1366, height: 720 });
  return await page.evaluate(() => {
    const input = document.querySelector('.register-form .input-input');
    const card = document.querySelector('.register-card');
    const cs = input ? getComputedStyle(input) : null;
    return {
      inputMinHeight: cs?.minHeight,
      inputPadding: cs?.padding,
      cardPadding: card ? getComputedStyle(card).padding : null,
      docH: document.documentElement.scrollHeight,
      sheetCount: document.styleSheets.length,
      mediaMatches: [...document.styleSheets].some(s => [...s.cssRules].some(r => r.media && r.media.mediaText.includes('max-height: 820'))),
    };
  });
};
