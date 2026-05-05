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
  title: '灵犀·校园',
  subtitle: '有灵魂的数字伙伴',
  website: 'http://129.204.195.175/lingxi/',
};

const PARTICLE_COUNT = 100;

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

export const Scene7: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const logoScale = spring({
    frame,
    fps,
    config: { damping: 12, stiffness: 200 },
  });

  const logoFloatY = Math.sin(frame * 0.06) * 15;
  const logoRotation = Math.sin(frame * 0.04) * 3;

  const textOpacity = interpolate(frame, [5, 20], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const ctaOpacity = interpolate(frame, [20, 40], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const ctaScale = spring({
    frame: frame - 20,
    fps,
    config: { damping: 15, stiffness: 100 },
  });

  const cameraZoom = 1 + Math.sin(frame * 0.02) * 0.03;

  return (
    <AbsoluteFill style={{ background: COLORS.bg, transform: `scale(${cameraZoom})` }}>
      <GridBackground />
      <FlowingGradient />
      <ParticleField count={PARTICLE_COUNT} />

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
            {CONTENT.title}
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
            {CONTENT.subtitle}
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
              {CONTENT.website}
            </span>
          </div>
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
