import { AbsoluteFill, useCurrentFrame, useVideoConfig, interpolate, spring, Easing } from "remotion";

const COLORS = {
  primary: '#6366f1',
  secondary: '#8b5cf6',
  accent: '#06b6d4',
  bg: '#0a0a0f',
  text: '#ffffff',
  textMuted: '#a1a1aa',
};

const CONTENT = {
  title: '灵犀·校园',
  subtitle: '有灵魂的数字伙伴',
  tags: ['AI原生', '情绪引擎', '数字生命'],
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

export const Scene1: React.FC = () => {
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
      <ParticleField count={PARTICLE_COUNT} />

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
            {CONTENT.title}
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
            {CONTENT.subtitle}
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
          {CONTENT.tags.map((tag, i) => {
            const floatY = Math.sin(frame * 0.05 + i) * 5;
            return (
              <div
                key={tag}
                style={{
                  padding: "16px 32px",
                  background: `${COLORS.primary}15`,
                  border: `1px solid ${COLORS.primary}40`,
                  borderRadius: 100,
                  fontSize: 24,
                  color: COLORS.text,
                  fontWeight: 500,
                  transform: `translateY(${floatY}px)`,
                }}
              >
                {tag}
              </div>
            );
          })}
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
