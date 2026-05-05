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
  title: '四层记忆系统',
  layers: [
    { name: '观察', duration: '72小时', color: '#3b82f6', icon: '👁️' },
    { name: '经验', duration: '14天', color: '#22c55e', icon: '💡' },
    { name: '模式', duration: '90天', color: '#f59e0b', icon: '🔄' },
    { name: '心智模型', duration: '365天', color: COLORS.secondary, icon: '🧠' },
  ],
  footer: '会记住你说的话 · 会识别行为模式 · 会越来越懂你',
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

export const Scene4: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const titleOpacity = interpolate(frame, [0, 20], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const cameraZoom = 1 + Math.sin(frame * 0.02) * 0.05;

  const footerOpacity = interpolate(frame, [90, 110], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill style={{ background: COLORS.bg }}>
      <div style={{ transform: `scale(${cameraZoom})` }}>
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
              flexDirection: "column",
              alignItems: "center",
              gap: 24,
            }}
          >
            {CONTENT.layers.map((layer, i) => {
              const delay = i * 15 + 20;
              const scale = spring({
                frame: frame - delay,
                fps,
                config: { damping: 12, stiffness: 200 },
              });

              const opacity = interpolate(frame, [delay, delay + 20], [0, 1], {
                extrapolateLeft: "clamp",
                extrapolateRight: "clamp",
              });

              const width = 900 - i * 60;
              const floatX = Math.sin(frame * 0.03 + i) * 20;
              const floatRotation = Math.sin(frame * 0.02 + i) * 1;

              return (
                <div
                  key={layer.name}
                  style={{
                    opacity,
                    transform: `scale(${scale}) translateX(${floatX}px) rotate(${floatRotation}deg)`,
                    display: "flex",
                    alignItems: "center",
                    gap: 40,
                    padding: "32px 48px",
                    background: `linear-gradient(135deg, ${layer.color}15, ${layer.color}05)`,
                    borderRadius: 24,
                    border: `1px solid ${layer.color}30`,
                    width,
                    boxShadow: `0 0 40px ${layer.color}15`,
                  }}
                >
                  <div
                    style={{
                      width: 80,
                      height: 80,
                      background: `linear-gradient(135deg, ${layer.color}, ${layer.color}cc)`,
                      borderRadius: 20,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      fontSize: 40,
                      boxShadow: `0 0 30px ${layer.color}40`,
                      transform: `rotate(${frame * 0.5}deg)`,
                    }}
                  >
                    <div style={{ transform: `rotate(${-frame * 0.5}deg)` }}>
                      {layer.icon}
                    </div>
                  </div>
                  <div style={{ flex: 1 }}>
                    <div
                      style={{
                        fontSize: 40,
                        color: COLORS.text,
                        fontWeight: 700,
                        marginBottom: 8,
                      }}
                    >
                      {layer.name}
                    </div>
                    <div
                      style={{
                        fontSize: 24,
                        color: COLORS.textMuted,
                      }}
                    >
                      保留 {layer.duration}
                    </div>
                  </div>
                  <div
                    style={{
                      padding: "12px 24px",
                      background: `${layer.color}20`,
                      borderRadius: 12,
                      fontSize: 20,
                      color: layer.color,
                      fontWeight: 600,
                    }}
                  >
                    Layer {i + 1}
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
