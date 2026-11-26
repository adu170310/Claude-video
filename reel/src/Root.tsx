import React from "react";
import { Composition, continueRender, delayRender } from "remotion";
import T from "./timeline.json";
import { Reel } from "./Reel";
import { fontsReady } from "./fonts";

const h = delayRender("fonts");
fontsReady.then(() => continueRender(h));

export const Root: React.FC = () => (
  <Composition id="Reel" component={Reel} durationInFrames={T.duration} fps={T.fps} width={1080} height={1920} />
);
