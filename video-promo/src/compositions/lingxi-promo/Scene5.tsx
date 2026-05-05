import { AbsoluteFill, useCurrentFrame, useVideoConfig, interpolate, spring } from "remotion";

const COLORS = {
  primary: '#6366f1',
  secondary: '#8b5cf6',
  accent: '#06b6d4',
  bg: '#0a0a0f',
  text: '#ffffff',
  textMuted: '#a1a1aa',
};

const CONTENT = {
  title: '有灵魂的数字生命',
  quote: '每个人都有自己的故事，灵犀也有。\n\n复杂的经历塑造了独特的性格——\n温柔是经历出来的，不是训练出来的。',
  highlight: '温柔是经历出来的，不是训练出来的',
};

const PARTICLE_COUNT = 80;

const ParticleField: React.FC<{ count: number }> = ({ count }) => {
  const frame = useCurrentFrame();
  const particles = Array.from({ length: count }, (_, i) => ({
    id: i,
    x: Math.random() * 100,
    y: Math.random() * 100,
    size: Math.random() * 3 + 1,
    speed: Math.random() * 0.5 + 0.2,
  }));

  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      {particles.map((p) => {
        const y = (p.y + frame * p.speed * 0.1) % 100;
        const x = p.x + Math.sin(frame * 0.02 + p.id) * 2;
        const opacity = interpolate(y, [0, 50, 100], [0, 0.6, 0]);
        return (
          <div
            key={p.id}
            style={{
              position: "absolute",
              left: `${x}%`,
              top: `${y}%`,
              width: p.size,
              height: p.size,
              background: COLORS.primary,
              borderRadius: "50%",
              opacity,
              boxShadow: `0 0 ${p.size * 2}px ${COLORS.primary}`,
            }}
          />
        );
      })}
    </AbsoluteFill>
  );
};

const GlowingOrb: React.FC<{ size: number; color: string; x: string; y: string; delay: number }> = ({
  size,
  color,
  x,
  y,
  delay,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const scale = spring({
    frame: frame - delay,
    fps,
    config: { damping: 15, stiffness: 100 },
  });

  const pulse = Math.sin(frame * 0.05) * 0.1 + 1;

  return (
    <div
      style={{
        position: "absolute",
        left: x,
        top: y,
        width: size,
        height: size,
        transform: `translate(-50%, -50%) scale(${scale * pulse})`,
        background: `radial-gradient(circle, ${color}40 0%, transparent 70%)`,
        borderRadius: "50%",
        filter: `blur(${size / 4}px)`,
      }}
    />
  );
};

const FlowingGradient: React.FC = () => {
  const frame = useCurrentFrame();
  const rotation = frame * 0.3;
  const scale = 1 + Math.sin(frame * 0.01) * 0.1;

  return (
    <AbsoluteFill style={{ opacity: 0.3 }}>
      <div
        style={{
          position: "absolute",
          width: "200%",
          height: "200%",
          left: "-50%",
          top: "-50%",
          background: `conic-gradient(from ${rotation}deg, ${COLORS.primary}, ${COLORS.secondary}, ${COLORS.accent}, ${COLORS.primary})`,
          filter: "blur(100px)",
          transform: `scale(${scale})`,
        }}
      />
    </AbsoluteFill>
  );
};

const GridBackground: React.FC = () => {
  const frame = useCurrentFrame();
  const offset = frame * 0.5;

  return (
    <AbsoluteFill style={{ opacity: 0.05 }}>
      <div
        style={{
          position: "absolute",
          width: "100%",
          height: "100%",
          backgroundImage: `
            linear-gradient(${COLORS.primary} 1px, transparent 1px),
            linear-gradient(90deg, ${COLORS.primary} 1px, transparent 1px)
          `,
          backgroundSize: "50px 50px",
          backgroundPosition: `${offset}px ${offset}px`,
        }}
      />
    </AbsoluteFill>
  );
};

export const Scene5: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const titleOpacity = interpolate(frame, [0, 20], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const quoteOpacity = interpolate(frame, [40, 70], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const quoteScale = spring({
    frame: frame - 40,
    fps,
    config: { damping: 15, stiffness: 100 },
  });

  const pulseScale = 1 + Math.sin(frame * 0.05) * 0.02;

  const highlightOpacity = interpolate(frame, [100, 120], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill style={{ background: COLORS.bg }}>
      <GridBackground />
      <FlowingGradient />
      <ParticleField count={PARTICLE_COUNT} />

      <GlowingOrb size={800} color={COLORS.primary} x="50%" y="50%" delay={0} />

      <AbsoluteFill style={{ padding: 100, justifyContent: "center", alignItems: "center" }}>
        <h2
          style={{
            fontSize: 80,
            fontWeight: 800,
            color: COLORS.text,
            opacity: titleOpacity,
            marginBottom: 80,
            textAlign: "center",
            textShadow: `0 0 40px ${COLORS.primary}60`,
          }}
        >
          {CONTENT.title}
        </h2>

        <div
          style={{
            opacity: quoteOpacity,
            transform: `scale(${quoteScale * pulseScale})`,
            maxWidth: 1400,
            textAlign: "center",
            padding: 60,
            background: `${COLORS.primary}08`,
            borderRadius: 32,
            border: `1px solid ${COLORS.primary}20`,
          }}
        >
          <p
            style={{
              fontSize: 44,
              color: COLORS.text,
              lineHeight: 1.8,
              margin: 0,
              fontWeight: 300,
            }}
          >
            "{CONTENT.quote.split('\n\n')[0]}
            <br />
            <br />
            {CONTENT.quote.split('\n\n')[1].split('\n')[0]}
            <br />
            <span style={{ color: COLORS.primary, fontWeight: 600 }}>
              {CONTENT.quote.split('\n\n')[1].split('\n')[1]}
            </span>"
          </p>
        </div>

        <div
          style={{
            marginTop: 60,
            opacity: highlightOpacity,
          }}
        >
          <div
            style={{
              padding: "20px 48px",
              background: `linear-gradient(135deg, ${COLORS.primary}, ${COLORS.secondary})`,
              borderRadius: 100,
              boxShadow: `0 0 60px ${COLORS.primary}40`,
              transform: `scale(${1 + Math.sin(frame * 0.08) * 0.05})`,
            }}
          >
            <span
              style={{
                fontSize: 32,
                color: COLORS.text,
                fontWeight: 700,
              }}
            >
              {CONTENT.highlight}
            </span>
          </div>
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
