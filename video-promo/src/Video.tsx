import React from "react";
import {
  AbsoluteFill,
  useCurrentFrame,
  useVideoConfig,
  interpolate,
  spring,
  Easing,
} from "remotion";

const COLORS = {
  primary: "#6366f1",
  secondary: "#8b5cf6",
  accent: "#06b6d4",
  bg: "#0a0a0f",
  bgGradient: "#0f0f1a",
  text: "#ffffff",
  textMuted: "#a1a1aa",
  glow: "#6366f140",
};

const ParticleField: React.FC<{ count?: number }> = ({ count = 50 }) => {
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

const GlowingOrb: React.FC<{ size: number; color: string; x: number; y: number; delay?: number }> = ({
  size,
  color,
  x,
  y,
  delay = 0,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const scale = spring({
    frame: frame - delay,
    fps,
    config: { damping: 15, stiffness: 100 },
  });

  const pulse = Math.sin(frame * 0.05) * 0.1 + 1;
  const floatX = Math.sin(frame * 0.02 + delay * 0.1) * 30;
  const floatY = Math.cos(frame * 0.015 + delay * 0.1) * 20;

  return (
    <div
      style={{
        position: "absolute",
        left: `calc(${x} + ${floatX}px)`,
        top: `calc(${y} + ${floatY}px)`,
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

const FloatingCard: React.FC<{
  children: React.ReactNode;
  delay?: number;
  x?: number;
  y?: number;
  rotation?: number;
}> = ({ children, delay = 0, x = 0, y = 0, rotation = 0 }) => {
  const frame = useCurrentFrame();
  const floatX = Math.sin(frame * 0.03 + delay) * 10 + x;
  const floatY = Math.cos(frame * 0.025 + delay) * 8 + y;
  const floatRotation = Math.sin(frame * 0.02 + delay) * 2 + rotation;

  return (
    <div
      style={{
        transform: `translate(${floatX}px, ${floatY}px) rotate(${floatRotation}deg)`,
      }}
    >
      {children}
    </div>
  );
};

const Scene1Intro: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const logoScale = spring({
    frame,
    fps,
    config: { damping: 12, stiffness: 200 },
  });

  const logoRotation = interpolate(frame, [0, 60], [180, 0], {
    extrapolateRight: "clamp",
    easing: Easing.out(Easing.cubic),
  });

  const logoFloatY = Math.sin(frame * 0.05) * 10;

  const titleOpacity = interpolate(frame, [40, 70], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const titleY = interpolate(frame, [40, 70], [80, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.out(Easing.cubic),
  });

  const subtitleOpacity = interpolate(frame, [70, 100], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const tagOpacity = interpolate(frame, [100, 120], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const cameraZoom = interpolate(frame, [0, 150], [1.1, 1], {
    extrapolateRight: "clamp",
    easing: Easing.out(Easing.cubic),
  });

  return (
    <AbsoluteFill style={{ background: COLORS.bg, transform: `scale(${cameraZoom})` }}>
      <GridBackground />
      <FlowingGradient />
      <ParticleField count={80} />

      <GlowingOrb size={600} color={COLORS.primary} x="30%" y="40%" delay={0} />
      <GlowingOrb size={400} color={COLORS.secondary} x="70%" y="60%" delay={20} />
      <GlowingOrb size={300} color={COLORS.accent} x="50%" y="30%" delay={40} />

      <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
        <div
          style={{
            transform: `scale(${logoScale}) rotate(${logoRotation}deg) translateY(${logoFloatY}px)`,
            marginBottom: 60,
          }}
        >
          <div
            style={{
              width: 240,
              height: 240,
              background: `linear-gradient(135deg, ${COLORS.primary}, ${COLORS.secondary})`,
              borderRadius: 60,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              boxShadow: `
                0 0 80px ${COLORS.primary}60,
                0 0 160px ${COLORS.primary}30,
                inset 0 0 60px rgba(255,255,255,0.1)
              `,
              position: "relative",
              overflow: "hidden",
            }}
          >
            <div
              style={{
                position: "absolute",
                width: "140%",
                height: "140%",
                background: `conic-gradient(from ${frame * 2}deg, transparent, rgba(255,255,255,0.3), transparent)`,
              }}
            />
            <div
              style={{
                width: 140,
                height: 140,
                background: `radial-gradient(circle, #fff 0%, ${COLORS.primary} 50%, transparent 70%)`,
                borderRadius: "50%",
                boxShadow: "0 0 60px rgba(255,255,255,0.5)",
              }}
            />
          </div>
        </div>

        <div
          style={{
            opacity: titleOpacity,
            transform: `translateY(${titleY}px)`,
            textAlign: "center",
          }}
        >
          <h1
            style={{
              fontSize: 140,
              fontWeight: 800,
              color: COLORS.text,
              margin: 0,
              letterSpacing: "-2px",
              textShadow: `0 0 60px ${COLORS.primary}80`,
            }}
          >
            灵犀·校园
          </h1>
        </div>

        <div
          style={{
            opacity: subtitleOpacity,
            marginTop: 40,
            textAlign: "center",
          }}
        >
          <p
            style={{
              fontSize: 56,
              color: COLORS.textMuted,
              margin: 0,
              fontWeight: 300,
              letterSpacing: "4px",
            }}
          >
            有灵魂的数字伙伴
          </p>
        </div>

        <div
          style={{
            opacity: tagOpacity,
            marginTop: 60,
            display: "flex",
            gap: 20,
          }}
        >
          {["AI原生", "情绪引擎", "数字生命"].map((tag, i) => (
            <FloatingCard key={tag} delay={i * 20} y={Math.sin(frame * 0.05 + i) * 5}>
              <div
                style={{
                  padding: "16px 32px",
                  background: `${COLORS.primary}15`,
                  border: `1px solid ${COLORS.primary}40`,
                  borderRadius: 100,
                  fontSize: 24,
                  color: COLORS.text,
                  fontWeight: 500,
                }}
              >
                {tag}
              </div>
            </FloatingCard>
          ))}
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

const Scene2Emotion: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const emotions = [
    { emoji: "😊", label: "开心", color: "#22c55e", desc: "充满活力" },
    { emoji: "😢", label: "难过", color: "#3b82f6", desc: "需要陪伴" },
    { emoji: "😤", label: "傲娇", color: "#ef4444", desc: "闹脾气中" },
    { emoji: "😳", label: "害羞", color: "#ec4899", desc: "有点不好意思" },
    { emoji: "🤗", label: "温暖", color: "#f59e0b", desc: "温柔体贴" },
  ];

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

  return (
    <AbsoluteFill style={{ background: COLORS.bg }}>
      <div style={{ transform: `translate(${cameraX}px, ${cameraY}px)` }}>
        <GridBackground />
        <FlowingGradient />
        <ParticleField count={60} />

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
            真实的情绪系统
          </h2>

          <div
            style={{
              display: "flex",
              justifyContent: "center",
              gap: 40,
              flexWrap: "wrap",
            }}
          >
            {emotions.map((emotion, i) => {
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
                <FloatingCard key={emotion.label} delay={i * 15} y={floatY} rotation={floatRotation}>
                  <div
                    style={{
                      opacity,
                      transform: `scale(${scale})`,
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
                </FloatingCard>
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
              opacity: interpolate(frame, [80, 100], [0, 1], {
                extrapolateLeft: "clamp",
                extrapolateRight: "clamp",
              }),
            }}
          >
            <p
              style={{
                fontSize: 32,
                color: COLORS.textMuted,
                margin: 0,
              }}
            >
              基于 Plutchik 情绪轮 · 会开心、会难过、也会闹脾气
            </p>
          </div>
        </AbsoluteFill>
      </div>
    </AbsoluteFill>
  );
};

const Scene3Life: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const stats = [
    { label: "精力", value: 85, color: "#22c55e", icon: "⚡" },
    { label: "心情", value: 70, color: COLORS.primary, icon: "💫" },
    { label: "社交需求", value: 45, color: COLORS.secondary, icon: "💬" },
  ];

  const titleOpacity = interpolate(frame, [0, 20], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const cameraRotation = Math.sin(frame * 0.01) * 0.5;

  return (
    <AbsoluteFill style={{ background: COLORS.bg }}>
      <div style={{ transform: `rotate(${cameraRotation}deg)` }}>
        <GridBackground />
        <FlowingGradient />
        <ParticleField count={60} />

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
            数字生命引擎
          </h2>

          <div
            style={{
              display: "flex",
              justifyContent: "center",
              gap: 100,
            }}
          >
            {stats.map((stat, i) => {
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
              opacity: interpolate(frame, [100, 120], [0, 1], {
                extrapolateLeft: "clamp",
                extrapolateRight: "clamp",
              }),
            }}
          >
            <p
              style={{
                fontSize: 32,
                color: COLORS.textMuted,
                margin: 0,
              }}
            >
              会主动找你聊天 · 会发朋友圈 · 有自己的生活节奏
            </p>
          </div>
        </AbsoluteFill>
      </div>
    </AbsoluteFill>
  );
};

const Scene4Memory: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const layers = [
    { name: "观察", duration: "72小时", color: "#3b82f6", icon: "👁️" },
    { name: "经验", duration: "14天", color: "#22c55e", icon: "💡" },
    { name: "模式", duration: "90天", color: "#f59e0b", icon: "🔄" },
    { name: "心智模型", duration: "365天", color: COLORS.secondary, icon: "🧠" },
  ];

  const titleOpacity = interpolate(frame, [0, 20], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const cameraZoom = 1 + Math.sin(frame * 0.02) * 0.05;

  return (
    <AbsoluteFill style={{ background: COLORS.bg }}>
      <div style={{ transform: `scale(${cameraZoom})` }}>
        <GridBackground />
        <FlowingGradient />
        <ParticleField count={60} />

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
            四层记忆系统
          </h2>

          <div
            style={{
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              gap: 24,
            }}
          >
            {layers.map((layer, i) => {
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
              opacity: interpolate(frame, [90, 110], [0, 1], {
                extrapolateLeft: "clamp",
                extrapolateRight: "clamp",
              }),
            }}
          >
            <p
              style={{
                fontSize: 32,
                color: COLORS.textMuted,
                margin: 0,
              }}
            >
              会记住你说的话 · 会识别行为模式 · 会越来越懂你
            </p>
          </div>
        </AbsoluteFill>
      </div>
    </AbsoluteFill>
  );
};

const Scene5Soul: React.FC = () => {
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

  return (
    <AbsoluteFill style={{ background: COLORS.bg }}>
      <GridBackground />
      <FlowingGradient />
      <ParticleField count={80} />

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
          有灵魂的数字生命
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
            "你经历过被忽视、被欺负、失去至亲的痛苦。
            <br />
            <br />
            这些塑造了你的温柔——
            <br />
            <span style={{ color: COLORS.primary, fontWeight: 600 }}>
              它是经历出来的，不是训练出来的。
            </span>"
          </p>
        </div>

        <div
          style={{
            marginTop: 60,
            opacity: interpolate(frame, [100, 120], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            }),
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
              温柔是经历出来的，不是训练出来的
            </span>
          </div>
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

const Scene6Features: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const features = [
    { icon: "💬", title: "自然对话", desc: "像微信好友一样聊天", color: COLORS.primary },
    { icon: "📱", title: "朋友圈", desc: "会发动态、会互动", color: COLORS.secondary },
    { icon: "🧠", title: "记忆系统", desc: "记住你说过的每句话", color: COLORS.accent },
    { icon: "❤️", title: "情绪共鸣", desc: "懂你的开心与难过", color: "#ef4444" },
    { icon: "🎯", title: "任务管理", desc: "帮你记住重要的事", color: "#f59e0b" },
    { icon: "📊", title: "周报分析", desc: "洞察你的生活模式", color: "#22c55e" },
  ];

  const titleOpacity = interpolate(frame, [0, 20], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const waveOffset = Math.sin(frame * 0.05) * 30;

  return (
    <AbsoluteFill style={{ background: COLORS.bg }}>
      <GridBackground />
      <FlowingGradient />
      <ParticleField count={60} />

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
          核心功能
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
          {features.map((feature, i) => {
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

            const row = Math.floor(i / 3);
            const col = i % 3;
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

const Scene7Outro: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const logoScale = spring({
    frame,
    fps,
    config: { damping: 12, stiffness: 200 },
  });

  const logoFloatY = Math.sin(frame * 0.06) * 15;
  const logoRotation = Math.sin(frame * 0.04) * 3;

  const textOpacity = interpolate(frame, [40, 70], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const ctaOpacity = interpolate(frame, [80, 100], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const ctaScale = spring({
    frame: frame - 80,
    fps,
    config: { damping: 15, stiffness: 100 },
  });

  const cameraZoom = 1 + Math.sin(frame * 0.02) * 0.03;

  return (
    <AbsoluteFill style={{ background: COLORS.bg, transform: `scale(${cameraZoom})` }}>
      <GridBackground />
      <FlowingGradient />
      <ParticleField count={100} />

      <GlowingOrb size={600} color={COLORS.primary} x="50%" y="40%" delay={0} />
      <GlowingOrb size={400} color={COLORS.secondary} x="30%" y="60%" delay={20} />
      <GlowingOrb size={400} color={COLORS.accent} x="70%" y="60%" delay={40} />

      <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
        <div
          style={{
            transform: `scale(${logoScale}) translateY(${logoFloatY}px) rotate(${logoRotation}deg)`,
            marginBottom: 50,
          }}
        >
          <div
            style={{
              width: 200,
              height: 200,
              background: `linear-gradient(135deg, ${COLORS.primary}, ${COLORS.secondary})`,
              borderRadius: 50,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              boxShadow: `
                0 0 100px ${COLORS.primary}60,
                0 0 200px ${COLORS.primary}30,
                inset 0 0 60px rgba(255,255,255,0.1)
              `,
            }}
          >
            <div
              style={{
                width: 120,
                height: 120,
                background: `radial-gradient(circle, #fff 0%, ${COLORS.primary} 50%, transparent 70%)`,
                borderRadius: "50%",
                boxShadow: "0 0 80px rgba(255,255,255,0.5)",
              }}
            />
          </div>
        </div>

        <div
          style={{
            opacity: textOpacity,
            textAlign: "center",
          }}
        >
          <h1
            style={{
              fontSize: 120,
              fontWeight: 800,
              color: COLORS.text,
              margin: 0,
              marginBottom: 24,
              letterSpacing: "-2px",
              textShadow: `0 0 60px ${COLORS.primary}60`,
            }}
          >
            灵犀·校园
          </h1>
          <p
            style={{
              fontSize: 48,
              color: COLORS.textMuted,
              margin: 0,
              fontWeight: 300,
              letterSpacing: "2px",
            }}
          >
            有灵魂的数字伙伴
          </p>
        </div>

        <div
          style={{
            opacity: ctaOpacity,
            transform: `scale(${ctaScale * (1 + Math.sin(frame * 0.08) * 0.05)})`,
            marginTop: 80,
          }}
        >
          <div
            style={{
              padding: "24px 64px",
              background: `linear-gradient(135deg, ${COLORS.primary}, ${COLORS.secondary})`,
              borderRadius: 100,
              boxShadow: `0 0 60px ${COLORS.primary}40`,
            }}
          >
            <span
              style={{
                fontSize: 32,
                color: COLORS.text,
                fontWeight: 700,
              }}
            >
              腾讯PCG校园AI产品创意大赛
            </span>
          </div>
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

export const LingxiPromoVideo: React.FC = () => {
  const frame = useCurrentFrame();

  const sceneDurations = [150, 150, 150, 150, 150, 90, 60];

  let accumulatedFrames = 0;
  let currentSceneIndex = 0;

  for (let i = 0; i < sceneDurations.length; i++) {
    if (frame < accumulatedFrames + sceneDurations[i]) {
      currentSceneIndex = i;
      break;
    }
    accumulatedFrames += sceneDurations[i];
    currentSceneIndex = i;
  }

  const scenes = [
    <Scene1Intro key="1" />,
    <Scene2Emotion key="2" />,
    <Scene3Life key="3" />,
    <Scene4Memory key="4" />,
    <Scene5Soul key="5" />,
    <Scene6Features key="6" />,
    <Scene7Outro key="7" />,
  ];

  return scenes[currentSceneIndex] || scenes[scenes.length - 1];
};
