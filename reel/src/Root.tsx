import React from 'react';
import { Composition } from 'remotion';
import { Reel } from './Reel';
import { TL } from './anim';

export const Root: React.FC = () => (
  <Composition id="AthloReel" component={Reel} durationInFrames={TL.duration} fps={TL.fps} width={1080} height={1920} />
);
