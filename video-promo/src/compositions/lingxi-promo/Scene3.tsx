import { AbsoluteFill, useCurrentFrame, useVideoConfig, interpolate, spring } from "remotion";

const COLORS = {
  primary: '#6366f1',
  secondary: '#8b5cf6',
  accent: '#06b6d4',
  bg: '#0a0a0f',
  bgGradient: '#0f0f1a',
  text: '#ffffff',
  textMuted: '#a1a1aa',
};

const CONTENT = {
  title: '数字生命引擎',
  stats: [
    { label: '精力', value: 85, color: '#22c55e', icon: '⚡' },
    { label: '心情', value: 70, color: COLORS.primary, icon: '💫' },
    { label: '社交需求', value: 45, color: COLORS.secondary, icon: '💬' },
  ],
  footer: '会主动找你聊天 · 会发朋友圈 · 有自己的生活节奏',
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

export const Scene3: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const titleOpacity = interpolate(frame, [0, 20], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const cameraRotation = Math.sin(frame * 0.01) * 0.5;

  const footerOpacity = interpolate(frame, [100, 120], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill style={{ background: COLORS.bg }}>
      <div style={{ transform: `rotate(${cameraRotation}deg)` }}>
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
              marginBottom: 100,
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
              gap: 100,
            }}
          >
            {CONTENT.stats.map((stat, i) => {
              const delay = i * 20 + 20;
              const progress = interpolate(
                frame,
                [delay, delay + 60],
                [0, stat.value],
                {
                  extrapolateLeft: "clamp",
                  extrapolateRight: "clamp",
                }
              );

              const opacity = interpolate(frame, [delay, delay + 20], [0, 1], {
                extrapolateLeft: "clamp",
                extrapolateRight: "clamp",
              });

              const floatY = Math.sin(frame * 0.04 + i * 1.5) * 20;
              const scale = 1 + Math.sin(frame * 0.06 + i) * 0.03;

              return (
                <div
                  key={stat.label}
                  style={{
                    opacity,
                    display: "flex",
                    flexDirection: "column",
                    alignItems: "center",
                    gap: 30,
                    transform: `translateY(${floatY}px) scale(${scale})`,
                  }}
                >
                  <div
                    style={{
                      width: 180,
                      height: 180,
                      background: `linear-gradient(135deg, ${stat.color}20, ${stat.color}05)`,
                      borderRadius: "50%",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      fontSize: 80,
                      boxShadow: `0 0 60px ${stat.color}30`,
                      border: `2px solid ${stat.color}30`,
                      transform: `rotate(${frame + i * 120}deg)`,
                    }}
                  >
                    <div style={{ transform: `rotate(${-frame - i * 120}deg)` }}>
                      {stat.icon}
                    </div>
                  </div>

                  <div
                    style={{
                      fontSize: 44,
                      color: COLORS.text,
                      fontWeight: 700,
                    }}
                  >
                    {stat.label}
                  </div>

                  <div
                    style={{
                      width: 300,
                      height: 12,
                      background: `${COLORS.bgGradient}`,
                      borderRadius: 6,
                      overflow: "hidden",
                      border: `1px solid ${stat.color}20`,
                    }}
                  >
                    <div
                      style={{
                        width: `${progress}%`,
                        height: "100%",
                        background: `linear-gradient(90deg, ${stat.color}, ${stat.color}cc)`,
                        borderRadius: 6,
                        boxShadow: `0 0 20px ${stat.color}60`,
                      }}
                    />
                  </div>

                  <div
                    style={{
                      fontSize: 64,
                      color: stat.color,
                      fontWeight: 800,
                      textShadow: `0 0 30px ${stat.color}60`,
                    }}
                  >
                    {Math.round(progress)}%
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
