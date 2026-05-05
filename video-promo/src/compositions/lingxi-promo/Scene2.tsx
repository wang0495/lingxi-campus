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
  title: '真实的情绪系统',
  emotions: [
    { emoji: '😊', label: '开心', color: '#22c55e', desc: '充满活力' },
    { emoji: '😢', label: '难过', color: '#3b82f6', desc: '需要陪伴' },
    { emoji: '😤', label: '傲娇', color: '#ef4444', desc: '闹脾气中' },
    { emoji: '😳', label: '害羞', color: '#ec4899', desc: '有点不好意思' },
    { emoji: '🤗', label: '温暖', color: '#f59e0b', desc: '温柔体贴' },
  ],
  footer: '基于 Plutchik 情绪轮 · 会开心、会难过、也会闹脾气',
};

const PARTICLE_COUNT = 60;

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

export const Scene2: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const titleOpacity = interpolate(frame, [0, 20], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const titleY = interpolate(frame, [0, 20], [-40, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const cameraX = Math.sin(frame * 0.02) * 20;
  const cameraY = Math.cos(frame * 0.015) * 15;

  const footerOpacity = interpolate(frame, [80, 100], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill style={{ background: COLORS.bg }}>
      <div style={{ transform: `translate(${cameraX}px, ${cameraY}px)` }}>
        <GridBackground />
        <FlowingGradient />
        <ParticleField count={PARTICLE_COUNT} />

        <AbsoluteFill style={{ padding: 100 }}>
          <h2
            style={{
              fontSize: 80,
              fontWeight: 800,
              color: COLORS.text,
              opacity: titleOpacity,
              transform: `translateY(${titleY}px)`,
              marginBottom: 80,
              textAlign: "center",
              textShadow: `0 0 40px ${COLORS.primary}60`,
            }}
          >
            {CONTENT.title}
          </h2>

          <div
            style={{
              display: "flex",
              justifyContent: "center",
              gap: 40,
              flexWrap: "wrap",
            }}
          >
            {CONTENT.emotions.map((emotion, i) => {
              const delay = i * 12 + 20;
              const scale = spring({
                frame: frame - delay,
                fps,
                config: { damping: 12, stiffness: 200 },
              });

              const opacity = interpolate(frame, [delay, delay + 20], [0, 1], {
                extrapolateLeft: "clamp",
                extrapolateRight: "clamp",
              });

              const glowIntensity = Math.sin(frame * 0.1 + i) * 20 + 40;
              const floatY = Math.sin(frame * 0.05 + i * 0.5) * 15;
              const floatRotation = Math.sin(frame * 0.03 + i) * 3;

              return (
                <div
                  key={emotion.label}
                  style={{
                    opacity,
                    transform: `scale(${scale}) translateY(${floatY}px) rotate(${floatRotation}deg)`,
                    display: "flex",
                    flexDirection: "column",
                    alignItems: "center",
                    gap: 24,
                    padding: 40,
                    background: `${emotion.color}08`,
                    borderRadius: 32,
                    border: `1px solid ${emotion.color}30`,
                    minWidth: 200,
                  }}
                >
                  <div
                    style={{
                      width: 140,
                      height: 140,
                      background: `linear-gradient(135deg, ${emotion.color}30, ${emotion.color}10)`,
                      borderRadius: 40,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      fontSize: 72,
                      boxShadow: `0 0 ${glowIntensity}px ${emotion.color}40`,
                      transform: `scale(${1 + Math.sin(frame * 0.08 + i) * 0.05})`,
                    }}
                  >
                    {emotion.emoji}
                  </div>
                  <div style={{ textAlign: "center" }}>
                    <div
                      style={{
                        fontSize: 40,
                        color: COLORS.text,
                        fontWeight: 700,
                        marginBottom: 8,
                      }}
                    >
                      {emotion.label}
                    </div>
                    <div
                      style={{
                        fontSize: 22,
                        color: COLORS.textMuted,
                      }}
                    >
                      {emotion.desc}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

          <div
            style={{
              position: "absolute",
              bottom: 100,
              left: 0,
              right: 0,
              textAlign: "center",
              opacity: footerOpacity,
            }}
          >
            <p
              style={{
                fontSize: 32,
                color: COLORS.textMuted,
                margin: 0,
              }}
            >
              {CONTENT.footer}
            </p>
          </div>
        </AbsoluteFill>
      </div>
    </AbsoluteFill>
  );
};
