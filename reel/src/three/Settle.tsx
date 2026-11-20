import { useEffect } from 'react';
import { useThree } from '@react-three/fiber';
import { useCurrentFrame, useDelayRender } from 'remotion';

/**
 * ThreeCanvas advances once per frame, which can run before the post-processing composer
 * has attached its passes. Advance again on the next animation frame and hold the
 * screenshot until that render has happened, so every frame goes through the composer.
 */
export const Settle: React.FC<{ passes?: number }> = ({ passes = 2 }) => {
  const frame = useCurrentFrame();
  const { advance } = useThree();
  const { delayRender, continueRender } = useDelayRender();
  useEffect(() => {
    const h = delayRender('settle three frame');
    let n = 0;
    let raf = 0;
    const tick = () => {
      advance(performance.now());
      n++;
      if (n < passes) raf = requestAnimationFrame(tick);
      else continueRender(h);
    };
    raf = requestAnimationFrame(tick);
    return () => {
      cancelAnimationFrame(raf);
      continueRender(h);
    };
  }, [frame, advance, passes, delayRender, continueRender]);
  return null;
};
