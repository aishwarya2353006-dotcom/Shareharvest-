import { useEffect, useState } from 'react';

export default function AnimatedMetric({ value, decimals = 0 }) {
  const target = Number(value);
  const [displayValue, setDisplayValue] = useState(0);

  useEffect(() => {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      setDisplayValue(target);
      return undefined;
    }

    const startedAt = performance.now();
    let frameId;
    const update = timestamp => {
      const progress = Math.min((timestamp - startedAt) / 700, 1);
      const easedProgress = 1 - ((1 - progress) ** 3);
      setDisplayValue(target * easedProgress);
      if (progress < 1) frameId = window.requestAnimationFrame(update);
    };

    frameId = window.requestAnimationFrame(update);
    return () => window.cancelAnimationFrame(frameId);
  }, [target]);

  return <span className="impact-metric-value">{displayValue.toFixed(decimals)}</span>;
}
