import { Composition } from "remotion";
import { LingxiPromoComposition } from "./compositions/lingxi-promo/VideoComposition";

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="lingxi-promo"
        component={LingxiPromoComposition}
        durationInFrames={900}
        fps={30}
        width={1920}
        height={1080}
      />
    </>
  );
};
