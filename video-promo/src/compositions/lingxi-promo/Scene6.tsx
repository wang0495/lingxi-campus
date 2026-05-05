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
  title: '核心功能',
  features: [
    { icon: '💬', title: '自然对话', desc: '像微信好友一样聊天', color: COLORS.primary },
    { icon: '📱', title: '朋友圈', desc: '会发动态、会互动', color: COLORS.secondary },
    { icon: '🧠', title: '记忆系统', desc: '记住你说过的每句话', color: COLORS.accent },
    { icon: '❤️', title: '情绪共鸣', desc: '懂你的开心与难过', color: '#ef4444' },
    { icon: '🎯', title: '任务管理', desc: '帮你记住重要的事', color: '#f59e0b' },
    { icon: '📊', title: '周报分析', desc: '洞察你的生活模式', color: '#22c55e' },
  ],
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

export const Scene6: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const titleOpacity = interpolate(frame, [0, 20], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const waveOffset = Math.sin(frame * 0.05) * 30;

  return (
    <AbsoluteFill style={{ background: COLORS.bg }}>
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
            transform: `translateY(${waveOffset * 0.3}px)`,
          }}
        >
          {CONTENT.title}
        </h2>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(3, 1fr)",
            gap: 40,
            maxWidth: 1600,
            margin: "0 auto",
          }}
        >
          {CONTENT.features.map((feature, i) => {
            const delay = i * 10 + 20;
            const scale = spring({
              frame: frame - delay,
              fps,
              config: { damping: 12, stiffness: 200 },
            });

            const opacity = interpolate(frame, [delay, delay + 20], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            });

            const waveY = Math.sin(frame * 0.04 + i * 0.8) * 15;
            const waveX = Math.cos(frame * 0.03 + i * 0.6) * 10;
            const rotation = Math.sin(frame * 0.02 + i) * 2;

            return (
              <div
                key={feature.title}
                style={{
                  opacity,
                  transform: `scale(${scale}) translate(${waveX}px, ${waveY}px) rotate(${rotation}deg)`,
                  background: `linear-gradient(135deg, ${feature.color}10, ${feature.color}05)`,
                  borderRadius: 32,
                  padding: 48,
                  border: `1px solid ${feature.color}20`,
                  textAlign: "center",
                  boxShadow: `0 0 40px ${feature.color}10`,
                }}
              >
                <div
                  style={{
                    width: 100,
                    height: 100,
                    background: `linear-gradient(135deg, ${feature.color}30, ${feature.color}10)`,
                    borderRadius: 28,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    fontSize: 56,
                    margin: "0 auto 24px",
                    boxShadow: `0 0 30px ${feature.color}30`,
                    transform: `scale(${1 + Math.sin(frame * 0.06 + i) * 0.08})`,
                  }}
                >
                  {feature.icon}
                </div>
                <div
                  style={{
                    fontSize: 36,
                    color: COLORS.text,
                    fontWeight: 700,
                    marginBottom: 12,
                  }}
                >
                  {feature.title}
                </div>
                <div
                  style={{
                    fontSize: 24,
                    color: COLORS.textMuted,
                  }}
                >
                  {feature.desc}
                </div>
              </div>
            );
          })}
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
