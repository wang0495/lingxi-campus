import { AbsoluteFill, Sequence, Audio } from "remotion";
import { Scene1 } from "./Scene1";
import { Scene2 } from "./Scene2";
import { Scene3 } from "./Scene3";
import { Scene4 } from "./Scene4";
import { Scene5 } from "./Scene5";
import { Scene6 } from "./Scene6";
import { Scene7 } from "./Scene7";
import backgroundMusic from "./background-music.mp3";

export const LingxiPromoComposition: React.FC = () => {
  return (
    <AbsoluteFill>
      <Audio src={backgroundMusic} volume={0.3} />
      <Sequence from={0} durationInFrames={150}>
        <Scene1 />
      </Sequence>
      <Sequence from={150} durationInFrames={150}>
        <Scene2 />
      </Sequence>
      <Sequence from={300} durationInFrames={150}>
        <Scene3 />
      </Sequence>
      <Sequence from={450} durationInFrames={150}>
        <Scene4 />
      </Sequence>
      <Sequence from={600} durationInFrames={150}>
        <Scene5 />
      </Sequence>
      <Sequence from={750} durationInFrames={90}>
        <Scene6 />
      </Sequence>
      <Sequence from={840} durationInFrames={60}>
        <Scene7 />
      </Sequence>
    </AbsoluteFill>
  );
};
