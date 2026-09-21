import React from 'react';
import {
  AbsoluteFill,
  Easing,
  Img,
  staticFile,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';
import {loadFont} from '@remotion/fonts';

// Piel de marketing (marca-quadro.md): carbón, papel, verde cancha.
const GREEN = '#0FCF89';
const CARBON = '#0B0B0B';
const PAPER = '#F4F4F0';

// Fuentes de marca, locales: el render corre offline (marca-quadro.md nota 3).
// loadFont bloquea el render por sí solo (delayRender interno).
loadFont({
  family: 'Archivo Black',
  url: staticFile('fonts/ArchivoBlack-Regular.ttf'),
  weight: '400',
});
loadFont({
  family: 'Inter',
  url: staticFile('fonts/Inter-Variable.ttf'),
  weight: '100 900',
});

const DISPLAY = '"Archivo Black", "Segoe UI", sans-serif';
const TEXT = '"Inter", "Segoe UI", sans-serif';

// Grano fino para el fondo oscuro (marca §6.3): tile de ruido en SVG, sin red
const GRAIN = `data:image/svg+xml,${encodeURIComponent(
  '<svg xmlns="http://www.w3.org/2000/svg" width="280" height="280">' +
    '<filter id="n"><feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="2" stitchTiles="stitch"/>' +
    '<feColorMatrix type="saturate" values="0"/></filter>' +
    '<rect width="280" height="280" filter="url(#n)"/></svg>'
)}`;

const LINE = 'rgba(244,244,240,0.11)';

// Encuadre del logo del club: los logos vienen en cualquier proporcion (el de
// Candu es 399x144). Metidos a la fuerza en un cuadrado se deforman, asi que
// se calcula la caja que entra en maxW x maxH sin cambiar la proporcion.
// el servicio mide el archivo con ffprobe y pasa logoW/logoH; sin esos
// props (Studio con los defaults) se cae al cuadrado de siempre.
const encuadrar = (w, h, maxW, maxH) => {
  if (!w || !h) return {width: maxH, height: maxH};
  const k = Math.min(maxW / w, maxH / h);
  return {width: Math.round(w * k), height: Math.round(h * k)};
};

export const Intro = ({club, logo, logoW, logoH}) => {
  const frame = useCurrentFrame();
  const {fps, durationInFrames} = useVideoConfig();

  // entrada de marca: sube y frena, nunca ease-in (marca §9).
  // SIN fundido a propósito: el fotograma 0 ya muestra la placa completa,
  // porque es el que WhatsApp usa como miniatura del video adjunto — y ahí
  // tiene que verse "Quadro para <club>", no un cuadro negro. La entrada es
  // solo asentamiento: a escala de miniatura no se nota, en el video sí.
  const rise = (delay, dist = 22) => {
    const p = spring({frame: frame - delay, fps, config: {damping: 200, mass: 0.8}});
    return {transform: `translateY(${(1 - p) * dist}px)`};
  };

  // el rebote se reserva para un acento: la tarjeta del club (marca §9.1)
  const cardIn = spring({
    frame: frame - 20,
    fps,
    config: {damping: 13, stiffness: 120, mass: 0.9},
  });
  const pillIn = spring({frame: frame - 27, fps, config: {damping: 200}});

  const ambient = spring({frame, fps, config: {damping: 200, mass: 1.4}});
  // piso alto: los glows y las líneas ya están en el fotograma 0 (miniatura)
  const ambientVis = 0.55 + 0.45 * ambient;
  // pulso ambiental del glow, ciclo de 2s (marca §9.1, loops ambientales)
  const pulse = 1 + 0.05 * Math.sin((frame / 60) * Math.PI * 2);

  const ruleW = interpolate(
    spring({frame: frame - 16, fps, config: {damping: 200}}),
    [0, 1],
    [0, 36]
  );

  // vida durante el hold: drift de escala sub-perceptual en los 3 segundos
  const drift = interpolate(frame, [0, durationInFrames - 1], [1, 1.022], {
    easing: Easing.inOut(Easing.cubic),
  });

  // salida: el contenido se va primero, el lavado termina en plano limpio
  // (así el corte a la demo no agarra fantasmas a medio disolver)
  const contentOut = interpolate(
    frame,
    [durationInFrames - 14, durationInFrames - 6],
    [1, 0],
    {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}
  );
  const wash = interpolate(
    frame,
    [durationInFrames - 14, durationInFrames - 4],
    [0, 1],
    {
      extrapolateLeft: 'clamp',
      extrapolateRight: 'clamp',
      easing: Easing.inOut(Easing.cubic),
    }
  );

  return (
    <AbsoluteFill style={{backgroundColor: CARBON, fontFamily: TEXT}}>
      {/* base: carbón que respira hacia negro-verdoso abajo (marca §7.1) */}
      <AbsoluteFill
        style={{
          background: `linear-gradient(180deg, ${CARBON} 0%, #0A1410 55%, #0F241B 100%)`,
        }}
      />

      {/* glow verde detrás del lockup + glow ambiental abajo a la izquierda */}
      <AbsoluteFill
        style={{
          background: `radial-gradient(circle at 50% 34%, rgba(15,207,137,${
            0.17 * pulse
          }) 0%, transparent 52%)`,
          opacity: ambientVis,
          transform: `scale(${interpolate(ambient, [0, 1], [1.04, 1])})`,
        }}
      />
      <AbsoluteFill
        style={{
          background:
            'radial-gradient(circle at 12% 88%, rgba(15,207,137,0.10) 0%, transparent 42%)',
          opacity: ambientVis,
        }}
      />

      {/* líneas de cancha: demarcación finísima, casi subliminal (marca §6.4) */}
      <div style={{position: 'absolute', top: 140, left: 0, right: 0, height: 2, backgroundColor: LINE, opacity: ambientVis}} />
      <div style={{position: 'absolute', bottom: 140, left: 0, right: 0, height: 2, backgroundColor: LINE, opacity: ambientVis}} />
      <div style={{position: 'absolute', left: 170, top: 0, bottom: 0, width: 2, backgroundColor: LINE, opacity: ambientVis}} />
      <div style={{position: 'absolute', right: 170, top: 0, bottom: 0, width: 2, backgroundColor: LINE, opacity: ambientVis}} />

      {/* grano al 8% en overlay: mata el flat digital (marca §6.3) */}
      <AbsoluteFill
        style={{
          backgroundImage: `url("${GRAIN}")`,
          opacity: 0.08,
          mixBlendMode: 'overlay',
        }}
      />

      <AbsoluteFill
        style={{
          justifyContent: 'center',
          alignItems: 'center',
          opacity: contentOut,
          transform: `scale(${drift})`,
        }}
      >
        {/* lockup: isotipo verde + wordmark en Archivo Black sobre papel (marca §5.1) */}
        <div style={{...rise(2, 26), display: 'flex', alignItems: 'center', gap: 26}}>
          <Img
            src={staticFile('quadro_cut.png')}
            style={{width: 136, height: 136, display: 'block'}}
          />
          <div
            style={{
              fontFamily: DISPLAY,
              fontSize: 118,
              letterSpacing: '-0.04em',
              color: PAPER,
              lineHeight: 1,
            }}
          >
            Quadro
          </div>
        </div>

        {/* tagline del end-card oficial, acá de apertura (marca §5.5) */}
        <div
          style={{
            ...rise(8, 20),
            marginTop: 26,
            fontSize: 25,
            fontWeight: 700,
            color: GREEN,
            letterSpacing: '0.34em',
            paddingLeft: '0.34em',
            textTransform: 'uppercase',
          }}
        >
          Gestión de torneos de pádel
        </div>

        {/* eyebrow "PARA" entre dos filetes verdes */}
        <div
          style={{
            ...rise(14, 16),
            display: 'flex',
            alignItems: 'center',
            gap: 24,
            margin: '58px 0 46px',
          }}
        >
          <div style={{width: ruleW, height: 2, backgroundColor: GREEN, borderRadius: 1}} />
          <div
            style={{
              fontSize: 19,
              fontWeight: 700,
              color: 'rgba(244,244,240,0.55)',
              letterSpacing: '0.3em',
              paddingLeft: '0.3em',
              textTransform: 'uppercase',
            }}
          >
            para
          </div>
          <div style={{width: ruleW, height: 2, backgroundColor: GREEN, borderRadius: 1}} />
        </div>

        {/* tarjeta del club: blanca porque integra logos JPG sin recortar (estilo.md) */}
        <div
          style={{
            position: 'relative',
            transform: `translateY(${(1 - cardIn) * 28}px) scale(${
              0.97 + cardIn * 0.03
            })`,
          }}
        >
          {/* tarjeta trasera verde translúcida (marca §6.6): mismo tamaño que la
              blanca, corrida parejo, para que asome un filete uniforme y se lea
              como stack intencional, no como elemento desalineado */}
          <div
            style={{
              position: 'absolute',
              inset: 0,
              borderRadius: 24,
              backgroundColor: `rgba(15,207,137,${0.22 * pillIn})`,
              transform: `translate(${14 * pillIn}px, ${14 * pillIn}px)`,
            }}
          />
          <div
            style={{
              position: 'relative',
              display: 'flex',
              alignItems: 'center',
              gap: 30,
              backgroundColor: '#FFFFFF',
              borderRadius: 24,
              padding: '22px 44px 22px 22px',
              boxShadow: '0 34px 70px -12px rgba(0,0,0,0.55)',
            }}
          >
            <Img
              src={staticFile(logo)}
              style={{
                ...encuadrar(logoW, logoH, 300, 140),
                borderRadius: 16,
                display: 'block',
                // keyline que asienta el logo, sobre todo los de baja resolución
                boxShadow: '0 0 0 1px rgba(0,0,0,0.08)',
              }}
            />
            <div
              style={{
                // nombres largos: achicar el cuerpo en vez de desbordar el cuadro
                fontSize:
                  club.length <= 26
                    ? 54
                    : Math.max(36, Math.round((54 * 26) / club.length)),
                fontWeight: 800,
                color: CARBON,
                letterSpacing: '-0.01em',
                whiteSpace: 'nowrap',
              }}
            >
              {club}
            </div>
          </div>
        </div>
      </AbsoluteFill>

      {/* lavado final a claro: el demo arranca en la app, que es clara */}
      <AbsoluteFill style={{backgroundColor: '#F8FAFC', opacity: wash}} />
    </AbsoluteFill>
  );
};

const INK = '#0A1F17';

export const Badge = ({club, logo, logoW, logoH}) => (
  <AbsoluteFill style={{fontFamily: TEXT}}>
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 14,
        backgroundColor: 'rgba(255,255,255,0.94)',
        borderRadius: 18,
        padding: '12px 22px 12px 12px',
        boxShadow: '0 8px 26px rgba(10,31,23,0.18)',
        width: 'fit-content',
      }}
    >
      <Img
        src={staticFile(logo)}
        style={{
          ...encuadrar(logoW, logoH, 165, 74),
          borderRadius: 12,
          display: 'block',
        }}
      />
      <div style={{fontSize: 25, fontWeight: 700, color: INK, whiteSpace: 'nowrap'}}>
        {club}
      </div>
    </div>
  </AbsoluteFill>
);
